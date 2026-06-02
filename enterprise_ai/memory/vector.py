from __future__ import annotations

import asyncio
import json
import math
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from enterprise_ai.memory.team import MemoryEntry, TeamMemory

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure Python cosine similarity — no numpy needed."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Embedding Providers
# ---------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    """Converts text into dense vectors."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    @abstractmethod
    def dimension(self) -> int: ...


class OpenAIEmbedding(EmbeddingProvider):
    """
    Embeddings via OpenAI API (or any compatible endpoint).
    Uses the openai SDK already in core deps — zero extra dependencies.

    Supports: text-embedding-3-small (1536d), text-embedding-3-large (3072d),
              text-embedding-ada-002 (1536d)
    """

    _DIMS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dim = self._DIMS.get(model, 1536)

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]


class OllamaEmbedding(EmbeddingProvider):
    """
    Local embeddings via Ollama (openai-compatible endpoint).
    No API key, runs fully offline.

    Popular models: nomic-embed-text (768d), mxbai-embed-large (1024d),
                    all-minilm (384d)
    """

    _DIMS = {
        "nomic-embed-text": 768,
        "mxbai-embed-large": 1024,
        "all-minilm": 384,
        "snowflake-arctic-embed": 1024,
    }

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434/v1",
    ) -> None:
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key="ollama", base_url=base_url)
        self._model = model
        self._dim = self._DIMS.get(model, 768)

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]


class CustomEmbedding(EmbeddingProvider):
    """
    Bring your own embedding function.

        def my_embed(texts: list[str]) -> list[list[float]]:
            return model.encode(texts).tolist()

        embedding = CustomEmbedding(fn=my_embed, dimension=384)
    """

    def __init__(
        self,
        fn: Callable[[list[str]], list[list[float]]],
        dimension: int,
    ) -> None:
        self._fn = fn
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fn, texts)


# ---------------------------------------------------------------------------
# Vector Backends
# ---------------------------------------------------------------------------

@dataclass
class _VectorEntry:
    id: str
    vector: list[float]
    content: str
    source: str
    agent_id: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_memory_entry(self) -> MemoryEntry:
        return MemoryEntry(
            id=self.id,
            content=self.content,
            source=self.source,
            agent_id=self.agent_id,
            created_at=self.created_at,
            metadata=self.metadata,
        )


class VectorBackend(ABC):
    @abstractmethod
    async def upsert(self, entry: _VectorEntry) -> None: ...

    @abstractmethod
    async def search(self, query_vector: list[float], limit: int) -> list[MemoryEntry]: ...

    @abstractmethod
    async def recent(self, limit: int) -> list[MemoryEntry]: ...


class InMemoryBackend(VectorBackend):
    """
    Pure Python in-memory vector store with cosine similarity.
    Zero dependencies. Best for development and small teams (< 10k entries).
    Data is lost on process exit — use SQLiteBackend for persistence.
    """

    def __init__(self) -> None:
        self._entries: list[_VectorEntry] = []
        self._lock = asyncio.Lock()

    async def upsert(self, entry: _VectorEntry) -> None:
        async with self._lock:
            self._entries.append(entry)

    async def search(self, query_vector: list[float], limit: int) -> list[MemoryEntry]:
        async with self._lock:
            entries = list(self._entries)
        scored = [
            (e, _cosine_similarity(query_vector, e.vector))
            for e in entries
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [e.to_memory_entry() for e, _ in scored[:limit]]

    async def recent(self, limit: int) -> list[MemoryEntry]:
        async with self._lock:
            entries = list(self._entries)
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return [e.to_memory_entry() for e in entries[:limit]]


class SQLiteVectorBackend(VectorBackend):
    """
    Persistent SQLite vector store with cosine similarity.
    Vectors stored as JSON arrays. Zero dependencies beyond sqlite3 (stdlib).
    Suitable for teams up to ~50k entries — beyond that, use qdrant.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._init()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vector_entries (
                id TEXT PRIMARY KEY,
                vector_json TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                agent_id TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                metadata_json TEXT DEFAULT '{}'
            )
        """)
        conn.commit()

    async def upsert(self, entry: _VectorEntry) -> None:
        async with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO vector_entries VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.id,
                    json.dumps(entry.vector),
                    entry.content,
                    entry.source,
                    entry.agent_id,
                    entry.created_at,
                    json.dumps(entry.metadata),
                ),
            )
            conn.commit()

    async def search(self, query_vector: list[float], limit: int) -> list[MemoryEntry]:
        async with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM vector_entries ORDER BY created_at DESC LIMIT 5000"
            ).fetchall()

        scored: list[tuple[sqlite3.Row, float]] = []
        for row in rows:
            try:
                vec = json.loads(row["vector_json"])
                score = _cosine_similarity(query_vector, vec)
                scored.append((row, score))
            except (json.JSONDecodeError, TypeError):
                continue

        scored.sort(key=lambda x: x[1], reverse=True)
        return [self._row_to_entry(row) for row, _ in scored[:limit]]

    async def recent(self, limit: int) -> list[MemoryEntry]:
        async with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM vector_entries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            source=row["source"],
            agent_id=row["agent_id"],
            created_at=row["created_at"],
            metadata=meta,
        )


