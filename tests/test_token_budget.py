"""Tests for TokenBudgetTracker."""
from __future__ import annotations

from enterprise_ai.engine.token_budget import TokenBudgetConfig, TokenBudgetTracker


def make_tracker(
    budget: int = 100_000,
    threshold: float = 0.90,
    diminishing: int = 500,
    limit: int = 5,
) -> tuple[TokenBudgetTracker, TokenBudgetConfig]:
    cfg = TokenBudgetConfig(
        turn_token_budget=budget,
        budget_completion_threshold=threshold,
        budget_diminishing_tokens=diminishing,
        budget_continuation_limit=limit,
    )
    return TokenBudgetTracker(cfg), cfg


# ── No budget ─────────────────────────────────────────────────────────────────

def test_no_budget_no_continuation():
    cfg = TokenBudgetConfig(turn_token_budget=0)
    tracker = TokenBudgetTracker(cfg)
    tracker.record_tokens(1000, 500)
    decision = tracker.should_continue_for_budget(budget=0, has_tool_calls=True)
    assert not decision.continue_loop


# ── Basic continuation ─────────────────────────────────────────────────────────

def test_continue_when_well_under_threshold():
    tracker, cfg = make_tracker(budget=100_000, threshold=0.90)
    tracker.record_tokens(10_000, 5_000)  # 15% used
    decision = tracker.should_continue_for_budget(budget=100_000, has_tool_calls=True)
    assert decision.continue_loop
    assert decision.nudge_message == "Continue with the task."


def test_stop_when_over_threshold():
    tracker, cfg = make_tracker(budget=100_000, threshold=0.90)
    tracker.record_tokens(85_000, 10_000)  # 95% used
    decision = tracker.should_continue_for_budget(budget=100_000, has_tool_calls=True)
    assert not decision.continue_loop


def test_stop_exactly_at_threshold():
    tracker, cfg = make_tracker(budget=100_000, threshold=0.90)
    tracker.record_tokens(90_000, 0)  # exactly 90%
    decision = tracker.should_continue_for_budget(budget=100_000, has_tool_calls=True)
    assert not decision.continue_loop


# ── Agent finished (no tool calls) ───────────────────────────────────────────

def test_no_continuation_when_no_tool_calls():
    tracker, cfg = make_tracker(budget=100_000)
    tracker.record_tokens(10_000, 5_000)
    # Model finished without tool calls → no nudge
    decision = tracker.should_continue_for_budget(budget=100_000, has_tool_calls=False)
    assert not decision.continue_loop


# ── Continuation limit ────────────────────────────────────────────────────────

def test_continuation_limit_respected():
    tracker, cfg = make_tracker(budget=1_000_000, limit=3)
    for _ in range(3):
        tracker.record_tokens(1_000, 500)
        decision = tracker.should_continue_for_budget(budget=1_000_000, has_tool_calls=True)
        assert decision.continue_loop
    # 4th attempt — at limit
    tracker.record_tokens(1_000, 500)
    decision = tracker.should_continue_for_budget(budget=1_000_000, has_tool_calls=True)
    assert not decision.continue_loop


# ── Diminishing returns ───────────────────────────────────────────────────────

def test_diminishing_returns_detection():
    tracker, cfg = make_tracker(budget=1_000_000, diminishing=500)
    # First check — sets baseline
    tracker.record_tokens(10_000, 5_000)
    tracker.should_continue_for_budget(budget=1_000_000, has_tool_calls=True)
    # Second check — tiny delta (< 500)
    tracker.record_tokens(100, 50)  # only 150 new tokens
    decision = tracker.should_continue_for_budget(budget=1_000_000, has_tool_calls=True)
    assert not decision.continue_loop


def test_no_diminishing_on_first_check():
    """First call never triggers diminishing returns."""
    tracker, cfg = make_tracker(budget=1_000_000, diminishing=500)
    tracker.record_tokens(100, 50)  # tiny amount
    decision = tracker.should_continue_for_budget(budget=1_000_000, has_tool_calls=True)
    # first check — no prior baseline, so diminishing check is skipped
    assert decision.continue_loop


# ── Reset ─────────────────────────────────────────────────────────────────────

def test_reset_clears_all_state():
    tracker, cfg = make_tracker(budget=100_000, limit=2)
    tracker.record_tokens(10_000, 5_000)
    tracker.should_continue_for_budget(budget=100_000, has_tool_calls=True)
    tracker.should_continue_for_budget(budget=100_000, has_tool_calls=True)

    tracker.reset()

    assert tracker.total_turn_tokens == 0
    assert tracker.budget_continuation_count == 0
    assert tracker.last_budget_check_tokens == 0
    assert tracker.last_budget_delta == 0

    # After reset, continuation works again
    tracker.record_tokens(10_000, 5_000)
    decision = tracker.should_continue_for_budget(budget=100_000, has_tool_calls=True)
    assert decision.continue_loop


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_accepts_token_budget():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    cfg = TokenBudgetConfig(turn_token_budget=50_000)
    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        token_budget=cfg,
    )
    assert agent._loop._token_budget_config is cfg
    assert agent._loop._budget_tracker is not None


def test_agent_default_no_token_budget():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))
    assert agent._loop._token_budget_config is None
    assert agent._loop._budget_tracker is None
