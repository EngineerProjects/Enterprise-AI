"""
Tool search bridge — progressive disclosure for large tool registries.

When the total estimated token count of all tool schemas exceeds `threshold_tokens`,
deferrable tools (MCPTool and any tool where is_deferrable() == True) are hidden
from the LLM's context. Three meta-tools replace them:

    tool_search(query)          → find tools by keyword
    tool_describe(name)         → get the full schema of one tool
    tool_call(name, args_json)  → invoke any tool by name

This keeps the LLM's context manageable when many MCP servers are connected.

Usage:
    bridge = ToolSearchBridge(registry, threshold_tokens=8_000)
    # Pass to QueryLoop — it calls bridge.schemas_for_llm() instead of
    # registry.schemas() when deciding what to expose to the LLM.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult, ToolSchema
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry

_META_NAMES = frozenset({"tool_search", "tool_describe", "tool_call"})


# ── Meta-tool input schemas ───────────────────────────────────────────────────

class _SearchInput(BaseModel):
    query: str = Field(description="Keywords to search for in tool names and descriptions.")


class _DescribeInput(BaseModel):
    name: str = Field(description="Exact tool name to retrieve the full schema for.")


class _CallInput(BaseModel):
    name: str = Field(description="Exact tool name to invoke.")
    args_json: str = Field(
        default="{}",
        description="JSON string of arguments to pass to the tool.",
    )


# ── Meta-tools ────────────────────────────────────────────────────────────────

class ToolSearchTool(BaseTool):
    name = "tool_search"
    description = (
        "Search for available tools by keyword. "
        "Use this to discover tools when you don't know the exact name. "
        "Returns tool names and short descriptions."
    )
    input_schema = _SearchInput

    def __init__(self, bridge: ToolSearchBridge) -> None:
        self._bridge = bridge

    async def call(self, input: _SearchInput, ctx: ToolContext) -> ToolResult:
        results = self._bridge.search(input.query)
        if not results:
            content = f"No tools found matching '{input.query}'."
        else:
            lines = [f"- {r['name']}: {r['description']}" for r in results]
            content = f"Found {len(results)} tool(s):\n" + "\n".join(lines)
        return ToolResult.ok(tool_call_id="", name=self.name, content=content)


class ToolDescribeTool(BaseTool):
    name = "tool_describe"
    description = (
        "Get the full schema (parameters and descriptions) of a specific tool by name. "
        "Use after tool_search to learn how to call a tool."
    )
    input_schema = _DescribeInput

    def __init__(self, bridge: ToolSearchBridge) -> None:
        self._bridge = bridge

    async def call(self, input: _DescribeInput, ctx: ToolContext) -> ToolResult:
        info = self._bridge.describe(input.name)
        if info is None:
            return ToolResult.error(
                tool_call_id="", name=self.name,
                error=f"Tool '{input.name}' not found. Use tool_search to discover available tools.",
            )
        content = json.dumps(info, indent=2)
        return ToolResult.ok(tool_call_id="", name=self.name, content=content)


class ToolCallTool(BaseTool):
    name = "tool_call"
    description = (
        "Invoke any available tool by name, including tools not listed in your context. "
        "Use tool_search and tool_describe first to discover and understand the tool. "
        "Pass arguments as a JSON string in args_json."
    )
    input_schema = _CallInput

    def __init__(self, bridge: ToolSearchBridge) -> None:
        self._bridge = bridge

    async def call(self, input: _CallInput, ctx: ToolContext) -> ToolResult:
        try:
            args = json.loads(input.args_json)
        except json.JSONDecodeError as e:
            return ToolResult.error(
                tool_call_id="", name=self.name,
                error=f"Invalid args_json: {e}. Must be a valid JSON object.",
            )
        return await self._bridge.call_tool(input.name, args, ctx)


# ── Bridge ────────────────────────────────────────────────────────────────────

class ToolSearchBridge:
    """
    Wraps a ToolRegistry and activates progressive disclosure when
    the tool schema token count exceeds the configured threshold.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        threshold_tokens: int = 8_000,
    ) -> None:
        self._registry = registry
        self._threshold = threshold_tokens
        self._search_tool = ToolSearchTool(self)
        self._describe_tool = ToolDescribeTool(self)
        self._call_tool = ToolCallTool(self)
        # Register meta-tools so the orchestrator can dispatch them
        for t in (self._search_tool, self._describe_tool, self._call_tool):
            registry.register(t)

    # ── Activation ───────────────────────────────────────────────────────────

    def _estimate_tokens(self) -> int:
        schemas = [
            t.to_schema()
            for t in self._registry.all()
            if t.name not in _META_NAMES
        ]
        chars = sum(
            len(s.name) + len(s.description) + len(str(s.input_schema))
            for s in schemas
        )
        return chars // 4

    def is_active(self) -> bool:
        """True when deferral should be applied (token count > threshold)."""
        return self._estimate_tokens() > self._threshold

    # ── Schema filtering ──────────────────────────────────────────────────────

    def schemas_for_llm(self) -> list[ToolSchema]:
        """
        Return the tool schemas to pass to the LLM.

        Inactive: all tool schemas (meta-tools excluded — not useful without deferral).
        Active:   non-deferrable tools + the three meta-tools only.
        """
        if not self.is_active():
            return [t.to_schema() for t in self._registry.all() if t.name not in _META_NAMES]

        result: list[ToolSchema] = []
        for tool in self._registry.all():
            if tool.name in _META_NAMES:
                result.append(tool.to_schema())
            elif not tool.is_deferrable():
                result.append(tool.to_schema())
        return result

    # ── Search / describe / call APIs (used by meta-tools) ───────────────────

    def search(self, query: str, max_results: int = 10) -> list[dict[str, str]]:
        q = query.lower()
        results: list[dict[str, str]] = []
        for tool in self._registry.all():
            if tool.name in _META_NAMES:
                continue
            if q in tool.name.lower() or q in tool.description.lower():
                results.append({
                    "name": tool.name,
                    "description": tool.description[:200],
                })
            if len(results) >= max_results:
                break
        return results

    def describe(self, name: str) -> dict[str, Any] | None:
        tool = self._registry.get(name)
        if tool is None or tool.name in _META_NAMES:
            return None
        schema = tool.to_schema()
        return {
            "name": schema.name,
            "description": schema.description,
            "input_schema": schema.input_schema,
        }

    async def call_tool(
        self,
        name: str,
        args: dict[str, Any],
        ctx: ToolContext,
    ) -> ToolResult:
        tool = self._registry.get(name)
        if tool is None:
            return ToolResult.error(
                tool_call_id="", name=name,
                error=f"Tool '{name}' not found. Use tool_search to list available tools.",
            )
        try:
            parsed = tool.parse_input(args)
            return await tool.call(parsed, ctx)
        except Exception as e:
            return ToolResult.error(tool_call_id="", name=name, error=str(e))
