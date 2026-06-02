from __future__ import annotations

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool


class TerminateInput(BaseModel):
    result: str = Field(description="Final result or summary to return to the caller.")
    status: str = Field(default="success", description="Completion status: success or failure.")


class TerminateTool(BaseTool):
    name = "terminate"
    description = (
        "End the current session and return a final result. "
        "Call this when the task is complete or when you determine it cannot be completed. "
        "The result will be returned to the caller."
    )
    input_schema = TerminateInput

    def is_concurrency_safe(self) -> bool:
        return False

    async def call(self, input: TerminateInput, ctx: ToolContext) -> ToolResult:
        return ToolResult.ok(tool_call_id="", name=self.name, content=input.result)
