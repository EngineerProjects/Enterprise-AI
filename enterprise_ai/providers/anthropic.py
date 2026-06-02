from __future__ import annotations

import json
from typing import Any, AsyncIterator

from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.schema import Message, Role, StreamEvent, ToolCall, ToolSchema


class AnthropicProvider(Provider):
    def __init__(self, model: str = "claude-opus-4-8", api_key: str | None = None) -> None:
        try:
            import anthropic as _anthropic
        except ImportError:
            raise ImportError("anthropic package required: pip install anthropic")
        self._client = _anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def _to_anthropic_messages(self, messages: list[Message]) -> tuple[str, list[dict]]:
        system = ""
        converted: list[dict] = []
        for msg in messages:
            if msg.role == Role.system:
                system = msg.text()
                continue
            if msg.role == Role.user:
                converted.append({"role": "user", "content": msg.text()})
            elif msg.role == Role.assistant:
                content: list[Any] = []
                if msg.text():
                    content.append({"type": "text", "text": msg.text()})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
                converted.append({"role": "assistant", "content": content})
            elif msg.role == Role.tool:
                if converted and converted[-1]["role"] == "user":
                    if isinstance(converted[-1]["content"], list):
                        converted[-1]["content"].append({"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.text()})
                    else:
                        converted[-1] = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.text()}]}
                else:
                    converted.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": msg.tool_call_id, "content": msg.text()}]})
        return system, converted

    def _to_anthropic_tools(self, tools: list[ToolSchema]) -> list[dict]:
        return [{"name": t.name, "description": t.description, "input_schema": t.input_schema} for t in tools]

    def _parse_response(self, resp: Any) -> LLMResponse:
        content = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            stop_reason=resp.stop_reason or "end_turn",
        )

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> LLMResponse:
        system, msgs = self._to_anthropic_messages(messages)
        params: dict[str, Any] = {"model": self._model, "max_tokens": max_tokens, "messages": msgs}
        if system:
            params["system"] = system
        if tools:
            params["tools"] = self._to_anthropic_tools(tools)
        resp = await self._client.messages.create(**params)
        return self._parse_response(resp)

    async def stream(  # type: ignore[override]
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        system, msgs = self._to_anthropic_messages(messages)
        params: dict[str, Any] = {"model": self._model, "max_tokens": max_tokens, "messages": msgs}
        if system:
            params["system"] = system
        if tools:
            params["tools"] = self._to_anthropic_tools(tools)

        current_tool_id = ""
        current_tool_name = ""
        current_tool_input = ""

        async with self._client.messages.stream(**params) as stream:
            async for event in stream:
                etype = event.type
                if etype == "content_block_start":
                    if hasattr(event, "content_block") and event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        current_tool_input = ""
                        yield StreamEvent.tool_start(current_tool_id, current_tool_name, {})
                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield StreamEvent.text(delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool_input += delta.partial_json
                elif etype == "content_block_stop":
                    if current_tool_id and current_tool_input:
                        try:
                            parsed = json.loads(current_tool_input)
                        except json.JSONDecodeError:
                            parsed = {}
                        yield StreamEvent.tool_start(current_tool_id, current_tool_name, parsed)
                        current_tool_id = ""
                        current_tool_name = ""
                        current_tool_input = ""
                elif etype == "message_stop":
                    final = await stream.get_final_message()
                    yield StreamEvent.end(final.content[0].text if final.content and final.content[0].type == "text" else "")
