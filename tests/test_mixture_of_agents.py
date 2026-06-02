"""Tests for item 14: Mixture of Agents (MoA)."""
from __future__ import annotations

import json

import pytest

from enterprise_ai.agent.mixture import AggregationStrategy, MixtureOfAgents, MixtureResult

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(response: str = "agent response"):
    """Build a minimal Agent backed by a fake provider."""
    from typing import AsyncIterator
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent

    class FakeProvider(Provider):
        def __init__(self, resp: str):
            self._resp = resp

        @property
        def model(self): return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content=self._resp, tool_calls=[])

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(provider=FakeProvider(response))
    return agent


# ── Constructor ───────────────────────────────────────────────────────────────

def test_requires_at_least_one_agent():
    with pytest.raises(ValueError, match="at least one"):
        MixtureOfAgents(agents=[])


def test_default_aggregator_is_first_agent():
    a = _make_agent("a")
    b = _make_agent("b")
    moa = MixtureOfAgents([a, b])
    assert moa._aggregator is a


def test_custom_aggregator():
    a = _make_agent("a")
    b = _make_agent("b")
    agg = _make_agent("agg")
    moa = MixtureOfAgents([a, b], aggregator=agg)
    assert moa._aggregator is agg


def test_default_strategy_is_synthesize():
    moa = MixtureOfAgents([_make_agent()])
    assert moa._strategy == AggregationStrategy.synthesize


# ── MixtureResult ─────────────────────────────────────────────────────────────

def test_mixture_result_fields():
    from enterprise_ai.schema.session import SessionResult
    r = MixtureResult(
        output="combined answer",
        strategy=AggregationStrategy.synthesize,
        agent_results=[SessionResult(session_id="s1", output="a1")],
        winner_index=None,
    )
    assert r.output == "combined answer"
    assert r.winner_index is None
    assert len(r.agent_results) == 1


# ── _parse_winner ─────────────────────────────────────────────────────────────

def test_parse_winner_valid():
    text = json.dumps({"winner": 2})
    assert MixtureOfAgents._parse_winner(text, 3) == 2


def test_parse_winner_clamps_to_range():
    text = json.dumps({"winner": 99})
    assert MixtureOfAgents._parse_winner(text, 3) == 2  # clamped to n-1


def test_parse_winner_negative_clamped():
    text = json.dumps({"winner": -5})
    assert MixtureOfAgents._parse_winner(text, 3) == 0


def test_parse_winner_invalid_json_returns_zero():
    assert MixtureOfAgents._parse_winner("not json", 3) == 0


def test_parse_winner_strips_fences():
    text = '```json\n{"winner": 1}\n```'
    assert MixtureOfAgents._parse_winner(text, 3) == 1


# ── _parse_best_of ────────────────────────────────────────────────────────────

def test_parse_best_of_picks_highest():
    text = json.dumps({"scores": [3.0, 9.0, 5.0]})
    assert MixtureOfAgents._parse_best_of(text, 3) == 1


def test_parse_best_of_empty_scores_returns_zero():
    text = json.dumps({"scores": []})
    assert MixtureOfAgents._parse_best_of(text, 3) == 0


def test_parse_best_of_invalid_json_returns_zero():
    assert MixtureOfAgents._parse_best_of("garbage", 3) == 0


def test_parse_best_of_truncates_to_n():
    # 5 scores but only 2 agents — extra scores ignored
    text = json.dumps({"scores": [1, 8, 9, 7, 2]})
    result = MixtureOfAgents._parse_best_of(text, 2)
    assert result in (0, 1)  # only indices 0 and 1 are valid


# ── _format_responses ─────────────────────────────────────────────────────────

def test_format_responses_labels_each():
    from enterprise_ai.schema.session import SessionResult
    results = [
        SessionResult(session_id="s1", output="answer A"),
        SessionResult(session_id="s2", output="answer B"),
    ]
    text = MixtureOfAgents._format_responses(results)
    assert "[Response 0]:" in text
    assert "[Response 1]:" in text
    assert "answer A" in text
    assert "answer B" in text


def test_format_responses_caps_output_length():
    from enterprise_ai.schema.session import SessionResult
    long_output = "x" * 3000
    results = [SessionResult(session_id="s1", output=long_output)]
    text = MixtureOfAgents._format_responses(results)
    assert len(text) < len(long_output)


