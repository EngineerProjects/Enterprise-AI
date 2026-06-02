from __future__ import annotations

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool


class PostTaskInput(BaseModel):
    title: str = Field(description="Short title for the task.")
    description: str = Field(description="Full description of what needs to be done.")


class ClaimTaskInput(BaseModel):
    task_id: str = Field(default="", description="Specific task ID to claim. Leave empty to claim the next available task.")
    timeout: float = Field(default=0.0, ge=0.0, description="Seconds to wait for a task to become available. 0 = return immediately.")


class CompleteTaskInput(BaseModel):
    task_id: str = Field(description="ID of the task to mark as complete.")
    result: str = Field(default="", description="Summary of what was accomplished.")


class FailTaskInput(BaseModel):
    task_id: str = Field(description="ID of the task to mark as failed.")
    reason: str = Field(default="", description="Why the task failed.")


class ListTasksInput(BaseModel):
    filter: str = Field(default="pending", description="Filter: pending, claimed, done, failed, all, mine.")


class PostTaskTool(BaseTool):
    name = "post_task"
    description = (
        "Post a new task to the team task board. "
        "Other agents can see and claim this task. "
        "Use to delegate work or break down the mission into sub-tasks."
    )
    input_schema = PostTaskInput

    async def call(self, input: PostTaskInput, ctx: ToolContext) -> ToolResult:
        board = ctx.metadata.get("task_board")
        if board is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No task board in context — agent is not in a team.")
        task = await board.post(title=input.title, description=input.description, posted_by=ctx.agent_id)
        return ToolResult.ok(
            tool_call_id="", name=self.name,
            content=f"Task posted: [{task.id[:8]}] {task.title}",
        )


class ClaimTaskTool(BaseTool):
    name = "claim_task"
    description = (
        "Claim a task from the team task board so you can work on it. "
        "Provide a task_id to claim a specific task, or leave empty to claim the next available one. "
        "Once claimed, the task is yours until you complete or fail it."
    )
    input_schema = ClaimTaskInput

    def is_concurrency_safe(self) -> bool:
        return False  # claiming tasks must be atomic

    async def call(self, input: ClaimTaskInput, ctx: ToolContext) -> ToolResult:
        board = ctx.metadata.get("task_board")
        if board is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No task board in context.")

        if input.task_id:
            task = await board.claim(input.task_id, ctx.agent_id)
        else:
            timeout = input.timeout if input.timeout > 0 else None
            task = await board.claim_next(ctx.agent_id, timeout=timeout)

        if task is None:
            pending = len(board.pending_tasks())
            return ToolResult.ok(
                tool_call_id="", name=self.name,
                content=f"No task available to claim. ({pending} pending on board)",
            )
        return ToolResult.ok(
            tool_call_id="", name=self.name,
            content=f"Claimed: [{task.id[:8]}] {task.title}\n\nDescription: {task.description}",
        )


class CompleteTaskTool(BaseTool):
    name = "complete_task"
    description = "Mark a claimed task as complete with a result summary."
    input_schema = CompleteTaskInput

    async def call(self, input: CompleteTaskInput, ctx: ToolContext) -> ToolResult:
        board = ctx.metadata.get("task_board")
        if board is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No task board in context.")
        ok = await board.complete(input.task_id, result=input.result)
        if not ok:
            return ToolResult.error(tool_call_id="", name=self.name, error=f"Cannot complete task {input.task_id[:8]} — not found or not claimed by you.")
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"Task {input.task_id[:8]} marked complete.")


class FailTaskTool(BaseTool):
    name = "fail_task"
    description = "Mark a claimed task as failed with a reason."
    input_schema = FailTaskInput

    async def call(self, input: FailTaskInput, ctx: ToolContext) -> ToolResult:
        board = ctx.metadata.get("task_board")
        if board is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No task board in context.")
        ok = await board.fail(input.task_id, reason=input.reason)
        if not ok:
            return ToolResult.error(tool_call_id="", name=self.name, error=f"Cannot fail task {input.task_id[:8]} — not found or not claimed.")
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"Task {input.task_id[:8]} marked failed.")


class ListTasksTool(BaseTool):
    name = "list_tasks"
    description = (
        "List tasks on the team task board. "
        "Filter: 'pending' (available to claim), 'claimed', 'done', 'failed', 'all', 'mine' (tasks you claimed)."
    )
    input_schema = ListTasksInput

    async def call(self, input: ListTasksInput, ctx: ToolContext) -> ToolResult:
        board = ctx.metadata.get("task_board")
        if board is None:
            return ToolResult.error(tool_call_id="", name=self.name, error="No task board in context.")

        f = input.filter.lower()
        if f == "pending":
            tasks = board.pending_tasks()
        elif f == "mine":
            tasks = board.tasks_by(ctx.agent_id)
        elif f == "all":
            tasks = board.all()
        else:
            from enterprise_ai.team.task_board import TaskStatus
            try:
                status = TaskStatus(f)
                tasks = [t for t in board.all() if t.status == status]
            except ValueError:
                tasks = board.all()

        if not tasks:
            return ToolResult.ok(tool_call_id="", name=self.name, content=f"No tasks ({f}).")
        lines = [str(t) for t in tasks]
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n".join(lines))
