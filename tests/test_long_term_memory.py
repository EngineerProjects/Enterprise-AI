"""
Unit tests for LongTermMemory and agent memory tools.
All in-memory (:memory:) — no disk state, no API calls.
"""
import pytest

from enterprise_ai.memory.long_term import LongTermMemory
from enterprise_ai.tools.builtin.agent_memory import (
    ForgetTool,
    RecallTool,
    RecentMemoriesTool,
    RememberTool,
)
from enterprise_ai.tools.context import ToolContext


def make_memory(agent_id: str = "test-agent") -> LongTermMemory:
    return LongTermMemory(agent_id=agent_id)  # :memory: by default


def make_ctx(agent_id: str = "test-agent", memory: LongTermMemory | None = None) -> ToolContext:
    ctx = ToolContext(agent_id=agent_id)
    if memory:
        ctx.metadata["agent_memory"] = memory
    return ctx


# ---------------------------------------------------------------------------
# LongTermMemory — core
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remember_and_recall():
    mem = make_memory()
    await mem.remember("Always use pytest for testing", category="preference")
    await mem.remember("Project uses PostgreSQL 15", category="fact")

    results = await mem.recall("pytest")
    assert len(results) >= 1
    assert any("pytest" in r.content for r in results)


@pytest.mark.asyncio
async def test_recall_no_results():
    mem = make_memory()
    await mem.remember("Something unrelated", category="note")
    results = await mem.recall("quantum physics xenon")
    assert results == []


@pytest.mark.asyncio
async def test_recent_returns_latest_first():
    import asyncio
    mem = make_memory()
    await mem.remember("First note", category="note")
    await asyncio.sleep(0.001)
    await mem.remember("Second note", category="note")
    await asyncio.sleep(0.001)
    await mem.remember("Third note", category="note")

    records = await mem.recent(limit=2)
    assert len(records) == 2
    assert "Third" in records[0].content
    assert "Second" in records[1].content


@pytest.mark.asyncio
async def test_agent_isolation():
    """Each agent only sees its own memories."""
    mem_alice = LongTermMemory(agent_id="alice")
    mem_bob = LongTermMemory(agent_id="bob")

    # They share the same in-memory DB by default (separate :memory: connections)
    # but each is scoped by agent_id
    await mem_alice.remember("Alice's secret", category="note")
    await mem_bob.remember("Bob's secret", category="note")

    alice_results = await mem_alice.recall("secret")
    bob_results = await mem_bob.recall("secret")

    assert all("Alice" in r.content for r in alice_results)
    assert all("Bob" in r.content for r in bob_results)


@pytest.mark.asyncio
async def test_forget_removes_record():
    mem = make_memory()
    record_id = await mem.remember("To be forgotten", category="note")

    deleted = await mem.forget(record_id)
    assert deleted is True

    results = await mem.recall("forgotten")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_forget_nonexistent_returns_false():
    mem = make_memory()
    deleted = await mem.forget("nonexistent-id")
    assert deleted is False


@pytest.mark.asyncio
async def test_count():
    mem = make_memory()
    assert await mem.count() == 0

    await mem.remember("A", category="note")
    await mem.remember("B", category="fact")
    assert await mem.count() == 2


@pytest.mark.asyncio
async def test_categories_preserved():
    mem = make_memory()
    await mem.remember("Use black for formatting", category="preference")
    await mem.remember("Authentication uses JWT", category="decision")

    all_records = await mem.recent(limit=10)
    categories = {r.category for r in all_records}
    assert "preference" in categories
    assert "decision" in categories


@pytest.mark.asyncio
async def test_metadata_preserved():
    mem = make_memory()
    await mem.remember("Important fact", category="fact", session_id="abc", priority=1)

    records = await mem.recent(limit=1)
    assert records[0].metadata.get("session_id") == "abc"


@pytest.mark.asyncio
async def test_context_block_empty():
    mem = make_memory()
    block = await mem.context_block(limit=5)
    assert block == ""


