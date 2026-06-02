from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, Callable

from enterprise_ai.engine.instructions import read_project_instructions
from enterprise_ai.engine.loop import QueryLoop
from enterprise_ai.engine.stop_hooks import StopHookEntry, StopHookRunner
from enterprise_ai.engine.token_budget import TokenBudgetConfig
from enterprise_ai.execution.compaction import TrimConfig
from enterprise_ai.execution.orchestrator import Orchestrator
from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.hooks.executor import HookExecutor
from enterprise_ai.hooks.registry import HookRegistry
from enterprise_ai.hooks.types import HookHandler
from enterprise_ai.mcp.config import MCPServerConfig
from enterprise_ai.mcp.manager import MCPManager
from enterprise_ai.memory.compaction import CompactionConfig, CompactionEngine
from enterprise_ai.memory.long_term import LongTermMemory
from enterprise_ai.memory.session import SessionMemory
from enterprise_ai.modes.execution import ExecutionMode
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
        toolset: str | None = None,
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
        fallback_provider: Provider | None = None,
        trim_config: TrimConfig | None = None,
        hooks: list[tuple[HookEvent, HookHandler]] | HookRegistry | None = None,
        stop_hooks: list[StopHookEntry] | None = None,
        execution_mode: ExecutionMode = ExecutionMode.execute,
        extended_thinking: bool = False,
        thinking_budget_tokens: int = 10_000,
        cache_system_prompt: bool = False,
        token_budget: TokenBudgetConfig | None = None,
        compaction_config: CompactionConfig | None = None,
        context_engine: Any | None = None,
        tool_search_threshold: int | None = None,
        stream_scrubbers: list | None = None,
        skill_vars: dict[str, str] | None = None,
        enable_shell_in_skills: bool = False,
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

        # Toolset resolution — merge toolset tools with explicitly passed tools
        # Explicit tools take precedence (by name) over toolset-resolved tools
        if toolset is not None:
            from enterprise_ai.tools.toolsets import resolve_toolset
            toolset_tools = resolve_toolset(toolset)
            explicit_names = {t.name for t in (tools or [])}
            tools = [t for t in toolset_tools if t.name not in explicit_names] + (tools or [])

        # Skills — resolve names and inject into system prompt
        self._skills = self._resolve_skills(skills or [])
        project_instructions = read_project_instructions(working_dir)
        effective_system = self._build_system_prompt(
            system_prompt,
            self._skills,
            project_instructions,
            skill_vars=skill_vars,
            enable_shell_in_skills=enable_shell_in_skills,
        )
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

        # Hooks — build executor from list or registry
        hook_executor: HookExecutor | None = None
        if hooks is not None:
            if isinstance(hooks, list):
                registry_obj = HookRegistry.from_list(hooks)
            else:
                registry_obj = hooks
            hook_executor = HookExecutor(registry_obj)

        # Stop hooks runner
        stop_hook_runner: StopHookRunner | None = (
            StopHookRunner(stop_hooks) if stop_hooks else None
        )

        # Compaction / context engine — custom engine takes priority over compaction_config
        effective_engine: Any | None
        if context_engine is not None:
            effective_engine = context_engine
        elif compaction_config is not None:
            effective_engine = CompactionEngine(self._provider, compaction_config)
        else:
            effective_engine = None
        compaction_engine = effective_engine  # kept for compat with SessionMemory param name

        # Tool search bridge — progressive disclosure for large MCP registries
        from enterprise_ai.tools.search_bridge import ToolSearchBridge
        search_bridge: ToolSearchBridge | None = (
            ToolSearchBridge(self._registry, tool_search_threshold)
            if tool_search_threshold is not None
            else None
        )

        # Stream scrubbers — stateful text filters applied to streaming output
        self._stream_scrubbers: list = list(stream_scrubbers) if stream_scrubbers else []

        # Core components
        self._memory = SessionMemory(max_messages=max_memory, compaction_engine=compaction_engine)
        self._orchestrator = Orchestrator(
            registry=self._registry,
            permissions=self._permissions,
            trim_config=trim_config,
            hooks=hook_executor,
            execution_mode=execution_mode,
        )
        self._loop = QueryLoop(
            provider=self._provider,
            registry=self._registry,
            orchestrator=self._orchestrator,
            memory=self._memory,
            system_prompt=effective_system,
            max_turns=max_turns,
            retry_config=retry_config,
            fallback_provider=fallback_provider,
            hooks=hook_executor,
            stop_hooks=stop_hook_runner,
            extended_thinking=extended_thinking,
            thinking_budget_tokens=thinking_budget_tokens,
            cache_system_prompt=cache_system_prompt,
            token_budget=token_budget,
            search_bridge=search_bridge,
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
        skill_vars: dict[str, str] | None = None,
        enable_shell_in_skills: bool = False,
    ) -> str:
        from enterprise_ai.prompt.builder import PromptBuilder

        builder = PromptBuilder()
        if base.strip():
            builder.add(base.strip())
        if project_instructions:
            builder.add(f"## Project Instructions\n\n{project_instructions}")
        for skill in skills:
            block = skill.system_prompt_block(
                vars=skill_vars,
                enable_shell=enable_shell_in_skills,
            )
            if block:
                builder.add(block)
        return builder.build()

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

    def _make_ctx(self, session_id: str = "", parent_session_id: str = "") -> ToolContext:
        ctx = ToolContext(
            session_id=session_id or str(uuid.uuid4()),
            agent_id=self.id,
            working_dir=self._working_dir,
            permission_mode=self._permissions.mode.value,
            max_sub_agent_depth=self._max_sub_agent_depth,
            parent_session_id=parent_session_id,
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

    async def run(
        self,
        prompt: str,
        session_id: str = "",
        parent_session_id: str = "",
    ) -> SessionResult:
        """Run the agent to completion and return the final result."""
        ctx = self._make_ctx(session_id, parent_session_id)
        enriched = await self._prepend_memories(prompt)
        return await self._loop.run(enriched, ctx)

    async def stream(
        self,
        prompt: str,
        session_id: str = "",
        parent_session_id: str = "",
    ) -> AsyncIterator[StreamEvent]:
        """Run the agent and stream events as they happen."""
        ctx = self._make_ctx(session_id, parent_session_id)
        enriched = await self._prepend_memories(prompt)
        for scrubber in self._stream_scrubbers:
            scrubber.reset()
        async for event in self._loop.stream(enriched, ctx):
            if event.type.value == "text_delta" and self._stream_scrubbers:
                delta = event.data.get("delta", "")
                for scrubber in self._stream_scrubbers:
                    delta = scrubber.process(delta)
                if not delta:
                    continue
                from enterprise_ai.schema import StreamEvent as SE
                yield SE.text(delta)
            else:
                yield event

    def snapshot(self) -> list:
        """Return a copy of the current conversation messages for forking."""
        return self._memory.get()

    def resume_from(self, messages: list) -> None:
        """
        Pre-load conversation messages into this agent's memory.
        Use with parent_session_id to implement session branching:

            # Fork from a completed session
            branch = Agent(provider=..., tools=[...])
            branch.resume_from(original_agent.snapshot())
            result = await branch.run(
                "Try a different approach.",
                parent_session_id=original_result.session_id,
            )
        """
        self._memory.clear()
        for msg in messages:
            self._memory.add(msg)

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

    def with_spawn(self, provider_factory: Callable | None = None) -> "Agent":
        """Enable sub-agent spawning via the spawn_agent tool.

        After calling this, the LLM can use spawn_agent(task="...") to delegate
        subtasks to isolated sub-agents that run to completion and return results.

        provider_factory: callable () → Provider for each sub-agent.
                          Defaults to reusing this agent's provider (stateless, safe).

        Usage:
            agent = Agent(provider=..., tools=[BashTool()]).with_spawn()
            # LLM can now call: spawn_agent(task="...", max_turns=20)

            # Custom provider per sub-agent:
            agent = Agent(...).with_spawn(
                provider_factory=lambda: AnthropicProvider(model="claude-haiku-4-5-20251001")
            )
        """
        from enterprise_ai.tools.builtin.spawn import SpawnTool

        factory: Callable = provider_factory or (lambda: self._provider)
        spawn_tool = SpawnTool(provider_factory=factory)
        self._registry.register(spawn_tool)
        # Expose parent registry so SpawnTool can optionally inherit tools to sub-agents
        self._metadata["_parent_registry"] = self._registry
        return self

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
