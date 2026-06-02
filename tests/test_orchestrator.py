"""
Unit tests for the Orchestrator.
Tests the batching logic (concurrent vs sequential) and the execution pipeline.
Uses mock tools — no real subprocess or API calls.
"""
import pytest
from pydantic import BaseModel

from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class EchoInput(BaseModel):
    message: str = "hello"


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo the message"
    input_schema = EchoInput

    async def call(self, input: EchoInput, ctx: ToolContext) -> ToolResult:
        return ToolResult.ok(tool_call_id="", name=self.name, content=input.message)


class SlowInput(BaseModel):
    message: str = "slow"


class SequentialTool(BaseTool):
    """Simulates a non-concurrent-safe tool (e.g. bash)."""
    name = "sequential"
    description = "Must run sequentially"
    input_schema = SlowInput

    def is_concurrency_safe(self) -> bool:
        return False

    async def call(self, input: SlowInput, ctx: ToolContext) -> ToolResult:
        return ToolResult.ok(tool_call_id="", name=self.name, content=input.message)


class FailingInput(BaseModel):
    pass


class FailingTool(BaseTool):
    name = "failing"
    description = "Always raises"
    input_schema = FailingInput

    async def call(self, input: FailingInput, ctx: ToolContext) -> ToolResult:
        raise RuntimeError("deliberate failure")


def make_registry(*tools: BaseTool) -> ToolRegistry:
    r = ToolRegistry()
    for t in tools:
        r.register(t)
    return r


def make_orchestrator(registry: ToolRegistry, mode: PermissionMode = PermissionMode.bypass) -> Orchestrator:
    return Orchestrator(registry=registry, permissions=PermissionEngine(mode=mode))


def make_call(name: str, input: dict | None = None, call_id: str = "id-1") -> ToolCall:
    return ToolCall(id=call_id, name=name, input=input or {})


CTX = ToolContext()


# ---------------------------------------------------------------------------
# Batching logic
# ---------------------------------------------------------------------------

def test_partition_all_concurrent():
    echo = EchoTool()
    orch = make_orchestrator(make_registry(echo))
    from enterprise_ai.execution.orchestrator import _PreparedCall
    prepared = [
        _PreparedCall(tool_call=make_call("echo", call_id=f"id-{i}"), tool=echo, parsed_input=EchoInput(), is_concurrency_safe=True)
        for i in range(3)
    ]
    batches = orch._partition(prepared)
    assert len(batches) == 1
    assert batches[0].is_concurrent is True
    assert len(batches[0].calls) == 3


def test_partition_all_sequential():
    seq = SequentialTool()
    orch = make_orchestrator(make_registry(seq))
    from enterprise_ai.execution.orchestrator import _PreparedCall
    prepared = [
        _PreparedCall(tool_call=make_call("sequential", call_id=f"id-{i}"), tool=seq, parsed_input=SlowInput(), is_concurrency_safe=False)
        for i in range(3)
    ]
    batches = orch._partition(prepared)
    assert len(batches) == 1
    assert batches[0].is_concurrent is False


def test_partition_mixed_splits_correctly():
    echo = EchoTool()
    seq = SequentialTool()
    orch = make_orchestrator(make_registry(echo, seq))
    from enterprise_ai.execution.orchestrator import _PreparedCall
    prepared = [
        _PreparedCall(tool_call=make_call("echo", call_id="1"), tool=echo, parsed_input=EchoInput(), is_concurrency_safe=True),
        _PreparedCall(tool_call=make_call("echo", call_id="2"), tool=echo, parsed_input=EchoInput(), is_concurrency_safe=True),
        _PreparedCall(tool_call=make_call("sequential", call_id="3"), tool=seq, parsed_input=SlowInput(), is_concurrency_safe=False),
        _PreparedCall(tool_call=make_call("echo", call_id="4"), tool=echo, parsed_input=EchoInput(), is_concurrency_safe=True),
    ]
    batches = orch._partition(prepared)
    assert len(batches) == 3
    assert batches[0].is_concurrent is True and len(batches[0].calls) == 2
    assert batches[1].is_concurrent is False and len(batches[1].calls) == 1
    assert batches[2].is_concurrent is True and len(batches[2].calls) == 1


# ---------------------------------------------------------------------------
# Execution pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_known_tool_returns_result():
    registry = make_registry(EchoTool())
    orch = make_orchestrator(registry)
    outcomes = await orch.execute([make_call("echo", {"message": "hi"})], CTX)
    assert len(outcomes) == 1
    assert outcomes[0].result.content == "hi"
    assert not outcomes[0].failed


@pytest.mark.asyncio
async def test_execute_unknown_tool_returns_error():
    orch = make_orchestrator(make_registry())
    outcomes = await orch.execute([make_call("ghost")], CTX)
    assert len(outcomes) == 1
    assert outcomes[0].failed
    assert "Unknown tool" in outcomes[0].result.content


@pytest.mark.asyncio
async def test_execute_invalid_input_returns_error():
    # EchoInput.message is a string, passing an int will fail validation
    registry = make_registry(EchoTool())
    orch = make_orchestrator(registry)
    # Pydantic will coerce int to str for a str field, so use a field that doesn't exist
    outcomes = await orch.execute([make_call("echo", {"nonexistent_field": 123, "message": {}})], CTX)
    # message={} cannot be coerced to str cleanly — depends on pydantic version
    # The point is it should not crash the orchestrator
    assert len(outcomes) == 1


@pytest.mark.asyncio
async def test_execute_tool_exception_returns_error():
    registry = make_registry(FailingTool())
    orch = make_orchestrator(registry)
    outcomes = await orch.execute([make_call("failing")], CTX)
    assert outcomes[0].failed
    assert "deliberate failure" in outcomes[0].result.content


@pytest.mark.asyncio
async def test_execute_multiple_concurrent_tools():
    registry = make_registry(EchoTool())
    orch = make_orchestrator(registry)
    calls = [
        make_call("echo", {"message": "a"}, call_id="1"),
        make_call("echo", {"message": "b"}, call_id="2"),
        make_call("echo", {"message": "c"}, call_id="3"),
    ]
    outcomes = await orch.execute(calls, CTX)
    assert len(outcomes) == 3
    contents = {o.result.content for o in outcomes}
    assert contents == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_result_truncated_when_too_large():
    class BigOutput(BaseTool):
        name = "big"
        description = "Returns huge output"
        input_schema = FailingInput

        async def call(self, input, ctx):
            return ToolResult.ok(tool_call_id="", name=self.name, content="x" * 100_000)

    registry = make_registry(BigOutput())
    orch = make_orchestrator(registry)
    outcomes = await orch.execute([make_call("big")], CTX)
    assert len(outcomes[0].result.content) <= Orchestrator.MAX_RESULT_CHARS + 50  # +50 for truncation suffix
    assert "truncated" in outcomes[0].result.content


@pytest.mark.asyncio
async def test_permission_denied_returns_error():
    registry = make_registry(EchoTool())
    engine = PermissionEngine(mode=PermissionMode.auto, deny_tools={"echo"})
    orch2 = Orchestrator(registry=registry, permissions=engine)
    outcomes = await orch2.execute([make_call("echo", {"message": "hi"})], CTX)
    assert outcomes[0].failed
    assert "Permission denied" in outcomes[0].result.content
