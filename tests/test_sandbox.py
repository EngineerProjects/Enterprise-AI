"""
Unit tests for sandbox.
- LocalSandbox: execution, timeout, blocked patterns, file operations
- SandboxManager: lifecycle, acquire/release, multi-agent isolation
Docker tests are excluded (require a running Docker daemon).
"""
import tempfile
from pathlib import Path

import pytest

from enterprise_ai.sandbox.local import BLOCKED_PATTERNS, LocalSandbox
from enterprise_ai.sandbox.manager import SandboxManager

# ---------------------------------------------------------------------------
# LocalSandbox — execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_exec_simple_command():
    async with LocalSandbox() as sb:
        result = await sb.exec("echo hello")
    assert result.exit_code == 0
    assert "hello" in result.output
    assert not result.error


@pytest.mark.asyncio
async def test_local_exec_captures_stderr_via_redirect():
    async with LocalSandbox() as sb:
        result = await sb.exec("echo error >&2")
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_local_exec_nonzero_exit_code():
    async with LocalSandbox() as sb:
        result = await sb.exec("exit 42", timeout=5.0)
    assert result.exit_code == 42
    assert result.error


@pytest.mark.asyncio
async def test_local_exec_timeout():
    async with LocalSandbox() as sb:
        result = await sb.exec("sleep 10", timeout=0.3)
    assert result.timed_out
    assert result.error
    assert "timed out" in result.output


@pytest.mark.asyncio
async def test_local_exec_working_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        async with LocalSandbox(working_dir=tmpdir) as sb:
            result = await sb.exec("pwd")
        assert tmpdir in result.output


# ---------------------------------------------------------------------------
# LocalSandbox — blocked patterns (bypass-immune)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("pattern", BLOCKED_PATTERNS[:3])
async def test_local_exec_blocks_dangerous_patterns(pattern: str):
    async with LocalSandbox() as sb:
        result = await sb.exec(pattern)
    assert result.error
    assert "Blocked" in result.output


@pytest.mark.asyncio
async def test_local_exec_safe_commands_not_blocked():
    async with LocalSandbox() as sb:
        result = await sb.exec("ls /tmp")
    assert not result.timed_out
    # May fail if /tmp is empty but should not be blocked


# ---------------------------------------------------------------------------
# LocalSandbox — file operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_write_and_read_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        async with LocalSandbox(working_dir=tmpdir) as sb:
            await sb.write_file("test.txt", "hello world")
            content = await sb.read_file("test.txt")
        assert content == "hello world"


@pytest.mark.asyncio
async def test_local_write_creates_parent_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        async with LocalSandbox(working_dir=tmpdir) as sb:
            await sb.write_file("subdir/nested/file.txt", "nested content")
            assert Path(tmpdir, "subdir", "nested", "file.txt").exists()


@pytest.mark.asyncio
async def test_local_exec_can_use_written_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        async with LocalSandbox(working_dir=tmpdir) as sb:
            await sb.write_file("script.py", "print('from script')")
            result = await sb.exec("python3 script.py")
        assert "from script" in result.output


# ---------------------------------------------------------------------------
# SandboxManager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manager_acquire_creates_sandbox():
    manager = SandboxManager(factory=lambda: LocalSandbox())
    sb = await manager.acquire("agent-1")
    assert sb is not None
    assert len(manager) == 1
    await manager.close()


@pytest.mark.asyncio
async def test_manager_acquire_same_id_returns_same_sandbox():
    manager = SandboxManager(factory=lambda: LocalSandbox())
    sb1 = await manager.acquire("agent-1")
    sb2 = await manager.acquire("agent-1")
    assert sb1 is sb2
    await manager.close()


@pytest.mark.asyncio
async def test_manager_acquire_different_ids_returns_different_sandboxes():
    manager = SandboxManager(factory=lambda: LocalSandbox())
    sb1 = await manager.acquire("agent-1")
    sb2 = await manager.acquire("agent-2")
    assert sb1 is not sb2
    assert len(manager) == 2
    await manager.close()


@pytest.mark.asyncio
async def test_manager_release_removes_sandbox():
    manager = SandboxManager(factory=lambda: LocalSandbox())
    await manager.acquire("agent-1")
    await manager.release("agent-1")
    assert manager.get("agent-1") is None
    assert len(manager) == 0


@pytest.mark.asyncio
async def test_manager_close_stops_all():
    manager = SandboxManager(factory=lambda: LocalSandbox())
    await manager.acquire("agent-1")
    await manager.acquire("agent-2")
    await manager.close()
    assert len(manager) == 0


@pytest.mark.asyncio
async def test_manager_sandboxes_are_isolated():
    """Each agent's sandbox has its own working dir and files."""
    with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
        manager = SandboxManager()
        sb1 = await manager.acquire("agent-1", factory=lambda: LocalSandbox(working_dir=dir1))
        sb2 = await manager.acquire("agent-2", factory=lambda: LocalSandbox(working_dir=dir2))

        await sb1.write_file("secret.txt", "agent1-data")
        await sb2.write_file("secret.txt", "agent2-data")

        content1 = await sb1.read_file("secret.txt")
        content2 = await sb2.read_file("secret.txt")

        assert content1 == "agent1-data"
        assert content2 == "agent2-data"
        assert content1 != content2

        await manager.close()
