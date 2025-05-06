"""Terminate tool for Enterprise AI."""

from typing import Any, Dict, Literal, Optional, Set, Union

from pydantic import Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.utility.terminate")


@register_tool(category="utility")
class Terminate(BaseTool):
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
    }

    # Define capabilities
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.UTILITY}

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Terminate tool with standard parameters.

        Args:
            name: Override for tool name
            description: Override for tool description
            parameters: Override for tool parameters schema
            config: Tool configuration settings
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            name=name or self.name,
            description=description or self.description,
            parameters=parameters or self.parameters,
        )

        # Store tool configuration
        self.config = config or ToolConfig()

        logger.debug("Terminate tool initialized")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the termination with the specified status and message.

        Args:
            **kwargs: Keyword arguments including:
                status: The termination status ('success' or 'failure')
                message: Optional explanation message

        Returns:
            ToolResult with termination status and message
        """
        status = kwargs.get("status")
        if not status:
            logger.error("Missing required 'status' parameter")
            return ToolResult(error="Status parameter is required")

        message = kwargs.get("message")

        if status not in ["success", "failure"]:
            logger.error(f"Invalid status value: {status}")
            return ToolResult(error=f"Invalid status: {status}. Must be 'success' or 'failure'")

        # Log the termination
        if status == "success":
            logger.info(f"Interaction terminated successfully: {message or 'No message provided'}")
        else:
            logger.warning(
                f"Interaction terminated with failure: {message or 'No message provided'}"
            )

        # Format the response
        response = f"The interaction has been completed with status: {status}"
        if message:
            response += f"\nMessage: {message}"

        return ToolResult(output=response)

    async def cleanup(self) -> None:
        """Clean up resources used by the terminate tool."""
        # No resources to clean up for this tool
        logger.debug("Terminate tool cleanup completed")
