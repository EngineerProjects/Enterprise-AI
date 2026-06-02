from __future__ import annotations

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool


class SearchMemoryInput(BaseModel):
    query: str = Field(description="Search query to find relevant entries in team shared memory.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum number of results to return.")


class WriteMemoryInput(BaseModel):
    content: str = Field(description="Note, finding, decision, or any information to store in team memory.")
    source: str = Field(default="note", description="Source label: 'note', 'decision', 'finding', 'research', etc.")


class RecentMemoryInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50, description="Number of recent entries to retrieve.")


class SearchMemoryTool(BaseTool):
    name = "search_memory"
    description = (
        "Search the team's shared memory for relevant context. "
        "Returns past mails, task results, decisions, and notes matching your query. "
        "Use before acting to check if teammates have already worked on this."
    )
    input_schema = SearchMemoryInput

    async def call(self, input: SearchMemoryInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("team_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No team memory in context — agent is not in a team with memory enabled.")

        results = await memory.search(input.query, limit=input.limit)
        if not results:
            return ToolResult.ok(tool_call_id="", name=self.name, content=f"No results found for: {input.query!r}")

        lines = [f"=== Result {i+1} ===\n{entry}" for i, entry in enumerate(results)]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n\n".join(lines))


class WriteMemoryTool(BaseTool):
    name = "write_memory"
    description = (
        "Store a note, finding, or decision in the team's shared memory. "
        "Other agents can search and retrieve this later. "
        "Use to share insights, record decisions, or document research findings."
    )
    input_schema = WriteMemoryInput

    async def call(self, input: WriteMemoryInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("team_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No team memory in context — agent is not in a team with memory enabled.")

        entry_id = await memory.write(
            content=input.content,
            source=input.source,
            agent_id=ctx.agent_id,
        )
        return ToolResult.ok(
            tool_call_id="", name=self.name,
            content=f"Stored in team memory [{entry_id[:8]}] as '{input.source}'.",
        )


class RecentMemoryTool(BaseTool):
    name = "recent_memory"
    description = (
        "Retrieve the most recent entries from team shared memory. "
        "Use at the start of a session to catch up on what teammates have done."
    )
    input_schema = RecentMemoryInput

    async def call(self, input: RecentMemoryInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("team_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No team memory in context.")

        results = await memory.recent(limit=input.limit)
        if not results:
            return ToolResult.ok(tool_call_id="", name=self.name, content="Team memory is empty.")

        lines = [str(entry) for entry in results]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n\n---\n\n".join(lines))
