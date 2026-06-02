"""Tests for item 8: session branching."""
from __future__ import annotations

import pytest

from enterprise_ai.schema.session import Session, SessionResult, SessionState
from enterprise_ai.tools.context import ToolContext

# ── Schema fields ─────────────────────────────────────────────────────────────

def test_session_has_parent_session_id():
    s = Session(id="child", agent_id="agent-1", parent_session_id="parent-123")
    assert s.parent_session_id == "parent-123"


def test_session_parent_defaults_empty():
    s = Session(id="s1", agent_id="a1")
    assert s.parent_session_id == ""


def test_session_result_has_parent_session_id():
    r = SessionResult(
        session_id="child",
        output="done",
        state=SessionState.done,
        parent_session_id="parent-abc",
    )
    assert r.parent_session_id == "parent-abc"


def test_session_result_parent_defaults_empty():
    r = SessionResult(session_id="s1", output="ok")
    assert r.parent_session_id == ""


def test_tool_context_has_parent_session_id():
    ctx = ToolContext(session_id="child", parent_session_id="parent-xyz")
    assert ctx.parent_session_id == "parent-xyz"


def test_tool_context_parent_defaults_empty():
    ctx = ToolContext(session_id="s1")
    assert ctx.parent_session_id == ""


# ── Loop propagates parent_session_id ────────────────────────────────────────

@pytest.mark.asyncio
async def test_loop_result_carries_parent_session_id():
    from typing import AsyncIterator

    from enterprise_ai.engine.loop import QueryLoop
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.memory.session import SessionMemory
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent
    from enterprise_ai.tools.registry import ToolRegistry

    class FakeProvider(Provider):
        @property
        def model(self):
            return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content="done", tool_calls=[])

        async def stream(self, messages, tools=None, max_tokens=8096, **kwargs) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    reg = ToolRegistry()
    loop = QueryLoop(
        provider=FakeProvider(),
        registry=reg,
        orchestrator=Orchestrator(registry=reg, permissions=PermissionEngine(mode=PermissionMode.auto)),
        memory=SessionMemory(),
    )
    ctx = ToolContext(
        session_id="child-session",
        agent_id="agent-1",
        working_dir=".",
        permission_mode="auto",
        parent_session_id="parent-session",
    )
    result = await loop.run("hello", ctx)
    assert result.parent_session_id == "parent-session"
    assert result.session_id == "child-session"


# ── Agent.snapshot() and resume_from() ───────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_snapshot_returns_messages():
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider
    from enterprise_ai.schema import Message

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))

    agent._memory.add(Message.user("hello"))
    agent._memory.add(Message.assistant("world"))

    snapshot = agent.snapshot()
    assert len(snapshot) == 2
    assert snapshot[0].text() == "hello"
    assert snapshot[1].text() == "world"


@pytest.mark.asyncio
async def test_agent_resume_from_loads_messages():
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider
    from enterprise_ai.schema import Message

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        source = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))
        target = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))

    source._memory.add(Message.user("context from source"))
    source._memory.add(Message.assistant("answer from source"))

    target.resume_from(source.snapshot())

    msgs = target._memory.get()
    assert len(msgs) == 2
    assert msgs[0].text() == "context from source"


@pytest.mark.asyncio
async def test_agent_resume_from_clears_existing_memory():
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider
    from enterprise_ai.schema import Message

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))

    agent._memory.add(Message.user("old message"))
    agent.resume_from([Message.user("new context")])

    msgs = agent._memory.get()
    assert len(msgs) == 1
    assert msgs[0].text() == "new context"


# ── Agent.run() accepts parent_session_id ────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_run_passes_parent_session_id():
    from typing import AsyncIterator
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent

    class FakeProvider(Provider):
        @property
        def model(self):
            return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content="done", tool_calls=[])

        async def stream(self, messages, tools=None, max_tokens=8096, **kwargs) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent = Agent(provider=FakeProvider())

    result = await agent.run("hello", parent_session_id="parent-42")
    assert result.parent_session_id == "parent-42"


# ── Branching workflow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_branch_workflow():
    """Simulate a fork: run session A, branch off from it, run session B."""
    from typing import AsyncIterator
    from unittest.mock import MagicMock, patch

    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.base import LLMResponse, Provider
    from enterprise_ai.schema import StreamEvent

    class EchoProvider(Provider):
        @property
        def model(self):
            return "echo"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            return LLMResponse(content="echo response", tool_calls=[])

        async def stream(self, messages, tools=None, max_tokens=8096, **kwargs) -> AsyncIterator[StreamEvent]:
            raise NotImplementedError
            yield

    # Session A
    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent_a = Agent(provider=EchoProvider())

    result_a = await agent_a.run("First message", session_id="session-a")
    assert result_a.session_id == "session-a"
    snapshot_a = agent_a.snapshot()

    # Branch: session B starts from A's history
    with patch("anthropic.AsyncAnthropic", return_value=MagicMock()):
        agent_b = Agent(provider=EchoProvider())

    agent_b.resume_from(snapshot_a)
    result_b = await agent_b.run(
        "Branched question",
        session_id="session-b",
        parent_session_id="session-a",
    )

    assert result_b.session_id == "session-b"
    assert result_b.parent_session_id == "session-a"
    # Session B's memory includes the imported context from A
    msgs_b = agent_b.snapshot()
    assert any(m.text() == "First message" for m in msgs_b)
