"""Planning tool for Enterprise AI."""

import asyncio
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.logger import get_logger

logger = get_logger("tool.planning.planning")

class PlanningTool(BaseTool):
    """Planning tool for creating and managing structured task plans."""

    name: str = "planning"
    short_description: str = "Create and manage structured task plans with step tracking and status updates."
    description: str = "Create and manage structured task plans with step tracking and status management"
    
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "Command to execute",
                "enum": ["create", "update", "list", "get", "set_active", "mark_step", "delete"],
                "type": "string",
            },
            "plan_id": {
                "description": "Plan identifier",
                "type": "string",
            },
            "title": {
                "description": "Plan title",
                "type": "string",
            },
            "steps": {
                "description": "List of plan steps",
                "type": "array",
                "items": {"type": "string"},
            },
            "step_index": {
                "description": "Step index (0-based)",
                "type": "integer",
            },
            "step_status": {
                "description": "Step status",
                "enum": ["not_started", "in_progress", "completed", "blocked"],
                "type": "string",
            },
            "step_notes": {
                "description": "Step notes",
                "type": "string",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.PLANNING}
    
    # Internal state
    plans: Dict[str, Dict[str, Any]] = Field(default_factory=dict, exclude=True)
    active_plan_id: Optional[str] = Field(default=None, exclude=True)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.plans = {}
        self.active_plan_id = None
        logger.debug("PlanningTool initialized")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute planning command."""
        command = kwargs.get("command")
        if not command:
            return ToolResult.create_error("Missing 'command' parameter", self.name)

        logger.info(f"Executing: {command}")

        try:
            if command == "create":
                return self._create_plan(
                    kwargs.get("plan_id"), 
                    kwargs.get("title"), 
                    kwargs.get("steps")
                )
            elif command == "update":
                return self._update_plan(
                    kwargs.get("plan_id"), 
                    kwargs.get("title"), 
                    kwargs.get("steps")
                )
            elif command == "list":
                return self._list_plans()
            elif command == "get":
                return self._get_plan(kwargs.get("plan_id"))
            elif command == "set_active":
                return self._set_active_plan(kwargs.get("plan_id"))
            elif command == "mark_step":
                return self._mark_step(
                    kwargs.get("plan_id"),
                    kwargs.get("step_index"),
                    kwargs.get("step_status"),
                    kwargs.get("step_notes")
                )
            elif command == "delete":
                return self._delete_plan(kwargs.get("plan_id"))
            else:
                return ToolResult.create_error(f"Unknown command: {command}", self.name)
                
        except Exception as e:
            logger.error(f"Error in {command}: {e}")
            return ToolResult.create_error(f"Command failed: {str(e)}", self.name)

    def _create_plan(self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]) -> ToolResult:
        """Create new plan."""
        if not plan_id:
            return ToolResult.create_error("plan_id required", self.name)
        if plan_id in self.plans:
            return ToolResult.create_error(f"Plan '{plan_id}' already exists", self.name)
        if not title:
            return ToolResult.create_error("title required", self.name)
        if not steps or not isinstance(steps, list):
            return ToolResult.create_error("steps must be non-empty list", self.name)

        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
        }

        self.plans[plan_id] = plan
        self.active_plan_id = plan_id
        logger.info(f"Created plan: {plan_id}")
        
        return ToolResult.create_success(
            f"Plan '{plan_id}' created\n\n{self._format_plan(plan)}", 
            self.name
        )

    def _update_plan(self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]) -> ToolResult:
        """Update existing plan."""
        if not plan_id:
            return ToolResult.create_error("plan_id required", self.name)
        if plan_id not in self.plans:
            return ToolResult.create_error(f"Plan '{plan_id}' not found", self.name)

        plan = self.plans[plan_id]
        
        if title:
            plan["title"] = title
            
        if steps:
            if not isinstance(steps, list):
                return ToolResult.create_error("steps must be list", self.name)
                
            # Preserve existing statuses where possible
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]
            
            new_statuses = []
            new_notes = []
            
            for i, step in enumerate(steps):
                if i < len(old_statuses):
                    new_statuses.append(old_statuses[i])
                    new_notes.append(old_notes[i])
                else:
                    new_statuses.append("not_started")
                    new_notes.append("")
            
            plan["steps"] = steps
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes

        logger.info(f"Updated plan: {plan_id}")
        return ToolResult.create_success(
            f"Plan '{plan_id}' updated\n\n{self._format_plan(plan)}", 
            self.name
        )

    def _list_plans(self) -> ToolResult:
        """List all plans."""
        if not self.plans:
            return ToolResult.create_success("No plans available", self.name)

        output = "Plans:\n"
        for plan_id, plan in self.plans.items():
            active_marker = " (active)" if plan_id == self.active_plan_id else ""
            completed = sum(1 for status in plan["step_statuses"] if status == "completed")
            total = len(plan["steps"])
            output += f"• {plan_id}{active_marker}: {plan['title']} ({completed}/{total})\n"

        return ToolResult.create_success(output, self.name)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Get plan details."""
        if not plan_id:
            if not self.active_plan_id:
                return ToolResult.create_error("No active plan and no plan_id specified", self.name)
            plan_id = self.active_plan_id

        if plan_id not in self.plans:
            return ToolResult.create_error(f"Plan '{plan_id}' not found", self.name)

        plan = self.plans[plan_id]
        return ToolResult.create_success(self._format_plan(plan), self.name)

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Set active plan."""
        if not plan_id:
            return ToolResult.create_error("plan_id required", self.name)
        if plan_id not in self.plans:
            return ToolResult.create_error(f"Plan '{plan_id}' not found", self.name)

        self.active_plan_id = plan_id
        plan = self.plans[plan_id]
        return ToolResult.create_success(
            f"Active plan: {plan_id}\n\n{self._format_plan(plan)}", 
            self.name
        )

    def _mark_step(self, plan_id: Optional[str], step_index: Optional[int], 
                   step_status: Optional[str], step_notes: Optional[str]) -> ToolResult:
        """Mark step status."""
        if not plan_id:
            if not self.active_plan_id:
                return ToolResult.create_error("No active plan and no plan_id specified", self.name)
            plan_id = self.active_plan_id

        if plan_id not in self.plans:
            return ToolResult.create_error(f"Plan '{plan_id}' not found", self.name)

        if step_index is None:
            return ToolResult.create_error("step_index required", self.name)

        plan = self.plans[plan_id]
        
        if step_index < 0 or step_index >= len(plan["steps"]):
            return ToolResult.create_error(
                f"Invalid step_index: {step_index} (0-{len(plan['steps'])-1})", 
                self.name
            )

        valid_statuses = ["not_started", "in_progress", "completed", "blocked"]
        if step_status and step_status not in valid_statuses:
            return ToolResult.create_error(f"Invalid status: {step_status}", self.name)

        if step_status:
            plan["step_statuses"][step_index] = step_status
        if step_notes:
            plan["step_notes"][step_index] = step_notes

        return ToolResult.create_success(
            f"Step {step_index} updated\n\n{self._format_plan(plan)}", 
            self.name
        )

    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:
        """Delete plan."""
        if not plan_id:
            return ToolResult.create_error("plan_id required", self.name)
        if plan_id not in self.plans:
            return ToolResult.create_error(f"Plan '{plan_id}' not found", self.name)

        del self.plans[plan_id]
        if self.active_plan_id == plan_id:
            self.active_plan_id = None

        return ToolResult.create_success(f"Plan '{plan_id}' deleted", self.name)

    def _format_plan(self, plan: Dict[str, Any]) -> str:
        """Format plan for display."""
        output = f"Plan: {plan['title']} (ID: {plan['plan_id']})\n"
        
        # Progress stats
        total = len(plan["steps"])
        completed = sum(1 for status in plan["step_statuses"] if status == "completed")
        in_progress = sum(1 for status in plan["step_statuses"] if status == "in_progress")
        blocked = sum(1 for status in plan["step_statuses"] if status == "blocked")
        
        percentage = (completed / total * 100) if total > 0 else 0
        output += f"Progress: {completed}/{total} ({percentage:.0f}%)\n"
        
        if in_progress > 0 or blocked > 0:
            output += f"Status: {in_progress} in progress, {blocked} blocked\n"
        
        output += "\nSteps:\n"
        
        # Format steps
        status_symbols = {
            "not_started": "[ ]",
            "in_progress": "[→]", 
            "completed": "[✓]",
            "blocked": "[!]",
        }
        
        for i, (step, status, notes) in enumerate(
            zip(plan["steps"], plan["step_statuses"], plan["step_notes"])
        ):
            symbol = status_symbols.get(status, "[ ]")
            output += f"{i}. {symbol} {step}\n"
            if notes:
                output += f"   Notes: {notes}\n"

        return output

    async def cleanup(self) -> None:
        """Clean up resources."""
        self.plans.clear()
        self.active_plan_id = None
        logger.debug("PlanningTool cleanup completed")