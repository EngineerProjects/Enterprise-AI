"""Terminate tool for Enterprise AI."""

from typing import Any, Dict, Literal, Optional

from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool


_TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task.
When you have finished all the tasks, call this tool to end the work."""


@register_tool(category="utility")
class Terminate(BaseTool):
    """Tool to signal the end of a conversation or task."""

    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
            },
            "message": {
                "type": "string",
                "description": "Optional message explaining the termination reason.",
            },
        },
        "required": ["status"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Terminate the current execution.

        Args:
            **kwargs: Keyword arguments including:
                status: The status of termination ('success' or 'failure')
                message: Optional explanation message

        Returns:
            ToolResult with termination status
        """
        status = kwargs.get("status")
        if not status:
            return ToolResult(error="Status parameter is required")

        message = kwargs.get("message")

        if status not in ["success", "failure"]:
            return ToolResult(error=f"Invalid status: {status}. Must be 'success' or 'failure'")

        response = f"The interaction has been completed with status: {status}"
        if message:
            response += f"\nMessage: {message}"

        return ToolResult(output=response)
