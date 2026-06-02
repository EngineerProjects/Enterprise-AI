from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    idle = "idle"
    running = "running"
    tool_calling = "tool_calling"
    done = "done"
    error = "error"


class CacheStats(BaseModel):
    """Prompt-caching token counts accumulated over a full agent session."""

    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_cached_tokens(self) -> int:
        return self.cache_read_tokens + self.cache_write_tokens

    @property
    def estimated_savings_pct(self) -> float:
        """
        Estimated cost reduction from cache reads.
        Anthropic charges ~10 % of normal input price for cache-read tokens,
        so each cache-read token saves ~90 % vs a regular input token.
        """
        total = self.total_cached_tokens
        if total == 0:
            return 0.0
        savings = self.cache_read_tokens * 0.9
        return round(savings / total * 100, 1)

    def add(self, read: int, write: int) -> None:
        self.cache_read_tokens += read
        self.cache_write_tokens += write


class SessionResult(BaseModel):
    session_id: str
    output: str
    state: SessionState = SessionState.done
    tool_calls_count: int = 0
    parent_session_id: str = ""
    cache_stats: CacheStats = Field(default_factory=CacheStats)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.idle
    agent_id: str = ""
    parent_session_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
