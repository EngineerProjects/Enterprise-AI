from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from enterprise_ai.execution.micro_compaction import TrimConfig, TrimStrategy, trim_tool_result
from enterprise_ai.permissions.engine import PermissionEngine
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry


@dataclass
class ToolOutcome:
    tool_call: ToolCall
    result: ToolResult
    error: str = ""

    @property
    def failed(self) -> bool:
        return bool(self.error) or self.result.is_error


@dataclass
class _PreparedCall:
    tool_call: ToolCall
    tool: BaseTool
    parsed_input: Any
    is_concurrency_safe: bool


@dataclass
class _Batch:
    calls: list[_PreparedCall] = field(default_factory=list)
    is_concurrent: bool = True


ProgressCallback = Callable[[ToolOutcome], Awaitable[None]]


class Orchestrator:
    """
    Executes tool calls with proper parallelization.

    Pipeline per tool call (12 steps):
    1. Resolve       — find tool in registry, check IsEnabled
    2. ValidateInput — parse and validate against Pydantic schema
    3. BackfillInput — stamp call id if missing
    4. PreHooks      — (extensible)
    5. SafetyCheck   — bypass-immune dangerous-pattern check
    6. Permissions   — deny rules → local → always-allow → global (mode)
    7. DenialTracking— record denials
    8. tool.call()   — actual execution
    9. PostHooks     — (extensible)
    10. FormatResult  — already handled by tool
    11. SizeLimit     — truncate oversized results
    12. ContextModify — (sequential only) applied in order
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionEngine,
        max_concurrency: int = 10,
        progress_callback: ProgressCallback | None = None,
        trim_config: TrimConfig | None = None,
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._sem = asyncio.Semaphore(max_concurrency)
        self._progress_callback = progress_callback
        self._trim_config = trim_config or TrimConfig(
            max_chars=40_000, strategy=TrimStrategy.snip
        )

    async def execute(self, tool_calls: list[ToolCall], ctx: ToolContext) -> list[ToolOutcome]:
        # Steps 1-3: resolve, validate, backfill
        prepared, early_errors = self._prepare(tool_calls)
        if early_errors:
            return early_errors

        # Partition into batches (concurrent vs sequential)
        batches = self._partition(prepared)

        outcomes: list[ToolOutcome] = []
        for batch in batches:
            if batch.is_concurrent:
                batch_outcomes = await asyncio.gather(
                    *[self._run_one(p, ctx) for p in batch.calls]
                )
                outcomes.extend(sorted(batch_outcomes, key=lambda o: tool_calls.index(o.tool_call)))
            else:
                for p in batch.calls:
                    outcome = await self._run_one(p, ctx)
                    outcomes.append(outcome)

            if self._progress_callback:
                for o in outcomes[-len(batch.calls):]:
                    await self._progress_callback(o)

        return outcomes

    def _prepare(self, tool_calls: list[ToolCall]) -> tuple[list[_PreparedCall], list[ToolOutcome]]:
        prepared = []
        errors = []
        for tc in tool_calls:
            # Step 1: stamp id
            if not tc.id:
                tc = tc.model_copy(update={"id": str(uuid.uuid4())})

            # Step 2: resolve
            tool = self._registry.get(tc.name)
            if tool is None:
                errors.append(ToolOutcome(
                    tool_call=tc,
                    result=ToolResult.error(tc.id, tc.name, f"Unknown tool: {tc.name!r}"),
                    error=f"Unknown tool: {tc.name!r}",
                ))
                continue

            # Step 3: validate input
            try:
                parsed = tool.parse_input(tc.input)
            except Exception as e:
                errors.append(ToolOutcome(
                    tool_call=tc,
                    result=ToolResult.error(tc.id, tc.name, f"Invalid input: {e}"),
                    error=str(e),
                ))
                continue

            prepared.append(_PreparedCall(
                tool_call=tc,
                tool=tool,
                parsed_input=parsed,
                is_concurrency_safe=tool.is_concurrency_safe(),
            ))
        return prepared, errors

    def _partition(self, prepared: list[_PreparedCall]) -> list[_Batch]:
        """Group calls: consecutive concurrent-safe calls into one batch, others solo."""
        if not prepared:
            return []
        batches: list[_Batch] = []
        current = _Batch(is_concurrent=prepared[0].is_concurrency_safe)
        for p in prepared:
            if p.is_concurrency_safe == current.is_concurrent:
                current.calls.append(p)
            else:
                batches.append(current)
                current = _Batch(calls=[p], is_concurrent=p.is_concurrency_safe)
        batches.append(current)
        return batches

    async def _run_one(self, p: _PreparedCall, ctx: ToolContext) -> ToolOutcome:
        tc = p.tool_call

        # Step 5-7: permissions
        perm = await self._permissions.check(tc)
        if not perm.allowed:
            return ToolOutcome(
                tool_call=tc,
                result=ToolResult.error(tc.id, tc.name, f"Permission denied: {perm.reason}"),
                error=perm.reason,
            )

        # Step 8: call
        async with self._sem:
            try:
                result = await p.tool.call(p.parsed_input, ctx)
                result = result.model_copy(update={"tool_call_id": tc.id})
            except Exception as e:
                return ToolOutcome(
                    tool_call=tc,
                    result=ToolResult.error(tc.id, tc.name, f"Tool raised an exception: {e}"),
                    error=str(e),
                )

        # Step 11: size limit — smart trim (snip by default, not brutal truncation)
        trimmed = trim_tool_result(result.content, self._trim_config)
        if trimmed != result.content:
            result = result.model_copy(update={"content": trimmed})

        return ToolOutcome(tool_call=tc, result=result)
