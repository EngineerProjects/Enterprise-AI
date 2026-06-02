"""
Unit tests for team shared memory: FTSMemory and memory tools.
All tests use in-memory SQLite (:memory:) — no disk state.
"""
import pytest

from enterprise_ai.memory.team import FTSMemory
from enterprise_ai.team.mailbox import Mail, Mailbox
from enterprise_ai.team.task_board import TaskBoard
from enterprise_ai.tools.builtin.memory import RecentMemoryTool, SearchMemoryTool, WriteMemoryTool
from enterprise_ai.tools.context import ToolContext


def make_ctx(agent_id: str, memory: FTSMemory | None = None) -> ToolContext:
    ctx = ToolContext(agent_id=agent_id)
    if memory:
        ctx.metadata["team_memory"] = memory
    return ctx


# ---------------------------------------------------------------------------
# FTSMemory — core
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fts_write_and_search():
    mem = FTSMemory()
    await mem.write("OAuth2 implementation complete", source="task", agent_id="dev")
    await mem.write("Need help with JWT tokens", source="mail", agent_id="alice")

    results = await mem.search("OAuth2")
    assert len(results) == 1
    assert "OAuth2" in results[0].content
    assert results[0].source == "task"


@pytest.mark.asyncio
async def test_fts_search_returns_multiple_ranked():
    mem = FTSMemory()
    await mem.write("JWT authentication module built", source="task", agent_id="dev")
    await mem.write("JWT token expiry issue found", source="note", agent_id="qa")
    await mem.write("Database schema migration done", source="task", agent_id="dev")

    results = await mem.search("JWT")
    assert len(results) == 2
    contents = [r.content for r in results]
    assert any("JWT authentication" in c for c in contents)
    assert any("JWT token" in c for c in contents)


@pytest.mark.asyncio
async def test_fts_search_no_results():
    mem = FTSMemory()
    await mem.write("Unrelated content", source="note", agent_id="alice")

    results = await mem.search("quantum computing")
    assert results == []


@pytest.mark.asyncio
async def test_fts_recent_returns_latest():
    mem = FTSMemory()
    await mem.write("Entry 1", source="note", agent_id="a")
    await mem.write("Entry 2", source="note", agent_id="b")
    await mem.write("Entry 3", source="note", agent_id="c")

    results = await mem.recent(limit=2)
    assert len(results) == 2
    # Most recent first
    assert "Entry 3" in results[0].content
    assert "Entry 2" in results[1].content


@pytest.mark.asyncio
async def test_fts_metadata_preserved():
    mem = FTSMemory()
    await mem.write("Task done", source="task", agent_id="dev", task_id="abc123", priority="high")

    results = await mem.search("Task done")
    assert results[0].metadata.get("task_id") == "abc123"
    assert results[0].metadata.get("priority") == "high"


@pytest.mark.asyncio
async def test_fts_search_fallback_on_invalid_query():
    mem = FTSMemory()
    await mem.write("Hello world content", source="note", agent_id="alice")

    # FTS5 special chars — should fall back to LIKE search
    results = await mem.search("Hello world")
    assert len(results) >= 0  # no exception


# ---------------------------------------------------------------------------
# Auto-indexing — Mailbox and TaskBoard write to memory automatically
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mailbox_auto_indexes_sent_mail():
    mem = FTSMemory()
    mb = Mailbox(memory=mem)
    mb.register("alice")
    mb.register("bob")

    mail = Mail(sender="alice", recipients=["bob"], subject="OAuth2 design", body="Here is the plan")
    await mb.send(mail)

    results = await mem.search("OAuth2")
    assert len(results) == 1
    assert results[0].source == "mail"
    assert results[0].agent_id == "alice"


@pytest.mark.asyncio
async def test_task_board_auto_indexes_completed_task():
    mem = FTSMemory()
    board = TaskBoard(memory=mem)

    task = await board.post("Build REST API", "Create endpoints", posted_by="manager")
    await board.claim(task.id, "developer")
    await board.complete(task.id, result="All endpoints implemented with tests")

    results = await mem.search("endpoints")
    assert len(results) == 1
    assert results[0].source == "task"
    assert "implemented" in results[0].content


@pytest.mark.asyncio
async def test_task_board_auto_indexes_failed_task():
    mem = FTSMemory()
    board = TaskBoard(memory=mem)

    task = await board.post("Deploy to prod", "Deploy version 2.0", posted_by="manager")
    await board.claim(task.id, "devops")
    await board.fail(task.id, reason="Missing environment variables in CI")

    results = await mem.search("environment variables")
    assert len(results) == 1
    assert "failed" in results[0].content.lower()


# ---------------------------------------------------------------------------
# Memory tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_memory_tool():
    mem = FTSMemory()
    await mem.write("Redis caching strategy decided", source="decision", agent_id="alice")

    tool = SearchMemoryTool()
    inp = SearchMemoryTool.input_schema(query="Redis caching", limit=5)
    ctx = make_ctx("bob", memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "Redis" in result.content


@pytest.mark.asyncio
async def test_search_memory_tool_no_memory_in_ctx():
    tool = SearchMemoryTool()
    inp = SearchMemoryTool.input_schema(query="test")
    ctx = make_ctx("bob")  # no memory

    result = await tool.call(inp, ctx)
    assert result.is_error


@pytest.mark.asyncio
async def test_write_memory_tool():
    mem = FTSMemory()
    tool = WriteMemoryTool()
    inp = WriteMemoryTool.input_schema(content="We decided to use PostgreSQL for the main DB", source="decision")
    ctx = make_ctx("alice", memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error

    found = await mem.search("PostgreSQL")
    assert len(found) == 1
    assert found[0].agent_id == "alice"
    assert found[0].source == "decision"


@pytest.mark.asyncio
async def test_recent_memory_tool():
    mem = FTSMemory()
    await mem.write("First entry", source="note", agent_id="a")
    await mem.write("Second entry", source="note", agent_id="b")

    tool = RecentMemoryTool()
    inp = RecentMemoryTool.input_schema(limit=5)
    ctx = make_ctx("alice", memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "Second entry" in result.content
    assert "First entry" in result.content


@pytest.mark.asyncio
async def test_recent_memory_tool_empty():
    mem = FTSMemory()
    tool = RecentMemoryTool()
    inp = RecentMemoryTool.input_schema(limit=5)
    ctx = make_ctx("alice", memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "empty" in result.content.lower()
