from __future__ import annotations

import json
from typing import Any, AsyncIterator

from enterprise_ai.prompt.cache import apply_cache_to_system, apply_cache_to_tools
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
from enterprise_ai.schema.event import EventType


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
                if isinstance(msg.content, list):
                    parts: list[Any] = []
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            parts.append({"type": "text", "text": block.text})
                        elif isinstance(block, ImageBlock):
                            parts.append({"type": "image", "source": block.source})
                    converted.append({"role": "user", "content": parts})
                else:
                    converted.append({"role": "user", "content": msg.text()})
            elif msg.role == Role.assistant:
                content: list[Any] = []
                # Thinking blocks must come first — Anthropic API requirement for multi-turn
                for tb in msg.thinking_blocks:
                    content.append(tb)
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
        thinking_content = ""
        thinking_blocks: list[dict] = []
        for block in resp.content:
            if block.type == "thinking":
                thinking_content += block.thinking
                thinking_blocks.append({
                    "type": "thinking",
                    "thinking": block.thinking,
                    "signature": getattr(block, "signature", ""),
                })
            elif block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            stop_reason=resp.stop_reason or "end_turn",
            thinking_content=thinking_content,
            thinking_blocks=thinking_blocks,
        )

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> LLMResponse:
        system, msgs = self._to_anthropic_messages(messages)
        extended_thinking: bool = kwargs.get("extended_thinking", False)
        thinking_budget: int = kwargs.get("thinking_budget_tokens", 10_000)

        effective_max_tokens = max(max_tokens, thinking_budget) if extended_thinking else max_tokens

        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": effective_max_tokens,
            "messages": msgs,
        }
        cache_prompt: bool = kwargs.get("cache_system_prompt", False)
        if system:
            params["system"] = apply_cache_to_system(system) if cache_prompt else system
        if tools:
            tool_list = self._to_anthropic_tools(tools)
            params["tools"] = apply_cache_to_tools(tool_list) if cache_prompt else tool_list

        if extended_thinking:
            params["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            resp = await self._client.beta.messages.create(
                **params, betas=["interleaved-thinking-2025-05-07"]
            )
        else:
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
        extended_thinking: bool = kwargs.get("extended_thinking", False)
        thinking_budget: int = kwargs.get("thinking_budget_tokens", 10_000)

        effective_max_tokens = max(max_tokens, thinking_budget) if extended_thinking else max_tokens

        params: dict[str, Any] = {
            "model": self._model,
            "max_tokens": effective_max_tokens,
            "messages": msgs,
        }
        cache_prompt: bool = kwargs.get("cache_system_prompt", False)
        if system:
            params["system"] = apply_cache_to_system(system) if cache_prompt else system
        if tools:
            tool_list = self._to_anthropic_tools(tools)
            params["tools"] = apply_cache_to_tools(tool_list) if cache_prompt else tool_list

        current_tool_id = ""
        current_tool_name = ""
        current_tool_input = ""
        current_thinking = ""
        in_thinking_block = False

        if extended_thinking:
            params["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
            stream_ctx = self._client.beta.messages.stream(
                **params, betas=["interleaved-thinking-2025-05-07"]
            )
        else:
            stream_ctx = self._client.messages.stream(**params)

        async with stream_ctx as stream:
            async for event in stream:
                etype = event.type
                if etype == "content_block_start":
                    if hasattr(event, "content_block"):
                        if event.content_block.type == "tool_use":
                            current_tool_id = event.content_block.id
                            current_tool_name = event.content_block.name
                            current_tool_input = ""
                            yield StreamEvent.tool_start(current_tool_id, current_tool_name, {})
                        elif event.content_block.type == "thinking":
                            current_thinking = ""
                            in_thinking_block = True
                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield StreamEvent.text(delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool_input += delta.partial_json
                    elif delta.type == "thinking_delta":
                        chunk = delta.thinking
                        current_thinking += chunk
                        yield StreamEvent.thinking(chunk)
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
                    if in_thinking_block:
                        in_thinking_block = False
                        current_thinking = ""
                elif etype == "message_stop":
                    final = await stream.get_final_message()
                    # Extract thinking blocks with signatures for multi-turn preservation
                    thinking_blocks: list[dict] = []
                    text_output = ""
                    for block in final.content:
                        if block.type == "thinking":
                            thinking_blocks.append({
                                "type": "thinking",
                                "thinking": block.thinking,
                                "signature": getattr(block, "signature", ""),
                            })
                        elif block.type == "text":
                            text_output = block.text
                    yield StreamEvent(
                        type=EventType.session_end,
                        data={"output": text_output, "thinking_blocks": thinking_blocks},
                    )
