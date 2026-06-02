from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

from enterprise_ai.engine.loop import QueryLoop
from enterprise_ai.engine.project_instructions import read_project_instructions
from enterprise_ai.execution.micro_compaction import TrimConfig
from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.mcp.config import MCPServerConfig
from enterprise_ai.mcp.manager import MCPManager
from enterprise_ai.memory.long_term import LongTermMemory
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
from enterprise_ai.providers.base import Provider
from enterprise_ai.providers.factory import create_provider
from enterprise_ai.providers.retry import RetryConfig
from enterprise_ai.schema import SessionResult, StreamEvent
from enterprise_ai.skills.registry import resolve_skills
from enterprise_ai.skills.skill import Skill
from enterprise_ai.tools.builtin.agent_memory import (
    ForgetTool,
    RecallTool,
    RecentMemoriesTool,
    RememberTool,
)
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
      - skill injection (Markdown+YAML procedures injected into system context)

    Usage:
        agent = Agent(
            provider=AnthropicProvider(model="claude-opus-4-8"),
            tools=[BashTool(), FileEditorTool()],
            system_prompt="You are a senior software engineer.",
            skills=["code-review", "systematic-debugging"],
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
        skills: list[str | Skill] | None = None,
        mcp_servers: list[MCPServerConfig] | None = None,
        long_term_memory: LongTermMemory | None = None,
        inject_memories: int = 5,
        permission_mode: PermissionMode | str = PermissionMode.auto,
        deny_tools: set[str] | None = None,
        working_dir: str = ".",
        max_turns: int = 50,
        max_memory: int = 200,
        agent_id: str | None = None,
        max_sub_agent_depth: int = 5,
        retry_config: RetryConfig | None = None,
        trim_config: TrimConfig | None = None,
        **provider_kwargs: Any,
    ) -> None:
        self.id = agent_id or str(uuid.uuid4())
        self._metadata: dict[str, Any] = {}
        self._max_sub_agent_depth = max_sub_agent_depth
        self._working_dir = working_dir

        # Provider
        if isinstance(provider, str):
            self._provider = create_provider(provider, **provider_kwargs)
        else:
            self._provider = provider

        # Skills — resolve names and inject into system prompt
        self._skills = self._resolve_skills(skills or [])
        project_instructions = read_project_instructions(working_dir)
        effective_system = self._build_system_prompt(system_prompt, self._skills, project_instructions)
        effective_deny = set(deny_tools or [])

        # MCP manager — stored for lifecycle management by caller
        self._mcp_manager: MCPManager | None = (
            MCPManager(mcp_servers) if mcp_servers else None
        )

        # Long-term memory — persists across sessions
        self._long_term_memory = long_term_memory
        self._inject_memories = inject_memories

        # Tools — filtered by skill allowed-tools restrictions if any
        self._registry = ToolRegistry()
        skill_allowed = self._merged_allowed_tools(self._skills)
        for tool in (tools or []):
            if skill_allowed is None or tool.name in skill_allowed:
                self._registry.register(tool)

        # Auto-register agent memory tools when long-term memory is configured
        if long_term_memory is not None:
            for mem_tool in (RememberTool(), RecallTool(), ForgetTool(), RecentMemoriesTool()):
                if skill_allowed is None or mem_tool.name in skill_allowed:
                    self._registry.register(mem_tool)

        # Permissions
        if isinstance(permission_mode, str):
            permission_mode = PermissionMode(permission_mode)
        self._permissions = PermissionEngine(mode=permission_mode, deny_tools=effective_deny)

        # Core components
        self._memory = SessionMemory(max_messages=max_memory)
        self._orchestrator = Orchestrator(
            registry=self._registry,
            permissions=self._permissions,
            trim_config=trim_config,
        )
        self._loop = QueryLoop(
            provider=self._provider,
            registry=self._registry,
            orchestrator=self._orchestrator,
            memory=self._memory,
            system_prompt=effective_system,
            max_turns=max_turns,
            retry_config=retry_config,
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_skills(skills: list[str | Skill]) -> list[Skill]:
        names = [s for s in skills if isinstance(s, str)]
        objs = [s for s in skills if isinstance(s, Skill)]
        return objs + resolve_skills(names)

    @staticmethod
    def _build_system_prompt(
        base: str,
        skills: list[Skill],
        project_instructions: str = "",
    ) -> str:
        parts = [base.strip()] if base.strip() else []
        if project_instructions:
            parts.append("## Project Instructions\n\n" + project_instructions)
        for skill in skills:
            block = skill.system_prompt_block()
            if block:
                parts.append(block)
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _merged_allowed_tools(skills: list[Skill]) -> set[str] | None:
        """
        Returns the union of allowed-tools across all skills that restrict tools.
        Returns None if no skill restricts tools (= all tools allowed).
        """
        restricted = [s for s in skills if s.restricts_tools()]
        if not restricted:
            return None
        allowed: set[str] = set()
        for skill in restricted:
            allowed.update(skill.allowed_tools)
        return allowed

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def _make_ctx(self, session_id: str = "") -> ToolContext:
        ctx = ToolContext(
            session_id=session_id or str(uuid.uuid4()),
            agent_id=self.id,
            working_dir=self._working_dir,
            permission_mode=self._permissions.mode.value,
            max_sub_agent_depth=self._max_sub_agent_depth,
        )
        ctx.metadata.update(self._metadata)
        if self._long_term_memory is not None:
            ctx.metadata["agent_memory"] = self._long_term_memory
        return ctx

    async def _prepend_memories(self, prompt: str) -> str:
        """Prepend recent long-term memories to the prompt if configured."""
        if self._long_term_memory is None or self._inject_memories <= 0:
            return prompt
        block = await self._long_term_memory.context_block(limit=self._inject_memories)
        if not block:
            return prompt
        return f"{block}\n\n---\n\n{prompt}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self, prompt: str, session_id: str = "") -> SessionResult:
        """Run the agent to completion and return the final result."""
        ctx = self._make_ctx(session_id)
        enriched = await self._prepend_memories(prompt)
        return await self._loop.run(enriched, ctx)

    async def stream(self, prompt: str, session_id: str = "") -> AsyncIterator[StreamEvent]:
        """Run the agent and stream events as they happen."""
        ctx = self._make_ctx(session_id)
        enriched = await self._prepend_memories(prompt)
        async for event in self._loop.stream(enriched, ctx):
            yield event

    async def connect_mcp(self) -> None:
        """
        Connect to all configured MCP servers and inject their tools into the registry.
        Call this before run() when using mcp_servers.

        Usage:
            agent = Agent(..., mcp_servers=[StdioServerConfig(...)])
            await agent.connect_mcp()
            result = await agent.run("Use the GitHub MCP server to list my repos")
            await agent.disconnect_mcp()

            # Or as context manager:
            async with agent.mcp():
                result = await agent.run("...")
        """
        if self._mcp_manager is None:
            return
        await self._mcp_manager.start()
        for tool in self._mcp_manager.tools:
            self._registry.register(tool)

    async def disconnect_mcp(self) -> None:
        """Disconnect from all MCP servers."""
        if self._mcp_manager is not None:
            await self._mcp_manager.stop()

    def mcp(self) -> _MCPContextManager:
        """Async context manager for MCP lifecycle."""
        return _MCPContextManager(self)

    def add_tool(self, tool: BaseTool) -> None:
        self._registry.register(tool)

    def add_skill(self, skill: str | Skill) -> None:
        """Add a skill after construction. Rebuilds the system prompt."""
        resolved = self._resolve_skills([skill])
        self._skills.extend(resolved)
        new_prompt = self._build_system_prompt("", self._skills)
        self._loop._system_prompt = new_prompt

    def reset_memory(self) -> None:
        self._memory.clear()

    @property
    def model(self) -> str:
        return self._provider.model

    @property
    def skills(self) -> list[Skill]:
        return list(self._skills)

    @property
    def mcp_manager(self) -> MCPManager | None:
        return self._mcp_manager


class _MCPContextManager:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    async def __aenter__(self) -> Agent:
        await self._agent.connect_mcp()
        return self._agent

    async def __aexit__(self, *_: object) -> None:
        await self._agent.disconnect_mcp()
