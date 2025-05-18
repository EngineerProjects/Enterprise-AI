"""
Team-specific workflow nodes for Enterprise AI.

This module provides workflow nodes that integrate with the team system.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Set

from enterprise_ai.agent.core.types import Task, TaskStatus
from enterprise_ai.flow.node import BaseNode
from enterprise_ai.flow.types import NodeStatus
from enterprise_ai.flow.types import FlowTeamProtocol
from enterprise_ai.logger import get_logger

logger = get_logger("flow.nodes.team")


class TeamTaskNode(BaseNode):
    """Node that assigns a task to a team."""

    def __init__(
        self,
        name: str,
        team: FlowTeamProtocol,
        task_description: str,
        target_agent_id: Optional[str] = None,
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
        result_key: str = "result",
        timeout: float = 300.0,
    ):
        """Initialize a team task node.

        Args:
            name: Human-readable name
            team: Team to assign the task to
            task_description: Description of the task
            target_agent_id: Optional ID of a specific agent in the team
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
            result_key: Key to use for storing the result in the context
            timeout: Maximum time to wait for task completion in seconds
        """
        super().__init__(name, dependencies, node_id)
        self._team = team
        self._task_description = task_description
        self._target_agent_id = target_agent_id
        self._result_key = result_key
        self._timeout = timeout

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the node by assigning a task to the team.

        Args:
            context: Workflow execution context

        Returns:
            Dictionary with the task result
        """
        # Create a task with relevant context
        task_desc = self._format_task_description(context)
        task = Task(
            id=f"flow-{self.id}",
            description=task_desc,
            status=TaskStatus.PENDING,
            metadata={"flow_node_id": self.id, "flow_context": context},
        )

        logger.info(f"Assigning task to team {self._team.id}: {task_desc}")

        # Assign task to team
        if self._target_agent_id:
            logger.info(f"Targeting specific agent {self._target_agent_id}")
            success = self._team.assign_task(task, self._target_agent_id)
        else:
            success = self._team.assign_task(task)

        if not success:
            self.status = NodeStatus.FAILED
            raise RuntimeError(f"Failed to assign task to team {self._team.id}")

        # For team tasks, we don't have a direct way to monitor progress
        # So we'll use the team coordinator if available, or just wait for timeout
        if hasattr(self._team, "get_task_status"):
            # Use team coordinator to monitor task
            return await self._monitor_with_coordinator(task.id, context)
        else:
            # Just wait for a fixed time
            logger.info(f"No team coordinator available, waiting for {self._timeout} seconds")
            await asyncio.sleep(self._timeout)
            return {self._result_key: f"Task assigned to team {self._team.id}"}

    async def _monitor_with_coordinator(
        self, task_id: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Monitor task execution using a team coordinator.

        Args:
            task_id: ID of the task to monitor
            context: Workflow execution context

        Returns:
            Dictionary with the task result
        """
        start_time = time.time()

        while True:
            # Check timeout
            if time.time() - start_time > self._timeout:
                self.status = NodeStatus.FAILED
                raise TimeoutError(f"Task execution timed out after {self._timeout} seconds")

            # Check task status
            status_info = self._team.get_task_status(task_id)
            if not status_info:
                # Wait and try again
                await asyncio.sleep(1)
                continue

            status, agent_id = status_info

            if status == TaskStatus.COMPLETED:
                # Get result
                result = self._team.collect_result(task_id)
                if result:
                    logger.info(f"Team {self._team.id} completed task: {result.data}")
                    return {self._result_key: result.data}
                else:
                    return {self._result_key: f"Task completed by agent {agent_id}"}

            elif status == TaskStatus.FAILED:
                self.status = NodeStatus.FAILED
                raise RuntimeError(f"Task failed: {agent_id}")

            # Wait before checking again
            await asyncio.sleep(1)

    def _format_task_description(self, context: Dict[str, Any]) -> str:
        """Format the task description with context variables.

        Args:
            context: Workflow execution context

        Returns:
            Formatted task description
        """
        # Simple template substitution
        desc = self._task_description
        for key, value in context.items():
            # Only substitute string, number, or boolean values
            if isinstance(value, (str, int, float, bool)):
                desc = desc.replace(f"{{{key}}}", str(value))

        return desc