class QdrantBackend(VectorBackend):
    """
    Production vector backend using Qdrant.
    Requires: pip install 'enterprise-ai[qdrant]'

    Supports local (in-memory or on-disk) and remote Qdrant instances.
    Best for large teams with millions of entries and high query throughput.
    """

    def __init__(
        self,
        collection: str = "enterprise_ai_team_memory",
        dimension: int = 1536,
        url: str | None = None,
        api_key: str | None = None,
        path: str | None = None,
    ) -> None:
        self._collection = collection
        self._dimension = dimension
        self._url = url
        self._api_key = api_key
        self._path = path
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from qdrant_client import AsyncQdrantClient
            except ImportError:
                raise ImportError("qdrant-client required: pip install 'enterprise-ai[qdrant]'")

            if self._url:
                self._client = AsyncQdrantClient(url=self._url, api_key=self._api_key)
            elif self._path:
                self._client = AsyncQdrantClient(path=self._path)
            else:
                self._client = AsyncQdrantClient(":memory:")

        return self._client

    async def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        client = self._get_client()
        collections = await client.get_collections()
        names = [c.name for c in collections.collections]
        if self._collection not in names:
            await client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dimension, distance=Distance.COSINE),
            )

    async def upsert(self, entry: _VectorEntry) -> None:
        from qdrant_client.models import PointStruct
        await self._ensure_collection()
        client = self._get_client()
        point = PointStruct(
            id=entry.id,
            vector=entry.vector,
            payload={
                "content": entry.content,
                "source": entry.source,
                "agent_id": entry.agent_id,
                "created_at": entry.created_at,
                **entry.metadata,
            },
        )
        await client.upsert(collection_name=self._collection, points=[point])

    async def search(self, query_vector: list[float], limit: int) -> list[MemoryEntry]:
        await self._ensure_collection()
        client = self._get_client()
        results = await client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
        )
        return [
            MemoryEntry(
                id=str(r.id),
                content=r.payload.get("content", ""),
                source=r.payload.get("source", ""),
                agent_id=r.payload.get("agent_id", ""),
                created_at=r.payload.get("created_at", ""),
                metadata={k: v for k, v in r.payload.items() if k not in ("content", "source", "agent_id", "created_at")},
            )
            for r in results
        ]

    async def recent(self, limit: int) -> list[MemoryEntry]:
        await self._ensure_collection()
        client = self._get_client()
        results, _ = await client.scroll(
            collection_name=self._collection,
            limit=limit,
            with_payload=True,
            order_by="created_at",
        )
        return [
            MemoryEntry(
                id=str(r.id),
                content=r.payload.get("content", ""),
                source=r.payload.get("source", ""),
                agent_id=r.payload.get("agent_id", ""),
                created_at=r.payload.get("created_at", ""),
                metadata={},
            )
            for r in results
        ]


class ChromaBackend(VectorBackend):
    """
    Local vector backend using ChromaDB.
    Requires: pip install 'enterprise-ai[chroma]'

    Persistent local vector DB with automatic embedding if configured.
    Good alternative to qdrant when you need local persistence without a server.
    """

    def __init__(
        self,
        collection: str = "enterprise_ai_team_memory",
        path: str | None = None,
    ) -> None:
        self._collection_name = collection
        self._path = path
        self._client: Any = None
        self._collection: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import chromadb
            except ImportError:
                raise ImportError("chromadb required: pip install 'enterprise-ai[chroma]'")
            if self._path:
                self._client = chromadb.PersistentClient(path=self._path)
            else:
                self._client = chromadb.EphemeralClient()
        return self._client

    def _get_collection(self) -> Any:
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def upsert(self, entry: _VectorEntry) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self._get_collection().upsert(
                ids=[entry.id],
                embeddings=[entry.vector],
                documents=[entry.content],
                metadatas=[{
                    "source": entry.source,
                    "agent_id": entry.agent_id,
                    "created_at": entry.created_at,
                    **{k: str(v) for k, v in entry.metadata.items()},
                }],
            ),
        )

    async def search(self, query_vector: list[float], limit: int) -> list[MemoryEntry]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self._get_collection().query(
                query_embeddings=[query_vector],
                n_results=limit,
                include=["documents", "metadatas"],
            ),
        )
        entries = []
        for doc, meta, entry_id in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["ids"][0],
        ):
            entries.append(MemoryEntry(
                id=entry_id,
                content=doc,
                source=meta.get("source", ""),
                agent_id=meta.get("agent_id", ""),
                created_at=meta.get("created_at", ""),
                metadata={k: v for k, v in meta.items() if k not in ("source", "agent_id", "created_at")},
            ))
        return entries

    async def recent(self, limit: int) -> list[MemoryEntry]:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: self._get_collection().get(
                limit=limit,
                include=["documents", "metadatas"],
            ),
        )
        entries = []
        for doc, meta, entry_id in zip(
            results["documents"],
            results["metadatas"],
            results["ids"],
        ):
            entries.append(MemoryEntry(
                id=entry_id,
                content=doc,
                source=meta.get("source", ""),
                agent_id=meta.get("agent_id", ""),
                created_at=meta.get("created_at", ""),
                metadata={},
            ))
        entries.sort(key=lambda e: e.created_at, reverse=True)
        return entries[:limit]


