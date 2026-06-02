from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any]


class ToolResult(BaseModel):
    tool_call_id: str
    name: str
    content: str
    is_error: bool = False

    @classmethod
    def ok(cls, tool_call_id: str, name: str, content: str) -> ToolResult:
        return cls(tool_call_id=tool_call_id, name=name, content=content)

    @classmethod
    def error(cls, tool_call_id: str, name: str, error: str) -> ToolResult:
        return cls(tool_call_id=tool_call_id, name=name, content=error, is_error=True)


class ToolSchema(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
