from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class MemoryRecord:
    id: str
    content: str
    category: str        # "note", "decision", "fact", "preference", "context"
    agent_id: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        ts = self.created_at[:19]
        return f"[{self.category}|{ts}] {self.content}"


class LongTermMemory:
    """
    Cross-session persistent memory for an individual agent.

    Unlike team shared memory (FTSMemory / VectorMemory), this is:
    - Private: only the owning agent reads/writes it
    - Persistent: survives process restarts
    - Agent-scoped: each agent_id has its own namespace

    Storage: SQLite FTS5 — zero extra dependencies.
    Location: configurable path or ":memory:" for tests.

    Usage:
        # Create with a file path (persists across sessions)
        mem = LongTermMemory(agent_id="my-agent", path="~/.enterprise-ai/memory/")

        # Or in-memory (tests / ephemeral agents)
        mem = LongTermMemory(agent_id="my-agent")

        # Write
        await mem.remember("Always use pytest for testing in this project", category="preference")

        # Search
        records = await mem.recall("testing framework")

        # Recent
        records = await mem.recent(limit=5)

    Agent integration:
        agent = Agent(
            ...,
            long_term_memory=LongTermMemory(agent_id="my-dev-agent", path="~/.enterprise-ai/memory/"),
        )
    """

    def __init__(
        self,
        agent_id: str = "",
        path: str | None = None,
        max_records: int = 10_000,
    ) -> None:
        self.agent_id = agent_id
        self._max_records = max_records
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None

        if path is None:
            self._db_path = ":memory:"
        else:
            db_dir = Path(path).expanduser()
            db_dir.mkdir(parents=True, exist_ok=True)
            safe_id = agent_id.replace("/", "_").replace("\\", "_") or "default"
            self._db_path = str(db_dir / f"{safe_id}.db")

        self._init()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init(self) -> None:
        conn = self._get_conn()
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories USING fts5(
                record_id,
                content,
                category,
                agent_id,
                created_at,
                metadata_json
            )
        """)
        conn.commit()

    async def remember(
        self,
        content: str,
        category: str = "note",
        **metadata: Any,
    ) -> str:
        """Write a memory record. Returns the record id."""
        record_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata)

        async with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, content, category, self.agent_id, created_at, metadata_json),
            )
            conn.commit()
            await self._trim_if_needed(conn)

        return record_id

    async def recall(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Full-text search over this agent's memories."""
        async with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT record_id, content, category, agent_id, created_at, metadata_json,
                           bm25(memories) as rank
                    FROM memories
                    WHERE memories MATCH ? AND agent_id = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, self.agent_id, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                # FTS5 syntax error — fall back to LIKE
                like = f"%{query}%"
                rows = conn.execute(
                    """
                    SELECT record_id, content, category, agent_id, created_at, metadata_json, 0 as rank
                    FROM memories
                    WHERE content LIKE ? AND agent_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (like, self.agent_id, limit),
                ).fetchall()

        return [self._row_to_record(r) for r in rows]

    async def recent(self, limit: int = 10) -> list[MemoryRecord]:
        """Return the most recent memory records for this agent."""
        async with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """
                SELECT record_id, content, category, agent_id, created_at, metadata_json, 0 as rank
                FROM memories
                WHERE agent_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (self.agent_id, limit),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    async def forget(self, record_id: str) -> bool:
        """Delete a specific memory record. Returns True if deleted."""
        async with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "DELETE FROM memories WHERE record_id = ? AND agent_id = ?",
                (record_id, self.agent_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    async def count(self) -> int:
        async with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id = ?",
                (self.agent_id,),
            ).fetchone()
            return row[0] if row else 0

    async def context_block(self, limit: int = 5) -> str:
        """
        Returns a formatted block of recent memories to inject into system context.
        Called automatically by Agent at session start if long_term_memory is set.
        """
        records = await self.recent(limit=limit)
        if not records:
            return ""
        lines = ["## Long-term memory (your persistent notes)"]
        for r in records:
            lines.append(f"- [{r.category}] {r.content}")
        return "\n".join(lines)

    async def _trim_if_needed(self, conn: sqlite3.Connection) -> None:
        """Remove oldest records if we exceed max_records."""
        row = conn.execute(
            "SELECT COUNT(*) FROM memories WHERE agent_id = ?", (self.agent_id,)
        ).fetchone()
        count = row[0] if row else 0
        if count > self._max_records:
            excess = count - self._max_records
            conn.execute(
                """
                DELETE FROM memories WHERE record_id IN (
                    SELECT record_id FROM memories WHERE agent_id = ?
                    ORDER BY created_at ASC LIMIT ?
                )
                """,
                (self.agent_id, excess),
            )
            conn.commit()

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return MemoryRecord(
            id=row["record_id"],
            content=row["content"],
            category=row["category"],
            agent_id=row["agent_id"],
            created_at=row["created_at"],
            metadata=meta,
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
