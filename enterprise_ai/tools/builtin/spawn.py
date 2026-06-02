from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool

if TYPE_CHECKING:
    pass


class SpawnInput(BaseModel):
    task: str = Field(description="The task or prompt for the sub-agent to complete.")
    system_prompt: str = Field(default="", description="Optional system prompt for the sub-agent.")
    tools: list[str] = Field(
        default_factory=list,
        description="Tool names to give the sub-agent. Empty = same tools as parent.",
    )
    max_turns: int = Field(default=20, ge=1, le=50, description="Max turns for the sub-agent.")


class SpawnTool(BaseTool):
    """
    Spawn a one-shot sub-agent to handle a specific subtask.

    The sub-agent runs to completion and returns its result to the parent agent.
    The sub-agent is ephemeral — it does not share memory with the parent.
    This is the same model as nexus-engine sub-agent delegation.
    """

    name = "spawn_agent"
    description = (
        "Spawn a one-shot sub-agent to complete a specific subtask. "
        "The sub-agent runs autonomously to completion and returns its result. "
        "Use this to parallelize work or delegate specialized tasks. "
        "The sub-agent is isolated — it does not share your session history."
    )
    input_schema = SpawnInput

    def __init__(self, provider_factory: Callable | None = None) -> None:
        # provider_factory: callable() → Provider, injected by Team or Agent
        self._provider_factory = provider_factory

    def is_concurrency_safe(self) -> bool:
        return True  # multiple sub-agents can run in parallel

    async def call(self, input: SpawnInput, ctx: ToolContext) -> ToolResult:
        # Depth check before anything else — fail fast and clearly
        if ctx.sub_agent_depth >= ctx.max_sub_agent_depth:
            return ToolResult.error(
                tool_call_id="", name=self.name,
                error=(
                    f"Sub-agent depth limit reached ({ctx.max_sub_agent_depth}). "
                    "Cannot spawn further sub-agents from this depth."
                ),
            )

        if self._provider_factory is None:
            return ToolResult.error(
                tool_call_id="", name=self.name,
                error="SpawnTool has no provider_factory — attach it via Team or Agent.with_spawn()"
            )

        from enterprise_ai.engine.loop import QueryLoop
        from enterprise_ai.execution.orchestrator import Orchestrator
        from enterprise_ai.memory.session import SessionMemory
        from enterprise_ai.permissions.engine import PermissionEngine, PermissionMode
        from enterprise_ai.providers.base import Provider
        from enterprise_ai.tools.registry import ToolRegistry

        provider: Provider = self._provider_factory()
        registry = ToolRegistry()

        # Sub-agent gets the tools specified, or inherits parent's context tools
        # In practice the parent agent fills this at inject time
        if ctx.metadata.get("_parent_registry") and not input.tools:
            parent_registry: ToolRegistry = ctx.metadata["_parent_registry"]
            for tool in parent_registry.all():
                registry.register(tool)

        permissions = PermissionEngine(mode=PermissionMode.auto)
        orchestrator = Orchestrator(registry=registry, permissions=permissions)
        memory = SessionMemory()

        from enterprise_ai.prompt.templates import SPAWN_DEFAULT_SYSTEM

        system = input.system_prompt or SPAWN_DEFAULT_SYSTEM
        loop = QueryLoop(
            provider=provider,
            registry=registry,
            orchestrator=orchestrator,
            memory=memory,
            system_prompt=system,
            max_turns=input.max_turns,
        )

        sub_ctx = ToolContext(
            session_id=f"{ctx.session_id}-sub",
            agent_id=f"{ctx.agent_id}-sub",
            working_dir=ctx.working_dir,
            permission_mode=PermissionMode.auto.value,
            sub_agent_depth=ctx.sub_agent_depth + 1,
            max_sub_agent_depth=ctx.max_sub_agent_depth,
        )

        result = await loop.run(input.task, sub_ctx)
        return ToolResult.ok(tool_call_id="", name=self.name, content=result.output)
