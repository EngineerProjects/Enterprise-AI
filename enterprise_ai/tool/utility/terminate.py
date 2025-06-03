"""Terminate tool for Enterprise AI."""

from typing import Any, Dict, Optional, Set, Union

from enterprise_ai.tool.core.base import BaseTool, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.utility.terminate")


@register_tool(category="utility")
class TerminateTool(BaseTool):
    """
    Tool to signal the completion or termination of a task or conversation.

    Key capabilities:
    * Signal successful completion of tasks
    * Indicate failure or inability to proceed
    * Provide explanatory messages about termination
    * Mark the end of a work session
    * Support graceful shutdown of processes

    Use this tool when:
    * All requested tasks have been completed successfully
    * A roadblock prevents further progress on the task
    * The conversation has reached its natural conclusion
    * You need to indicate task completion status
    * You need to provide a final summary before ending

    Notes:
    * Always include a status (success/failure) when terminating
    * Provide a clear message explaining the reason for termination
    * The terminate command is final and ends the interaction
    """

    name: str = "terminate"
    description: str = """
    Signal the end of an interaction when tasks are completed or cannot proceed.

    * Purpose: Indicate when work is finished or when progress is not possible
    * Usage: Call this tool when all tasks are complete or when blocked
    * Features: Status indication, explanatory messages
    * Returns: Final status with optional explanatory message

    When terminating, always provide a status ('success' or 'failure') and optionally
    include a message explaining the completion or the roadblock encountered.
    """

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
        "additionalProperties": False,
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.UTILITY}

    def __init__(self, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the Terminate tool."""
        super().__init__(**kwargs)
        self.config = config or ToolConfig()
        logger.debug("TerminateTool initialized")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the termination with the specified status and message."""
        status = kwargs.get("status")
        if not status:
            logger.error("Missing required 'status' parameter")
            return ToolResult(
                tool_call_id="", 
                name=self.name, 
                result="", 
                error="Status parameter is required"
            )

        message = kwargs.get("message")

        if status not in ["success", "failure"]:
            logger.error(f"Invalid status value: {status}")
            return ToolResult(
                tool_call_id="", 
                name=self.name, 
                result="", 
                error=f"Invalid status: {status}. Must be 'success' or 'failure'"
            )

        # Log the termination
        log_message = message or "No message provided"
        if status == "success":
            logger.info(f"Interaction terminated successfully: {log_message}")
        else:
            logger.warning(f"Interaction terminated with failure: {log_message}")

        # Format the response
        response = f"The interaction has been completed with status: {status}"
        if message:
            response += f"\nMessage: {message}"

        return ToolResult(tool_call_id="", name=self.name, result=response)

    async def cleanup(self) -> None:
        """Clean up resources used by the terminate tool."""
        logger.debug("TerminateTool cleanup completed")