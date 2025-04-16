"""
Team coordinator for Enterprise AI.

This module provides a coordinator for managing task delegation,
tracking, and result collection within teams.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, cast
from collections import deque, defaultdict

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.message import (
    BaseAgentMessage,
    QueryMessage,
    TaskAssignmentMessage,
    TaskUpdateMessage,
    create_message,
)
from enterprise_ai.team.types import TeamProtocol
from enterprise_ai.logger import get_logger

logger = get_logger("team.coordinator")


class TaskResult:
    """Container for task execution results."""

    def __init__(
        self,
        task_id: str,
        status: TaskStatus,
        agent_id: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        completed_at: Optional[float] = None,
    ):
        """Initialize a task result.

        Args:
            task_id: ID of the completed task
            status: Final status of the task
            agent_id: ID of the agent that completed the task
            data: Optional result data
            error: Optional error message
            completed_at: Optional timestamp of completion
        """
        self.task_id = task_id
        self.status = status
        self.agent_id = agent_id
        self.data = data or {}
        self.error = error
        self.completed_at = completed_at or time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation
        """
        return {
            "task_id": self.task_id,
            "status": self.status.name,
            "agent_id": self.agent_id,
            "data": self.data,
            "error": self.error,
            "completed_at": self.completed_at,
        }


