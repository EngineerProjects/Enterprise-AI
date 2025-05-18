"""
Agent-specific workflow nodes for Enterprise AI.

This module provides workflow nodes that integrate with the agent system.
"""

import asyncio
import time
from typing import Any, Dict, Optional, Set, cast

from enterprise_ai.agent.core.types import AgentProtocol, Task, TaskStatus
from enterprise_ai.flow.node import BaseNode
from enterprise_ai.flow.types import NodeStatus
from enterprise_ai.logger import get_logger

logger = get_logger("flow.nodes.agent")


class AgentTaskNode(BaseNode):
    """Node that assigns a task to a specific agent."""

    def __init__(
        self,
        name: str,
        agent: AgentProtocol,
        task_description: str,
        dependencies: Optional[Set[str]] = None,
        node_id: Optional[str] = None,
        result_key: str = "result",
        timeout: float = 60.0,
    ):
        """Initialize an agent task node.

        Args:
            name: Human-readable name
            agent: Agent to assign the task to
            task_description: Description of the task
            dependencies: Optional set of node IDs this node depends on
            node_id: Optional node ID (generated if not provided)
            result_key: Key to use for storing the result in the context
            timeout: Maximum time to wait for task completion in seconds
        """
        super().__init__(name, dependencies, node_id)
        self._agent = agent
        self._task_description = task_description
        self._result_key = result_key
        self._timeout = timeout

    async def _execute_internal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the node by assigning a task to the agent.

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

        logger.info(f"Assigning task to agent {self._agent.id}: {task_desc}")

        # Assign task to agent
        success = self._agent.assign_task(task)
        if not success:
            self.status = NodeStatus.FAILED
            raise RuntimeError(f"Failed to assign task to agent {self._agent.id}")

        # Process the task
        start_time = time.time()
        status = TaskStatus.PENDING

        # Wait for task to complete or timeout
        while status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            # Check timeout
            if time.time() - start_time > self._timeout:
                self.status = NodeStatus.FAILED
                raise TimeoutError(f"Task execution timed out after {self._timeout} seconds")

            # Process the task
            status = self._agent.process_task()

            # If not done, wait a bit
            if status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                await asyncio.sleep(0.5)

        # Check result
        if status == TaskStatus.FAILED:
            self.status = NodeStatus.FAILED
            raise RuntimeError("Agent failed to complete the task")

        # Extract result from task metadata
        task = cast(Task, self._agent.state.current_task)
        if task and task.metadata:
            result = task.metadata.get("response", "No response available")
        else:
            result = "Task completed but no result available"

        logger.info(f"Agent {self._agent.id} completed task: {result}")
        return {self._result_key: result}

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
