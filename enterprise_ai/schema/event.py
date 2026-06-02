from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class EventType(str, Enum):
    text_delta = "text_delta"
    tool_start = "tool_start"
    tool_result = "tool_result"
    thinking = "thinking"
    session_end = "session_end"
    error = "error"


class StreamEvent(BaseModel):
    type: EventType
    data: dict[str, Any] = {}

    @classmethod
    def text(cls, delta: str) -> StreamEvent:
        return cls(type=EventType.text_delta, data={"delta": delta})

    @classmethod
    def tool_start(cls, tool_call_id: str, name: str, input: dict[str, Any]) -> StreamEvent:
        return cls(type=EventType.tool_start, data={"id": tool_call_id, "name": name, "input": input})

    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str, is_error: bool = False) -> StreamEvent:
        return cls(type=EventType.tool_result, data={"id": tool_call_id, "name": name, "content": content, "is_error": is_error})

    @classmethod
    def end(cls, output: str) -> StreamEvent:
        return cls(type=EventType.session_end, data={"output": output})

    @classmethod
    def thinking(cls, delta: str) -> StreamEvent:
        return cls(type=EventType.thinking, data={"delta": delta})

    @classmethod
    def err(cls, message: str) -> StreamEvent:
        return cls(type=EventType.error, data={"message": message})
