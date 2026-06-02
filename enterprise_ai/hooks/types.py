from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from enterprise_ai.hooks.events import HookEvent


@dataclass
class HookPayload:
    event: HookEvent
    session_id: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class HookResult:
    # If True on pre_tool_use → tool execution is blocked
    stop: bool = False
    # On pre_tool_use: return {"tool_input": {...}} to replace the tool's input
    modified_data: dict[str, Any] | None = None
    # Human-readable reason (shown in error results when stop=True)
    message: str = ""


# Handler type: async function that receives a payload and returns a result
HookHandler = Callable[[HookPayload], Awaitable[HookResult | None]]
