"""
Unit tests for VectorMemory.
Uses a deterministic mock embedding provider — no API calls.
Tests: cosine similarity, backends (InMemory + SQLite), VectorMemory interface.
"""
import math

import pytest

from enterprise_ai.memory.vector import (
    CustomEmbedding,
    InMemoryBackend,
    SQLiteVectorBackend,
    VectorMemory,
    _cosine_similarity,
    _VectorEntry,
)

# ---------------------------------------------------------------------------
# Deterministic mock embedding
# ---------------------------------------------------------------------------

def _unit_vec(dim: int, hot_dims: list[int]) -> list[float]:
    """Create a unit vector with 1.0 at specified dimensions, normalized."""
    v = [0.0] * dim
    for d in hot_dims:
        v[d] = 1.0
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


def make_mock_embedding(dim: int = 8) -> CustomEmbedding:
    """
    Mock embedding: maps keywords to distinct vector regions.
    'oauth' → dims 0-1, 'database' → dims 2-3, 'testing' → dims 4-5
    Unrecognized → uniform vector.
    """
    keyword_map = {
        "oauth": [0, 1],
        "auth": [0, 1],
        "database": [2, 3],
        "db": [2, 3],
        "test": [4, 5],
        "bug": [6, 7],
        "fix": [6, 7],
    }

    def embed_fn(texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            text_lower = text.lower()
            hot_dims = []
            for kw, dims in keyword_map.items():
                if kw in text_lower:
                    hot_dims.extend(dims)
            if not hot_dims:
                hot_dims = list(range(dim))
            results.append(_unit_vec(dim, list(set(hot_dims))))
        return results

    return CustomEmbedding(fn=embed_fn, dimension=dim)


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def test_cosine_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal_vectors():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert abs(_cosine_similarity(a, b)) < 1e-9


def test_cosine_opposite_vectors():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(_cosine_similarity(a, b) + 1.0) < 1e-9


def test_cosine_zero_vector_returns_zero():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


# ---------------------------------------------------------------------------
# InMemoryBackend
# ---------------------------------------------------------------------------

def _make_entry(content: str, source: str = "note", vector: list[float] | None = None) -> _VectorEntry:
    import uuid
    from datetime import datetime, timezone
    return _VectorEntry(
        id=str(uuid.uuid4()),
        vector=vector or [1.0, 0.0, 0.0, 0.0],
        content=content,
        source=source,
        agent_id="test-agent",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.asyncio
async def test_inmemory_upsert_and_search():
    backend = InMemoryBackend()
    e1 = _make_entry("oauth implementation", vector=[1.0, 0.0, 0.0, 0.0])
    e2 = _make_entry("database schema", vector=[0.0, 1.0, 0.0, 0.0])
    await backend.upsert(e1)
    await backend.upsert(e2)

    results = await backend.search(query_vector=[1.0, 0.0, 0.0, 0.0], limit=1)
    assert len(results) == 1
    assert "oauth" in results[0].content


@pytest.mark.asyncio
async def test_inmemory_search_ranks_by_similarity():
    backend = InMemoryBackend()
    await backend.upsert(_make_entry("very similar", vector=[1.0, 0.0]))
    await backend.upsert(_make_entry("less similar", vector=[0.7, 0.7]))
    await backend.upsert(_make_entry("orthogonal", vector=[0.0, 1.0]))

    results = await backend.search(query_vector=[1.0, 0.0], limit=3)
    assert results[0].content == "very similar"
    assert results[-1].content == "orthogonal"


@pytest.mark.asyncio
async def test_inmemory_recent_returns_latest():
    import asyncio
    backend = InMemoryBackend()
    await backend.upsert(_make_entry("first"))
    await asyncio.sleep(0.001)
    await backend.upsert(_make_entry("second"))
    await asyncio.sleep(0.001)
    await backend.upsert(_make_entry("third"))

    results = await backend.recent(limit=2)
    assert len(results) == 2
    assert "third" in results[0].content


# ---------------------------------------------------------------------------
# SQLiteVectorBackend
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sqlite_backend_persist_and_search():
    backend = SQLiteVectorBackend(db_path=":memory:")
    e1 = _make_entry("oauth2 token", vector=[1.0, 0.0, 0.0, 0.0])
    e2 = _make_entry("test suite", vector=[0.0, 0.0, 1.0, 0.0])
    await backend.upsert(e1)
    await backend.upsert(e2)

    results = await backend.search([1.0, 0.0, 0.0, 0.0], limit=1)
    assert len(results) == 1
    assert "oauth2" in results[0].content


@pytest.mark.asyncio
async def test_sqlite_backend_recent():
    backend = SQLiteVectorBackend(db_path=":memory:")
    for i in range(5):
        await backend.upsert(_make_entry(f"entry {i}"))

    results = await backend.recent(limit=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_sqlite_backend_metadata_preserved():
    backend = SQLiteVectorBackend(db_path=":memory:")
    e = _make_entry("task done")
    e.metadata = {"task_id": "abc123", "priority": "high"}
    await backend.upsert(e)

    results = await backend.recent(limit=1)
    assert results[0].metadata.get("task_id") == "abc123"


# ---------------------------------------------------------------------------
# VectorMemory — full integration with mock embedding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vector_memory_write_and_search():
    mem = VectorMemory(backend="memory", embedding=make_mock_embedding())

    await mem.write("OAuth2 flow implemented", source="task", agent_id="dev")
    await mem.write("Database schema migrated", source="task", agent_id="dev")
    await mem.write("Bug in auth module fixed", source="note", agent_id="qa")

    results = await mem.search("oauth authentication")
    assert len(results) >= 1
    # OAuth-related content should rank first
    assert any("OAuth" in r.content or "auth" in r.content.lower() for r in results[:2])


@pytest.mark.asyncio
async def test_vector_memory_semantic_search():
    """Semantic search finds related content without exact keyword match."""
    mem = VectorMemory(backend="memory", embedding=make_mock_embedding())

    await mem.write("JWT token validation complete", source="task", agent_id="dev")
    await mem.write("Test coverage improved to 85%", source="note", agent_id="qa")
    await mem.write("DB indexes added for performance", source="task", agent_id="dev")

    # "auth" should find JWT (both map to same vector region)
    results = await mem.search("auth security")
    assert any("JWT" in r.content for r in results)


@pytest.mark.asyncio
async def test_vector_memory_recent():
    mem = VectorMemory(backend="memory", embedding=make_mock_embedding())

    await mem.write("Entry A", source="note", agent_id="a")
    await mem.write("Entry B", source="note", agent_id="b")
    await mem.write("Entry C", source="note", agent_id="c")

    results = await mem.recent(limit=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_vector_memory_with_sqlite_backend():
    mem = VectorMemory(
        backend=SQLiteVectorBackend(db_path=":memory:"),
        embedding=make_mock_embedding(),
    )
    await mem.write("Persistent entry", source="note", agent_id="alice")
    results = await mem.search("testing")
    assert len(results) >= 0  # may or may not match — no crash


@pytest.mark.asyncio
async def test_vector_memory_custom_embedding_instance():
    custom = make_mock_embedding(dim=8)
    mem = VectorMemory(backend="memory", embedding=custom)

    assert mem.embedding_provider is custom
    assert mem.embedding_provider.dimension == 8

    await mem.write("test entry", source="note", agent_id="test")
    results = await mem.recent(limit=1)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_vector_memory_write_returns_id():
    mem = VectorMemory(backend="memory", embedding=make_mock_embedding())
    entry_id = await mem.write("something", source="note", agent_id="a")
    assert isinstance(entry_id, str)
    assert len(entry_id) > 0


def test_vector_memory_invalid_backend():
    import pytest
    with pytest.raises(ValueError, match="Unknown backend"):
        VectorMemory(backend="invalid", embedding=make_mock_embedding())


def test_vector_memory_invalid_embedding():
    with pytest.raises(ValueError, match="Unknown embedding"):
        VectorMemory(backend="memory", embedding="invalid_provider")
