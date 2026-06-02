from __future__ import annotations

from enum import Enum
from typing import Any, Union

from pydantic import BaseModel


class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


class TextBlock(BaseModel):
    type: str = "text"
    text: str


class ImageBlock(BaseModel):
    type: str = "image"
    source: dict[str, Any]


ContentBlock = Union[TextBlock, ImageBlock]


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any]


class Message(BaseModel):
    role: Role
    content: str | list[ContentBlock] = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        return "".join(b.text for b in self.content if isinstance(b, TextBlock))

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role=Role.system, content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role=Role.user, content=content)

    @classmethod
    def assistant(cls, content: str, tool_calls: list[ToolCall] | None = None) -> Message:
        return cls(role=Role.assistant, content=content, tool_calls=tool_calls)

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str, name: str = "") -> Message:
        return cls(role=Role.tool, content=content, tool_call_id=tool_call_id, name=name)
