"""Tests for stop hooks."""
import asyncio

import pytest

from enterprise_ai.engine.stop_hooks import StopHookEntry, StopHookInput, StopHookResult, StopHookRunner
from enterprise_ai.schema import Message


def make_input(stop_reason: str = "no_tool_calls", turn: int = 0) -> StopHookInput:
    return StopHookInput(
        session_id="sid-test",
        turn_number=turn,
        stop_reason=stop_reason,
        messages=[Message.user("do something")],
        tool_calls_count=2,
    )


def make_runner(
    hooks: list[StopHookEntry],
    timeout_s: float = 5.0,
    mode: str = "all",
) -> StopHookRunner:
    return StopHookRunner(hooks, timeout_s=timeout_s, mode=mode)


# ── Basic behaviour ───────────────────────────────────────────────────────────

async def test_no_hooks_returns_no_continuation():
    runner = make_runner([])
    result = await runner.run(make_input())
    assert not result.continue_loop
    assert result.inject_messages == []
    assert result.error is None


async def test_hook_can_force_continuation():
    async def force_continue(inp: StopHookInput) -> StopHookResult:
        return StopHookResult(continue_loop=True)

    runner = make_runner([StopHookEntry("force", force_continue)])
    result = await runner.run(make_input())
    assert result.continue_loop


async def test_hook_can_inject_messages():
    reminder = Message.user("Don't forget to write tests!")

    async def inject(inp: StopHookInput) -> StopHookResult:
        return StopHookResult(continue_loop=True, inject_messages=[reminder])

    runner = make_runner([StopHookEntry("inject", inject)])
    result = await runner.run(make_input())
    assert result.continue_loop
    assert reminder in result.inject_messages


async def test_hook_receives_correct_input():
    received: list[StopHookInput] = []

    async def capture(inp: StopHookInput) -> StopHookResult:
        received.append(inp)
        return StopHookResult()

    runner = make_runner([StopHookEntry("cap", capture)])
    await runner.run(make_input(stop_reason="terminate", turn=3))
    assert received[0].stop_reason == "terminate"
    assert received[0].turn_number == 3
    assert received[0].session_id == "sid-test"


async def test_hook_error_is_propagated():
    async def failing_hook(inp: StopHookInput) -> StopHookResult:
        return StopHookResult(error=RuntimeError("quality gate failed"))

    runner = make_runner([StopHookEntry("fail", failing_hook)])
    result = await runner.run(make_input())
    assert result.error is not None
    assert "quality gate" in str(result.error)
    assert not result.continue_loop


async def test_hook_exception_is_swallowed():
    async def exploding_hook(inp: StopHookInput) -> StopHookResult:
        raise ValueError("unexpected crash")

    runner = make_runner([StopHookEntry("boom", exploding_hook)])
    result = await runner.run(make_input())
    # Exception swallowed, session ends normally
    assert not result.continue_loop
    assert result.error is None


async def test_hook_timeout_is_ignored():
    async def slow_hook(inp: StopHookInput) -> StopHookResult:
        await asyncio.sleep(10)
        return StopHookResult(continue_loop=True)

    runner = make_runner([StopHookEntry("slow", slow_hook)], timeout_s=0.05)
    result = await runner.run(make_input())
    assert not result.continue_loop  # timed out, didn't count


# ── Priority ordering ────────────────────────────────────────────────────────

async def test_hooks_run_in_priority_order():
    order: list[int] = []

    async def h0(inp: StopHookInput) -> StopHookResult:
        order.append(0)
        return StopHookResult()

    async def h5(inp: StopHookInput) -> StopHookResult:
        order.append(5)
        return StopHookResult()

    async def h2(inp: StopHookInput) -> StopHookResult:
        order.append(2)
        return StopHookResult()

    runner = make_runner([
        StopHookEntry("h5", h5, priority=5),
        StopHookEntry("h0", h0, priority=0),
        StopHookEntry("h2", h2, priority=2),
    ])
    await runner.run(make_input())
    assert order == [0, 2, 5]


# ── mode="all" vs mode="first" ────────────────────────────────────────────────

async def test_mode_all_accumulates_messages():
    msg1 = Message.user("msg 1")
    msg2 = Message.user("msg 2")

    async def h1(inp: StopHookInput) -> StopHookResult:
        return StopHookResult(continue_loop=True, inject_messages=[msg1])

    async def h2(inp: StopHookInput) -> StopHookResult:
        return StopHookResult(continue_loop=True, inject_messages=[msg2])

    runner = make_runner(
        [StopHookEntry("h1", h1), StopHookEntry("h2", h2)],
        mode="all",
    )
    result = await runner.run(make_input())
    assert result.continue_loop
    assert msg1 in result.inject_messages
    assert msg2 in result.inject_messages


async def test_mode_first_stops_at_first_continuation():
    called: list[int] = []

    async def h1(inp: StopHookInput) -> StopHookResult:
        called.append(1)
        return StopHookResult(continue_loop=True)

    async def h2(inp: StopHookInput) -> StopHookResult:
        called.append(2)
        return StopHookResult()

    runner = make_runner(
        [StopHookEntry("h1", h1, priority=0), StopHookEntry("h2", h2, priority=10)],
        mode="first",
    )
    result = await runner.run(make_input())
    assert result.continue_loop
    assert 2 not in called  # h2 never ran


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_accepts_stop_hooks():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    async def quality_gate(inp: StopHookInput) -> StopHookResult:
        return StopHookResult()

    agent = Agent(
        provider=AnthropicProvider(model="claude-haiku-4-5-20251001"),
        stop_hooks=[StopHookEntry("quality_gate", quality_gate)],
    )
    assert agent._loop._stop_hooks is not None


def test_agent_no_stop_hooks_is_none():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-haiku-4-5-20251001"))
    assert agent._loop._stop_hooks is None
