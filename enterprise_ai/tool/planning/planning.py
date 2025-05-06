"""Planning tool for Enterprise AI."""

import asyncio
from typing import Any, Dict, List, Literal, Optional, Set, Union
from pydantic import Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.planning.planning")


@register_tool(category="planning")
class PlanningTool(BaseTool):
    """
    A planning tool for creating and managing structured task plans.

    Key capabilities:
    * Create detailed plans with titled steps
    * Track progress and status of individual steps
    * Update and modify existing plans
    * Mark steps as completed, in progress, or blocked
    * Maintain multiple plans simultaneously
    * Add notes to individual plan steps

    Use this tool when:
    * You need to break down complex tasks into manageable steps
    * You want to track progress on multi-step processes
    * You need to organize work into a structured format
    * You want to document dependencies or blockers in a workflow
    * You need to collaborate on a sequence of operations

    Notes:
    * Plans are stored for the duration of the session
    * One plan can be set as the "active" plan for simplified access
    * Plans track completion status automatically
    * Each step can have its own status and notes
    """

    name: str = "planning"
    description: str = """
    A planning tool that allows the creation and management of structured task plans.
    
    * Purpose: Create, update, and track progress on multi-step plans
    * Usage: Break down complex tasks, track step completion, document workflows
    * Features: Step status tracking, plan management, progress monitoring
    * Returns: Plan details, step status, and progress metrics
    
    Plans can be created with multiple steps, and each step can be marked with statuses
    like "not_started", "in_progress", "completed", or "blocked". Multiple plans can
    be maintained simultaneously, with one designated as the active plan.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The command to execute. Available commands: create, update, list, get, set_active, mark_step, delete.",
                "enum": [
                    "create",
                    "update",
                    "list",
                    "get",
                    "set_active",
                    "mark_step",
                    "delete",
                ],
                "type": "string",
            },
            "plan_id": {
                "description": "Unique identifier for the plan. Required for create, update, set_active, and delete commands. Optional for get and mark_step (uses active plan if not specified).",
                "type": "string",
            },
            "title": {
                "description": "Title for the plan. Required for create command, optional for update command.",
                "type": "string",
            },
            "steps": {
                "description": "List of plan steps. Required for create command, optional for update command.",
                "type": "array",
                "items": {"type": "string"},
            },
            "step_index": {
                "description": "Index of the step to update (0-based). Required for mark_step command.",
                "type": "integer",
            },
            "step_status": {
                "description": "Status to set for a step. Used with mark_step command.",
                "enum": ["not_started", "in_progress", "completed", "blocked"],
                "type": "string",
            },
            "step_notes": {
                "description": "Additional notes for a step. Optional for mark_step command.",
                "type": "string",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    # Define tool capabilities
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.PLANNING}

    # Tool fields
    plans: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Dictionary of active plans"
    )
    current_plan_id: Optional[str] = Field(default=None, description="Currently active plan ID")

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the planning tool with standard parameters.

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

        # Initialize plans and current plan ID
        self.plans = {}
        self._current_plan_id = None

        logger.debug("PlanningTool initialized")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the planning tool with the given command and parameters.

        Args:
            **kwargs: Keyword arguments including:
                command: The operation to perform (create, update, list, get, set_active, mark_step, delete)
                plan_id: Unique identifier for the plan
                title: Title for the plan (used with create command)
                steps: List of steps for the plan (used with create command)
                step_index: Index of the step to update (used with mark_step command)
                step_status: Status to set for a step (used with mark_step command)
                step_notes: Additional notes for a step (used with mark_step command)

        Returns:
            ToolResult containing the result of the operation
        """
        # Extract parameters from kwargs
        command = kwargs.get("command")
        if not command:
            logger.error("Missing required 'command' parameter")
            return ToolResult(error="Parameter 'command' is required")

        plan_id = kwargs.get("plan_id")
        title = kwargs.get("title")
        steps = kwargs.get("steps")
        step_index = kwargs.get("step_index")
        step_status = kwargs.get("step_status")
        step_notes = kwargs.get("step_notes")

        logger.info(f"Executing planning command: {command}")

        try:
            # Apply timeout from config if needed
            timeout = self.config.timeout if hasattr(self.config, "timeout") else None

            # Execute appropriate command
            if command == "create":
                return self._create_plan(plan_id, title, steps)
            elif command == "update":
                return self._update_plan(plan_id, title, steps)
            elif command == "list":
                return self._list_plans()
            elif command == "get":
                return self._get_plan(plan_id)
            elif command == "set_active":
                return self._set_active_plan(plan_id)
            elif command == "mark_step":
                return self._mark_step(plan_id, step_index, step_status, step_notes)
            elif command == "delete":
                return self._delete_plan(plan_id)
            else:
                logger.error(f"Unrecognized command: {command}")
                return ToolResult(
                    error=f"Unrecognized command: {command}. Allowed commands are: create, update, list, get, set_active, mark_step, delete"
                )
        except Exception as e:
            logger.error(f"Error executing planning command {command}: {e}")
            return ToolResult(error=f"Error executing command: {str(e)}")

    def _create_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """
        Create a new plan with the given ID, title, and steps.

        Args:
            plan_id: ID of the plan to create
            title: Title for the new plan
            steps: List of steps for the plan

        Returns:
            ToolResult with the created plan details
        """
        if not plan_id:
            logger.error("Missing required 'plan_id' parameter")
            return ToolResult(error="Parameter `plan_id` is required for command: create")

        if plan_id in self.plans:
            logger.warning(f"Plan with ID '{plan_id}' already exists")
            return ToolResult(
                error=f"A plan with ID '{plan_id}' already exists. Use 'update' to modify existing plans."
            )

        if not title:
            logger.error("Missing required 'title' parameter")
            return ToolResult(error="Parameter `title` is required for command: create")

        if (
            not steps
            or not isinstance(steps, list)
            or not all(isinstance(step, str) for step in steps)
        ):
            logger.error("Invalid or missing 'steps' parameter")
            return ToolResult(
                error="Parameter `steps` must be a non-empty list of strings for command: create"
            )

        # Create a new plan with initialized step statuses
        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
        }

        self.plans[plan_id] = plan
        self._current_plan_id = plan_id  # Set as active plan

        logger.info(f"Created new plan: {plan_id}")

        return ToolResult(
            output=f"Plan created successfully with ID: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _update_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """
        Update an existing plan with new title or steps.

        Args:
            plan_id: ID of the plan to update
            title: New title for the plan (optional)
            steps: New list of steps for the plan (optional)

        Returns:
            ToolResult with the updated plan details
        """
        if not plan_id:
            logger.error("Missing required 'plan_id' parameter")
            return ToolResult(error="Parameter `plan_id` is required for command: update")

        if plan_id not in self.plans:
            logger.warning(f"Plan with ID '{plan_id}' not found")
            return ToolResult(error=f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]

        # Log what we're updating
        if title:
            logger.debug(f"Updating title for plan {plan_id}")
        if steps:
            logger.debug(f"Updating steps for plan {plan_id}")

        if title:
            plan["title"] = title

        if steps:
            if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
                logger.error("Invalid 'steps' parameter")
                return ToolResult(
                    error="Parameter `steps` must be a list of strings for command: update"
                )

            # Preserve existing step statuses for unchanged steps
            old_steps = plan["steps"]
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]

            # Create new step statuses and notes
            new_statuses = []
            new_notes = []

            for i, step in enumerate(steps):
                # If the step exists at the same position in old steps, preserve status and notes
                if i < len(old_steps) and step == old_steps[i]:
                    new_statuses.append(old_statuses[i])
                    new_notes.append(old_notes[i])
                else:
                    new_statuses.append("not_started")
                    new_notes.append("")

            plan["steps"] = steps
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes

        logger.info(f"Updated plan: {plan_id}")
        return ToolResult(
            output=f"Plan updated successfully: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _list_plans(self) -> ToolResult:
        """
        List all available plans.

        Returns:
            ToolResult with a list of available plans
        """
        if not self.plans:
            logger.info("No plans available")
            return ToolResult(output="No plans available. Create a plan with the 'create' command.")

        output = "Available plans:\n"
        for plan_id, plan in self.plans.items():
            current_marker = " (active)" if plan_id == self._current_plan_id else ""
            completed = sum(1 for status in plan["step_statuses"] if status == "completed")
            total = len(plan["steps"])
            progress = f"{completed}/{total} steps completed"
            output += f"• {plan_id}{current_marker}: {plan['title']} - {progress}\n"

        logger.info(f"Listed {len(self.plans)} plans")
        return ToolResult(output=output)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:
        """
        Get details of a specific plan.

        Args:
            plan_id: ID of the plan to retrieve (uses active plan if None)

        Returns:
            ToolResult with plan details
        """
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                logger.warning("No active plan and no plan_id specified")
                return ToolResult(
                    error="No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id
            logger.debug(f"Using active plan: {plan_id}")

        if plan_id not in self.plans:
            logger.warning(f"Plan with ID '{plan_id}' not found")
            return ToolResult(error=f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]
        logger.info(f"Retrieved plan details: {plan_id}")
        return ToolResult(output=self._format_plan(plan))

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:
        """
        Set a plan as the active plan.

        Args:
            plan_id: ID of the plan to set as active

        Returns:
            ToolResult confirming the active plan
        """
        if not plan_id:
            logger.error("Missing required 'plan_id' parameter")
            return ToolResult(error="Parameter `plan_id` is required for command: set_active")

        if plan_id not in self.plans:
            logger.warning(f"Plan with ID '{plan_id}' not found")
            return ToolResult(error=f"No plan found with ID: {plan_id}")

        self._current_plan_id = plan_id
        logger.info(f"Set active plan: {plan_id}")
        return ToolResult(
            output=f"Plan '{plan_id}' is now the active plan.\n\n{self._format_plan(self.plans[plan_id])}"
        )

    def _mark_step(
        self,
        plan_id: Optional[str],
        step_index: Optional[int],
        step_status: Optional[str],
        step_notes: Optional[str],
    ) -> ToolResult:
        """
        Mark a step with a specific status and optional notes.

        Args:
            plan_id: ID of the plan (uses active plan if None)
            step_index: Index of the step to update (0-based)
            step_status: New status for the step
            step_notes: Optional notes for the step

        Returns:
            ToolResult with updated plan details
        """
        if not plan_id:
            # If no plan_id is provided, use the current active plan
            if not self._current_plan_id:
                logger.warning("No active plan and no plan_id specified")
                return ToolResult(
                    error="No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id
            logger.debug(f"Using active plan: {plan_id}")

        if plan_id not in self.plans:
            logger.warning(f"Plan with ID '{plan_id}' not found")
            return ToolResult(error=f"No plan found with ID: {plan_id}")

        if step_index is None:
            logger.error("Missing required 'step_index' parameter")
            return ToolResult(error="Parameter `step_index` is required for command: mark_step")

        plan = self.plans[plan_id]

        if step_index < 0 or step_index >= len(plan["steps"]):
            logger.error(f"Step index out of range: {step_index}")
            return ToolResult(
                error=f"Invalid step_index: {step_index}. Valid indices range from 0 to {len(plan['steps']) - 1}."
            )

        if step_status and step_status not in [
            "not_started",
            "in_progress",
            "completed",
            "blocked",
        ]:
            logger.error(f"Invalid step status: {step_status}")
            return ToolResult(
                error=f"Invalid step_status: {step_status}. Valid statuses are: not_started, in_progress, completed, blocked"
            )

        # Update step status if provided
        if step_status:
            logger.debug(f"Updating step {step_index} status to {step_status}")
            plan["step_statuses"][step_index] = step_status

        # Update step notes if provided
        if step_notes:
            logger.debug(f"Updating step {step_index} notes")
            plan["step_notes"][step_index] = step_notes

        logger.info(f"Updated step {step_index} in plan {plan_id}")
        return ToolResult(
            output=f"Step {step_index} updated in plan '{plan_id}'.\n\n{self._format_plan(plan)}"
        )

    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:
        """
        Delete a plan.

        Args:
            plan_id: ID of the plan to delete

        Returns:
            ToolResult confirming the deletion
        """
        if not plan_id:
            logger.error("Missing required 'plan_id' parameter")
            return ToolResult(error="Parameter `plan_id` is required for command: delete")

        if plan_id not in self.plans:
            logger.warning(f"Plan with ID '{plan_id}' not found")
            return ToolResult(error=f"No plan found with ID: {plan_id}")

        del self.plans[plan_id]

        # If the deleted plan was the active plan, clear the active plan
        if self._current_plan_id == plan_id:
            self._current_plan_id = None

        logger.info(f"Deleted plan: {plan_id}")
        return ToolResult(output=f"Plan '{plan_id}' has been deleted.")

    def _format_plan(self, plan: Dict[str, Any]) -> str:
        """
        Format a plan for display.

        Args:
            plan: Plan data to format

        Returns:
            Formatted plan as string
        """
        output = f"Plan: {plan['title']} (ID: {plan['plan_id']})\n"
        output += "=" * len(output) + "\n\n"

        # Calculate progress statistics
        total_steps = len(plan["steps"])
        completed = sum(1 for status in plan["step_statuses"] if status == "completed")
        in_progress = sum(1 for status in plan["step_statuses"] if status == "in_progress")
        blocked = sum(1 for status in plan["step_statuses"] if status == "blocked")
        not_started = sum(1 for status in plan["step_statuses"] if status == "not_started")

        output += f"Progress: {completed}/{total_steps} steps completed "
        if total_steps > 0:
            percentage = (completed / total_steps) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"

        output += f"Status: {completed} completed, {in_progress} in progress, {blocked} blocked, {not_started} not started\n\n"
        output += "Steps:\n"

        # Add each step with its status and notes
        for i, (step, status, notes) in enumerate(
            zip(plan["steps"], plan["step_statuses"], plan["step_notes"])
        ):
            status_symbol = {
                "not_started": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
                "blocked": "[!]",
            }.get(status, "[ ]")

            output += f"{i}. {status_symbol} {step}\n"
            if notes:
                output += f"   Notes: {notes}\n"

        return output

    async def cleanup(self) -> None:
        """Clean up resources used by the planning tool."""
        # No resources to clean up for this tool
        logger.debug("PlanningTool cleanup completed")
