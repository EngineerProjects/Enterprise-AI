"""
Team task management for Enterprise AI.

This module provides functionality for team task management, 
including breaking down complex tasks, assigning tasks to team members,
tracking task status and dependencies, and coordinating team tasks.
"""

import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.architecture.utils import generate_id
from enterprise_ai.agent.core.types import AgentProtocol, Task
from enterprise_ai.logger import get_logger
from enterprise_ai.team.architecture.messaging import TeamMessage, TeamMessageType
from enterprise_ai.team.core.types import TeamProtocol

logger = get_logger("team.architecture.task_manager")


class TaskStatus(Enum):
    """Status of a team task."""
    
    PENDING = auto()  # Task has been created but not yet assigned
    ASSIGNED = auto()  # Task has been assigned to an agent but not started
    IN_PROGRESS = auto()  # Task is currently being worked on
    BLOCKED = auto()  # Task is blocked waiting for another task or resource
    COMPLETED = auto()  # Task has been completed successfully
    FAILED = auto()  # Task has failed or was unable to be completed


class TeamTask:
    """Representation of a task within a team.
    
    This class extends the basic agent task concept to support
    team-specific properties like dependencies, assignments,
    and hierarchical decomposition.
    """
    
    def __init__(
        self,
        task_id: Optional[str] = None,
        description: str = "",
        parent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        status: TaskStatus = TaskStatus.PENDING,
        dependencies: Optional[List[str]] = None,
        subtasks: Optional[List[str]] = None,
        deadline: Optional[datetime] = None,
        priority: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        **kwargs: Any,
    ):
        """Initialize a team task.
        
        Args:
            task_id: Unique identifier for the task
            description: Description of the task
            parent_id: ID of the parent task (if this is a subtask)
            team_id: ID of the team this task belongs to
            assigned_to: ID of the agent assigned to this task
            status: Current status of the task
            dependencies: List of task IDs that must be completed before this task
            subtasks: List of subtask IDs
            deadline: Optional deadline for the task
            priority: Priority level (higher is more important)
            metadata: Additional metadata for the task
            created_at: Timestamp when the task was created
            updated_at: Timestamp when the task was last updated
            **kwargs: Additional task parameters
        """
        self.id = task_id or generate_id("task-")
        self.description = description
        self.parent_id = parent_id
        self.team_id = team_id
        self.assigned_to = assigned_to
        self.status = status
        self.dependencies = dependencies or []
        self.subtasks = subtasks or []
        self.deadline = deadline
        self.priority = priority
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or self.created_at
        
        # Store any additional parameters
        for key, value in kwargs.items():
            self.metadata[key] = value
    
    def update_status(self, status: TaskStatus) -> bool:
        """Update the task status.
        
        Args:
            status: New status for the task
            
        Returns:
            True if status was updated, False otherwise
        """
        if not isinstance(status, TaskStatus):
            logger.error(f"Invalid status for task {self.id}: {status}")
            return False
        
        self.status = status
        self.updated_at = datetime.now()
        logger.info(f"Updated task {self.id} status to {status.name}")
        return True
    
    def assign(self, agent_id: str) -> bool:
        """Assign the task to an agent.
        
        Args:
            agent_id: ID of the agent to assign
            
        Returns:
            True if task was assigned, False otherwise
        """
        self.assigned_to = agent_id
        self.updated_at = datetime.now()
        
        # If previously pending, update status to assigned
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.ASSIGNED
        
        logger.info(f"Assigned task {self.id} to agent {agent_id}")
        return True
    
    def add_dependency(self, task_id: str) -> bool:
        """Add a dependency to this task.
        
        Args:
            task_id: ID of the task that must be completed first
            
        Returns:
            True if dependency was added, False otherwise
        """
        if task_id in self.dependencies:
            logger.warning(f"Task {self.id} already depends on {task_id}")
            return False
        
        if task_id == self.id:
            logger.error(f"Task {self.id} cannot depend on itself")
            return False
        
        self.dependencies.append(task_id)
        self.updated_at = datetime.now()
        logger.info(f"Added dependency on task {task_id} to task {self.id}")
        return True
    
    def remove_dependency(self, task_id: str) -> bool:
        """Remove a dependency from this task.
        
        Args:
            task_id: ID of the dependency to remove
            
        Returns:
            True if dependency was removed, False otherwise
        """
        if task_id not in self.dependencies:
            logger.warning(f"Task {self.id} does not depend on {task_id}")
            return False
        
        self.dependencies.remove(task_id)
        self.updated_at = datetime.now()
        logger.info(f"Removed dependency on task {task_id} from task {self.id}")
        return True
    
    def add_subtask(self, task_id: str) -> bool:
        """Add a subtask to this task.
        
        Args:
            task_id: ID of the subtask
            
        Returns:
            True if subtask was added, False otherwise
        """
        if task_id in self.subtasks:
            logger.warning(f"Task {task_id} is already a subtask of {self.id}")
            return False
        
        if task_id == self.id:
            logger.error(f"Task {self.id} cannot be a subtask of itself")
            return False
        
        self.subtasks.append(task_id)
        self.updated_at = datetime.now()
        logger.info(f"Added subtask {task_id} to task {self.id}")
        return True
    
    def remove_subtask(self, task_id: str) -> bool:
        """Remove a subtask from this task.
        
        Args:
            task_id: ID of the subtask to remove
            
        Returns:
            True if subtask was removed, False otherwise
        """
        if task_id not in self.subtasks:
            logger.warning(f"Task {task_id} is not a subtask of {self.id}")
            return False
        
        self.subtasks.remove(task_id)
        self.updated_at = datetime.now()
        logger.info(f"Removed subtask {task_id} from task {self.id}")
        return True
    
    def set_priority(self, priority: int) -> bool:
        """Set the priority of the task.
        
        Args:
            priority: New priority (1-5, higher is more important)
            
        Returns:
            True if priority was set, False otherwise
        """
        if not isinstance(priority, int) or priority < 1 or priority > 5:
            logger.error(f"Invalid priority for task {self.id}: {priority} (must be 1-5)")
            return False
        
        self.priority = priority
        self.updated_at = datetime.now()
        logger.info(f"Set priority of task {self.id} to {priority}")
        return True
    
    def set_deadline(self, deadline: datetime) -> bool:
        """Set the deadline for the task.
        
        Args:
            deadline: New deadline
            
        Returns:
            True if deadline was set, False otherwise
        """
        if not isinstance(deadline, datetime):
            logger.error(f"Invalid deadline for task {self.id}: {deadline}")
            return False
        
        self.deadline = deadline
        self.updated_at = datetime.now()
        logger.info(f"Set deadline of task {self.id} to {deadline}")
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the task to a dictionary.
        
        Returns:
            Dictionary representation of the task
        """
        result = {
            "id": self.id,
            "description": self.description,
            "status": self.status.name,
            "priority": self.priority,
            "team_id": self.team_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        # Add optional fields if they exist
        if self.parent_id:
            result["parent_id"] = self.parent_id
        
        if self.assigned_to:
            result["assigned_to"] = self.assigned_to
        
        if self.dependencies:
            result["dependencies"] = self.dependencies
        
        if self.subtasks:
            result["subtasks"] = self.subtasks
        
        if self.deadline:
            result["deadline"] = self.deadline.isoformat()
        
        if self.metadata:
            result["metadata"] = self.metadata
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamTask":
        """Create a task from a dictionary.
        
        Args:
            data: Dictionary containing task data
            
        Returns:
            TeamTask instance
        """
        # Extract and convert fields
        status_str = data.get("status", "PENDING")
        try:
            status = TaskStatus[status_str] if isinstance(status_str, str) else TaskStatus.PENDING
        except KeyError:
            logger.warning(f"Invalid task status: {status_str}, defaulting to PENDING")
            status = TaskStatus.PENDING
        
        # Convert timestamp strings to datetime objects
        created_at = None
        if "created_at" in data and data["created_at"]:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                created_at = datetime.now()
        
        updated_at = None
        if "updated_at" in data and data["updated_at"]:
            try:
                updated_at = datetime.fromisoformat(data["updated_at"])
            except (ValueError, TypeError):
                updated_at = datetime.now()
        
        deadline = None
        if "deadline" in data and data["deadline"]:
            try:
                deadline = datetime.fromisoformat(data["deadline"])
            except (ValueError, TypeError):
                logger.warning(f"Invalid deadline format: {data['deadline']}")
        
        # Create the task
        return cls(
            task_id=data.get("id"),
            description=data.get("description", ""),
            parent_id=data.get("parent_id"),
            team_id=data.get("team_id"),
            assigned_to=data.get("assigned_to"),
            status=status,
            dependencies=data.get("dependencies", []),
            subtasks=data.get("subtasks", []),
            deadline=deadline,
            priority=data.get("priority", 1),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )
    
    @classmethod
    def from_agent_task(cls, task: Task, team_id: Optional[str] = None) -> "TeamTask":
        """Create a team task from an agent task.
        
        Args:
            task: Agent task to convert
            team_id: Optional team ID to associate with the task
            
        Returns:
            TeamTask instance
        """
        # If it's already a TeamTask, just return it
        if isinstance(task, TeamTask):
            if team_id and not task.team_id:
                task.team_id = team_id
            return task
        
        # Create new TeamTask from the agent task
        metadata = {}
        
        # If task is a dict, extract metadata
        if isinstance(task, dict):
            # Copy all attributes not explicitly handled
            for key, value in task.items():
                if key not in ["id", "description", "metadata", "status"]:
                    metadata[key] = value
            
            # Extract nested metadata if it exists
            if "metadata" in task and isinstance(task["metadata"], dict):
                for key, value in task["metadata"].items():
                    metadata[key] = value
                    
            # Get task ID and description
            task_id = task.get("id")
            description = task.get("description", "")
            
            # Convert status if present
            status = TaskStatus.PENDING
            if "status" in task:
                try:
                    status_str = task["status"]
                    if isinstance(status_str, str):
                        status = TaskStatus[status_str]
                except KeyError:
                    pass
                
        else:
            # Handle non-dict tasks (treat as description string)
            task_id = None
            description = str(task)
            status = TaskStatus.PENDING
        
        # Create the TeamTask
        return cls(
            task_id=task_id,
            description=description,
            team_id=team_id,
            status=status,
            metadata=metadata,
        )


class TaskManager:
    """Team task manager.
    
    This component handles all aspects of team task management, including:
    - Assigning tasks to team members
    - Tracking task status and progress
    - Managing task dependencies
    - Balancing workload across team members
    - Handling task notifications and updates
    """
    
    def __init__(self, team: "TeamProtocol"):
        """Initialize the task manager.
        
        Args:
            team: Team that this manager belongs to
        """
        self._team = team
        self._tasks: Dict[str, TeamTask] = {}
        self._task_assignments: Dict[str, List[str]] = {}  # agent_id -> list of task_ids
        self._parent_child_index: Dict[str, List[str]] = {}  # parent_id -> list of child_ids
        
        logger.info(f"Initialized task manager for team {team.id}")
    
    @property
    def task_count(self) -> int:
        """Get the number of tasks managed by this team.
        
        Returns:
            Number of tasks
        """
        return len(self._tasks)
    
    def create_task(self, task_data: Union[str, Dict[str, Any], Task, TeamTask]) -> TeamTask:
        """Create a new task.
        
        Args:
            task_data: Task data or description
            
        Returns:
            Created TeamTask
        """
        # Convert to TeamTask if needed
        if isinstance(task_data, TeamTask):
            task = task_data
            # Ensure team_id is set
            if not task.team_id:
                task.team_id = self._team.id
        elif isinstance(task_data, dict) or isinstance(task_data, Task):
            # Convert from agent task or dict
            task = TeamTask.from_agent_task(cast(Task, task_data), team_id=self._team.id)
        else:
            # Create from description string
            task = TeamTask(
                description=str(task_data),
                team_id=self._team.id,
            )
        
        # Store the task
        self._tasks[task.id] = task
        
        # Update parent-child index if this is a child task
        if task.parent_id:
            if task.parent_id not in self._parent_child_index:
                self._parent_child_index[task.parent_id] = []
            self._parent_child_index[task.parent_id].append(task.id)
            
            # Also update the parent's subtasks list
            parent = self.get_task(task.parent_id)
            if parent:
                parent.add_subtask(task.id)
        
        logger.info(f"Created task {task.id} in team {self._team.id}")
        return task
    
    def get_task(self, task_id: str) -> Optional[TeamTask]:
        """Get a task by ID.
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Task with the specified ID, or None if not found
        """
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs: Any) -> bool:
        """Update a task.
        
        Args:
            task_id: ID of the task to update
            **kwargs: Attributes to update
            
        Returns:
            True if task was updated, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Cannot update task: task {task_id} not found")
            return False
        
        # Update specified attributes
        updated = False
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
                updated = True
            elif key == "status" and isinstance(value, str):
                # Handle status enum conversion
                try:
                    task.status = TaskStatus[value.upper()]
                    updated = True
                except KeyError:
                    logger.warning(f"Invalid status value: {value}")
            else:
                # Store in metadata
                task.metadata[key] = value
                updated = True
        
        if updated:
            task.updated_at = datetime.now()
            logger.info(f"Updated task {task_id}")
        
        return updated
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task.
        
        Args:
            task_id: ID of the task to delete
            
        Returns:
            True if task was deleted, False otherwise
        """
        if task_id not in self._tasks:
            logger.warning(f"Cannot delete task: task {task_id} not found")
            return False
        
        task = self._tasks[task_id]
        
        # Remove from agent assignments
        if task.assigned_to:
            assignments = self._task_assignments.get(task.assigned_to, [])
            if task_id in assignments:
                assignments.remove(task_id)
        
        # Remove from parent-child index
        if task.parent_id and task.parent_id in self._parent_child_index:
            if task_id in self._parent_child_index[task.parent_id]:
                self._parent_child_index[task.parent_id].remove(task_id)
            
            # Also remove from parent's subtasks list
            parent = self.get_task(task.parent_id)
            if parent:
                parent.remove_subtask(task_id)
        
        # Remove any child tasks
        if task_id in self._parent_child_index:
            child_ids = list(self._parent_child_index[task_id])
            for child_id in child_ids:
                self.delete_task(child_id)
            del self._parent_child_index[task_id]
        
        # Remove from tasks dictionary
        del self._tasks[task_id]
        
        logger.info(f"Deleted task {task_id}")
        return True
    
    def get_all_tasks(self) -> List[TeamTask]:
        """Get all tasks.
        
        Returns:
            List of all tasks
        """
        return list(self._tasks.values())
    
    def get_root_tasks(self) -> List[TeamTask]:
        """Get all top-level tasks with no parent.
        
        Returns:
            List of root tasks
        """
        return [task for task in self._tasks.values() if not task.parent_id]
    
    def get_subtasks(self, task_id: str) -> List[TeamTask]:
        """Get all subtasks of a task.
        
        Args:
            task_id: ID of the parent task
            
        Returns:
            List of subtask objects
        """
        subtask_ids = self._parent_child_index.get(task_id, [])
        return [self._tasks[sid] for sid in subtask_ids if sid in self._tasks]
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to a specific agent.
        
        Args:
            task_id: ID of the task to assign
            agent_id: ID of the agent to assign the task to
            
        Returns:
            True if task was assigned, False otherwise
        """
        # Validate task and agent
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Cannot assign task: task {task_id} not found")
            return False
        
        agent = self._team.get_member(agent_id)
        if not agent:
            logger.warning(f"Cannot assign task: agent {agent_id} not in team {self._team.id}")
            return False
        
        # Update task assignment
        task.assign(agent_id)
        
        # Update agent assignments index
        if agent_id not in self._task_assignments:
            self._task_assignments[agent_id] = []
        if task_id not in self._task_assignments[agent_id]:
            self._task_assignments[agent_id].append(task_id)
        
        # Delegate to agent
        try:
            agent_task_data = task.to_dict()
            result = agent.assign_task(agent_task_data)
            logger.info(f"Delegated task {task_id} to agent {agent_id}: {result}")
        except Exception as e:
            logger.error(f"Error delegating task {task_id} to agent {agent_id}: {e}")
        
        return True
    
    def unassign_task(self, task_id: str) -> bool:
        """Unassign a task from its current agent.
        
        Args:
            task_id: ID of the task to unassign
            
        Returns:
            True if task was unassigned, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Cannot unassign task: task {task_id} not found")
            return False
        
        if not task.assigned_to:
            logger.warning(f"Task {task_id} is not currently assigned")
            return False
        
        # Remove from agent assignments index
        agent_id = task.assigned_to
        if agent_id in self._task_assignments and task_id in self._task_assignments[agent_id]:
            self._task_assignments[agent_id].remove(task_id)
        
        # Update task status to pending
        task.assigned_to = None
        if task.status == TaskStatus.ASSIGNED:
            task.status = TaskStatus.PENDING
        
        task.updated_at = datetime.now()
        
        logger.info(f"Unassigned task {task_id} from agent {agent_id}")
        return True
    
    def get_agent_tasks(self, agent_id: str) -> List[TeamTask]:
        """Get all tasks assigned to a specific agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tasks assigned to the agent
        """
        task_ids = self._task_assignments.get(agent_id, [])
        return [self._tasks[tid] for tid in task_ids if tid in self._tasks]
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[TeamTask]:
        """Get all tasks with a specific status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of tasks with the specified status
        """
        return [task for task in self._tasks.values() if task.status == status]
    
    def decompose_task(
        self, 
        task_id: str, 
        subtasks: List[Union[str, Dict[str, Any], TeamTask]]
    ) -> List[TeamTask]:
        """Decompose a task into subtasks.
        
        Args:
            task_id: ID of the parent task
            subtasks: List of subtask descriptions or data
            
        Returns:
            List of created subtask objects
        """
        parent_task = self.get_task(task_id)
        if not parent_task:
            logger.warning(f"Cannot decompose task: task {task_id} not found")
            return []
        
        created_subtasks: List[TeamTask] = []
        
        # Create each subtask
        for subtask_data in subtasks:
            # Handle different input formats
            if isinstance(subtask_data, TeamTask):
                # Ensure this is connected to the parent
                subtask_data.parent_id = task_id
                subtask_data.team_id = self._team.id
                subtask = self.create_task(subtask_data)
            elif isinstance(subtask_data, dict):
                # Ensure parent_id is set correctly
                subtask_dict = dict(subtask_data)
                subtask_dict["parent_id"] = task_id
                subtask_dict["team_id"] = self._team.id
                subtask = self.create_task(subtask_dict)
            else:
                # Create from description string
                subtask = TeamTask(
                    description=str(subtask_data),
                    parent_id=task_id,
                    team_id=self._team.id,
                )
                subtask = self.create_task(subtask)
            
            created_subtasks.append(subtask)
            logger.info(f"Created subtask {subtask.id} for parent task {task_id}")
        
        return created_subtasks
    
    def check_dependencies(self, task_id: str) -> bool:
        """Check if all dependencies of a task are satisfied.
        
        Args:
            task_id: ID of the task to check
            
        Returns:
            True if all dependencies are completed, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Cannot check dependencies: task {task_id} not found")
            return False
        
        # If no dependencies, consider them satisfied
        if not task.dependencies:
            return True
        
        # Check each dependency
        for dep_id in task.dependencies:
            dep_task = self.get_task(dep_id)
            if not dep_task:
                logger.warning(f"Dependency task {dep_id} not found")
                return False
            
            if dep_task.status != TaskStatus.COMPLETED:
                logger.info(f"Dependency {dep_id} not completed for task {task_id}")
                return False
        
        logger.info(f"All dependencies completed for task {task_id}")
        return True
    
    def update_status(self, task_id: str, status: Union[TaskStatus, str]) -> bool:
        """Update the status of a task.
        
        Args:
            task_id: ID of the task to update
            status: New status
            
        Returns:
            True if status was updated, False otherwise
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Cannot update status: task {task_id} not found")
            return False
        
        # Convert string status to enum if needed
        resolved_status = status
        if isinstance(status, str):
            try:
                resolved_status = TaskStatus[status.upper()]
            except KeyError:
                logger.warning(f"Invalid status: {status}")
                return False
        
        # Update task status
        task.update_status(resolved_status)
        
        # If task is now completed, check if parent task can be completed
        if resolved_status == TaskStatus.COMPLETED and task.parent_id:
            self._check_parent_completion(task.parent_id)
        
        return True
    
    def _check_parent_completion(self, parent_id: str) -> None:
        """Check if a parent task can be marked as completed.
        
        This is called when a subtask is completed to see if all subtasks
        of the parent are now complete.
        
        Args:
            parent_id: ID of the parent task to check
        """
        parent = self.get_task(parent_id)
        if not parent or not parent.subtasks:
            return
        
        # Check if all subtasks are completed
        all_completed = True
        for subtask_id in parent.subtasks:
            subtask = self.get_task(subtask_id)
            if not subtask or subtask.status != TaskStatus.COMPLETED:
                all_completed = False
                break
        
        # If all subtasks are completed, complete the parent task
        if all_completed and parent.status != TaskStatus.COMPLETED:
            parent.update_status(TaskStatus.COMPLETED)
            logger.info(f"Automatically completed parent task {parent_id} as all subtasks are complete")
            
            # Recursively check if grandparent can be completed
            if parent.parent_id:
                self._check_parent_completion(parent.parent_id)
    
    def find_available_tasks(self, agent_id: Optional[str] = None) -> List[TeamTask]:
        """Find tasks that are available to be worked on.
        
        This looks for tasks that aren't blocked by dependencies
        and aren't already assigned or in progress.
        
        Args:
            agent_id: Optional agent ID to find tasks for
            
        Returns:
            List of available tasks
        """
        available_tasks: List[TeamTask] = []
        
        for task in self._tasks.values():
            # Skip tasks that are not in pending status
            if task.status != TaskStatus.PENDING:
                continue
            
            # Skip tasks assigned to a different agent
            if agent_id and task.assigned_to and task.assigned_to != agent_id:
                continue
            
            # Check dependencies
            dependencies_met = self.check_dependencies(task.id)
            if not dependencies_met:
                continue
            
            available_tasks.append(task)
        
        # Sort by priority (higher first)
        available_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        return available_tasks
    
    def find_blocked_tasks(self) -> List[Tuple[TeamTask, List[TeamTask]]]:
        """Find tasks that are blocked by dependencies.
        
        Returns:
            List of (task, blocking_dependencies) tuples
        """
        blocked_tasks: List[Tuple[TeamTask, List[TeamTask]]] = []
        
        for task in self._tasks.values():
            if not task.dependencies:
                continue
            
            # Find blocking dependencies
            blocking_deps: List[TeamTask] = []
            for dep_id in task.dependencies:
                dep_task = self.get_task(dep_id)
                if dep_task and dep_task.status != TaskStatus.COMPLETED:
                    blocking_deps.append(dep_task)
            
            if blocking_deps:
                blocked_tasks.append((task, blocking_deps))
        
        return blocked_tasks
    
    def assign_available_tasks(self) -> int:
        """Automatically assign available tasks to team members.
        
        Uses sophisticated algorithm to match tasks to agents based on
        capabilities, workload, and priorities.
        
        Returns:
            Number of tasks assigned
        """
        # Get all team members
        members = self._team.get_members()
        if not members:
            logger.warning(f"No team members in team {self._team.id} to assign tasks to")
            return 0
        
        # Get current workload
        workload: Dict[str, Dict[str, Any]] = {}
        for agent in members:
            agent_tasks = self.get_agent_tasks(agent.id)
            active_tasks = [
                t for t in agent_tasks 
                if t.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
            ]
            
            # Calculate capacity based on active tasks (inverse of workload)
            capacity = max(0, 5 - len(active_tasks))  # Assume max capacity of 5 tasks
            
            workload[agent.id] = {
                "active_tasks": len(active_tasks),
                "capacity": capacity,
                "agent": agent
            }
        
        # Get available tasks
        available_tasks = self.find_available_tasks()
        if not available_tasks:
            logger.info(f"No available tasks to assign in team {self._team.id}")
            return 0
        
        # Sort tasks by priority (higher first)
        available_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        # Collect agent capabilities
        agent_capabilities: Dict[str, Dict[str, Any]] = {}
        for agent in members:
            caps = set()
            if hasattr(agent, "capabilities"):
                caps.update(getattr(agent, "capabilities", set()))
            
            if hasattr(agent, "role") and hasattr(agent.role, "capabilities"):
                caps.update(getattr(agent.role, "capabilities", set()))
                
            agent_capabilities[agent.id] = {
                "capabilities": caps,
                "role": getattr(agent, "role", None)
            }
        
        # Use Hungarian algorithm for assignment (simplified version)
        # First, build cost matrix where lower cost = better assignment
        tasks_assigned = 0
        
        # Process tasks one by one, starting with highest priority
        for task in available_tasks:
            # Skip already assigned tasks
            if task.assigned_to:
                continue
                
            # Find best agent for this specific task
            best_agent_id = self.find_agent_for_task(task)
            
            if best_agent_id:
                # Check if agent has capacity
                if workload[best_agent_id]["capacity"] > 0:
                    # Assign task
                    if self.assign_task(task.id, best_agent_id):
                        tasks_assigned += 1
                        
                        # Update workload
                        workload[best_agent_id]["capacity"] -= 1
                        workload[best_agent_id]["active_tasks"] += 1
                        
                        logger.info(f"Assigned task {task.id} to agent {best_agent_id} based on capability match")
                else:
                    # Agent at capacity, find next best
                    available_agents = [
                        agent_id for agent_id, data in workload.items()
                        if data["capacity"] > 0
                    ]
                    
                    if available_agents:
                        # Find agent with highest capacity
                        next_agent_id = max(
                            available_agents,
                            key=lambda a: workload[a]["capacity"]
                        )
                        
                        if self.assign_task(task.id, next_agent_id):
                            tasks_assigned += 1
                            
                            # Update workload
                            workload[next_agent_id]["capacity"] -= 1
                            workload[next_agent_id]["active_tasks"] += 1
                            
                            logger.info(f"Assigned task {task.id} to agent {next_agent_id} based on availability")
            else:
                # Find any available agent
                available_agents = [
                    agent_id for agent_id, data in workload.items()
                    if data["capacity"] > 0
                ]
                
                if available_agents:
                    # Find agent with highest capacity
                    next_agent_id = max(
                        available_agents,
                        key=lambda a: workload[a]["capacity"]
                    )
                    
                    if self.assign_task(task.id, next_agent_id):
                        tasks_assigned += 1
                        
                        # Update workload
                        workload[next_agent_id]["capacity"] -= 1
                        workload[next_agent_id]["active_tasks"] += 1
                        
                        logger.info(f"Assigned task {task.id} to agent {next_agent_id} as fallback")
        
        logger.info(f"Automatically assigned {tasks_assigned} tasks in team {self._team.id}")
        return tasks_assigned
    
    def get_task_tree(self, root_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a hierarchical tree of tasks.
        
        Args:
            root_task_id: Optional root task ID to start from, or None for all root tasks
            
        Returns:
            Dictionary with hierarchical task structure
        """
        def build_tree(task_id: str) -> Dict[str, Any]:
            task = self.get_task(task_id)
            if not task:
                return {}
            
            tree = task.to_dict()
            
            # Add children
            children = self.get_subtasks(task_id)
            if children:
                tree["children"] = [build_tree(child.id) for child in children]
            
            return tree
        
        if root_task_id:
            # Build tree from specific root
            return build_tree(root_task_id)
        else:
            # Build trees for all root tasks
            root_tasks = self.get_root_tasks()
            return {
                "roots": [build_tree(task.id) for task in root_tasks]
            }
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get a summary of all tasks by status.
        
        Returns:
            Dictionary with task summary information
        """
        summary = {
            "total": len(self._tasks),
            "by_status": {},
            "by_agent": {},
        }
        
        # Count by status
        for status in TaskStatus:
            tasks = self.get_tasks_by_status(status)
            summary["by_status"][status.name] = len(tasks)
        
        # Count by agent
        for agent_id in self._task_assignments:
            agent_tasks = self.get_agent_tasks(agent_id)
            agent_name = "Unknown"
            
            # Try to get agent name
            agent = self._team.get_member(agent_id)
            if agent and hasattr(agent, "name"):
                agent_name = getattr(agent, "name", agent_id)
            
            # Create summary for this agent
            status_counts = {}
            for task in agent_tasks:
                status_name = task.status.name
                status_counts[status_name] = status_counts.get(status_name, 0) + 1
            
            summary["by_agent"][agent_id] = {
                "name": agent_name,
                "total": len(agent_tasks),
                "by_status": status_counts,
            }
        
        return summary
    
    def find_agent_for_task(self, task: TeamTask) -> Optional[str]:
        """Find the best agent to handle a particular task.
        
        This considers workload, capabilities, and task requirements.
        Uses a sophisticated matching algorithm to find optimal assignments.
        
        Args:
            task: Task to find an agent for
            
        Returns:
            ID of the best agent, or None if no suitable agent found
        """
        # Get all team members
        members = self._team.get_members()
        if not members:
            logger.warning(f"No team members in team {self._team.id} to assign tasks to")
            return None
        
        # Get current workload and capacity
        workload: Dict[str, Dict[str, Any]] = {}
        for agent in members:
            agent_tasks = self.get_agent_tasks(agent.id)
            active_tasks = [
                t for t in agent_tasks 
                if t.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
            ]
            
            # Calculate workload score - higher values mean more capacity
            workload_score = 10 - min(10, len(active_tasks))
            
            # Calculate priority score - higher values mean higher priority tasks
            priority_score = sum(t.priority for t in active_tasks) / max(1, len(active_tasks))
            
            workload[agent.id] = {
                "count": len(active_tasks),
                "workload_score": workload_score,
                "priority_score": priority_score,
                "capacity": workload_score  # Base capacity on workload
            }
        
        # Extract task requirements and keywords
        task_requirements = set()
        task_keywords = set()
        
        # Extract from description
        description = task.description.lower()
        
        # Look for common requirement indicators in description
        domains = [
            "finance", "accounting", "legal", "programming", "development", 
            "design", "marketing", "research", "analysis", "writing", 
            "math", "science", "engineering", "management", "leadership",
            "planning", "data", "ai", "machine learning", "content"
        ]
        
        for domain in domains:
            if domain in description:
                task_requirements.add(domain)
                
        # Also check metadata for requirements
        if task.metadata:
            # Check for explicit requirements field
            if "requirements" in task.metadata:
                reqs = task.metadata["requirements"]
                if isinstance(reqs, list):
                    task_requirements.update(req.lower() for req in reqs if isinstance(req, str))
                elif isinstance(reqs, str):
                    task_requirements.add(reqs.lower())
                    
            # Check for keywords field
            if "keywords" in task.metadata:
                keywords = task.metadata["keywords"]
                if isinstance(keywords, list):
                    task_keywords.update(kw.lower() for kw in keywords if isinstance(kw, str))
                elif isinstance(keywords, str):
                    task_keywords.add(keywords.lower())
                    
            # Check for domain field
            if "domain" in task.metadata:
                domain = task.metadata["domain"]
                if isinstance(domain, str):
                    task_requirements.add(domain.lower())
        
        # Calculate agent suitability scores
        agent_scores: Dict[str, float] = {}
        
        for agent in members:
            agent_id = agent.id
            base_score = workload[agent_id]["workload_score"]  # Start with workload capacity
            
            # Check for capabilities match
            capability_score = 0
            if hasattr(agent, "capabilities") and task_requirements:
                agent_capabilities = getattr(agent, "capabilities", set())
                
                # Calculate overlap between requirements and capabilities
                matching_capabilities = sum(1 for req in task_requirements 
                                           if any(req in cap.lower() for cap in agent_capabilities))
                
                # Normalize by total requirements
                if task_requirements:
                    capability_score = 5 * (matching_capabilities / len(task_requirements))
            
            # Check for role match
            role_score = 0
            if (hasattr(agent, "role") and 
                task_requirements and 
                hasattr(agent.role, "capabilities")):
                
                role_capabilities = getattr(agent.role, "capabilities", [])
                
                # Calculate overlap between requirements and role capabilities
                matching_role_caps = sum(1 for req in task_requirements 
                                        if any(req in cap.lower() for cap in role_capabilities))
                
                # Normalize by total requirements
                if task_requirements:
                    role_score = 3 * (matching_role_caps / len(task_requirements))
            
            # Check for expertise (if team has expertise data)
            expertise_score = 0
            team_collaboration = None
            
            # Try to access expertise data if available in team
            if hasattr(self._team, "collaboration") and self._team.collaboration:
                team_collaboration = self._team.collaboration
            elif hasattr(self._team, "_expertise_areas") and task_requirements:
                # Check if agent has relevant expertise
                agent_expertise = getattr(self._team, "_expertise_areas", {}).get(agent_id, {})
                
                # Calculate expertise match
                expertise_matches = sum(level for domain, level in agent_expertise.items()
                                     if any(req in domain.lower() for req in task_requirements))
                
                # Normalize
                if agent_expertise:
                    expertise_score = 3 * min(1.0, expertise_matches / len(task_requirements))
            
            # Previous success with similar tasks
            success_score = 0
            similar_tasks = [t for t in self.get_agent_tasks(agent_id) 
                            if t.status == TaskStatus.COMPLETED and 
                            any(req in t.description.lower() for req in task_requirements)]
            
            if similar_tasks:
                success_score = min(2.0, len(similar_tasks) * 0.5)
            
            # Calculate final weighted score
            final_score = (
                base_score * 0.4 +      # 40% workload capacity
                capability_score * 0.2 + # 20% capability match
                role_score * 0.2 +      # 20% role match
                expertise_score * 0.1 +  # 10% expertise
                success_score * 0.1      # 10% previous success
            )
            
            agent_scores[agent_id] = final_score
        
        # Select agent with highest score
        if agent_scores:
            best_agent_id = max(agent_scores.items(), key=lambda x: x[1])[0]
            logger.info(f"Selected agent {best_agent_id} with score {agent_scores[best_agent_id]} for task {task.id}")
            return best_agent_id
        
        return None
