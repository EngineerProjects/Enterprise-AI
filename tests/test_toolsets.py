"""Tests for item 4: toolset system."""
from __future__ import annotations

import pytest

from enterprise_ai.tools.toolsets import (
    TOOLSETS,
    _collect_names,
    list_toolsets,
    register_tool_factory,
    register_toolset,
    resolve_toolset,
)

# ── Built-in toolsets ─────────────────────────────────────────────────────────

def test_all_builtin_toolsets_listed():
    names = list(TOOLSETS)
    for expected in ("minimal", "development", "research", "full", "team_worker"):
        assert expected in names


def test_list_toolsets_returns_descriptions():
    ts = list_toolsets()
    assert isinstance(ts, dict)
    assert all(isinstance(v, str) for v in ts.values())
    assert "development" in ts


# ── Name collection ───────────────────────────────────────────────────────────

def test_minimal_toolset_names():
    names = _collect_names("minimal", set())
    assert "bash" in names
    assert "file_editor" in names
    assert "terminate" in names


def test_development_toolset_names():
    names = _collect_names("development", set())
    assert "bash" in names
    assert "code_search" in names


def test_team_worker_includes_development():
    names = _collect_names("team_worker", set())
    # from includes: ["development"]
    assert "bash" in names
    assert "file_editor" in names
    # from own tools
    assert "spawn_agent" in names
    assert "post_task" in names


def test_no_duplicate_names():
    names = _collect_names("team_worker", set())
    assert len(names) == len(set(names))


def test_unknown_toolset_raises():
    with pytest.raises(ValueError, match="Unknown toolset"):
        _collect_names("does_not_exist", set())


# ── Cycle detection ───────────────────────────────────────────────────────────

def test_cycle_in_includes_does_not_hang():
    """A toolset that includes itself (or a cycle) should not infinite-loop."""
    register_toolset("cycle_a", {"tools": [], "includes": ["cycle_b"]})
    register_toolset("cycle_b", {"tools": [], "includes": ["cycle_a"]})
    # Should not raise or hang
    names = _collect_names("cycle_a", set())
    assert isinstance(names, list)
    # Clean up
    del TOOLSETS["cycle_a"]
    del TOOLSETS["cycle_b"]


# ── Resolution ────────────────────────────────────────────────────────────────

def test_resolve_minimal_returns_tool_instances():
    tools = resolve_toolset("minimal")
    assert len(tools) >= 2
    names = [t.name for t in tools]
    assert "bash" in names
    assert "terminate" in names


def test_resolve_development_returns_tool_instances():
    tools = resolve_toolset("development")
    names = [t.name for t in tools]
    assert "bash" in names
    assert "code_search" in names


def test_resolve_team_worker_includes_development_tools():
    tools = resolve_toolset("team_worker")
    names = [t.name for t in tools]
    assert "bash" in names
    assert "spawn_agent" in names
    assert "post_task" in names


# ── Custom toolset + factory ──────────────────────────────────────────────────

def test_register_custom_toolset_and_factory():
    from pydantic import BaseModel

    from enterprise_ai.schema import ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool

    class MyInput(BaseModel):
        x: str = ""

    class MyTool(BaseTool):
        name = "my_custom_tool"
        description = "custom"
        input_schema = MyInput

        async def call(self, input, ctx: ToolContext) -> ToolResult:
            return ToolResult.ok("", name=self.name, content="ok")

    register_tool_factory("my_custom_tool", MyTool)
    register_toolset("my_company", {
        "description": "Company stack",
        "tools": ["my_custom_tool"],
        "includes": ["minimal"],
    })

    tools = resolve_toolset("my_company")
    names = [t.name for t in tools]
    assert "my_custom_tool" in names
    assert "bash" in names

    # Cleanup
    del TOOLSETS["my_company"]


def test_custom_factory_overrides_builtin():
    """A custom factory with the same name as a built-in takes precedence."""
    from pydantic import BaseModel

    from enterprise_ai.schema import ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool

    class FakeBash(BaseTool):
        name = "bash"
        description = "fake bash"
        input_schema = BaseModel

        async def call(self, input, ctx: ToolContext) -> ToolResult:
            return ToolResult.ok("", name=self.name, content="fake")

    register_tool_factory("bash", FakeBash)
    tools = resolve_toolset("minimal")
    bash_tool = next(t for t in tools if t.name == "bash")
    assert isinstance(bash_tool, FakeBash)

    # Restore built-in
    from enterprise_ai.tools.toolsets import _EXTRA_FACTORIES
    del _EXTRA_FACTORIES["bash"]


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_toolset_param_wires_tools():
    """Agent(toolset=...) populates _registry with the resolved tools."""
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            toolset="minimal",
        )
    tool_names = {t.name for t in agent._registry.all()}
    assert "bash" in tool_names
    assert "terminate" in tool_names


def test_agent_explicit_tools_override_toolset():
    """Tools passed explicitly take precedence over same-named toolset tools."""
    from unittest.mock import MagicMock, patch

    from pydantic import BaseModel

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider
    from enterprise_ai.schema import ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool

    class CustomBash(BaseTool):
        name = "bash"
        description = "custom bash"
        input_schema = BaseModel

        async def call(self, input, ctx: ToolContext) -> ToolResult:
            return ToolResult.ok("", name=self.name, content="custom")

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            toolset="minimal",
            tools=[CustomBash()],
        )
    bash = agent._registry.get("bash")
    assert isinstance(bash, CustomBash)


def test_agent_toolset_and_tools_merged():
    """Toolset tools + explicit tools both appear in the registry."""
    from unittest.mock import MagicMock, patch

    from pydantic import BaseModel

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider
    from enterprise_ai.schema import ToolResult
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.contract import BaseTool

    class ExtraTool(BaseTool):
        name = "extra_tool"
        description = "extra"
        input_schema = BaseModel

        async def call(self, input, ctx: ToolContext) -> ToolResult:
            return ToolResult.ok("", name=self.name, content="extra")

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            toolset="minimal",
            tools=[ExtraTool()],
        )
    tool_names = {t.name for t in agent._registry.all()}
    assert "bash" in tool_names
    assert "extra_tool" in tool_names
