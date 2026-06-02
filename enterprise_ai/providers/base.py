from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from enterprise_ai.schema import Message, StreamEvent, ToolSchema


class LLMResponse:
    def __init__(
        self,
        content: str,
        tool_calls: list,
        input_tokens: int = 0,
        output_tokens: int = 0,
        stop_reason: str = "end_turn",
        thinking_content: str = "",
        thinking_blocks: list[dict] | None = None,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.stop_reason = stop_reason
        self.thinking_content = thinking_content
        self.thinking_blocks: list[dict] = thinking_blocks or []
        # Prompt caching stats (Anthropic-specific; zero for other providers)
        self.cache_read_tokens = cache_read_tokens
        self.cache_write_tokens = cache_write_tokens

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class Provider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> LLMResponse: ...

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        # Non-async: implementations are async generators, which are directly iterable.
        # Declaring async here would make mypy expect a coroutine-returning-iterator
        # instead of an async generator.
        ...

    @property
    @abstractmethod
    def model(self) -> str: ...
