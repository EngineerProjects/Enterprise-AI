from __future__ import annotations

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool


class RememberInput(BaseModel):
    content: str = Field(description="What to remember. Be specific and self-contained — this will be read in future sessions without the current context.")
    category: str = Field(
        default="note",
        description="Category: 'note' (general), 'decision' (choices made), 'fact' (project facts), 'preference' (how things should be done), 'context' (project background).",
    )


class RecallInput(BaseModel):
    query: str = Field(description="What to search for in your long-term memory.")
    limit: int = Field(default=5, ge=1, le=20, description="Maximum results to return.")


class ForgetInput(BaseModel):
    record_id: str = Field(description="ID of the memory record to delete.")


class RecentMemoriesInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=50, description="Number of recent memories to retrieve.")


class RememberTool(BaseTool):
    name = "remember"
    description = (
        "Save something to your long-term memory — it will be available in future sessions. "
        "Use for: project conventions, important decisions, things you've learned, "
        "preferences the user has expressed, or context that will help you later. "
        "Be specific and self-contained — future-you won't have this conversation's context."
    )
    input_schema = RememberInput

    async def call(self, input: RememberInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("agent_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No long-term memory configured for this agent.")

        record_id = await memory.remember(content=input.content, category=input.category)
        return ToolResult.ok(
            tool_call_id="", name=self.name,
            content=f"Saved to long-term memory [{record_id[:8]}] as '{input.category}'.",
        )


class RecallTool(BaseTool):
    name = "recall"
    description = (
        "Search your long-term memory from previous sessions. "
        "Use when you need to remember something from past work: conventions, decisions, facts, preferences."
    )
    input_schema = RecallInput

    async def call(self, input: RecallInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("agent_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No long-term memory configured for this agent.")

        records = await memory.recall(input.query, limit=input.limit)
        if not records:
            return ToolResult.ok(tool_call_id="", name=self.name, content=f"No memories found for: {input.query!r}")

        lines = [str(r) for r in records]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n\n".join(lines))


class ForgetTool(BaseTool):
    name = "forget"
    description = "Delete a specific memory record by its ID. Use to remove outdated or incorrect memories."
    input_schema = ForgetInput

    async def call(self, input: ForgetInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("agent_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No long-term memory configured.")

        deleted = await memory.forget(input.record_id)
        if deleted:
            return ToolResult.ok(tool_call_id="", name=self.name, content=f"Deleted memory {input.record_id[:8]}.")
        return ToolResult.error(tool_call_id="", name=self.name, error=f"Record {input.record_id[:8]} not found.")


class RecentMemoriesTool(BaseTool):
    name = "recent_memories"
    description = (
        "List your most recent long-term memories from previous sessions. "
        "Useful at the start of a session to catch up on what you remembered before."
    )
    input_schema = RecentMemoriesInput

    async def call(self, input: RecentMemoriesInput, ctx: ToolContext) -> ToolResult:
        memory = ctx.metadata.get("agent_memory")
        if memory is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No long-term memory configured.")

        records = await memory.recent(limit=input.limit)
        if not records:
            return ToolResult.ok(tool_call_id="", name=self.name, content="No long-term memories yet.")

        lines = [str(r) for r in records]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n\n".join(lines))
