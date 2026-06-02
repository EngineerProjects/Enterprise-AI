"""Tests for the hook system."""
import asyncio

from enterprise_ai.hooks import HookEvent, HookExecutor, HookPayload, HookRegistry, HookResult

# ── Helpers ──────────────────────────────────────────────────────────────────

def make_executor(handlers: list | None = None, timeout_s: float = 5.0) -> HookExecutor:
    registry = HookRegistry()
    if handlers:
        for event, handler in handlers:
            registry.on(event, handler)
    return HookExecutor(registry, timeout_s=timeout_s)


async def noop_handler(payload: HookPayload) -> HookResult:
    return HookResult()


async def stop_handler(payload: HookPayload) -> HookResult:
    return HookResult(stop=True, message="blocked by test")


async def modify_handler(payload: HookPayload) -> HookResult:
    return HookResult(modified_data={"tool_input": {"cmd": "echo modified"}})


async def raising_handler(payload: HookPayload) -> HookResult:
    raise ValueError("handler exploded")


# ── Registry ─────────────────────────────────────────────────────────────────

def test_registry_registers_handler():
    reg = HookRegistry()
    reg.on(HookEvent.pre_tool_use, noop_handler)
    assert noop_handler in reg.handlers_for(HookEvent.pre_tool_use)


def test_registry_unregisters_handler():
    reg = HookRegistry()
    reg.on(HookEvent.pre_tool_use, noop_handler)
    reg.off(HookEvent.pre_tool_use, noop_handler)
    assert noop_handler not in reg.handlers_for(HookEvent.pre_tool_use)


def test_registry_handlers_sorted_by_priority():
    call_order: list[int] = []

    async def h0(p: HookPayload) -> None:
        call_order.append(0)

    async def h5(p: HookPayload) -> None:
        call_order.append(5)

    async def h2(p: HookPayload) -> None:
        call_order.append(2)

    reg = HookRegistry()
    reg.on(HookEvent.turn_start, h5, priority=5)
    reg.on(HookEvent.turn_start, h0, priority=0)
    reg.on(HookEvent.turn_start, h2, priority=2)
    assert reg.handlers_for(HookEvent.turn_start) == [h0, h2, h5]


def test_registry_from_list():
    reg = HookRegistry.from_list([
        (HookEvent.pre_tool_use, noop_handler),
        (HookEvent.on_error, noop_handler),
    ])
    assert reg.has_handlers(HookEvent.pre_tool_use)
    assert reg.has_handlers(HookEvent.on_error)
    assert not reg.has_handlers(HookEvent.turn_start)


def test_registry_has_handlers_false_when_empty():
    reg = HookRegistry()
    assert not reg.has_handlers(HookEvent.pre_tool_use)


# ── Executor — fire ───────────────────────────────────────────────────────────

async def test_fire_calls_handler():
    called: list[HookPayload] = []

    async def capture(payload: HookPayload) -> None:
        called.append(payload)

    executor = make_executor([(HookEvent.turn_start, capture)])
    await executor.fire(HookEvent.turn_start, "sid-1", {"turn": 0})
    assert len(called) == 1
    assert called[0].session_id == "sid-1"
    assert called[0].data["turn"] == 0


async def test_fire_no_handlers_returns_empty_result():
    executor = make_executor()
    result = await executor.fire(HookEvent.turn_start, "sid", {})
    assert not result.stop
    assert result.modified_data is None


async def test_fire_multiple_handlers_all_called():
    count = [0]

    async def inc(p: HookPayload) -> None:
        count[0] += 1

    executor = make_executor([
        (HookEvent.post_api_call, inc),
        (HookEvent.post_api_call, inc),
        (HookEvent.post_api_call, inc),
    ])
    await executor.fire(HookEvent.post_api_call, "sid", {})
    assert count[0] == 3


