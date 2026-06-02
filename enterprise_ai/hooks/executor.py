from __future__ import annotations

import asyncio
import logging
from typing import Any

from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.hooks.registry import HookRegistry
from enterprise_ai.hooks.types import HookPayload, HookResult

log = logging.getLogger(__name__)


class HookExecutor:
    """
    Fires hooks and collects results.

    - Handlers run in priority order (lowest first).
    - Each handler has an individual timeout; a slow handler is skipped,
      not propagated as an error.
    - Exceptions inside handlers are logged and swallowed (except on_error
      handlers which must not raise).
    - pre_tool_use is the only event where stop=True or modified_data
      actually affects execution. All other events are fire-and-forget.
    """

    def __init__(
        self,
        registry: HookRegistry,
        timeout_s: float = 30.0,
    ) -> None:
        self._registry = registry
        self._timeout_s = timeout_s

    async def fire(
        self,
        event: HookEvent,
        session_id: str,
        data: dict[str, Any],
    ) -> HookResult:
        """
        Fire all handlers for the event.
        Returns the first result with stop=True if any, otherwise HookResult().
        """
        handlers = self._registry.handlers_for(event)
        if not handlers:
            return HookResult()

        payload = HookPayload(event=event, session_id=session_id, data=data)
        accumulated = HookResult()

        for handler in handlers:
            try:
                raw = await asyncio.wait_for(handler(payload), timeout=self._timeout_s)
            except asyncio.TimeoutError:
                log.warning("Hook %s timed out after %.1fs", handler.__name__, self._timeout_s)
                continue
            except Exception:
                log.exception("Hook %s raised an exception", getattr(handler, "__name__", repr(handler)))
                continue

            result = raw or HookResult()

            # Accumulate modified_data (last writer wins)
            if result.modified_data is not None:
                accumulated.modified_data = result.modified_data

            # Any stop=True short-circuits the rest
            if result.stop:
                return HookResult(
                    stop=True,
                    modified_data=accumulated.modified_data,
                    message=result.message,
                )

        return accumulated

    async def fire_pre_tool(
        self,
        session_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> HookResult:
        """Fire pre_tool_use. Can block (stop=True) or modify input."""
        return await self.fire(
            HookEvent.pre_tool_use,
            session_id,
            {"tool_name": tool_name, "tool_input": tool_input},
        )

    async def fire_post_tool(
        self,
        session_id: str,
        tool_name: str,
        result_content: str,
        is_error: bool,
    ) -> None:
        """Fire post_tool_use or post_tool_use_fail (notification only)."""
        event = HookEvent.post_tool_use_fail if is_error else HookEvent.post_tool_use
        await self.fire(
            event,
            session_id,
            {"tool_name": tool_name, "result": result_content, "is_error": is_error},
        )
