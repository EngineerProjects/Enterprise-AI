"""
Unit tests for PermissionEngine.
Tests the critical logic: deny rules, bypass-immune safety check, and the three modes.
"""
import pytest

from enterprise_ai.permissions.engine import (
    ALWAYS_DENY_PATTERNS,
    PermissionDecision,
    PermissionEngine,
    PermissionMode,
)
from enterprise_ai.schema import ToolCall


def make_call(name: str, input: dict | None = None) -> ToolCall:
    return ToolCall(id="test-id", name=name, input=input or {})


# ---------------------------------------------------------------------------
# Deny rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deny_tool_blocked():
    engine = PermissionEngine(deny_tools={"bash"})
    result = await engine.check(make_call("bash"))
    assert result.decision == PermissionDecision.deny
    assert "deny list" in result.reason


@pytest.mark.asyncio
async def test_deny_tool_does_not_block_other_tools():
    engine = PermissionEngine(deny_tools={"bash"})
    result = await engine.check(make_call("file_editor"))
    assert result.allowed


# ---------------------------------------------------------------------------
# Safety check — bypass-immune
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("dangerous", ALWAYS_DENY_PATTERNS[:3])
async def test_safety_check_blocks_dangerous_patterns(dangerous: str):
    engine = PermissionEngine(mode=PermissionMode.bypass)  # bypass mode still blocked by safety
    result = await engine.check(make_call("bash", {"command": dangerous}))
    assert result.decision == PermissionDecision.deny


@pytest.mark.asyncio
async def test_safety_check_is_bypass_immune():
    """Even in bypass mode, dangerous patterns are blocked."""
    engine = PermissionEngine(mode=PermissionMode.bypass)
    result = await engine.check(make_call("bash", {"command": "rm -rf /"}))
    assert result.decision == PermissionDecision.deny


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bypass_mode_allows_everything():
    engine = PermissionEngine(mode=PermissionMode.bypass)
    result = await engine.check(make_call("bash", {"command": "ls"}))
    assert result.allowed


@pytest.mark.asyncio
async def test_auto_mode_allows_normal_tools():
    engine = PermissionEngine(mode=PermissionMode.auto)
    result = await engine.check(make_call("bash", {"command": "ls"}))
    assert result.allowed


@pytest.mark.asyncio
async def test_on_request_mode_allows_when_callback_approves():
    async def approve(_call):
        return True

    engine = PermissionEngine(mode=PermissionMode.on_request, ask_callback=approve)
    result = await engine.check(make_call("bash", {"command": "ls"}))
    assert result.allowed


@pytest.mark.asyncio
async def test_on_request_mode_denies_when_callback_rejects():
    async def reject(_call):
        return False

    engine = PermissionEngine(mode=PermissionMode.on_request, ask_callback=reject)
    result = await engine.check(make_call("bash", {"command": "ls"}))
    assert result.decision == PermissionDecision.deny
    assert engine.denial_count("bash") == 1


@pytest.mark.asyncio
async def test_always_allow_tools_skip_on_request():
    """terminate and code_search are always allowed regardless of mode."""
    engine = PermissionEngine(mode=PermissionMode.on_request)  # no callback
    result = await engine.check(make_call("terminate"))
    assert result.allowed


@pytest.mark.asyncio
async def test_explicit_allow_list_skips_on_request():
    engine = PermissionEngine(mode=PermissionMode.on_request, allow_tools={"bash"})
    result = await engine.check(make_call("bash", {"command": "ls"}))
    assert result.allowed


# ---------------------------------------------------------------------------
# Denial tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_denial_count_increments():
    async def reject(_):
        return False

    engine = PermissionEngine(mode=PermissionMode.on_request, ask_callback=reject)
    for _ in range(3):
        await engine.check(make_call("bash"))
    assert engine.denial_count("bash") == 3
    assert engine.denial_count("file_editor") == 0
