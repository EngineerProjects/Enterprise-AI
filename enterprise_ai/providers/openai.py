from __future__ import annotations

import json
from typing import Any, AsyncIterator

from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.schema import (
    ImageBlock,
    Message,
    Role,
    StreamEvent,
    TextBlock,
    ToolCall,
    ToolSchema,
)


class OpenAIProvider(Provider):
    """Covers OpenAI, OpenRouter, Ollama — any OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai package required: pip install openai")
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def _to_openai_messages(self, messages: list[Message]) -> list[dict]:
        converted = []
        for msg in messages:
            if msg.role == Role.system:
                converted.append({"role": "system", "content": msg.text()})
            elif msg.role == Role.user:
                if isinstance(msg.content, list):
                    parts: list[Any] = []
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            parts.append({"type": "text", "text": block.text})
                        elif isinstance(block, ImageBlock):
                            src = block.source
                            if src.get("type") == "url":
                                parts.append({"type": "image_url", "image_url": {"url": src["url"]}})
                            else:
                                mt = src.get("media_type", "image/jpeg")
                                data = src.get("data", "")
                                parts.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}"}})
                    converted.append({"role": "user", "content": parts})
                else:
                    converted.append({"role": "user", "content": msg.text()})
            elif msg.role == Role.assistant:
                entry: dict[str, Any] = {"role": "assistant", "content": msg.text() or ""}
                if msg.tool_calls:
                    entry["tool_calls"] = [
                        {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.input)}}
                        for tc in msg.tool_calls
                    ]
                converted.append(entry)
            elif msg.role == Role.tool:
                converted.append({"role": "tool", "tool_call_id": msg.tool_call_id or "", "content": msg.text()})
        return converted

    def _to_openai_tools(self, tools: list[ToolSchema]) -> list[dict]:
        return [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}}
            for t in tools
        ]

    def _parse_response(self, resp: Any) -> LLMResponse:
        choice = resp.choices[0]
        msg = choice.message
        content = msg.content or ""
        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))
        usage = resp.usage
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            stop_reason=choice.finish_reason or "stop",
        )

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_openai_messages(messages),
            "max_tokens": max_tokens,
        }
        if tools:
            params["tools"] = self._to_openai_tools(tools)
        resp = await self._client.chat.completions.create(**params)
        return self._parse_response(resp)

    async def stream(  # type: ignore[override]
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        params: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_openai_messages(messages),
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            params["tools"] = self._to_openai_tools(tools)

        tool_calls_buf: dict[int, dict] = {}
        full_content = ""

        async for chunk in await self._client.chat.completions.create(**params):
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            if delta.content:
                full_content += delta.content
                yield StreamEvent.text(delta.content)
            if delta.tool_calls:
                for tc_chunk in delta.tool_calls:
                    idx = tc_chunk.index
                    if idx not in tool_calls_buf:
                        tool_calls_buf[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_chunk.id:
                        tool_calls_buf[idx]["id"] = tc_chunk.id
                    if tc_chunk.function:
                        if tc_chunk.function.name:
                            tool_calls_buf[idx]["name"] = tc_chunk.function.name
                        if tc_chunk.function.arguments:
                            tool_calls_buf[idx]["arguments"] += tc_chunk.function.arguments
            finish = chunk.choices[0].finish_reason if chunk.choices else None
            if finish in ("tool_calls", "stop"):
                for tc_data in tool_calls_buf.values():
                    try:
                        args = json.loads(tc_data["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    yield StreamEvent.tool_start(tc_data["id"], tc_data["name"], args)
                if finish == "stop":
                    yield StreamEvent.end(full_content)
