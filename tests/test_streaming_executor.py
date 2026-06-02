"""Tests for StreamingToolCoordinator."""
from __future__ import annotations

import asyncio

from pydantic import BaseModel

from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.execution.streaming_executor import StreamingToolCoordinator
from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
from enterprise_ai.schema import StreamEvent, ToolResult
from enterprise_ai.schema.event import EventType
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry


def make_ctx() -> ToolContext:
    return ToolContext(session_id="sid-test")


def make_orchestrator(tools: list[BaseTool] | None = None) -> Orchestrator:
    registry = ToolRegistry()
    for t in (tools or []):
        registry.register(t)
    return Orchestrator(
        registry=registry,
        permissions=PermissionEngine(mode=PermissionMode.auto),
    )


def tool_start_event(tool_id: str, name: str, input: dict) -> StreamEvent:
    return StreamEvent(type=EventType.tool_start, data={"id": tool_id, "name": name, "input": input})


# ── observe() behaviour ───────────────────────────────────────────────────────

def test_first_tool_start_no_submit():
    """First tool_start (empty input) should NOT trigger a submit."""
    orch = make_orchestrator()
    coord = StreamingToolCoordinator(orch, make_ctx())

    coord.observe(tool_start_event("t1", "bash", {}))
    assert not coord.has_pending


async def test_second_tool_start_submits():
    """Second tool_start (same ID, full input) should trigger a submit."""
    class FakeTool(BaseTool):
        name = "bash"
        description = "run"
        input_schema = type("I", (BaseModel,), {})

        async def call(self, input, ctx):
            return ToolResult.ok(tool_call_id="t1", name="bash", content="ok")

    orch = make_orchestrator([FakeTool()])
    coord = StreamingToolCoordinator(orch, make_ctx())

    coord.observe(tool_start_event("t1", "bash", {}))                     # first: placeholder
    coord.observe(tool_start_event("t1", "bash", {"cmd": "echo hi"}))    # second: submit
    assert coord.has_pending
    # Drain pending tasks to avoid ResourceWarning
    await coord.collect_results()


def test_partial_input_not_submitted():
    """Non-tool events don't trigger submission."""
    orch = make_orchestrator()
    coord = StreamingToolCoordinator(orch, make_ctx())

    coord.observe(StreamEvent.text("hello"))
    coord.observe(StreamEvent.thinking("thinking..."))
    assert not coord.has_pending


# ── collect_results() ─────────────────────────────────────────────────────────

async def test_collect_results_empty():
    orch = make_orchestrator()
    coord = StreamingToolCoordinator(orch, make_ctx())
    results = await coord.collect_results()
    assert results == []


async def test_tool_submitted_on_input_complete():
    class EchoInput(BaseModel):
        msg: str = ""

    class EchoTool(BaseTool):
        name = "echo"
        description = "echo"
        input_schema = EchoInput

        async def call(self, input, ctx):
            return ToolResult.ok(tool_call_id="t1", name="echo", content=f"echo:{input.msg}")

    orch = make_orchestrator([EchoTool()])
    coord = StreamingToolCoordinator(orch, make_ctx())

    coord.observe(tool_start_event("t1", "echo", {}))
    coord.observe(tool_start_event("t1", "echo", {"msg": "hello"}))

    results = await coord.collect_results()
    assert len(results) == 1
    assert "echo:hello" in results[0].result.content


async def test_results_collected_in_order():
    """Multiple tools: all results collected regardless of completion order."""
    class CountInput(BaseModel):
        n: int = 0

    class CountTool(BaseTool):
        name = "count"
        description = "count"
        input_schema = CountInput

        async def call(self, input, ctx):
            await asyncio.sleep(0)  # yield to event loop
            return ToolResult.ok(tool_call_id=f"t{input.n}", name="count", content=str(input.n))

    orch = make_orchestrator([CountTool()])
    coord = StreamingToolCoordinator(orch, make_ctx())

    for i in range(3):
        coord.observe(tool_start_event(f"t{i}", "count", {}))
        coord.observe(tool_start_event(f"t{i}", "count", {"n": i}))

    results = await coord.collect_results()
    assert len(results) == 3
    contents = {r.result.content for r in results}
    assert contents == {"0", "1", "2"}


async def test_pending_cleared_after_collect():
    class NullInput(BaseModel):
        pass

    class NullTool(BaseTool):
        name = "null"
        description = "null"
        input_schema = NullInput

        async def call(self, input, ctx):
            return ToolResult.ok(tool_call_id="t1", name="null", content="")

    orch = make_orchestrator([NullTool()])
    coord = StreamingToolCoordinator(orch, make_ctx())

    coord.observe(tool_start_event("t1", "null", {}))
    coord.observe(tool_start_event("t1", "null", {}))

    await coord.collect_results()
    assert not coord.has_pending

    # Second collect is safe
    results2 = await coord.collect_results()
    assert results2 == []
