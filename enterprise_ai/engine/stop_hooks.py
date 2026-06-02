from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from enterprise_ai.schema import Message

log = logging.getLogger(__name__)


@dataclass
class StopHookInput:
    """Snapshot passed to stop hooks after the loop decides to stop."""

    session_id: str
    turn_number: int
    # "no_tool_calls" | "terminate" | "max_turns"
    stop_reason: str
    # Read-only snapshot of current conversation
    messages: list[Message]
    tool_calls_count: int


@dataclass
class StopHookResult:
    # If True, the loop runs one more turn
    continue_loop: bool = False
    # Messages appended to session memory before the next turn
    inject_messages: list[Message] = field(default_factory=list)
    # Hard failure — stops the loop, session ends as error
    error: Exception | None = None


StopHookFn = Callable[[StopHookInput], Awaitable[StopHookResult]]


@dataclass
class StopHookEntry:
    name: str
    handler: StopHookFn
    priority: int = 0


class StopHookRunner:
    """
    Runs stop hooks after each potential session-end point.

    A hook can:
    - Force one more loop turn (continue_loop=True)
    - Inject messages into the conversation before that turn
    - Signal a hard failure (error=...)
    - Do nothing (default — session ends normally)

    mode="all"   → all hooks run; continue if any returns continue_loop=True
    mode="first" → stops at the first hook that returns continue_loop=True

    Example use-cases:
        - "If the agent produced no file, retry once with a reminder"
        - "Quality gate: if test score < 80%, inject feedback and continue"
        - Post-execution compliance checks
    """

    def __init__(
        self,
        hooks: list[StopHookEntry],
        timeout_s: float = 30.0,
        mode: str = "all",
    ) -> None:
        self._hooks = sorted(hooks, key=lambda h: h.priority)
        self._timeout_s = timeout_s
        self._mode = mode

    async def run(self, input: StopHookInput) -> StopHookResult:
        accumulated_messages: list[Message] = []
        should_continue = False

        for entry in self._hooks:
            try:
                result = await asyncio.wait_for(
                    entry.handler(input), timeout=self._timeout_s
                )
            except asyncio.TimeoutError:
                log.warning("Stop hook %r timed out after %.1fs", entry.name, self._timeout_s)
                continue
            except Exception:
                log.exception("Stop hook %r raised an exception", entry.name)
                continue

            if result.error is not None:
                return StopHookResult(error=result.error)

            accumulated_messages.extend(result.inject_messages)

            if result.continue_loop:
                should_continue = True
                if self._mode == "first":
                    return StopHookResult(
                        continue_loop=True,
                        inject_messages=accumulated_messages,
                    )

        return StopHookResult(
            continue_loop=should_continue,
            inject_messages=accumulated_messages,
        )
