from __future__ import annotations

import uuid
from typing import AsyncIterator

from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.providers.base import Provider
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
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._orchestrator = orchestrator
        self._memory = memory
        self._system_prompt = system_prompt
        self._max_turns = max_turns

    async def run(self, prompt: str, ctx: ToolContext) -> SessionResult:
        session = Session(id=ctx.session_id or str(uuid.uuid4()), agent_id=ctx.agent_id)
        session.state = SessionState.running

        self._memory.add(Message.user(prompt))

        tool_calls_count = 0
        final_output = ""

        for _ in range(self._max_turns):
            messages = self._build_messages()
            tools = self._registry.schemas() if self._registry.all() else None

            try:
                resp = await self._provider.complete(messages, tools=tools)
            except Exception as e:
                session.state = SessionState.error
                return SessionResult(session_id=session.id, output=f"Provider error: {e}", state=SessionState.error)

            if resp.content:
                self._memory.add(Message.assistant(resp.content, tool_calls=resp.tool_calls or None))

            if not resp.has_tool_calls:
                final_output = resp.content
                session.state = SessionState.done
                break

            # Tool calling turn
            session.state = SessionState.tool_calling
            tool_calls_count += len(resp.tool_calls)

            # Check for terminate signal before executing
            terminate_call = next((tc for tc in resp.tool_calls if tc.name == "terminate"), None)
            if terminate_call:
                final_output = terminate_call.input.get("result", "")
                session.state = SessionState.done
                break

            outcomes = await self._orchestrator.execute(resp.tool_calls, ctx)

            for outcome in outcomes:
                self._memory.add(
                    Message.tool_result(outcome.result.tool_call_id, outcome.result.content, name=outcome.result.name)
                )

            session.state = SessionState.running
        else:
            session.state = SessionState.error
            final_output = f"Max turns ({self._max_turns}) reached without completing the task."

        return SessionResult(
            session_id=session.id,
            output=final_output,
            state=session.state,
            tool_calls_count=tool_calls_count,
        )

    async def stream(self, prompt: str, ctx: ToolContext) -> AsyncIterator[StreamEvent]:
        session = Session(id=ctx.session_id or str(uuid.uuid4()), agent_id=ctx.agent_id)
        session.state = SessionState.running

        self._memory.add(Message.user(prompt))
        tool_calls_count = 0

        for _ in range(self._max_turns):
            messages = self._build_messages()
            tools = self._registry.schemas() if self._registry.all() else None

            # Collect streamed tool calls while yielding text
            pending_tool_calls: list[ToolCall] = []
            last_text = ""

            try:
                async for event in self._provider.stream(messages, tools=tools):
                    if event.type.value == "text_delta":
                        last_text += event.data.get("delta", "")
                        yield event
                    elif event.type.value == "tool_start":
                        tc = ToolCall(
                            id=event.data["id"],
                            name=event.data["name"],
                            input=event.data.get("input", {}),
                        )
                        pending_tool_calls.append(tc)
                        yield event
                    elif event.type.value == "session_end":
                        if last_text:
                            self._memory.add(Message.assistant(last_text))
                        session.state = SessionState.done
                        yield event
                        return
            except Exception as e:
                yield StreamEvent.err(str(e))
                return

            if not pending_tool_calls:
                break

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

            session.state = SessionState.running

        if session.state != SessionState.done:
            yield StreamEvent.err(f"Max turns ({self._max_turns}) reached")

    def _build_messages(self) -> list[Message]:
        messages = []
        if self._system_prompt:
            messages.append(Message.system(self._system_prompt))
        messages.extend(self._memory.get())
        return messages