async def test_fire_stop_short_circuits_remaining():
    count = [0]

    async def inc(p: HookPayload) -> None:
        count[0] += 1

    reg = HookRegistry()
    reg.on(HookEvent.pre_tool_use, stop_handler, priority=0)
    reg.on(HookEvent.pre_tool_use, inc, priority=10)  # should NOT run
    executor = HookExecutor(reg)

    result = await executor.fire(HookEvent.pre_tool_use, "sid", {})
    assert result.stop
    assert count[0] == 0


async def test_fire_error_does_not_propagate():
    executor = make_executor([(HookEvent.pre_tool_use, raising_handler)])
    # Should not raise
    result = await executor.fire(HookEvent.pre_tool_use, "sid", {})
    assert not result.stop


async def test_fire_timeout_skips_handler():
    async def slow_handler(p: HookPayload) -> HookResult:
        await asyncio.sleep(10)
        return HookResult()

    executor = make_executor([(HookEvent.pre_tool_use, slow_handler)], timeout_s=0.05)
    result = await executor.fire(HookEvent.pre_tool_use, "sid", {})
    assert not result.stop  # timed out but didn't crash


async def test_fire_accumulates_modified_data():
    async def mod1(p: HookPayload) -> HookResult:
        return HookResult(modified_data={"tool_input": {"x": 1}})

    async def mod2(p: HookPayload) -> HookResult:
        return HookResult(modified_data={"tool_input": {"x": 2}})

    reg = HookRegistry()
    reg.on(HookEvent.pre_tool_use, mod1, priority=0)
    reg.on(HookEvent.pre_tool_use, mod2, priority=10)
    executor = HookExecutor(reg)

    result = await executor.fire(HookEvent.pre_tool_use, "sid", {})
    # Last writer wins
    assert result.modified_data == {"tool_input": {"x": 2}}


# ── Executor — fire_pre_tool / fire_post_tool ─────────────────────────────────

async def test_fire_pre_tool_passes_correct_data():
    received: list[dict] = []

    async def capture(p: HookPayload) -> None:
        received.append(p.data)

    executor = make_executor([(HookEvent.pre_tool_use, capture)])
    await executor.fire_pre_tool("sid", "bash", {"cmd": "ls"})
    assert received[0]["tool_name"] == "bash"
    assert received[0]["tool_input"] == {"cmd": "ls"}


async def test_fire_post_tool_uses_fail_event_on_error():
    events: list[HookEvent] = []

    async def capture(p: HookPayload) -> None:
        events.append(p.event)

    reg = HookRegistry()
    reg.on(HookEvent.post_tool_use, capture)
    reg.on(HookEvent.post_tool_use_fail, capture)
    executor = HookExecutor(reg)

    await executor.fire_post_tool("sid", "bash", "output", is_error=False)
    await executor.fire_post_tool("sid", "bash", "error msg", is_error=True)

    assert events[0] == HookEvent.post_tool_use
    assert events[1] == HookEvent.post_tool_use_fail


# ── Agent integration ─────────────────────────────────────────────────────────

def test_agent_accepts_hooks_list():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    called = []

    async def my_hook(p: HookPayload) -> None:
        called.append(p.event)

    agent = Agent(
        provider=AnthropicProvider(model="claude-haiku-4-5-20251001"),
        hooks=[(HookEvent.turn_start, my_hook)],
    )
    # Verify the executor was wired up
    assert agent._loop._hooks is not None


def test_agent_accepts_hooks_registry():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    reg = HookRegistry()
    reg.on(HookEvent.pre_tool_use, noop_handler)

    agent = Agent(
        provider=AnthropicProvider(model="claude-haiku-4-5-20251001"),
        hooks=reg,
    )
    assert agent._loop._hooks is not None
    assert agent._orchestrator._hooks is not None


def test_agent_no_hooks_leaves_executor_none():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-haiku-4-5-20251001"))
    assert agent._loop._hooks is None
    assert agent._orchestrator._hooks is None
