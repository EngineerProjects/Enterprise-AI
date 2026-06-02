"""Tests for Anthropic prompt caching (cache_control)."""
from __future__ import annotations

from enterprise_ai.providers.base import LLMResponse
from enterprise_ai.schema import Message, ToolSchema


def _make_anthropic() -> object:
    from enterprise_ai.providers.anthropic import AnthropicProvider
    from enterprise_ai.providers.credential_pool import CredentialPool

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._pool = CredentialPool([None])
    provider._clients = [None]
    return provider


def _make_tools() -> list[ToolSchema]:
    return [
        ToolSchema(name="bash", description="Run bash", input_schema={"type": "object"}),
        ToolSchema(name="read", description="Read file", input_schema={"type": "object"}),
    ]


# ── System prompt caching ─────────────────────────────────────────────────────

def test_no_caching_system_is_plain_string():
    """Without cache_system_prompt, system is passed as a plain string."""

    provider = _make_anthropic()
    msgs = [Message.system("You are helpful."), Message.user("Hi")]
    system, _ = provider._to_anthropic_messages(msgs)
    # System is extracted as plain string; caching applied in complete()/stream()
    assert system == "You are helpful."


async def test_caching_builds_cache_control_block(monkeypatch):
    """With cache_system_prompt=True, system is wrapped with cache_control."""
    from unittest.mock import MagicMock

    provider = _make_anthropic()
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        resp = MagicMock()
        resp.content = []
        resp.usage.input_tokens = 0
        resp.usage.output_tokens = 0
        resp.stop_reason = "end_turn"
        return resp

    client = MagicMock()
    client.messages.create = fake_create
    provider._clients = [client]
    provider._model = "claude-opus-4-8"

    messages = [Message.system("Long system prompt."), Message.user("Do something")]
    await provider.complete(messages, cache_system_prompt=True)

    system_param = captured.get("system")
    assert isinstance(system_param, list), "System should be a list when caching"
    assert len(system_param) == 1
    block = system_param[0]
    assert block["type"] == "text"
    assert block["text"] == "Long system prompt."
    assert block["cache_control"] == {"type": "ephemeral"}


async def test_no_caching_system_stays_string(monkeypatch):
    from unittest.mock import MagicMock

    provider = _make_anthropic()
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        resp = MagicMock()
        resp.content = []
        resp.usage.input_tokens = 0
        resp.usage.output_tokens = 0
        resp.stop_reason = "end_turn"
        return resp

    client = MagicMock()
    client.messages.create = fake_create
    provider._clients = [client]
    provider._model = "claude-opus-4-8"

    messages = [Message.system("Short prompt."), Message.user("Hello")]
    await provider.complete(messages, cache_system_prompt=False)

    assert captured.get("system") == "Short prompt."


# ── Tool schema caching ───────────────────────────────────────────────────────

async def test_tools_last_entry_gets_cache_control(monkeypatch):
    """With cache_system_prompt=True, the last tool gets cache_control."""
    from unittest.mock import MagicMock

    provider = _make_anthropic()
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        resp = MagicMock()
        resp.content = []
        resp.usage.input_tokens = 0
        resp.usage.output_tokens = 0
        resp.stop_reason = "end_turn"
        return resp

    client = MagicMock()
    client.messages.create = fake_create
    provider._clients = [client]
    provider._model = "claude-opus-4-8"

    tools = _make_tools()
    messages = [Message.user("use tools")]
    await provider.complete(messages, tools=tools, cache_system_prompt=True)

    tool_list = captured.get("tools", [])
    assert len(tool_list) == 2
    # Only the last tool gets cache_control
    assert "cache_control" not in tool_list[0]
    assert tool_list[-1]["cache_control"] == {"type": "ephemeral"}


async def test_tools_no_caching_no_cache_control(monkeypatch):
    from unittest.mock import MagicMock

    provider = _make_anthropic()
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        resp = MagicMock()
        resp.content = []
        resp.usage.input_tokens = 0
        resp.usage.output_tokens = 0
        resp.stop_reason = "end_turn"
        return resp

    client = MagicMock()
    client.messages.create = fake_create
    provider._clients = [client]
    provider._model = "claude-opus-4-8"

    tools = _make_tools()
    messages = [Message.user("use tools")]
    await provider.complete(messages, tools=tools, cache_system_prompt=False)

    tool_list = captured.get("tools", [])
    assert all("cache_control" not in t for t in tool_list)


# ── Agent / Loop integration ──────────────────────────────────────────────────

def test_agent_accepts_cache_system_prompt():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        cache_system_prompt=True,
    )
    assert agent._loop._cache_system_prompt is True


def test_agent_default_no_caching():
    from enterprise_ai.agent.agent import Agent
    from enterprise_ai.providers.anthropic import AnthropicProvider

    agent = Agent(provider=AnthropicProvider(model="claude-opus-4-8"))
    assert agent._loop._cache_system_prompt is False


async def test_loop_passes_cache_kwarg_to_provider():
    from enterprise_ai.engine.loop import QueryLoop
    from enterprise_ai.execution.orchestrator import Orchestrator
    from enterprise_ai.memory.session import SessionMemory
    from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
    from enterprise_ai.providers.base import Provider
    from enterprise_ai.tools.registry import ToolRegistry

    captured: dict = {}

    class FakeProvider(Provider):
        @property
        def model(self) -> str:
            return "fake"

        async def complete(self, messages, tools=None, max_tokens=8096, **kwargs):
            captured.update(kwargs)
            return LLMResponse(content="ok", tool_calls=[])

        async def stream(self, messages, tools=None, max_tokens=8096, **kwargs):
            return
            yield

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
        cache_system_prompt=True,
    )

    await loop._call_provider([Message.user("hi")], None)
    assert captured.get("cache_system_prompt") is True
