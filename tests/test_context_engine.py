"""Tests for item 13: ContextEngine plugin interface."""
from __future__ import annotations

import pytest

from enterprise_ai.memory.context_engine import ContextEngine
from enterprise_ai.schema import Message

# ── ContextEngine ABC ─────────────────────────────────────────────────────────

def test_context_engine_is_abstract():
    import inspect
    assert inspect.isabstract(ContextEngine)


def test_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        ContextEngine()  # type: ignore[abstract]


def test_lifecycle_hooks_have_defaults():
    """The four lifecycle hooks should not require override."""

    class MinimalEngine(ContextEngine):
        def should_compact(self, messages):
            return False

        async def compact(self, messages, system_prompt=""):
            return messages

    engine = MinimalEngine()
    # These should not raise
    engine.on_session_start("s1")
    engine.on_session_end("s1", [])
    engine.on_session_reset()
    engine.carry_over_new_session_context("old", "new")


# ── CompactionEngine implements ContextEngine ─────────────────────────────────

def test_compaction_engine_is_context_engine():
    from enterprise_ai.memory.compaction import CompactionEngine
    assert issubclass(CompactionEngine, ContextEngine)


def test_compaction_engine_instantiable_as_context_engine():
    from unittest.mock import MagicMock

    from enterprise_ai.memory.compaction import CompactionConfig, CompactionEngine

    provider = MagicMock()
    engine: ContextEngine = CompactionEngine(provider, CompactionConfig())
    assert isinstance(engine, ContextEngine)


# ── SessionMemory accepts ContextEngine ───────────────────────────────────────

def test_session_memory_accepts_context_engine():
    from enterprise_ai.memory.session import SessionMemory

    class NoopEngine(ContextEngine):
        def should_compact(self, messages):
            return False

        async def compact(self, messages, system_prompt=""):
            return messages

    mem = SessionMemory(compaction_engine=NoopEngine())
    mem.add(Message.user("hello"))
    assert len(mem) == 1


@pytest.mark.asyncio
async def test_session_memory_calls_custom_engine():
    from enterprise_ai.memory.session import SessionMemory

    compact_called = False

    class CountingEngine(ContextEngine):
        def should_compact(self, messages):
            return len(messages) >= 2

        async def compact(self, messages, system_prompt=""):
            nonlocal compact_called
            compact_called = True
            return messages[-1:]  # keep only last message

    mem = SessionMemory(compaction_engine=CountingEngine())
    mem.add(Message.user("msg1"))
    mem.add(Message.user("msg2"))

    compacted = await mem.maybe_compact()
    assert compacted is True
    assert compact_called
    assert len(mem) == 1


# ── Custom engine swappable in Agent ─────────────────────────────────────────

def test_agent_accepts_context_engine():
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    class SlimEngine(ContextEngine):
        def should_compact(self, messages):
            return len(messages) > 10

        async def compact(self, messages, system_prompt=""):
            return messages[-5:]

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            context_engine=SlimEngine(),
        )

    assert agent._memory._compaction_engine is not None
    assert isinstance(agent._memory._compaction_engine, SlimEngine)


def test_context_engine_overrides_compaction_config():
    """context_engine= takes priority over compaction_config=."""
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.memory.compaction import CompactionConfig
    from enterprise_ai.providers.anthropic import AnthropicProvider

    class CustomEngine(ContextEngine):
        def should_compact(self, messages):
            return False

        async def compact(self, messages, system_prompt=""):
            return messages

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            context_engine=CustomEngine(),
            compaction_config=CompactionConfig(),  # should be ignored
        )

    assert isinstance(agent._memory._compaction_engine, CustomEngine)


# ── Lifecycle hooks called by loop ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_context_engine_lifecycle_hooks_called():
    from typing import AsyncIterator

    from enterprise_ai.engine.loop import QueryLoop
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.memory.session import SessionMemory
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent
    from enterprise_ai.tools.context import ToolContext
    from enterprise_ai.tools.registry import ToolRegistry

    events: list[str] = []

    class TrackingEngine(ContextEngine):
        def should_compact(self, messages):
            return False

        async def compact(self, messages, system_prompt=""):
            return messages

        def on_session_start(self, session_id):
            events.append(f"start:{session_id}")

        def on_session_end(self, session_id, messages):
            events.append(f"end:{session_id}")

    class FakeProvider(Provider):
        @property
        def model(self):
            return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content="done", tool_calls=[])

        async def stream(self, *a, **kw) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    # The loop fires session_start/end hooks — wire the engine to hook events
    from enterprise_ai.hooks.events import HookEvent
    from enterprise_ai.hooks.executor import HookExecutor
    from enterprise_ai.hooks.registry import HookRegistry

    engine = TrackingEngine()
    reg = ToolRegistry()
    memory = SessionMemory(compaction_engine=engine)

    hook_reg = HookRegistry()

    async def on_start(payload):
        engine.on_session_start(payload.session_id)

    async def on_end(payload):
        engine.on_session_end(payload.session_id, memory.get())

    hook_reg.on(HookEvent.session_start, on_start)
    hook_reg.on(HookEvent.session_end, on_end)
    hook_executor = HookExecutor(hook_reg)

    loop = QueryLoop(
        provider=FakeProvider(),
        registry=reg,
        orchestrator=Orchestrator(registry=reg, permissions=PermissionEngine(mode=PermissionMode.auto)),
        memory=memory,
        hooks=hook_executor,
    )
    ctx = ToolContext(session_id="hook-test", agent_id="a1", working_dir=".", permission_mode="auto")
    await loop.run("hello", ctx)

    assert any("start:hook-test" in e for e in events)
    assert any("end:hook-test" in e for e in events)