@pytest.mark.asyncio
async def test_context_block_with_memories():
    mem = make_memory()
    await mem.remember("Always write tests first", category="preference")
    await mem.remember("Use async/await everywhere", category="preference")

    block = await mem.context_block(limit=5)
    assert "Long-term memory" in block
    assert "write tests" in block
    assert "async/await" in block


@pytest.mark.asyncio
async def test_max_records_trims_oldest():
    mem = LongTermMemory(agent_id="test", max_records=3)

    for i in range(5):
        await mem.remember(f"Record {i}", category="note")

    count = await mem.count()
    assert count == 3

    # The 3 most recent should survive
    records = await mem.recent(limit=10)
    contents = [r.content for r in records]
    assert "Record 4" in contents
    assert "Record 3" in contents
    assert "Record 2" in contents
    # Oldest should be gone
    assert "Record 0" not in contents
    assert "Record 1" not in contents


@pytest.mark.asyncio
async def test_persistent_path(tmp_path):
    """Memories written to a file persist across LongTermMemory instances."""
    agent_id = "persistent-agent"
    path = str(tmp_path)

    mem1 = LongTermMemory(agent_id=agent_id, path=path)
    await mem1.remember("Persisted fact", category="fact")
    mem1.close()

    mem2 = LongTermMemory(agent_id=agent_id, path=path)
    records = await mem2.recall("Persisted")
    assert len(records) == 1
    assert "Persisted fact" in records[0].content
    mem2.close()


# ---------------------------------------------------------------------------
# Agent memory tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remember_tool():
    mem = make_memory()
    tool = RememberTool()
    inp = RememberTool.input_schema(content="Use mypy for type checking", category="preference")
    ctx = make_ctx(memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "preference" in result.content

    records = await mem.recall("mypy type checking")
    assert len(records) == 1


@pytest.mark.asyncio
async def test_recall_tool():
    mem = make_memory()
    await mem.remember("OAuth2 with PKCE flow", category="decision")

    tool = RecallTool()
    inp = RecallTool.input_schema(query="OAuth2", limit=5)
    ctx = make_ctx(memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "OAuth2" in result.content or "PKCE" in result.content


@pytest.mark.asyncio
async def test_recall_tool_no_results():
    mem = make_memory()
    tool = RecallTool()
    inp = RecallTool.input_schema(query="nonexistent topic xyz")
    ctx = make_ctx(memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "No memories" in result.content


@pytest.mark.asyncio
async def test_forget_tool():
    mem = make_memory()
    record_id = await mem.remember("Outdated info", category="note")

    tool = ForgetTool()
    inp = ForgetTool.input_schema(record_id=record_id)
    ctx = make_ctx(memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert await mem.count() == 0


@pytest.mark.asyncio
async def test_recent_memories_tool():
    mem = make_memory()
    await mem.remember("Entry 1", category="note")
    await mem.remember("Entry 2", category="fact")

    tool = RecentMemoriesTool()
    inp = RecentMemoriesTool.input_schema(limit=5)
    ctx = make_ctx(memory=mem)

    result = await tool.call(inp, ctx)
    assert not result.is_error
    assert "Entry 1" in result.content
    assert "Entry 2" in result.content


@pytest.mark.asyncio
async def test_tools_error_without_memory():
    """Tools return error when agent has no long-term memory configured."""
    ctx = make_ctx()  # no memory

    for tool_cls, input_cls, kwargs in [
        (RememberTool, RememberTool.input_schema, {"content": "x"}),
        (RecallTool, RecallTool.input_schema, {"query": "x"}),
        (RecentMemoriesTool, RecentMemoriesTool.input_schema, {}),
    ]:
        tool = tool_cls()
        inp = input_cls(**kwargs)
        result = await tool.call(inp, ctx)
        assert result.is_error, f"{tool.name} should return error without memory"
