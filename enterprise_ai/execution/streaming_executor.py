from __future__ import annotations

import asyncio

from enterprise_ai.execution.orchestrator import Orchestrator, ToolOutcome
from enterprise_ai.schema import StreamEvent, ToolCall
from enterprise_ai.schema.event import EventType
from enterprise_ai.tools.context import ToolContext


class StreamingToolCoordinator:
    """
    Submits tool calls to the orchestrator as soon as their JSON input is
    complete during streaming, without waiting for the stream to end.

    Usage in a streaming loop:
        coordinator = StreamingToolCoordinator(orchestrator, ctx)
        async for event in provider.stream(...):
            coordinator.observe(event)
            yield event
        outcomes = await coordinator.collect_results()
    """

    def __init__(self, orchestrator: Orchestrator, ctx: ToolContext) -> None:
        self._orchestrator = orchestrator
        self._ctx = ctx
        self._pending: dict[str, asyncio.Task] = {}  # tool_id → executing task
        self._seen: set[str] = set()  # tool IDs seen on first tool_start (placeholder)

    def observe(self, event: StreamEvent) -> None:
        """Feed each stream event to the coordinator."""
        if event.type != EventType.tool_start:
            return
        tool_id = event.data["id"]
        if tool_id in self._seen:
            # Second tool_start event = input is complete → submit immediately
            tc = ToolCall(
                id=tool_id,
                name=event.data["name"],
                input=event.data.get("input", {}),
            )
            self._submit(tc)
        else:
            # First tool_start event = placeholder (empty input)
            self._seen.add(tool_id)

    def _submit(self, tc: ToolCall) -> None:
        task = asyncio.create_task(self._orchestrator.execute([tc], self._ctx))
        self._pending[tc.id] = task

    async def collect_results(self) -> list[ToolOutcome]:
        """Wait for all pending tool tasks and return flattened results."""
        if not self._pending:
            return []
        raw = await asyncio.gather(*self._pending.values(), return_exceptions=True)
        self._pending.clear()
        self._seen.clear()
        outcomes: list[ToolOutcome] = []
        for result in raw:
            if isinstance(result, list):
                outcomes.extend(result)
            # Exceptions are silently dropped — tool errors surface via ToolResult.is_error
        return outcomes

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)
