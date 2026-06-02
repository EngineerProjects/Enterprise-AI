"""Tests for execution modes (plan, execute, pair_programming)."""
import pytest

from enterprise_ai.modes.execution import ExecutionMode, is_execute_mode, is_pair_programming_mode, is_plan_mode


# ── Enum values ───────────────────────────────────────────────────────────────

def test_execute_is_default_value():
    assert ExecutionMode.execute == "execute"


def test_plan_value():
    assert ExecutionMode.plan == "plan"


def test_pair_programming_value():
    assert ExecutionMode.pair_programming == "pair_programming"


# ── Helper functions ──────────────────────────────────────────────────────────

def test_is_plan_mode_true_for_plan():
    assert is_plan_mode(ExecutionMode.plan)
    assert is_plan_mode("plan")


def test_is_plan_mode_false_for_execute():
    assert not is_plan_mode(ExecutionMode.execute)
    assert not is_plan_mode("execute")


def test_is_execute_mode_true_for_execute():
    assert is_execute_mode(ExecutionMode.execute)
    assert is_execute_mode("execute")


def test_is_execute_mode_true_for_pair_programming():
    # pair_programming also executes tools
    assert is_execute_mode(ExecutionMode.pair_programming)


def test_is_execute_mode_false_for_plan():
    assert not is_execute_mode(ExecutionMode.plan)


def test_is_pair_programming_true():
    assert is_pair_programming_mode(ExecutionMode.pair_programming)
    assert is_pair_programming_mode("pair_programming")


def test_is_pair_programming_false_for_execute():
    assert not is_pair_programming_mode(ExecutionMode.execute)


# ── Orchestrator plan mode ────────────────────────────────────────────────────

async def test_plan_mode_does_not_execute_tool():
    """In plan mode, tools return a description, not real output."""
    import asyncio
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.modes.execution import ExecutionMode
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.schema import ToolCall, ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool
    from enterprise_ai.tools.registry import ToolRegistry
    from pydantic import BaseModel

    executed = []

    class DummyInput(BaseModel):
        cmd: str = "echo hi"

    class DummyTool(BaseTool):
        name = "dummy"
        description = "A dummy tool"
        input_schema = DummyInput

        async def call(self, input, ctx):
            executed.append(True)
            return ToolResult.ok(tool_call_id="", name="dummy", content="real output")

    registry = ToolRegistry()
    registry.register(DummyTool())
    permissions = PermissionEngine(mode=PermissionMode.auto)
    ctx = ToolContext(session_id="sid")

    orch = Orchestrator(
        registry=registry,
        permissions=permissions,
        execution_mode=ExecutionMode.plan,
    )
    tc = ToolCall(id="1", name="dummy", input={"cmd": "echo hi"})
    outcomes = await orch.execute([tc], ctx)

    # Tool was NOT actually executed
    assert not executed
    # Result contains plan description
    assert "[PLAN]" in outcomes[0].result.content
    assert "dummy" in outcomes[0].result.content


async def test_execute_mode_runs_tool():
    """In execute mode (default), tools run normally."""
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.modes.execution import ExecutionMode
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.schema import ToolCall, ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool
    from enterprise_ai.tools.registry import ToolRegistry
    from pydantic import BaseModel

    class DummyInput(BaseModel):
        cmd: str = "echo hi"

    class DummyTool(BaseTool):
        name = "dummy"
        description = "A dummy tool"
        input_schema = DummyInput

        async def call(self, input, ctx):
            return ToolResult.ok(tool_call_id="", name="dummy", content="real output")

    registry = ToolRegistry()
    registry.register(DummyTool())
    permissions = PermissionEngine(mode=PermissionMode.auto)
    ctx = ToolContext(session_id="sid")

    orch = Orchestrator(
        registry=registry,
        permissions=permissions,
        execution_mode=ExecutionMode.execute,
    )
    tc = ToolCall(id="1", name="dummy", input={"cmd": "echo hi"})
    outcomes = await orch.execute([tc], ctx)

    assert outcomes[0].result.content == "real output"
    assert "[PLAN]" not in outcomes[0].result.content


async def test_plan_mode_includes_tool_input_in_description():
    """Plan description should contain the tool's input."""
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.modes.execution import ExecutionMode
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.schema import ToolCall, ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool
    from enterprise_ai.tools.registry import ToolRegistry
    from pydantic import BaseModel

    class SearchInput(BaseModel):
        query: str = "test"

    class SearchTool(BaseTool):
        name = "search"
        description = "Search"
        input_schema = SearchInput

        async def call(self, input, ctx):
            return ToolResult.ok(tool_call_id="", name="search", content="results")

    registry = ToolRegistry()
    registry.register(SearchTool())
    permissions = PermissionEngine(mode=PermissionMode.auto)
    ctx = ToolContext(session_id="sid")

    orch = Orchestrator(
        registry=registry,
        permissions=permissions,
        execution_mode=ExecutionMode.plan,
    )
    tc = ToolCall(id="1", name="search", input={"query": "enterprise ai sdk"})
    outcomes = await orch.execute([tc], ctx)
    assert "enterprise ai sdk" in outcomes[0].result.content


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_accepts_execution_mode():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.modes.execution import ExecutionMode
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(
        provider=AnthropicProvider(model="claude-haiku-4-5-20251001"),
        execution_mode=ExecutionMode.plan,
    )
    assert agent._orchestrator._execution_mode == ExecutionMode.plan


def test_agent_default_execution_mode_is_execute():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.modes.execution import ExecutionMode
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-haiku-4-5-20251001"))
    assert agent._orchestrator._execution_mode == ExecutionMode.execute
