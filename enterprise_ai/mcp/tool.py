from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from enterprise_ai.schema import ToolResult, ToolSchema
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool

if TYPE_CHECKING:
    from enterprise_ai.mcp.client import MCPClient


class _AnyInput(BaseModel):
    """Generic input model that accepts any fields — used for MCP tools."""
    model_config = ConfigDict(extra="allow")


class MCPTool(BaseTool):
    """
    Wraps an MCP tool as an enterprise-ai BaseTool.

    The MCP tool's JSON Schema input_schema is preserved and passed to the LLM
    as-is. On call, the input dict is forwarded to the MCP server via the client.
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        client: MCPClient,
        server_name: str = "",
    ) -> None:
        self._name = name
        self._description = description
        self._mcp_input_schema = input_schema
        self._client = client
        self._server_name = server_name

    # BaseTool requires class attributes — we override the properties instead
    @property  # type: ignore[override]
    def name(self) -> str:  # type: ignore[override]
        return self._name

    @property  # type: ignore[override]
    def description(self) -> str:  # type: ignore[override]
        return self._description

    @property  # type: ignore[override]
    def input_schema(self) -> type[BaseModel]:  # type: ignore[override]
        return _AnyInput

    def to_schema(self) -> ToolSchema:  # type: ignore[override]
        return ToolSchema(
            name=self._name,
            description=self._description,
            input_schema=self._mcp_input_schema,
        )

    def parse_input(self, raw: dict[str, Any]) -> BaseModel:
        return _AnyInput.model_validate(raw)

    def is_concurrency_safe(self) -> bool:
        return True  # MCP tool calls are independent by default

    async def call(self, input: Any, ctx: ToolContext) -> ToolResult:
        # Extract the raw dict from the _AnyInput model
        if isinstance(input, BaseModel):
            raw = input.model_dump(exclude_none=True)
        else:
            raw = dict(input) if input else {}

        try:
            content = await self._client.call_tool(self._name, raw)
            return ToolResult.ok(tool_call_id="", name=self._name, content=content)
        except Exception as e:
            return ToolResult.error(tool_call_id="", name=self._name, error=str(e))