# ---------------------------------------------------------------------------
# VectorMemory — the public class
# ---------------------------------------------------------------------------

class VectorMemory(TeamMemory):
    """
    Semantic team shared memory using dense vector embeddings.

    Finds relevant context even without keyword match — ideal for fuzzy queries
    and large memory corpora. Complements FTSMemory (keyword search).

    Backends (select via backend= parameter):
        "memory"   — in-memory, zero deps, dev/testing, data lost on exit
        "sqlite"   — SQLite persistence, zero deps, small-medium teams
        "qdrant"   — production, external Qdrant service (pip install enterprise-ai[qdrant])
        "chroma"   — local persistence, no server (pip install enterprise-ai[chroma])

    Embedding providers (select via embedding= parameter):
        "openai"   — text-embedding-3-small (default), API-based
        "ollama"   — nomic-embed-text, fully local via Ollama
        or pass any EmbeddingProvider instance directly

    Usage:
        # Dev — in-memory, OpenAI embeddings
        mem = VectorMemory()

        # Persistent SQLite, Ollama local embeddings
        mem = VectorMemory(backend="sqlite", db_path="team.db", embedding="ollama")

        # Production — Qdrant
        mem = VectorMemory(backend="qdrant", url="http://localhost:6333")

        # Custom embedding function
        mem = VectorMemory(embedding=CustomEmbedding(fn=my_model.encode, dimension=384))
    """

    def __init__(
        self,
        backend: str | VectorBackend = "memory",
        embedding: str | EmbeddingProvider = "openai",
        embedding_model: str | None = None,
        # Backend-specific kwargs
        db_path: str = ":memory:",
        url: str | None = None,
        api_key: str | None = None,
        path: str | None = None,
        collection: str = "enterprise_ai_team_memory",
    ) -> None:
        # Embedding provider
        if isinstance(embedding, EmbeddingProvider):
            self._embedding = embedding
        elif embedding == "openai":
            self._embedding = OpenAIEmbedding(model=embedding_model or "text-embedding-3-small")
        elif embedding == "ollama":
            self._embedding = OllamaEmbedding(model=embedding_model or "nomic-embed-text")
        else:
            raise ValueError(f"Unknown embedding provider: {embedding!r}. Use 'openai', 'ollama', or an EmbeddingProvider instance.")

        # Vector backend
        if isinstance(backend, VectorBackend):
            self._backend = backend
        elif backend == "memory":
            self._backend = InMemoryBackend()
        elif backend == "sqlite":
            self._backend = SQLiteVectorBackend(db_path=db_path)
        elif backend == "qdrant":
            self._backend = QdrantBackend(
                collection=collection,
                dimension=self._embedding.dimension,
                url=url,
                api_key=api_key,
                path=path,
            )
        elif backend == "chroma":
            self._backend = ChromaBackend(collection=collection, path=path)
        else:
            raise ValueError(f"Unknown backend: {backend!r}. Use 'memory', 'sqlite', 'qdrant', or 'chroma'.")

    async def write(self, content: str, source: str, agent_id: str, **metadata: Any) -> str:
        vectors = await self._embedding.embed([content])
        entry = _VectorEntry(
            id=str(uuid.uuid4()),
            vector=vectors[0],
            content=content,
            source=source,
            agent_id=agent_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata,
        )
        await self._backend.upsert(entry)
        return entry.id

    async def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        vectors = await self._embedding.embed([query])
        return await self._backend.search(vectors[0], limit=limit)

    async def recent(self, limit: int = 10) -> list[MemoryEntry]:
        return await self._backend.recent(limit=limit)

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        return self._embedding

    @property
    def backend(self) -> VectorBackend:
        return self._backend
