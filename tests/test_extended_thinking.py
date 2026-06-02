"""Tests for extended thinking support."""
from __future__ import annotations

from unittest.mock import MagicMock

from enterprise_ai.providers.base import LLMResponse
from enterprise_ai.schema import Message, StreamEvent
from enterprise_ai.schema.event import EventType

# ── LLMResponse thinking fields ─────────────────────────────────────────────

def test_llm_response_default_no_thinking():
    resp = LLMResponse(content="hello", tool_calls=[])
    assert resp.thinking_content == ""
    assert resp.thinking_blocks == []


def test_llm_response_stores_thinking_content():
    resp = LLMResponse(
        content="answer",
        tool_calls=[],
        thinking_content="Let me think...",
        thinking_blocks=[{"type": "thinking", "thinking": "Let me think...", "signature": "sig123"}],
    )
    assert resp.thinking_content == "Let me think..."
    assert len(resp.thinking_blocks) == 1
    assert resp.thinking_blocks[0]["signature"] == "sig123"


# ── Message thinking_blocks ───────────────────────────────────────────────────

def test_message_default_no_thinking_blocks():
    msg = Message.assistant("hello")
    assert msg.thinking_blocks == []


def test_message_assistant_stores_thinking_blocks():
    blocks = [{"type": "thinking", "thinking": "analysis", "signature": "abc"}]
    msg = Message.assistant("hello", thinking_blocks=blocks)
    assert msg.thinking_blocks == blocks


def test_message_thinking_blocks_none_becomes_empty():
    msg = Message.assistant("hello", thinking_blocks=None)
    assert msg.thinking_blocks == []


# ── StreamEvent.thinking ─────────────────────────────────────────────────────

def test_stream_event_thinking_type():
    evt = StreamEvent.thinking("step 1")
    assert evt.type == EventType.thinking
    assert evt.data["delta"] == "step 1"


def test_stream_event_thinking_empty_delta():
    evt = StreamEvent.thinking("")
    assert evt.type == EventType.thinking
    assert evt.data["delta"] == ""


# ── AnthropicProvider._parse_response with thinking blocks ────────────────────

def test_parse_response_extracts_thinking_block():
    from enterprise_ai.providers.anthropic import AnthropicProvider

    provider = AnthropicProvider.__new__(AnthropicProvider)

    thinking_block = MagicMock()
    thinking_block.type = "thinking"
    thinking_block.thinking = "Deep analysis here"
    thinking_block.signature = "sig-abc"

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Final answer"

    resp = MagicMock()
    resp.content = [thinking_block, text_block]
    resp.usage.input_tokens = 100
    resp.usage.output_tokens = 50
    resp.stop_reason = "end_turn"

    result = provider._parse_response(resp)

    assert result.content == "Final answer"
    assert result.thinking_content == "Deep analysis here"
    assert len(result.thinking_blocks) == 1
    assert result.thinking_blocks[0]["thinking"] == "Deep analysis here"
    assert result.thinking_blocks[0]["signature"] == "sig-abc"
    assert result.thinking_blocks[0]["type"] == "thinking"


def test_parse_response_multiple_thinking_blocks():
    from enterprise_ai.providers.anthropic import AnthropicProvider

    provider = AnthropicProvider.__new__(AnthropicProvider)

    def make_thinking(text: str) -> MagicMock:
        b = MagicMock()
        b.type = "thinking"
        b.thinking = text
        b.signature = f"sig-{text[:3]}"
        return b

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "result"

    resp = MagicMock()
    resp.content = [make_thinking("first"), make_thinking("second"), text_block]
    resp.usage.input_tokens = 10
    resp.usage.output_tokens = 5
    resp.stop_reason = "end_turn"

    result = provider._parse_response(resp)

    assert result.thinking_content == "firstsecond"
    assert len(result.thinking_blocks) == 2


# ── AnthropicProvider._to_anthropic_messages with thinking blocks ─────────────

def test_thinking_blocks_included_in_assistant_message_reconstruction():
    from enterprise_ai.providers.anthropic import AnthropicProvider

    provider = AnthropicProvider.__new__(AnthropicProvider)

    blocks = [{"type": "thinking", "thinking": "my analysis", "signature": "sig-xyz"}]
    msg = Message.assistant("the answer", thinking_blocks=blocks)

    _, converted = provider._to_anthropic_messages([msg])

    assert len(converted) == 1
    content = converted[0]["content"]
    # Thinking block must come first
    assert content[0]["type"] == "thinking"
    assert content[0]["thinking"] == "my analysis"
    assert content[0]["signature"] == "sig-xyz"
    # Text follows
    assert content[1]["type"] == "text"
    assert content[1]["text"] == "the answer"


def test_no_thinking_blocks_no_extra_content():
    from enterprise_ai.providers.anthropic import AnthropicProvider

    provider = AnthropicProvider.__new__(AnthropicProvider)
    msg = Message.assistant("plain answer")

    _, converted = provider._to_anthropic_messages([msg])

    content = converted[0]["content"]
    # Only text block, no thinking
    assert all(b["type"] != "thinking" for b in content)


# ── Agent extended_thinking params ───────────────────────────────────────────

def test_agent_accepts_extended_thinking_params():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        extended_thinking=True,
        thinking_budget_tokens=16_000,
    )
    assert agent._loop._extended_thinking is True
    assert agent._loop._thinking_budget_tokens == 16_000


def test_agent_default_no_extended_thinking():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))
    assert agent._loop._extended_thinking is False
    assert agent._loop._thinking_budget_tokens == 10_000


# ── Loop passes thinking kwargs to provider ───────────────────────────────────

async def test_loop_passes_extended_thinking_to_provider():
    """_call_provider must forward extended_thinking kwargs to provider.complete()."""
    from enterprise_ai.engine.loop import QueryLoop
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.memory.session import SessionMemory
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.providers.base import Provider
    from enterprise_ai.tools.registry import ToolRegistry

    captured_kwargs: dict = {}

    class FakeProvider(Provider):
        @property
        def model(self) -> str:
            return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            captured_kwargs.update(kwargs)
            return LLMResponse(content="done", tool_calls=[])

        async def stream(self, messages, tools=None, max_tokens=8096, **kwargs):
            return
            yield  # make it an async generator

    registry = ToolRegistry()
    orchestrator = Orchestrator(
        registry=registry,
        permissions=PermissionEngine(mode=PermissionMode.auto),
    )
    loop = QueryLoop(
        provider=FakeProvider(),
        registry=registry,
        orchestrator=orchestrator,
        memory=SessionMemory(),
        extended_thinking=True,
        thinking_budget_tokens=20_000,
    )

    messages = [Message.user("think hard")]
    await loop._call_provider(messages, None)

    assert captured_kwargs.get("extended_thinking") is True
    assert captured_kwargs.get("thinking_budget_tokens") == 20_000