class TeamCoordinator:
    """Coordinator for task delegation and result collection.

    This class manages the assignment of tasks to appropriate team members,
    tracks task status, and collects results.
    """

    def __init__(self, team: TeamProtocol):
        """Initialize a team coordinator.

        Args:
            team: Team to coordinate
        """
        self.team = team
        self._task_queue: deque[Task] = deque()
        self._task_assignments: Dict[str, str] = {}  # task_id -> agent_id
        self._task_results: Dict[str, TaskResult] = {}
        self._task_dependencies: Dict[str, Set[str]] = defaultdict(
            set
        )  # task_id -> dependency task_ids
        self._dependent_tasks: Dict[str, Set[str]] = defaultdict(
            set
        )  # task_id -> dependent task_ids
        self._pending_dependencies: Dict[str, Set[str]] = defaultdict(
            set
        )  # task_id -> pending dependency task_ids
        logger.info(f"Initialized team coordinator for team {team.id}")

    def submit_task(self, task: Task, dependencies: Optional[List[str]] = None) -> bool:
        """Submit a task for execution by the team.

        Args:
            task: Task to execute
            dependencies: Optional list of task IDs that must complete before this task

        Returns:
            True if task was submitted, False otherwise
        """
        # Check if task already exists
        if task.id in self._task_assignments or task.id in self._task_results:
            logger.warning(f"Task {task.id} already exists in coordinator")
            return False

        # Record dependencies if specified
        if dependencies:
            for dep_id in dependencies:
                # Check if dependency exists and is not already completed
                if dep_id not in self._task_assignments and dep_id not in self._task_results:
                    logger.warning(f"Dependency task {dep_id} does not exist")
                    return False

                # Add dependency relationship
                self._task_dependencies[task.id].add(dep_id)
                self._dependent_tasks[dep_id].add(task.id)

                # If dependency is not completed, add to pending
                if dep_id not in self._task_results:
                    self._pending_dependencies[task.id].add(dep_id)

        # If task has pending dependencies, don't add to queue yet
        if task.id in self._pending_dependencies and self._pending_dependencies[task.id]:
            logger.info(f"Task {task.id} has pending dependencies, will execute later")
            return True

        # Add to queue for immediate execution
        self._task_queue.append(task)
        logger.info(f"Submitted task {task.id} to team {self.team.id}")
        return True

    def process_tasks(self, max_tasks: int = 10) -> int:
        """Process pending tasks up to the specified limit.

        Args:
            max_tasks: Maximum number of tasks to process

        Returns:
            Number of tasks processed
        """
        processed = 0

        while processed < max_tasks and self._task_queue:
            task = self._task_queue.popleft()
            assigned = self._assign_task(task)

            if assigned:
                processed += 1
            else:
                # Put task back in queue if assignment failed
                self._task_queue.append(task)
                # Avoid infinite loop if task can't be assigned
                logger.warning(f"Failed to assign task {task.id}, putting back in queue")
                break

        return processed

    def _assign_task(self, task: Task) -> bool:
        """Assign a task to an appropriate team member.

        This method implements the logic for choosing the best agent
        for a task based on capabilities and current load.

        Args:
            task: Task to assign

        Returns:
            True if task was assigned, False otherwise
        """
        # Extract task metadata to look for hints
        metadata = task.metadata or {}

        # Check if there's a suggested agent
        suggested_agent_id = metadata.get("suggested_agent")
        if suggested_agent_id:
            success = self.team.assign_task(task, suggested_agent_id)
            if success:
                self._task_assignments[task.id] = suggested_agent_id
                logger.info(f"Assigned task {task.id} to suggested agent {suggested_agent_id}")
                return True

        # Check if there's a required capability
        required_capability = metadata.get("required_capability")
        if required_capability:
            # Find agents with the required capability
            capable_agents = []

            # Check manager
            try:
                manager = self.team.manager
                # Safely check for role attribute
                if hasattr(manager, "role"):
                    manager_role = getattr(manager, "role")
                    if manager_role and required_capability in manager_role.capabilities:
                        capable_agents.append(manager.id)
            except (RuntimeError, AttributeError):
                # No manager or no manager role
                pass

            # Check members
            for agent_id, agent in self.team.members.items():
                # Safely check for role attribute
                if hasattr(agent, "role"):
                    agent_role = getattr(agent, "role")
                    if agent_role and required_capability in agent_role.capabilities:
                        capable_agents.append(agent_id)

            # Assign to first available capable agent
            for agent_id in capable_agents:
                success = self.team.assign_task(task, agent_id)
                if success:
                    self._task_assignments[task.id] = agent_id
                    logger.info(f"Assigned task {task.id} to capable agent {agent_id}")
                    return True

        # Default: let team decide
        success = self.team.assign_task(task)
        if success:
            # Determine which agent got assigned (we'll assume manager if not specified)
            agent_id = "manager"  # Default assumption
            # In a real implementation, we would need a way to track which agent
            # actually received the task, perhaps through a response message
            self._task_assignments[task.id] = agent_id
            logger.info(f"Assigned task {task.id} to team manager")
            return True

        logger.warning(f"Failed to assign task {task.id}")
        return False

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        agent_id: str,
        result_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update the status of a task and process any dependent tasks.

        Args:
            task_id: ID of the task to update
            status: New status
            agent_id: ID of the agent reporting the status
            result_data: Optional result data
            error: Optional error message

        Returns:
            True if update was processed, False otherwise
        """
        # Check if task exists
        if task_id not in self._task_assignments and task_id not in self._task_results:
            logger.warning(f"Task {task_id} not found")
            return False

        # If task is already completed, ignore
        if task_id in self._task_results:
            logger.warning(f"Task {task_id} already has a result")
            return False

        # For completed or failed tasks, record the result
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self._task_results[task_id] = TaskResult(
                task_id=task_id,
                status=status,
                agent_id=agent_id,
                data=result_data,
                error=error,
            )

            # Remove from assignments if present
            if task_id in self._task_assignments:
                del self._task_assignments[task_id]

            # Process dependent tasks
            if task_id in self._dependent_tasks:
                for dependent_id in self._dependent_tasks[task_id]:
                    # Remove this task from the dependents' pending dependencies
                    if dependent_id in self._pending_dependencies:
                        self._pending_dependencies[dependent_id].discard(task_id)

                        # If all dependencies are satisfied, queue the dependent task
                        if not self._pending_dependencies[dependent_id]:
                            # Find the dependent task - it might be waiting to be processed
                            dependent_task = self._find_dependent_task(dependent_id)
                            if dependent_task:
                                self._task_queue.append(dependent_task)
                                logger.info(
                                    f"Dependencies satisfied for task {dependent_id}, queued for execution"
                                )

            logger.info(f"Recorded {status.name} result for task {task_id} from agent {agent_id}")
            return True

        # For in-progress tasks, just acknowledge
        logger.info(f"Updated task {task_id} status to {status.name}")
        return True

    def _find_dependent_task(self, task_id: str) -> Optional[Task]:
        """Find a dependent task that's waiting for dependencies.

        This is a helper method for finding tasks that are waiting for
        dependencies but haven't been queued yet.

        Args:
            task_id: ID of the task to find

        Returns:
            Task object or None if not found
        """
        # In a real implementation, we would need to have a way to
        # store and retrieve unqueued tasks. This is a placeholder.
        # For now, we'll assume we don't have the task and should
        # rely on the caller to resubmit it.
        return None

    def get_task_status(self, task_id: str) -> Optional[Tuple[TaskStatus, str]]:
        """Get the current status of a task.

        Args:
            task_id: ID of the task to check

        Returns:
            Tuple of (status, agent_id) if found, None otherwise
        """
        # Check if task has a result
        if task_id in self._task_results:
            result = self._task_results[task_id]
            return (result.status, result.agent_id)

        # Check if task is assigned
        if task_id in self._task_assignments:
            agent_id = self._task_assignments[task_id]
            # We don't know the actual status here without querying the agent
            # In a real implementation, we might want to query the agent
            return (TaskStatus.IN_PROGRESS, agent_id)

        # Check if task is in queue
        for task in self._task_queue:
            if task.id == task_id:
                return (TaskStatus.PENDING, "none")

        # Check if task has dependencies
        if task_id in self._pending_dependencies and self._pending_dependencies[task_id]:
            return (TaskStatus.BLOCKED, "none")

        return None

    def collect_result(self, task_id: str) -> Optional[TaskResult]:
        """Get the result of a completed task.

        Args:
            task_id: ID of the task

        Returns:
            TaskResult if task is completed, None otherwise
        """
        return self._task_results.get(task_id)

    def collect_all_results(self) -> Dict[str, TaskResult]:
        """Get all task results.

        Returns:
            Dictionary of all task results
        """
        return self._task_results.copy()

    def get_pending_tasks(self) -> List[str]:
        """Get IDs of pending tasks.

        Returns:
            List of pending task IDs
        """
        return [task.id for task in self._task_queue]

    def get_active_tasks(self) -> Dict[str, str]:
        """Get currently assigned tasks.

        Returns:
            Dictionary mapping task ID to agent ID
        """
        return self._task_assignments.copy()

    def clear_completed_tasks(self, older_than_seconds: Optional[float] = None) -> int:
        """Clear completed tasks from history.

        Args:
            older_than_seconds: Only clear tasks older than this many seconds

        Returns:
            Number of tasks cleared
        """
        if older_than_seconds is None:
            # Clear all completed tasks
            count = len(self._task_results)
            self._task_results.clear()
            return count

        # Clear only tasks older than the specified time
        now = time.time()
        to_clear = [
            task_id
            for task_id, result in self._task_results.items()
            if now - result.completed_at > older_than_seconds
        ]

        for task_id in to_clear:
            del self._task_results[task_id]

        return len(to_clear)
