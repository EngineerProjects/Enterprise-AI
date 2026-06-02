from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from enterprise_ai.engine.loop import QueryLoop
from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
from enterprise_ai.providers.base import Provider
from enterprise_ai.providers.factory import create_provider
from enterprise_ai.schema import SessionResult, StreamEvent
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool
from enterprise_ai.tools.registry import ToolRegistry


class Agent:
    """
    An autonomous agent — the primary public API of enterprise-ai.

    One Agent = one complete agentic runtime:
      - multi-turn loop (LLM → tools → LLM)
      - parallel tool orchestration
      - permission pipeline
      - streaming events
      - session memory

    Usage:
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            tools=[BashTool(), FileEditorTool()],
            system_prompt="You are a senior software engineer.",
        )
        result = await agent.run("Fix the failing test in tests/auth_test.py")

        # Or streaming:
        async for event in agent.stream("Refactor the auth module"):
            print(event)
    """

    def __init__(
        self,
        provider: Provider | str = "anthropic",
        tools: list[BaseTool] | None = None,
        system_prompt: str = "",
        permission_mode: PermissionMode | str = PermissionMode.auto,
        deny_tools: set[str] | None = None,
        working_dir: str = ".",
        max_turns: int = 50,
        max_memory: int = 200,
        agent_id: str | None = None,
        **provider_kwargs: Any,
    ) -> None:
        self.id = agent_id or str(uuid.uuid4())
        self._metadata: dict[str, Any] = {}

        # Provider
        if isinstance(provider, str):
            self._provider = create_provider(provider, **provider_kwargs)
        else:
            self._provider = provider

        # Tools
        self._registry = ToolRegistry()
        for tool in (tools or []):
            self._registry.register(tool)

        # Permissions
        if isinstance(permission_mode, str):
            permission_mode = PermissionMode(permission_mode)
        self._permissions = PermissionEngine(mode=permission_mode, deny_tools=deny_tools)

        # Core components
        self._memory = SessionMemory(max_messages=max_memory)
        self._orchestrator = Orchestrator(
            registry=self._registry,
            permissions=self._permissions,
        )
        self._loop = QueryLoop(
            provider=self._provider,
            registry=self._registry,
            orchestrator=self._orchestrator,
            memory=self._memory,
            system_prompt=system_prompt,
            max_turns=max_turns,
        )
        self._working_dir = working_dir

    def _make_ctx(self, session_id: str = "") -> ToolContext:
        return ToolContext(
            session_id=session_id or str(uuid.uuid4()),
            agent_id=self.id,
            working_dir=self._working_dir,
            permission_mode=self._permissions.mode.value,
        )

    async def run(self, prompt: str, session_id: str = "") -> SessionResult:
        """Run the agent to completion and return the final result."""
        ctx = self._make_ctx(session_id)
        return await self._loop.run(prompt, ctx)

    async def stream(self, prompt: str, session_id: str = "") -> AsyncIterator[StreamEvent]:
        """Run the agent and stream events as they happen."""
        ctx = self._make_ctx(session_id)
        async for event in self._loop.stream(prompt, ctx):
            yield event

    def add_tool(self, tool: BaseTool) -> None:
        self._registry.register(tool)

    def reset_memory(self) -> None:
        self._memory.clear()

    @property
    def model(self) -> str:
        return self._provider.model
