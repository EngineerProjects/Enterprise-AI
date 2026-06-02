from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MemoryEntry:
    id: str
    content: str
    source: str          # "mail", "task", "note"
    agent_id: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        ts = self.created_at[:19]
        return f"[{self.source}|{self.agent_id}|{ts}]\n{self.content}"


class TeamMemory(ABC):
    """Base contract for team shared memory backends."""

    @abstractmethod
    async def write(
        self,
        content: str,
        source: str,
        agent_id: str,
        **metadata: Any,
    ) -> str: ...  # returns entry id

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[MemoryEntry]: ...

    @abstractmethod
    async def recent(self, limit: int = 10) -> list[MemoryEntry]: ...


class FTSMemory(TeamMemory):
    """
    Vectorless team shared memory backed by SQLite FTS5.

    - Zero external dependencies (sqlite3 is stdlib)
    - Offline-first — no API calls needed
    - Full-text search with BM25 ranking
    - Works in-memory (":memory:") or persisted (file path)

    All team communication is auto-indexed here:
    - Every mail sent via Mailbox
    - Every task completed or failed on TaskBoard
    - Agent notes via WriteMemoryTool

    Agents query via SearchMemoryTool.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._lock = asyncio.Lock()
        self._init()

    def _init(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory USING fts5(
                entry_id,
                content,
                source,
                agent_id,
                created_at,
                metadata_json
            )
        """)
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    async def write(self, content: str, source: str, agent_id: str, **metadata: Any) -> str:
        entry_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata)

        async with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO memory VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, content, source, agent_id, created_at, metadata_json),
            )
            conn.commit()

        return entry_id

    async def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        async with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT entry_id, content, source, agent_id, created_at, metadata_json,
                           bm25(memory) as rank
                    FROM memory
                    WHERE memory MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                # FTS5 syntax error — fall back to simple LIKE search
                like = f"%{query}%"
                rows = conn.execute(
                    """
                    SELECT entry_id, content, source, agent_id, created_at, metadata_json,
                           0 as rank
                    FROM memory
                    WHERE content LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (like, limit),
                ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    async def recent(self, limit: int = 10) -> list[MemoryEntry]:
        async with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """
                SELECT entry_id, content, source, agent_id, created_at, metadata_json, 0 as rank
                FROM memory
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return MemoryEntry(
            id=row["entry_id"],
            content=row["content"],
            source=row["source"],
            agent_id=row["agent_id"],
            created_at=row["created_at"],
            metadata=meta,
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
