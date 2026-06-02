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


class SessionResult(BaseModel):
    session_id: str
    output: str
    state: SessionState = SessionState.done
    tool_calls_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: SessionState = SessionState.idle
    agent_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
