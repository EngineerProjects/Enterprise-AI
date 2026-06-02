"""Tests for sub-agent depth limiting in SpawnTool."""
import pytest

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.builtin.spawn import SpawnInput, SpawnTool
from enterprise_ai.tools.context import ToolContext


def make_ctx(depth: int = 0, max_depth: int = 5) -> ToolContext:
    return ToolContext(
        session_id="test-session",
        agent_id="test-agent",
        sub_agent_depth=depth,
        max_sub_agent_depth=max_depth,
    )


async def test_spawn_blocked_at_max_depth():
    tool = SpawnTool(provider_factory=None)
    ctx = make_ctx(depth=5, max_depth=5)
    input_ = SpawnInput(task="do something")
    result = await tool.call(input_, ctx)
    assert result.is_error
    assert "depth limit" in result.content.lower()


async def test_spawn_blocked_above_max_depth():
    tool = SpawnTool(provider_factory=None)
    ctx = make_ctx(depth=7, max_depth=5)
    input_ = SpawnInput(task="do something")
    result = await tool.call(input_, ctx)
    assert result.is_error
    assert "depth limit" in result.content.lower()


async def test_spawn_no_factory_error_is_not_depth_error():
    """At depth < max, error should be about missing factory, not depth limit."""
    tool = SpawnTool(provider_factory=None)
    ctx = make_ctx(depth=0, max_depth=5)
    input_ = SpawnInput(task="do something")
    result = await tool.call(input_, ctx)
    assert result.is_error
    assert "provider_factory" in result.content.lower()
    assert "depth" not in result.content.lower()


async def test_depth_zero_is_under_limit():
    tool = SpawnTool(provider_factory=None)
    ctx = make_ctx(depth=0, max_depth=5)
    input_ = SpawnInput(task="do something")
    result = await tool.call(input_, ctx)
    # Should fail on missing factory, not depth
    assert "depth limit" not in result.content.lower()


async def test_depth_one_below_limit_passes():
    tool = SpawnTool(provider_factory=None)
    ctx = make_ctx(depth=4, max_depth=5)
    input_ = SpawnInput(task="do something")
    result = await tool.call(input_, ctx)
    assert "depth limit" not in result.content.lower()


def test_context_carries_depth_fields():
    ctx = make_ctx(depth=2, max_depth=8)
    assert ctx.sub_agent_depth == 2
    assert ctx.max_sub_agent_depth == 8


def test_context_default_depth():
    ctx = ToolContext()
    assert ctx.sub_agent_depth == 0
    assert ctx.max_sub_agent_depth == 5
