"""
Team coordinator for Enterprise AI.

This module provides a coordinator for managing task delegation,
tracking, and result collection within teams with support for
tool-based capabilities and intelligent task routing.
"""

import time
import uuid
import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast
from collections import deque, defaultdict

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.message import (
    BaseAgentMessage,
    QueryMessage,
    TaskAssignmentMessage,
    TaskUpdateMessage,
    create_message,
)
from enterprise_ai.team.types import TeamProtocol, ToolCapableTeamProtocol
from enterprise_ai.tool.core.result import ToolResult
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
        tool_results: Optional[Dict[str, ToolResult]] = None,
    ):
        """Initialize a task result.

        Args:
            task_id: ID of the completed task
            status: Final status of the task
            agent_id: ID of the agent that completed the task
            data: Optional result data
            error: Optional error message
            completed_at: Optional timestamp of completion
            tool_results: Optional map of tool names to results from task execution
        """
        self.task_id = task_id
        self.status = status
        self.agent_id = agent_id
        self.data = data or {}
        self.error = error
        self.completed_at = completed_at or time.time()
        self.tool_results = tool_results or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation
        """
        result_dict = {
            "task_id": self.task_id,
            "status": self.status.name,
            "agent_id": self.agent_id,
            "data": self.data,
            "error": self.error,
            "completed_at": self.completed_at,
        }

        # Add tool results if present
        if self.tool_results:
            result_dict["tool_results"] = {
                tool_name: result.output if not result.error else {"error": result.error}
                for tool_name, result in self.tool_results.items()
            }

        return result_dict

    def add_tool_result(self, tool_name: str, result: ToolResult) -> None:
        """
        Add a tool result to this task result.

        Args:
            tool_name: Name of the tool
            result: Result of the tool execution
        """
        self.tool_results[tool_name] = result


class ToolRequirementTracker:
    """
    Tracks tool requirements for tasks and finds capable agents.

    This class analyzes tasks for tool requirements and helps
    assign them to agents with appropriate capabilities.
    """

    def __init__(self, team: TeamProtocol):
        """
        Initialize a tool requirement tracker.

        Args:
            team: Team to track requirements for
        """
        self._team = team
        self._task_requirements: Dict[str, Set[str]] = {}  # task_id -> set of tool names
        self._capability_cache: Dict[
            str, Dict[str, List[str]]
        ] = {}  # tool_name -> {capability_level -> [agent_ids]}

        # Last capability update timestamp
        self._last_cache_update = 0.0
        self._cache_validity_period = 60.0  # seconds

    def analyze_task(self, task: Task) -> Set[str]:
        """
        Analyze a task to identify required tools.

        Args:
            task: Task to analyze

        Returns:
            Set of required tool names
        """
        required_tools = set()

        # Check explicit metadata requirements
        if task.metadata:
            # Single required tool
            if "required_tool" in task.metadata:
                required_tools.add(task.metadata["required_tool"])

            # Multiple required tools
            if "required_tools" in task.metadata and isinstance(
                task.metadata["required_tools"], (list, set)
            ):
                required_tools.update(task.metadata["required_tools"])

            # Tool capability requirements
            if "tool_capabilities" in task.metadata and isinstance(
                task.metadata["tool_capabilities"], (list, set)
            ):
                # Add tools that match the required capabilities
                capabilities = task.metadata["tool_capabilities"]
                self._update_capability_cache()

                for capability in capabilities:
                    for tool_name in self._capability_cache.keys():
                        if capability.lower() in tool_name.lower():
                            required_tools.add(tool_name)

        # Check if the task description mentions tools
        if hasattr(self._team, "get_available_tools"):
            tools = []
            for agent_tools in self._team.get_available_tools().values():
                tools.extend(agent_tools)

            # Get unique tool names
            unique_tools = set(tools)

            # Check if any tool names are mentioned in the task description
            description = task.description.lower()
            for tool_name in unique_tools:
                if tool_name.lower() in description:
                    required_tools.add(tool_name)

        # Store requirements for this task
        self._task_requirements[task.id] = required_tools

        return required_tools

    def _update_capability_cache(self) -> None:
        """Update the capability cache if it's stale."""
        current_time = time.time()

        # Check if cache is still valid
        if (current_time - self._last_cache_update) < self._cache_validity_period:
            return

        # Clear and rebuild cache
        self._capability_cache.clear()

        # Only update if team supports tool capabilities
        if not hasattr(self._team, "find_agents_by_tool_capability"):
            self._last_cache_update = current_time
            return

        # Get all available tools
        all_tools = set()
        if hasattr(self._team, "get_available_tools"):
            for agent_tools in self._team.get_available_tools().values():
                all_tools.update(agent_tools)

        # For each tool, find capable agents
        for tool_name in all_tools:
            capable_agents = self._team.find_agents_by_tool_capability(tool_name)

            self._capability_cache[tool_name] = {
                "all": capable_agents,
            }

        self._last_cache_update = current_time

    def find_capable_agents(self, task_id: str) -> Dict[str, List[str]]:
        """
        Find agents capable of handling a task's tool requirements.

        Args:
            task_id: ID of the task

        Returns:
            Map of tool names to lists of capable agent IDs
        """
        result: Dict[str, List[str]] = {}

        # Get required tools for this task
        required_tools = self._task_requirements.get(task_id, set())

        # Check if the team can find agents by tool capability
        if not hasattr(self._team, "find_agents_by_tool_capability"):
            return result

        # Find agents for each tool
        for tool_name in required_tools:
            capable_agents = self._team.find_agents_by_tool_capability(tool_name)
            result[tool_name] = capable_agents

        return result

    def get_best_agent_for_task(self, task_id: str) -> Optional[str]:
        """
        Find the best agent for a task based on tool capabilities.

        Args:
            task_id: ID of the task

        Returns:
            ID of the most capable agent, or None if no suitable agent
        """
        # Get required tools for this task
        required_tools = self._task_requirements.get(task_id, set())

        if not required_tools or not hasattr(self._team, "find_agents_by_tool_capability"):
            return None

        # Count how many required tools each agent can handle
        agent_capabilities: Dict[str, int] = {}

        for tool_name in required_tools:
            capable_agents = self._team.find_agents_by_tool_capability(tool_name)

            for agent_id in capable_agents:
                if agent_id in agent_capabilities:
                    agent_capabilities[agent_id] += 1
                else:
                    agent_capabilities[agent_id] = 1

        # Find the agent with the most capabilities
        if not agent_capabilities:
            return None

        max_capabilities = max(agent_capabilities.values())
        best_agents = [
            agent_id for agent_id, count in agent_capabilities.items() if count == max_capabilities
        ]

        # If there are multiple equally capable agents, just take the first one
        return best_agents[0] if best_agents else None


