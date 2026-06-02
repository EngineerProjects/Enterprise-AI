"""Tests for Agent.with_spawn()."""
from __future__ import annotations

from enterprise_ai.agent.agent import Agent
from enterprise_ai.providers.anthropic import AnthropicProvider
from enterprise_ai.providers.base import Provider


def make_agent(**kwargs) -> Agent:
    return Agent(provider=AnthropicProvider(model="claude-haiku-4-5-20251001"), **kwargs)


# ── Basic wiring ──────────────────────────────────────────────────────────────

def test_with_spawn_registers_tool():
    agent = make_agent()
    assert not any(t.name == "spawn_agent" for t in agent._registry.all())
    agent.with_spawn()
    assert any(t.name == "spawn_agent" for t in agent._registry.all())


def test_with_spawn_returns_self():
    agent = make_agent()
    result = agent.with_spawn()
    assert result is agent


def test_with_spawn_chainable():
    """Agent(...).with_spawn() can be chained at construction time."""
    agent = make_agent().with_spawn()
    assert any(t.name == "spawn_agent" for t in agent._registry.all())


def test_with_spawn_idempotent():
    """Calling with_spawn() twice still only registers one spawn_agent tool."""
    agent = make_agent()
    agent.with_spawn()
    agent.with_spawn()
    spawn_tools = [t for t in agent._registry.all() if t.name == "spawn_agent"]
    # ToolRegistry.register() replaces if same name — should still be exactly 1
    assert len(spawn_tools) == 1


# ── provider_factory ──────────────────────────────────────────────────────────

def test_with_spawn_default_factory_uses_agent_provider():
    """Without a custom factory, spawn tool reuses the agent's own provider."""
    agent = make_agent()
    agent.with_spawn()

    spawn_tool = next(t for t in agent._registry.all() if t.name == "spawn_agent")
    factory = spawn_tool._provider_factory
    assert factory is not None
    # Factory returns the same provider instance
    created = factory()
    assert created is agent._provider


def test_with_spawn_custom_factory_used():
    """A custom provider_factory is stored and called by SpawnTool."""
    custom_calls: list[int] = []

    def my_factory() -> Provider:
        custom_calls.append(1)
        return AnthropicProvider(model="claude-haiku-4-5-20251001")

    agent = make_agent()
    agent.with_spawn(provider_factory=my_factory)

    spawn_tool = next(t for t in agent._registry.all() if t.name == "spawn_agent")
    spawn_tool._provider_factory()
    assert custom_calls == [1]


# ── Parent registry injection ─────────────────────────────────────────────────

def test_with_spawn_injects_parent_registry():
    agent = make_agent()
    assert "_parent_registry" not in agent._metadata
    agent.with_spawn()
    assert agent._metadata.get("_parent_registry") is agent._registry


# ── Depth limiting still applies ──────────────────────────────────────────────

async def test_spawn_blocked_at_max_depth():
    """SpawnTool still refuses to spawn when depth limit is reached."""
    from enterprise_ai.tools.builtin.spawn import SpawnInput
    from enterprise_ai.tools.context import ToolContext

    agent = make_agent(max_sub_agent_depth=2)
    agent.with_spawn()

    spawn_tool = next(t for t in agent._registry.all() if t.name == "spawn_agent")
    ctx = ToolContext(
        session_id="sid",
        sub_agent_depth=2,
        max_sub_agent_depth=2,
    )
    result = await spawn_tool.call(SpawnInput(task="do something"), ctx)
    assert result.is_error
    assert "depth limit" in result.content.lower()


# ── Team integration ──────────────────────────────────────────────────────────

def test_team_agents_can_have_spawn():
    """Agents in a Team can each have with_spawn() — no conflict."""
    from enterprise_ai.team.team import Team

    agents = [make_agent().with_spawn() for _ in range(3)]
    team = Team(agents=agents)
    for agent in team.agents:
        assert any(t.name == "spawn_agent" for t in agent._registry.all())
