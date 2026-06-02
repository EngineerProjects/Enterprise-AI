from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.schema import Message, Role, StreamEvent, ToolCall, ToolSchema


class BedrockProvider(Provider):
    """
    AWS Bedrock provider using the `converse` API.

    Supports all Bedrock models with the converse API:
    - Anthropic Claude: anthropic.claude-3-5-sonnet-20241022-v2:0
    - Meta Llama: meta.llama3-3-70b-instruct-v1:0
    - Mistral: mistral.mistral-large-2402-v1:0
    - Amazon Titan: amazon.titan-text-premier-v1:0
    - And many more (see AWS Bedrock model catalog)

    Authentication uses standard boto3 credential chain:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
    - ~/.aws/credentials file
    - IAM role (when running on AWS)
    - AWS SSO

    Usage:
        provider = BedrockProvider(
            model="anthropic.claude-3-5-sonnet-20241022-v2:0",
            region="us-east-1",
        )
    """

    def __init__(
        self,
        model: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1",
        profile: str | None = None,
    ) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 required: pip install 'enterprise-ai[bedrock]'")

        session = boto3.Session(profile_name=profile)
        self._client = session.client("bedrock-runtime", region_name=region)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Message conversion: enterprise_ai → Bedrock converse format
    # ------------------------------------------------------------------

    def _to_bedrock_messages(
        self, messages: list[Message]
    ) -> tuple[list[dict[str, Any]], str]:
        """Returns (bedrock_messages, system_text)."""
        system_text = ""
        bedrock_msgs: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.system:
                system_text = msg.text()
                continue

            if msg.role == Role.user:
                bedrock_msgs.append({"role": "user", "content": [{"text": msg.text()}]})

            elif msg.role == Role.assistant:
                content: list[dict[str, Any]] = []
                if msg.text():
                    content.append({"text": msg.text()})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content.append({
                            "toolUse": {
                                "toolUseId": tc.id,
                                "name": tc.name,
                                "input": tc.input,
                            }
                        })
                bedrock_msgs.append({"role": "assistant", "content": content})

            elif msg.role == Role.tool:
                # Tool results are attached to the preceding user turn
                tool_result_block: dict[str, Any] = {
                    "toolResult": {
                        "toolUseId": msg.tool_call_id or "",
                        "content": [{"text": msg.text()}],
                    }
                }
                if bedrock_msgs and bedrock_msgs[-1]["role"] == "user":
                    bedrock_msgs[-1]["content"].append(tool_result_block)
                else:
                    bedrock_msgs.append({"role": "user", "content": [tool_result_block]})

        return bedrock_msgs, system_text

    def _to_bedrock_tools(self, tools: list[ToolSchema]) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "toolSpec": {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": {"json": t.input_schema},
                    }
                }
                for t in tools
            ]
        }

    def _parse_converse_response(self, response: dict[str, Any]) -> LLMResponse:
        output = response.get("output", {}).get("message", {})
        content_blocks = output.get("content", [])

        text = ""
        tool_calls: list[ToolCall] = []

        for block in content_blocks:
            if "text" in block:
                text += block["text"]
            elif "toolUse" in block:
                tu = block["toolUse"]
                tool_calls.append(ToolCall(
                    id=tu.get("toolUseId", ""),
                    name=tu.get("name", ""),
                    input=tu.get("input", {}),
                ))

        usage = response.get("usage", {})
        stop_reason = response.get("stopReason", "end_turn")

        return LLMResponse(
            content=text,
            tool_calls=tool_calls,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            stop_reason=stop_reason,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> LLMResponse:
        bedrock_msgs, system_text = self._to_bedrock_messages(messages)

        params: dict[str, Any] = {
            "modelId": self._model,
            "messages": bedrock_msgs,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system_text:
            params["system"] = [{"text": system_text}]
        if tools:
            params["toolConfig"] = self._to_bedrock_tools(tools)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.converse(**params),
        )
        return self._parse_converse_response(response)

    async def stream(  # type: ignore[override]
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
        max_tokens: int = 8096,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        bedrock_msgs, system_text = self._to_bedrock_messages(messages)

        params: dict[str, Any] = {
            "modelId": self._model,
            "messages": bedrock_msgs,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system_text:
            params["system"] = [{"text": system_text}]
        if tools:
            params["toolConfig"] = self._to_bedrock_tools(tools)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.converse_stream(**params),
        )

        stream = response.get("stream", [])

        # Bridge sync event stream → async generator via a thread-safe queue.
        # _process_stream runs in a thread pool; the async generator consumes
        # events concurrently so streaming is truly real-time.
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

        def _process_stream() -> None:
            current_tool_id = ""
            current_tool_name = ""
            current_tool_input = ""
            full_text = ""

            def _put(ev: StreamEvent | None) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, ev)

            try:
                for event in stream:
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"].get("delta", {})
                        if "text" in delta:
                            full_text += delta["text"]
                            _put(StreamEvent.text(delta["text"]))
                        elif "toolUse" in delta:
                            current_tool_input += delta["toolUse"].get("input", "")

                    elif "contentBlockStart" in event:
                        start = event["contentBlockStart"].get("start", {})
                        if "toolUse" in start:
                            tu = start["toolUse"]
                            current_tool_id = tu.get("toolUseId", "")
                            current_tool_name = tu.get("name", "")
                            current_tool_input = ""
                            _put(StreamEvent.tool_start(current_tool_id, current_tool_name, {}))

                    elif "contentBlockStop" in event:
                        if current_tool_id and current_tool_input:
                            try:
                                parsed = json.loads(current_tool_input)
                            except json.JSONDecodeError:
                                parsed = {}
                            _put(StreamEvent.tool_start(current_tool_id, current_tool_name, parsed))
                            current_tool_id = ""
                            current_tool_name = ""
                            current_tool_input = ""

                    elif "messageStop" in event:
                        _put(StreamEvent.end(full_text))

            except Exception as e:
                _put(StreamEvent.err(str(e)))
            finally:
                _put(None)  # sentinel

        # Start processing in background thread while consuming from queue
        bg = loop.run_in_executor(None, _process_stream)

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            await bg