class TeamCoordinator:
    """Coordinator for task delegation and result collection.

    This class manages the assignment of tasks to appropriate team members,
    tracks task status, and collects results with awareness of tool
    capabilities and dependencies.
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

        # Initialize tool requirement tracker
        self._tool_tracker = ToolRequirementTracker(team)

        # Track tasks waiting for tool access
        self._waiting_for_tools: Dict[str, Set[str]] = {}  # task_id -> set of tool names

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

        # Analyze task for tool requirements
        required_tools = self._tool_tracker.analyze_task(task)  # noqa: F841

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
        # Find the most capable agent for this task based on tool requirements
        best_agent_id = self._tool_tracker.get_best_agent_for_task(task.id)

        if best_agent_id:
            # Try assigning to the most capable agent
            success = self.team.assign_task(task, best_agent_id)
            if success:
                self._task_assignments[task.id] = best_agent_id
                logger.info(
                    f"Assigned task {task.id} to agent {best_agent_id} based on tool capabilities"
                )
                return True

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
        tool_results: Optional[Dict[str, ToolResult]] = None,
    ) -> bool:
        """Update the status of a task and process any dependent tasks.

        Args:
            task_id: ID of the task to update
            status: New status
            agent_id: ID of the agent reporting the status
            result_data: Optional result data
            error: Optional error message
            tool_results: Optional map of tool names to execution results

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
            task_result = TaskResult(
                task_id=task_id,
                status=status,
                agent_id=agent_id,
                data=result_data,
                error=error,
                tool_results=tool_results,
            )

            self._task_results[task_id] = task_result

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

    # Tool-aware methods

    def request_tool_for_task(self, task_id: str, tool_name: str, must_have: bool = False) -> bool:
        """
        Request access to a tool for a specific task.

        Args:
            task_id: ID of the task
            tool_name: Name of the tool to request
            must_have: Whether the tool is required for the task

        Returns:
            True if the tool is available or request was queued, False if not possible
        """
        # Check if task exists
        if task_id not in self._task_assignments and task_id not in self._task_results:
            logger.warning(f"Task {task_id} not found")
            return False

        # Check if ToolCapableTeam
        if not hasattr(self.team, "find_agents_by_tool_capability"):
            logger.warning(f"Team {self.team.id} does not support tool capabilities")
            return False

        # Find agents with this tool
        capable_agents = self.team.find_agents_by_tool_capability(tool_name)

        if not capable_agents:
            if must_have:
                logger.warning(f"No agent has required tool {tool_name} for task {task_id}")
                return False
            else:
                # Add to waiting list
                if task_id not in self._waiting_for_tools:
                    self._waiting_for_tools[task_id] = set()

                self._waiting_for_tools[task_id].add(tool_name)
                logger.info(f"Added task {task_id} to waiting list for tool {tool_name}")
                return True

        # Get the assigned agent
        assigned_agent_id = self._task_assignments.get(task_id)
        if not assigned_agent_id:
            logger.warning(f"Task {task_id} is not assigned to any agent")
            return False

        # If the assigned agent has the tool, we're good
        if assigned_agent_id in capable_agents:
            return True

        # Otherwise, try to share the tool with the assigned agent
        if not hasattr(self.team, "share_tool"):
            return False

        # Find an agent that can share the tool
        for owner_id in capable_agents:
            # Try to share from the first agent that has it
            if isinstance(self.team, ToolCapableTeamProtocol):
                # Check if sharing is possible
                policy = self.team.get_tool_sharing_policy()
                if policy.can_share_tool(owner_id, tool_name):
                    # Share the tool
                    success = self.team.share_tool(tool_name, owner_id, assigned_agent_id)
                    if success:
                        logger.info(
                            f"Shared tool {tool_name} from agent {owner_id} "
                            f"to agent {assigned_agent_id} for task {task_id}"
                        )
                        return True

        # If we couldn't share, and it's required, we need to reassign the task
        if must_have and capable_agents:
            # Get the task
            for task in self._task_queue:
                if task.id == task_id:
                    # Remove from queue
                    self._task_queue.remove(task)

                    # Remove current assignment
                    if task_id in self._task_assignments:
                        del self._task_assignments[task_id]

                    # Assign to a capable agent
                    new_agent_id = capable_agents[0]
                    success = self.team.assign_task(task, new_agent_id)

                    if success:
                        self._task_assignments[task_id] = new_agent_id
                        logger.info(
                            f"Reassigned task {task_id} from {assigned_agent_id} "
                            f"to {new_agent_id} based on tool requirements"
                        )
                        return True
                    else:
                        # Put back in queue
                        self._task_queue.append(task)
                        logger.warning(f"Failed to reassign task {task_id}, putting back in queue")
                        return False

        # Add to waiting list if it's not required
        if not must_have:
            if task_id not in self._waiting_for_tools:
                self._waiting_for_tools[task_id] = set()

            self._waiting_for_tools[task_id].add(tool_name)
            logger.info(f"Added task {task_id} to waiting list for tool {tool_name}")
            return True

        return False

    async def execute_tool_for_task(
        self,
        task_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        wait_if_unavailable: bool = False,
    ) -> Optional[ToolResult]:
        """
        Execute a tool for a specific task.

        Args:
            task_id: ID of the task
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            wait_if_unavailable: Whether to wait if the tool is not immediately available

        Returns:
            Tool execution result, or None if not possible
        """
        # Check if task exists and is assigned
        if task_id not in self._task_assignments:
            logger.warning(f"Task {task_id} not assigned")
            return None

        # Get the assigned agent
        assigned_agent_id = self._task_assignments[task_id]

        # Check if the team supports tool execution
        if not hasattr(self.team, "execute_tool"):
            logger.warning(f"Team {self.team.id} does not support tool execution")
            return None

        # First check if the assigned agent has access to the tool
        capable_agents = []
        if hasattr(self.team, "find_agents_by_tool_capability"):
            capable_agents = self.team.find_agents_by_tool_capability(tool_name)

        if assigned_agent_id in capable_agents:
            # Execute using the assigned agent
            try:
                result = await self.team.execute_tool(tool_name, parameters, assigned_agent_id)

                # Record in task result if successful
                if task_id in self._task_results:
                    self._task_results[task_id].add_tool_result(tool_name, result)

                return result
            except Exception as e:
                logger.error(f"Error executing tool {tool_name} for task {task_id}: {e}")
                return None

        # If assigned agent doesn't have access, try to get access
        success = self.request_tool_for_task(task_id, tool_name, must_have=not wait_if_unavailable)

        if success:
            # If tool was shared, try again
            try:
                result = await self.team.execute_tool(tool_name, parameters, assigned_agent_id)

                # Record in task result if successful
                if task_id in self._task_results:
                    self._task_results[task_id].add_tool_result(tool_name, result)

                return result
            except Exception as e:
                logger.error(f"Error executing tool {tool_name} for task {task_id}: {e}")

        # If we're willing to wait, try to find another agent to execute the tool
        if wait_if_unavailable:
            # Find an agent with the tool
            if hasattr(self.team, "find_agents_by_tool_capability"):
                capable_agents = self.team.find_agents_by_tool_capability(tool_name)

                if capable_agents:
                    # Execute using the first capable agent
                    try:
                        result = await self.team.execute_tool(
                            tool_name, parameters, capable_agents[0]
                        )

                        # Record in task result if successful
                        if task_id in self._task_results:
                            self._task_results[task_id].add_tool_result(tool_name, result)

                        return result
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name} for task {task_id}: {e}")

        return None
