"""Tests for item 10: cache hit/miss tracking."""
from __future__ import annotations

import pytest

from enterprise_ai.schema.session import CacheStats, SessionResult

# ── CacheStats model ──────────────────────────────────────────────────────────

def test_defaults_zero():
    s = CacheStats()
    assert s.cache_read_tokens == 0
    assert s.cache_write_tokens == 0


def test_add_accumulates():
    s = CacheStats()
    s.add(read=100, write=50)
    s.add(read=200, write=0)
    assert s.cache_read_tokens == 300
    assert s.cache_write_tokens == 50


def test_total_cached_tokens():
    s = CacheStats(cache_read_tokens=100, cache_write_tokens=200)
    assert s.total_cached_tokens == 300


def test_estimated_savings_no_cache():
    s = CacheStats()
    assert s.estimated_savings_pct == 0.0


def test_estimated_savings_all_reads():
    # All reads → 90 % savings
    s = CacheStats(cache_read_tokens=1000, cache_write_tokens=0)
    assert s.estimated_savings_pct == 90.0


def test_estimated_savings_all_writes():
    # All writes → 0 % savings (writes cost full price)
    s = CacheStats(cache_read_tokens=0, cache_write_tokens=1000)
    assert s.estimated_savings_pct == 0.0


def test_estimated_savings_mixed():
    s = CacheStats(cache_read_tokens=900, cache_write_tokens=100)
    # 900 * 0.9 / 1000 = 0.81 → 81 %
    assert s.estimated_savings_pct == 81.0


# ── SessionResult carries cache_stats ────────────────────────────────────────

def test_session_result_has_cache_stats():
    r = SessionResult(session_id="s1", output="done")
    assert isinstance(r.cache_stats, CacheStats)
    assert r.cache_stats.cache_read_tokens == 0


def test_session_result_custom_cache_stats():
    stats = CacheStats(cache_read_tokens=500, cache_write_tokens=100)
    r = SessionResult(session_id="s1", output="done", cache_stats=stats)
    assert r.cache_stats.cache_read_tokens == 500


# ── LLMResponse carries cache tokens ─────────────────────────────────────────

def test_llm_response_cache_fields_default_zero():
    from enterprise_ai.providers.base import LLMResponse
    r = LLMResponse(content="hi", tool_calls=[])
    assert r.cache_read_tokens == 0
    assert r.cache_write_tokens == 0


def test_llm_response_cache_fields_set():
    from enterprise_ai.providers.base import LLMResponse
    r = LLMResponse(
        content="hi", tool_calls=[],
        cache_read_tokens=300, cache_write_tokens=150,
    )
    assert r.cache_read_tokens == 300
    assert r.cache_write_tokens == 150


# ── Loop accumulates cache stats across turns ─────────────────────────────────

@pytest.mark.asyncio
async def test_loop_accumulates_cache_stats():
    from typing import AsyncIterator

    from enterprise_ai.engine.loop import QueryLoop
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.memory.session import SessionMemory
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.registry import ToolRegistry

    call_n = 0

    class CachingProvider(Provider):
        @property
        def model(self):
            return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            nonlocal call_n
            call_n += 1
            return LLMResponse(
                content="done",
                tool_calls=[],
                cache_read_tokens=100 * call_n,
                cache_write_tokens=50,
            )

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    reg = ToolRegistry()
    loop = QueryLoop(
        provider=CachingProvider(),
        registry=reg,
        orchestrator=Orchestrator(registry=reg, permissions=PermissionEngine(mode=PermissionMode.auto)),
        memory=SessionMemory(),
    )
    ctx = ToolContext(session_id="s1", agent_id="a1", working_dir=".", permission_mode="auto")
    result = await loop.run("hello", ctx)

    assert result.cache_stats.cache_read_tokens == 100  # one LLM call
    assert result.cache_stats.cache_write_tokens == 50


# ── Anthropic provider extracts cache tokens from usage ──────────────────────

def test_anthropic_parse_response_extracts_cache_tokens():
    from unittest.mock import MagicMock, patch

    from enterprise_ai.providers.anthropic import AnthropicProvider

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(type="text", text="hello")]
    mock_resp.stop_reason = "end_turn"
    mock_resp.usage = MagicMock(
        input_tokens=100,
        output_tokens=20,
        cache_read_input_tokens=400,
        cache_creation_input_tokens=200,
    )

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        provider = AnthropicProvider()

    llm_resp = provider._parse_response(mock_resp)
    assert llm_resp.cache_read_tokens == 400
    assert llm_resp.cache_write_tokens == 200


def test_anthropic_parse_response_no_cache_attrs():
    """Provider without cache attrs (non-cached call) returns zeros."""
    from unittest.mock import MagicMock, patch

    from enterprise_ai.providers.anthropic import AnthropicProvider

    mock_resp = MagicMock(spec=["content", "stop_reason", "usage"])
    mock_resp.content = [MagicMock(type="text", text="hi")]
    mock_resp.stop_reason = "end_turn"
    mock_resp.usage = MagicMock(spec=["input_tokens", "output_tokens"])
    mock_resp.usage.input_tokens = 50
    mock_resp.usage.output_tokens = 10

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        provider = AnthropicProvider()

    llm_resp = provider._parse_response(mock_resp)
    assert llm_resp.cache_read_tokens == 0
    assert llm_resp.cache_write_tokens == 0
