"""Tests for LLM-based compaction (memory/compaction.py)."""
from __future__ import annotations

from unittest.mock import MagicMock

from enterprise_ai.memory.compaction import CompactionConfig, CompactionEngine
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.providers.base import LLMResponse
from enterprise_ai.schema import Message


def make_messages(n: int, role: str = "user") -> list[Message]:
    if role == "user":
        return [Message.user(f"message {i}") for i in range(n)]
    return [Message.assistant(f"response {i}") for i in range(n)]


def make_engine(
    threshold: float = 0.85,
    keep_recent: int = 3,
    max_failures: int = 3,
) -> tuple[CompactionEngine, MagicMock]:
    cfg = CompactionConfig(
        auto_compact_threshold=threshold,
        keep_recent_messages=keep_recent,
        max_consecutive_failures=max_failures,
    )
    provider = MagicMock()
    engine = CompactionEngine(provider, cfg)
    return engine, provider


# ── Token estimation ──────────────────────────────────────────────────────────

def test_estimate_tokens_approximate():
    engine, _ = make_engine()
    msgs = [Message.user("a" * 4000)]
    tokens = engine._estimate_tokens(msgs)
    assert 900 <= tokens <= 1100  # ~1000 ± 10%


def test_estimate_tokens_empty():
    engine, _ = make_engine()
    assert engine._estimate_tokens([]) == 0


# ── should_compact ────────────────────────────────────────────────────────────

def test_should_compact_above_threshold():
    # threshold = 0.85 * 200_000 = 170_000 tokens ≈ 680_000 chars
    engine, _ = make_engine(threshold=0.85)
    # Create messages totalling > 680k chars
    msgs = [Message.user("x" * 700_000)]
    assert engine.should_compact(msgs)


def test_should_not_compact_below_threshold():
    engine, _ = make_engine(threshold=0.85)
    msgs = [Message.user("short message")]
    assert not engine.should_compact(msgs)


def test_should_not_compact_after_max_failures():
    engine, _ = make_engine(max_failures=2)
    engine._consecutive_failures = 2
    msgs = [Message.user("x" * 700_000)]
    assert not engine.should_compact(msgs)


# ── _split ────────────────────────────────────────────────────────────────────

def test_split_keeps_recent():
    engine, _ = make_engine(keep_recent=3)
    msgs = make_messages(10)
    to_compact, to_keep = engine._split(msgs)
    assert len(to_keep) == 3
    assert to_keep == msgs[-3:]


def test_split_with_fewer_messages_than_keep():
    engine, _ = make_engine(keep_recent=5)
    msgs = make_messages(3)
    to_compact, to_keep = engine._split(msgs)
    assert to_compact == []
    assert to_keep == msgs


# ── compact ───────────────────────────────────────────────────────────────────

async def test_compact_returns_summary_message():
    engine, provider = make_engine(keep_recent=2)

    async def fake_complete(messages, max_tokens=2000, **_):
        return LLMResponse(content="Summary of earlier events.", tool_calls=[])

    provider.complete = fake_complete

    msgs = make_messages(10)
    result = await engine.compact(msgs)

    # summary + 2 recent
    assert len(result) == 3
    assert "summary" in result[0].text().lower() or "compacted" in result[0].text().lower()
    assert result[1] == msgs[-2]
    assert result[2] == msgs[-1]


async def test_compact_preserves_recent_messages():
    engine, provider = make_engine(keep_recent=3)

    async def fake_complete(messages, max_tokens=2000, **_):
        return LLMResponse(content="Summary.", tool_calls=[])

    provider.complete = fake_complete

    msgs = make_messages(8)
    result = await engine.compact(msgs)

    recent = result[-3:]
    assert recent == msgs[-3:]


async def test_compact_with_system_prompt():
    engine, provider = make_engine(keep_recent=2)

    async def fake_complete(messages, max_tokens=2000, **_):
        return LLMResponse(content="Summary.", tool_calls=[])

    provider.complete = fake_complete

    msgs = make_messages(6)
    result = await engine.compact(msgs, system_prompt="You are a helper.")

    assert result[0].role.value == "system"
    assert result[0].text() == "You are a helper."


async def test_compact_falls_back_on_provider_error():
    engine, provider = make_engine(keep_recent=2)

    async def failing_complete(messages, max_tokens=2000, **_):
        raise RuntimeError("provider error")

    provider.complete = failing_complete

    msgs = make_messages(6)
    result = await engine.compact(msgs)

    # Fallback: original messages returned unchanged
    assert result == msgs
    assert engine._consecutive_failures == 1


async def test_compact_resets_failures_on_success():
    engine, provider = make_engine()
    engine._consecutive_failures = 2

    async def ok_complete(messages, max_tokens=2000, **_):
        return LLMResponse(content="Summary.", tool_calls=[])

    provider.complete = ok_complete

    msgs = make_messages(15)
    await engine.compact(msgs)
    assert engine._consecutive_failures == 0


# ── SessionMemory.maybe_compact ───────────────────────────────────────────────

async def test_session_memory_no_engine_returns_false():
    mem = SessionMemory()
    result = await mem.maybe_compact()
    assert result is False


async def test_session_memory_compacts_and_replaces():
    engine, provider = make_engine(threshold=0.0, keep_recent=2)  # threshold=0 → always compact

    async def fake_complete(messages, max_tokens=2000, **_):
        return LLMResponse(content="Summary.", tool_calls=[])

    provider.complete = fake_complete

    mem = SessionMemory(compaction_engine=engine)
    for i in range(6):
        mem.add(Message.user(f"msg {i}"))

    compacted = await mem.maybe_compact()
    assert compacted is True
    # summary + 2 recent
    assert len(mem) == 3


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_accepts_compaction_config():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    cfg = CompactionConfig(keep_recent_messages=5)
    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        compaction_config=cfg,
    )
    assert agent._memory._compaction_engine is not None


def test_agent_default_no_compaction():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))
    assert agent._memory._compaction_engine is None