# ── Full run — synthesize strategy ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_synthesize_calls_aggregator():
    agent_a = _make_agent("Answer from agent A")
    agent_b = _make_agent("Answer from agent B")
    aggregator = _make_agent("Synthesized final answer")

    moa = MixtureOfAgents(
        [agent_a, agent_b],
        aggregator=aggregator,
        strategy=AggregationStrategy.synthesize,
    )
    result = await moa.run("What is 2+2?")

    assert result.strategy == AggregationStrategy.synthesize
    assert result.output == "Synthesized final answer"
    assert len(result.agent_results) == 2
    assert result.winner_index is None


@pytest.mark.asyncio
async def test_run_vote_returns_winner_response():
    agent_a = _make_agent("Answer A")
    agent_b = _make_agent("Answer B")
    agent_c = _make_agent("Answer C")

    # Aggregator votes for index 1
    class VoteProvider:
        @property
        def model(self): return "vote"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            from enterprise_ai.providers.base import LLMResponse
            return LLMResponse(content='{"winner": 1}', tool_calls=[])

    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        aggregator = Agent(provider=VoteProvider())

    moa = MixtureOfAgents(
        [agent_a, agent_b, agent_c],
        aggregator=aggregator,
        strategy=AggregationStrategy.vote,
    )
    result = await moa.run("Explain recursion.")

    assert result.strategy == AggregationStrategy.vote
    assert result.winner_index == 1
    assert result.output == "Answer B"


@pytest.mark.asyncio
async def test_run_best_of_returns_highest_scored():
    agent_a = _make_agent("Answer A")
    agent_b = _make_agent("Answer B")

    # Aggregator scores: A=3, B=9 → winner is B (index 1)
    class ScoreProvider:
        @property
        def model(self): return "scorer"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            from enterprise_ai.providers.base import LLMResponse
            return LLMResponse(content='{"scores": [3, 9]}', tool_calls=[])

    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        aggregator = Agent(provider=ScoreProvider())

    moa = MixtureOfAgents(
        [agent_a, agent_b],
        aggregator=aggregator,
        strategy=AggregationStrategy.best_of,
    )
    result = await moa.run("Describe a binary tree.")

    assert result.strategy == AggregationStrategy.best_of
    assert result.winner_index == 1
    assert result.output == "Answer B"


@pytest.mark.asyncio
async def test_run_all_agents_called_in_parallel():
    """Every agent in the list should be called exactly once."""
    call_counts: list[int] = [0, 0, 0]

    def make_counting_agent(idx: int):
        from typing import AsyncIterator
        from unittest.mock import MagicMock, patch

        from enterprise_ai.agent.agent import Agent
        from enterprise_ai.providers.base import LLMResponse, Provider
        from enterprise_ai.schema import StreamEvent

        class CountingProvider(Provider):
            @property
            def model(self): return "counter"

            async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
                call_counts[idx] += 1
                return LLMResponse(content=f"response-{idx}", tool_calls=[])

            async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
                raise NotImplementedError
                yield

        with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
            return Agent(provider=CountingProvider())

    agents = [make_counting_agent(i) for i in range(3)]
    aggregator = _make_agent("synthesized")
    moa = MixtureOfAgents(agents, aggregator=aggregator)
    await moa.run("test prompt")

    assert call_counts == [1, 1, 1]


@pytest.mark.asyncio
async def test_failed_agent_wrapped_as_error_result():
    """An agent that raises should produce an error SessionResult, not crash MoA."""
    from typing import AsyncIterator
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.base import Provider
    from enterprise_ai.schema import StreamEvent
    from enterprise_ai.schema.session import SessionState

    class BoomProvider(Provider):
        @property
        def model(self): return "boom"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            raise RuntimeError("network failure")

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        failing_agent = Agent(provider=BoomProvider())
    ok_agent = _make_agent("ok response")
    aggregator = _make_agent("merged")

    moa = MixtureOfAgents([failing_agent, ok_agent], aggregator=aggregator)
    result = await moa.run("question")

    # Should not raise; one result is error, the other is ok
    assert len(result.agent_results) == 2
    error_results = [r for r in result.agent_results if r.state == SessionState.error]
    assert len(error_results) == 1
    assert "network failure" in error_results[0].output
