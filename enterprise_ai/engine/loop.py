from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

from enterprise_ai.engine.stop_hooks import StopHookInput, StopHookRunner
from enterprise_ai.engine.token_budget import BudgetDecision, TokenBudgetConfig, TokenBudgetTracker
from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.hooks.executor import HookExecutor
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.providers.base import LLMResponse, Provider
from enterprise_ai.providers.retry import (
    RetryConfig,
    calculate_backoff,
    is_retryable_error,
    parse_retry_after,
)
from enterprise_ai.schema import (
    Message,
    Session,
    SessionResult,
    SessionState,
    StreamEvent,
    ToolCall,
)
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.registry import ToolRegistry

MAX_TURNS = 50


class QueryLoop:
    """
    The core agentic loop.

    State machine:
        IDLE → RUNNING → TOOL_CALLING → RUNNING → … → DONE | ERROR
    """

    def __init__(
        self,
        provider: Provider,
        registry: ToolRegistry,
        orchestrator: Orchestrator,
        memory: SessionMemory,
        system_prompt: str = "",
        max_turns: int = MAX_TURNS,
        retry_config: RetryConfig | None = None,
        hooks: HookExecutor | None = None,
        stop_hooks: StopHookRunner | None = None,
        extended_thinking: bool = False,
        thinking_budget_tokens: int = 10_000,
        cache_system_prompt: bool = False,
        token_budget: TokenBudgetConfig | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._orchestrator = orchestrator
        self._memory = memory
        self._system_prompt = system_prompt
        self._max_turns = max_turns
        self._retry_config = retry_config
        self._hooks = hooks
        self._stop_hooks = stop_hooks
        self._extended_thinking = extended_thinking
        self._thinking_budget_tokens = thinking_budget_tokens
        self._cache_system_prompt = cache_system_prompt
        self._token_budget_config = token_budget
        self._budget_tracker: TokenBudgetTracker | None = (
            TokenBudgetTracker(token_budget) if token_budget else None
        )

    def _build_extra_kwargs(self) -> dict:
        extra: dict = {}
        if self._extended_thinking:
            extra["extended_thinking"] = True
            extra["thinking_budget_tokens"] = self._thinking_budget_tokens
        if self._cache_system_prompt:
            extra["cache_system_prompt"] = True
        return extra

    async def run(self, prompt: str, ctx: ToolContext) -> SessionResult:
        session = Session(id=ctx.session_id or str(uuid.uuid4()), agent_id=ctx.agent_id)
        session.state = SessionState.running
        sid = session.id

        if self._hooks:
            await self._hooks.fire(HookEvent.session_start, sid, {"agent_id": ctx.agent_id})
            await self._hooks.fire(HookEvent.query_start, sid, {"prompt": prompt})

        self._memory.add(Message.user(prompt))
        if self._budget_tracker:
            self._budget_tracker.reset()

        tool_calls_count = 0
        final_output = ""

        for turn_num in range(self._max_turns):
            messages = self._build_messages()
            tools = self._registry.schemas() if self._registry.all() else None

            if self._hooks:
                await self._hooks.fire(HookEvent.turn_start, sid, {"turn": turn_num})
                await self._hooks.fire(HookEvent.pre_api_call, sid, {"messages_count": len(messages)})

            try:
                resp = await self._call_provider(messages, tools)
            except Exception as e:
                if self._hooks:
                    await self._hooks.fire(HookEvent.on_error, sid, {"error": str(e), "turn": turn_num})
                session.state = SessionState.error
                return SessionResult(session_id=sid, output=f"Provider error: {e}", state=SessionState.error)

            if self._hooks:
                await self._hooks.fire(HookEvent.post_api_call, sid, {
                    "input_tokens": resp.input_tokens,
                    "output_tokens": resp.output_tokens,
                })

            if self._budget_tracker:
                self._budget_tracker.record_tokens(resp.input_tokens, resp.output_tokens)

            if resp.content:
                self._memory.add(Message.assistant(
                    resp.content,
                    tool_calls=resp.tool_calls or None,
                    thinking_blocks=resp.thinking_blocks or None,
                ))

            if not resp.has_tool_calls:
                final_output = resp.content

                if self._stop_hooks:
                    sh_result = await self._stop_hooks.run(StopHookInput(
                        session_id=sid,
                        turn_number=turn_num,
                        stop_reason="no_tool_calls",
                        messages=list(self._memory.get()),
                        tool_calls_count=tool_calls_count,
                    ))
                    if sh_result.error is not None:
                        session.state = SessionState.error
                        return SessionResult(session_id=sid, output=str(sh_result.error), state=SessionState.error)
                    if sh_result.continue_loop:
                        for msg in sh_result.inject_messages:
                            self._memory.add(msg)
                        session.state = SessionState.running
                        continue

                session.state = SessionState.done
                if self._hooks:
                    await self._hooks.fire(HookEvent.turn_end, sid, {"stop_reason": "no_tool_calls"})
                break

            # Token budget nudge — inject "Continue" when budget allows
            if self._budget_tracker and self._token_budget_config:
                decision: BudgetDecision = self._budget_tracker.should_continue_for_budget(
                    budget=self._token_budget_config.turn_token_budget,
                    has_tool_calls=resp.has_tool_calls,
                )
                if decision.continue_loop:
                    self._memory.add(Message.user(decision.nudge_message))

            # Tool calling turn
            session.state = SessionState.tool_calling
            tool_calls_count += len(resp.tool_calls)

            terminate_call = next((tc for tc in resp.tool_calls if tc.name == "terminate"), None)
            if terminate_call:
                final_output = terminate_call.input.get("result", "")
                session.state = SessionState.done
                if self._hooks:
                    await self._hooks.fire(HookEvent.turn_end, sid, {"stop_reason": "terminate"})
                break

            if self._hooks:
                await self._hooks.fire(HookEvent.tool_uses_start, sid, {"count": len(resp.tool_calls)})

            outcomes = await self._orchestrator.execute(resp.tool_calls, ctx)

            if self._hooks:
                await self._hooks.fire(HookEvent.tool_uses_complete, sid, {"count": len(outcomes)})

            for outcome in outcomes:
                self._memory.add(
                    Message.tool_result(outcome.result.tool_call_id, outcome.result.content, name=outcome.result.name)
                )

            # LLM-based compaction after each tool turn
            compacted = await self._memory.maybe_compact(system_prompt=self._system_prompt)
            if compacted and self._hooks:
                await self._hooks.fire(HookEvent.post_compact, sid, {})

            if self._hooks:
                await self._hooks.fire(HookEvent.turn_end, sid, {"stop_reason": "tool_calls_done"})
            session.state = SessionState.running
        else:
            session.state = SessionState.error
            final_output = f"Max turns ({self._max_turns}) reached without completing the task."

        if self._hooks:
            await self._hooks.fire(HookEvent.query_complete, sid, {"output": final_output})
            await self._hooks.fire(HookEvent.session_end, sid, {"state": session.state.value})

        return SessionResult(
            session_id=sid,
            output=final_output,
            state=session.state,
            tool_calls_count=tool_calls_count,
        )

    async def stream(self, prompt: str, ctx: ToolContext) -> AsyncIterator[StreamEvent]:
        session = Session(id=ctx.session_id or str(uuid.uuid4()), agent_id=ctx.agent_id)
        session.state = SessionState.running

        self._memory.add(Message.user(prompt))
        if self._budget_tracker:
            self._budget_tracker.reset()

        extra = self._build_extra_kwargs()
        tool_calls_count = 0

        for turn_num in range(self._max_turns):
            messages = self._build_messages()
            tools = self._registry.schemas() if self._registry.all() else None

            # Dict-based dedup: second tool_start (full input) overwrites first (placeholder)
            tool_calls_map: dict[str, ToolCall] = {}
            last_text = ""
            session_end_event: StreamEvent | None = None

            try:
                async for event in self._provider.stream(messages, tools=tools, **extra):
                    if event.type.value == "text_delta":
                        last_text += event.data.get("delta", "")
                        yield event
                    elif event.type.value == "tool_start":
                        data = event.data
                        tc = ToolCall(
                            id=data["id"],
                            name=data["name"],
                            input=data.get("input", {}),
                        )
                        tool_calls_map[tc.id] = tc
                        yield event
                    elif event.type.value == "thinking":
                        yield event
                    elif event.type.value == "session_end":
                        session_end_event = event
                        break  # break inner loop; process below
            except Exception as e:
                yield StreamEvent.err(str(e))
                return

            pending_tool_calls = list(tool_calls_map.values())

            if not pending_tool_calls:
                if last_text:
                    thinking_blocks = (session_end_event.data.get("thinking_blocks") or []) if session_end_event else []
                    self._memory.add(Message.assistant(last_text, thinking_blocks=thinking_blocks or None))

                if self._stop_hooks:
                    sh_result = await self._stop_hooks.run(StopHookInput(
                        session_id=session.id,
                        turn_number=turn_num,
                        stop_reason="no_tool_calls",
                        messages=list(self._memory.get()),
                        tool_calls_count=tool_calls_count,
                    ))
                    if sh_result.error is not None:
                        yield StreamEvent.err(str(sh_result.error))
                        return
                    if sh_result.continue_loop:
                        for msg in sh_result.inject_messages:
                            self._memory.add(msg)
                        continue

                session.state = SessionState.done
                if session_end_event:
                    yield session_end_event
                return

            # Tool calling
            session.state = SessionState.tool_calling
            tool_calls_count += len(pending_tool_calls)

            if last_text:
                self._memory.add(Message.assistant(last_text, tool_calls=pending_tool_calls))

            terminate_call = next((tc for tc in pending_tool_calls if tc.name == "terminate"), None)
            if terminate_call:
                final = terminate_call.input.get("result", "")
                self._memory.add(Message.assistant(final))
                yield StreamEvent.end(final)
                return

            outcomes = await self._orchestrator.execute(pending_tool_calls, ctx)
            for outcome in outcomes:
                self._memory.add(
                    Message.tool_result(outcome.result.tool_call_id, outcome.result.content, name=outcome.result.name)
                )
                yield StreamEvent.tool_result(
                    outcome.result.tool_call_id,
                    outcome.result.name,
                    outcome.result.content,
                    outcome.result.is_error,
                )

            compacted = await self._memory.maybe_compact(system_prompt=self._system_prompt)
            if compacted and self._hooks:
                await self._hooks.fire(HookEvent.post_compact, session.id, {})

            session.state = SessionState.running

        if session.state != SessionState.done:
            yield StreamEvent.err(f"Max turns ({self._max_turns}) reached")

    def _build_messages(self) -> list[Message]:
        messages = []
        if self._system_prompt:
            messages.append(Message.system(self._system_prompt))
        messages.extend(self._memory.get())
        return messages

    async def _call_provider(self, messages: list[Message], tools: list | None) -> LLMResponse:
        """Call provider.complete() with optional retry + backoff on transient errors."""
        extra = self._build_extra_kwargs()

        if self._retry_config is None:
            return await self._provider.complete(messages, tools=tools, **extra)

        cfg = self._retry_config
        last_exc: Exception | None = None
        for attempt in range(1, cfg.max_attempts + 1):
            try:
                return await self._provider.complete(messages, tools=tools, **extra)
            except Exception as exc:
                last_exc = exc
                if attempt == cfg.max_attempts:
                    break
                if not is_retryable_error(exc, cfg):
                    raise
                headers = {}
                resp = getattr(exc, "response", None)
                if resp is not None:
                    headers = dict(getattr(resp, "headers", {}))
                retry_after = parse_retry_after(headers)
                delay = retry_after if retry_after is not None else calculate_backoff(cfg, attempt)
                await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]
