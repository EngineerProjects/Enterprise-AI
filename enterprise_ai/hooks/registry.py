from __future__ import annotations

from collections import defaultdict

from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.hooks.types import HookHandler


class HookRegistry:
    """
    Stores hook handlers keyed by event.

    Usage:
        registry = HookRegistry()
        registry.on(HookEvent.pre_tool_use, my_handler)
        registry.on(HookEvent.on_error, my_error_handler, priority=10)
    """

    def __init__(self) -> None:
        # event → sorted list of (priority, handler)
        self._handlers: dict[HookEvent, list[tuple[int, HookHandler]]] = defaultdict(list)

    def on(
        self,
        event: HookEvent,
        handler: HookHandler,
        priority: int = 0,
    ) -> None:
        """Register a handler. Lower priority = runs first."""
        self._handlers[event].append((priority, handler))
        self._handlers[event].sort(key=lambda x: x[0])

    def off(self, event: HookEvent, handler: HookHandler) -> None:
        """Unregister a handler."""
        self._handlers[event] = [
            (p, h) for p, h in self._handlers[event] if h is not handler
        ]

    def handlers_for(self, event: HookEvent) -> list[HookHandler]:
        """Return handlers sorted by priority (lowest first)."""
        return [h for _, h in self._handlers[event]]

    def has_handlers(self, event: HookEvent) -> bool:
        return bool(self._handlers[event])

    @classmethod
    def from_list(
        cls,
        hooks: list[tuple[HookEvent, HookHandler]],
    ) -> "HookRegistry":
        """Convenience: build a registry from [(event, handler), ...] pairs."""
        registry = cls()
        for event, handler in hooks:
            registry.on(event, handler)
        return registry
