"""Tests for item 6: tool search bridge."""
from __future__ import annotations

import pytest
from pydantic import BaseModel

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry
from enterprise_ai.tools.search_bridge import _META_NAMES, ToolSearchBridge


def _make_tool(name: str, description: str = "", deferrable: bool = False) -> BaseTool:
    class _Input(BaseModel):
        x: str = ""

    class _T(BaseTool):
        input_schema = _Input

        def is_deferrable(self) -> bool:
            return deferrable

        async def call(self, input, ctx: ToolContext) -> ToolResult:
            return ToolResult.ok("", name=self.name, content="ok")

    t = _T()
    t.__class__.name = name
    t.__class__.description = description or name
    return t


def _make_fat_tool(name: str, n_chars: int = 10_000) -> BaseTool:
    """Tool with a description long enough to push past the threshold."""
    return _make_tool(name, description="x" * n_chars, deferrable=True)


# ── Activation logic ──────────────────────────────────────────────────────────

def test_bridge_inactive_below_threshold():
    reg = ToolRegistry()
    reg.register(_make_tool("bash", "run commands"))
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)
    assert not bridge.is_active()


def test_bridge_active_above_threshold():
    reg = ToolRegistry()
    reg.register(_make_fat_tool("big_mcp", n_chars=50_000))
    bridge = ToolSearchBridge(reg, threshold_tokens=1_000)
    assert bridge.is_active()


# ── schemas_for_llm ───────────────────────────────────────────────────────────

def test_inactive_bridge_returns_all_non_meta_schemas():
    reg = ToolRegistry()
    reg.register(_make_tool("bash"))
    reg.register(_make_tool("search"))
    bridge = ToolSearchBridge(reg, threshold_tokens=100_000)

    schemas = bridge.schemas_for_llm()
    names = {s.name for s in schemas}
    assert "bash" in names
    assert "search" in names
    assert not names & _META_NAMES  # meta-tools not in schemas when inactive


def test_active_bridge_hides_deferrable_tools():
    reg = ToolRegistry()
    reg.register(_make_tool("bash", deferrable=False))
    reg.register(_make_fat_tool("mcp_github", n_chars=50_000))
    bridge = ToolSearchBridge(reg, threshold_tokens=1_000)

    schemas = bridge.schemas_for_llm()
    names = {s.name for s in schemas}

    assert "bash" in names               # non-deferrable always visible
    assert "mcp_github" not in names     # deferrable — hidden when active
    assert "tool_search" in names        # meta-tools appear
    assert "tool_describe" in names
    assert "tool_call" in names


def test_active_bridge_exposes_meta_tools():
    reg = ToolRegistry()
    reg.register(_make_fat_tool("mcp_x", n_chars=50_000))
    bridge = ToolSearchBridge(reg, threshold_tokens=100)

    schemas = bridge.schemas_for_llm()
    names = {s.name for s in schemas}
    assert _META_NAMES <= names


# ── Meta-tools registered in registry ────────────────────────────────────────

def test_meta_tools_registered_in_registry():
    reg = ToolRegistry()
    ToolSearchBridge(reg, threshold_tokens=10_000)
    assert reg.get("tool_search") is not None
    assert reg.get("tool_describe") is not None
    assert reg.get("tool_call") is not None


# ── Search API ────────────────────────────────────────────────────────────────

def test_search_finds_by_name():
    reg = ToolRegistry()
    reg.register(_make_tool("github_issues", "list github issues"))
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)

    results = bridge.search("github")
    assert any(r["name"] == "github_issues" for r in results)


def test_search_finds_by_description():
    reg = ToolRegistry()
    reg.register(_make_tool("t1", "fetches data from the database"))
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)

    results = bridge.search("database")
    assert len(results) == 1


def test_search_excludes_meta_tools():
    reg = ToolRegistry()
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)

    results = bridge.search("tool")  # would match meta-tool names
    assert all(r["name"] not in _META_NAMES for r in results)


def test_search_no_results():
    reg = ToolRegistry()
    reg.register(_make_tool("bash"))
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)

    assert bridge.search("xxxxxxxxxxxxxxx") == []


# ── Describe API ──────────────────────────────────────────────────────────────

def test_describe_returns_schema():
    reg = ToolRegistry()
    reg.register(_make_tool("my_tool", "does things"))
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)

    info = bridge.describe("my_tool")
    assert info is not None
    assert info["name"] == "my_tool"
    assert "input_schema" in info


def test_describe_unknown_tool():
    reg = ToolRegistry()
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)
    assert bridge.describe("nonexistent") is None


def test_describe_meta_tool_returns_none():
    reg = ToolRegistry()
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)
    assert bridge.describe("tool_search") is None


# ── call_tool API ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_tool_dispatches_to_real_tool():
    reg = ToolRegistry()
    reg.register(_make_tool("bash"))
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)

    ctx = ToolContext(session_id="test", agent_id="test", working_dir=".")
    result = await bridge.call_tool("bash", {}, ctx)
    assert not result.is_error
    assert result.content == "ok"


@pytest.mark.asyncio
async def test_call_tool_unknown_returns_error():
    reg = ToolRegistry()
    bridge = ToolSearchBridge(reg, threshold_tokens=10_000)
    ctx = ToolContext(session_id="test", agent_id="test", working_dir=".")

    result = await bridge.call_tool("nonexistent", {}, ctx)
    assert result.is_error


# ── is_deferrable on MCPTool ──────────────────────────────────────────────────

def test_mcp_tool_is_deferrable():
    from unittest.mock import MagicMock

    from enterprise_ai.mcp.tool import MCPTool

    mock_client = MagicMock()
    tool = MCPTool(
        name="github_search",
        description="search github",
        input_schema={"type": "object", "properties": {}},
        client=mock_client,
    )
    assert tool.is_deferrable() is True


def test_base_tool_is_not_deferrable_by_default():
    tool = _make_tool("my_tool")
    assert tool.is_deferrable() is False
