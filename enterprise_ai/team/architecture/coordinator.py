"""
Team coordination for Enterprise AI.

This module provides functionality for coordinating team activities,
including collaboration, shared resources, and conflict resolution.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, MessageProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.team.architecture.messaging import TeamMessage, TeamMessageType
from enterprise_ai.team.architecture.task_manager import TaskStatus, TeamTask
from enterprise_ai.team.core.types import TeamProtocol

logger = get_logger("team.architecture.coordinator")


class CoordinationStrategy(Enum):
    """Enumeration of coordination strategies."""
    
    CENTRALIZED = "centralized"      # Manager makes all decisions
    DECENTRALIZED = "decentralized"  # Agents decide independently
    VOTING = "voting"                # Decisions made by voting
    CONSENSUS = "consensus"          # Decisions require consensus
    HYBRID = "hybrid"                # Mix of centralized and decentralized


class CoordinationEvent(Enum):
    """Enumeration of coordination events."""
    
    TASK_ASSIGNED = "task_assigned"           # A task was assigned
    TASK_STARTED = "task_started"             # A task was started
    TASK_COMPLETED = "task_completed"         # A task was completed
    TASK_FAILED = "task_failed"               # A task failed
    TASK_BLOCKED = "task_blocked"             # A task is blocked
    RESOURCE_REQUESTED = "resource_requested" # A resource was requested
    RESOURCE_RELEASED = "resource_released"   # A resource was released
    CONFLICT_DETECTED = "conflict_detected"   # A conflict was detected
    CONFLICT_RESOLVED = "conflict_resolved"   # A conflict was resolved
    MEMBER_JOINED = "member_joined"           # A member joined the team
    MEMBER_LEFT = "member_left"               # A member left the team


class ConflictType(Enum):
    """Types of conflicts that can occur in teams."""
    
    RESOURCE_CONFLICT = "resource_conflict"      # Multiple agents need same resource
    TASK_DEPENDENCY_CONFLICT = "task_dependency"  # Dependency issues between tasks
    CAPABILITY_CONFLICT = "capability_conflict"   # Capability overlap/gap issues
    PRIORITY_CONFLICT = "priority_conflict"       # Conflicting task priorities
    APPROACH_CONFLICT = "approach_conflict"       # Different approaches to solution
    COMMUNICATION_CONFLICT = "communication"      # Communication breakdowns
    GOAL_ALIGNMENT_CONFLICT = "goal_alignment"    # Different goals or interpretations


class ConflictStatus(Enum):
    """Status of a team conflict."""
    
    DETECTED = "detected"           # Conflict has been detected
    ANALYZING = "analyzing"         # Analyzing the conflict
    MEDIATING = "mediating"         # Actively mediating the conflict
    ESCALATED = "escalated"         # Escalated to higher authority
    RESOLVED = "resolved"           # Conflict has been resolved
    UNRESOLVABLE = "unresolvable"   # Conflict cannot be resolved


class CoordinationManager:
    """Team coordination manager.
    
    This component handles all aspects of team coordination, including:
    - Facilitating collaboration between team members
    - Managing shared resources
    - Coordinating tool usage and sharing
    - Handling conflicts and competing requests
    - Optimizing team operations
    """
    
    def __init__(self, team: "TeamProtocol"):
        """Initialize the coordination manager.
        
        Args:
            team: Team that this manager belongs to
        """
        self._team = team
        self._strategy = CoordinationStrategy.CENTRALIZED
        self._event_handlers: Dict[CoordinationEvent, List[Any]] = {}
        self._resource_locks: Dict[str, asyncio.Lock] = {}
        self._resource_ownership: Dict[str, str] = {}  # resource_id -> agent_id
        self._resource_requests: Dict[str, List[str]] = {}  # resource_id -> list of agent_ids
        self._conflicts: List[Dict[str, Any]] = []
        
        logger.info(f"Initialized coordination manager for team {team.id}")
    
    @property
    def strategy(self) -> CoordinationStrategy:
        """Get the current coordination strategy.
        
        Returns:
            Current coordination strategy
        """
        return self._strategy
    
    def set_strategy(self, strategy: CoordinationStrategy) -> None:
        """Set the coordination strategy.
        
        Args:
            strategy: New coordination strategy
        """
        self._strategy = strategy
        logger.info(f"Set coordination strategy for team {self._team.id} to {strategy.value}")
    
    def register_event_handler(
        self, 
        event: CoordinationEvent, 
        handler: Any
    ) -> None:
        """Register a handler for a coordination event.
        
        Args:
            event: Event to handle
            handler: Function to call when the event occurs
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        
        self._event_handlers[event].append(handler)
        logger.info(f"Registered handler for {event.value} event in team {self._team.id}")
    
    def trigger_event(
        self, 
        event: CoordinationEvent, 
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Trigger a coordination event.
        
        Args:
            event: Event to trigger
            data: Optional data to pass to handlers
        """
        if event not in self._event_handlers:
            return
        
        event_data = data or {}
        event_data["timestamp"] = datetime.now()
        event_data["team_id"] = self._team.id
        event_data["event"] = event.value
        
        # Call all handlers
        for handler in self._event_handlers[event]:
            try:
                handler(event_data)
            except Exception as e:
                logger.error(f"Error in event handler for {event.value}: {e}")
        
        logger.info(f"Triggered {event.value} event in team {self._team.id}")
    
    async def request_resource(
        self, 
        agent_id: str, 
        resource_id: str, 
        priority: int = 1
    ) -> bool:
        """Request a shared resource.
        
        Args:
            agent_id: ID of the requesting agent
            resource_id: ID of the resource
            priority: Priority of the request (higher = more important)
            
        Returns:
            True if resource granted, False if denied
        """
        # Create lock if it doesn't exist
        if resource_id not in self._resource_locks:
            self._resource_locks[resource_id] = asyncio.Lock()
        
        # If resource is not owned, grant it immediately
        if resource_id not in self._resource_ownership:
            self._resource_ownership[resource_id] = agent_id
            logger.info(f"Granted resource {resource_id} to agent {agent_id} in team {self._team.id}")
            
            # Trigger event
            self.trigger_event(
                CoordinationEvent.RESOURCE_REQUESTED,
                {
                    "agent_id": agent_id,
                    "resource_id": resource_id,
                    "granted": True,
                    "priority": priority,
                }
            )
            
            return True
        
        # If resource is already owned by this agent, grant it
        if self._resource_ownership[resource_id] == agent_id:
            logger.info(f"Resource {resource_id} already owned by agent {agent_id} in team {self._team.id}")
            return True
        
        # Otherwise, add to request queue
        if resource_id not in self._resource_requests:
            self._resource_requests[resource_id] = []
        
        # Add request with priority
        self._resource_requests[resource_id].append(agent_id)
        logger.info(f"Added request for resource {resource_id} from agent {agent_id} in team {self._team.id}")
        
        # If using centralized strategy, let manager decide
        if self._strategy == CoordinationStrategy.CENTRALIZED:
            manager = getattr(self._team, "_membership", None)
            if manager and hasattr(manager, "manager") and manager.manager:
                manager_id = manager.manager.id
                
                # Create and send resource request message
                message = TeamMessage(
                    sender_id=agent_id,
                    receiver_id=manager_id,
                    message_type="RESOURCE_REQUEST",
                    content=f"Request for resource {resource_id} with priority {priority}",
                    team_id=self._team.id,
                    team_message_type=TeamMessageType.COORDINATION,
                    metadata={
                        "resource_id": resource_id,
                        "priority": priority,
                    }
                )
                
                # Route message to manager
                try:
                    messaging_manager = getattr(self._team, "_messaging", None)
                    if messaging_manager:
                        messaging_manager.route_message(message)
                except Exception as e:
                    logger.error(f"Error routing resource request message: {e}")
        
        # Trigger event
        self.trigger_event(
            CoordinationEvent.RESOURCE_REQUESTED,
            {
                "agent_id": agent_id,
                "resource_id": resource_id,
                "granted": False,
                "priority": priority,
            }
        )
        
        # For now, just deny the request
        return False
    
    def release_resource(
        self, 
        agent_id: str, 
        resource_id: str
    ) -> bool:
        """Release a shared resource.
        
        Args:
            agent_id: ID of the releasing agent
            resource_id: ID of the resource
            
        Returns:
            True if resource released, False otherwise
        """
        # Check if resource is owned by this agent
        if resource_id not in self._resource_ownership:
            logger.warning(f"Resource {resource_id} not owned by any agent in team {self._team.id}")
            return False
        
        if self._resource_ownership[resource_id] != agent_id:
            logger.warning(f"Resource {resource_id} not owned by agent {agent_id} in team {self._team.id}")
            return False
        
        # Release the resource
        del self._resource_ownership[resource_id]
        logger.info(f"Released resource {resource_id} from agent {agent_id} in team {self._team.id}")
        
        # Trigger event
        self.trigger_event(
            CoordinationEvent.RESOURCE_RELEASED,
            {
                "agent_id": agent_id,
                "resource_id": resource_id,
            }
        )
        
        # Check if anyone is waiting for this resource
        if resource_id in self._resource_requests and self._resource_requests[resource_id]:
            # Grant to next agent in queue
            next_agent_id = self._resource_requests[resource_id].pop(0)
            self._resource_ownership[resource_id] = next_agent_id
            
            logger.info(f"Granted resource {resource_id} to waiting agent {next_agent_id} in team {self._team.id}")
            
            # If queue is empty, clean up
            if not self._resource_requests[resource_id]:
                del self._resource_requests[resource_id]
            
            # Trigger event
            self.trigger_event(
                CoordinationEvent.RESOURCE_REQUESTED,
                {
                    "agent_id": next_agent_id,
                    "resource_id": resource_id,
                    "granted": True,
                    "priority": 1,  # Default priority
                }
            )
        
        return True
    
    def register_conflict(
        self, 
        description: str, 
        agents: List[str], 
        conflict_type: Union[ConflictType, str] = ConflictType.RESOURCE_CONFLICT,
        resource_id: Optional[str] = None,
        task_ids: Optional[List[str]] = None,
        severity: int = 1,  # 1-5 scale, with 5 being most severe
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Register a conflict between agents.
        
        Args:
            description: Description of the conflict
            agents: List of agent IDs involved in the conflict
            conflict_type: Type of conflict
            resource_id: Optional ID of the resource in conflict
            task_ids: Optional list of task IDs involved in the conflict
            severity: Severity level (1-5)
            metadata: Additional conflict metadata
            
        Returns:
            ID of the registered conflict
        """
        conflict_id = f"conflict-{len(self._conflicts) + 1}"
        
        # Normalize conflict type
        if isinstance(conflict_type, str):
            try:
                conflict_type = ConflictType[conflict_type.upper()]
            except KeyError:
                logger.warning(f"Invalid conflict type: {conflict_type}, defaulting to RESOURCE_CONFLICT")
                conflict_type = ConflictType.RESOURCE_CONFLICT
        
        # Create conflict record
        conflict = {
            "id": conflict_id,
            "description": description,
            "type": conflict_type.value,
            "agents": agents,
            "resource_id": resource_id,
            "task_ids": task_ids or [],
            "severity": min(5, max(1, severity)),
            "status": ConflictStatus.DETECTED.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "resolved_at": None,
            "resolution": None,
            "resolution_steps": [],
            "escalation_level": 0,  # 0 = not escalated, 1+ = escalation level
            "metadata": metadata or {},
        }
        
        self._conflicts.append(conflict)
        logger.info(f"Registered {conflict_type.value} conflict {conflict_id} in team {self._team.id}: {description}")
        
        # Determine if this is a high-severity conflict that needs immediate attention
        if severity >= 4:
            # Auto-escalate high severity conflicts
            self._escalate_conflict(conflict_id)
        
        # Trigger event
        self.trigger_event(
            CoordinationEvent.CONFLICT_DETECTED,
            {
                "conflict_id": conflict_id,
                "description": description,
                "type": conflict_type.value,
                "agents": agents,
                "resource_id": resource_id,
                "task_ids": task_ids,
                "severity": severity,
            }
        )
        
        return conflict_id
    
    def resolve_conflict(
        self, 
        conflict_id: str, 
        resolution: str,
        resolution_steps: Optional[List[str]] = None
    ) -> bool:
        """Resolve a registered conflict.
        
        Args:
            conflict_id: ID of the conflict
            resolution: Description of the resolution
            resolution_steps: Optional list of steps taken to resolve
            
        Returns:
            True if conflict resolved, False otherwise
        """
        # Find the conflict
        for conflict in self._conflicts:
            if conflict["id"] == conflict_id:
                if conflict["status"] == ConflictStatus.RESOLVED.value:
                    logger.warning(f"Conflict {conflict_id} already resolved in team {self._team.id}")
                    return False
                
                # Update conflict
                conflict["status"] = ConflictStatus.RESOLVED.value
                conflict["resolved_at"] = datetime.now().isoformat()
                conflict["updated_at"] = datetime.now().isoformat()
                conflict["resolution"] = resolution
                
                if resolution_steps:
                    conflict["resolution_steps"] = resolution_steps
                
                logger.info(f"Resolved conflict {conflict_id} in team {self._team.id}: {resolution}")
                
                # Post-resolution actions based on conflict type
                if "type" in conflict:
                    # For resource conflicts, check if we can release or reassign resources
                    if conflict["type"] == ConflictType.RESOURCE_CONFLICT.value and conflict.get("resource_id"):
                        # Check resource queue
                        resource_id = conflict["resource_id"]
                        if resource_id in self._resource_requests and self._resource_requests[resource_id]:
                            # Auto-assign resource to next agent in queue as part of resolution
                            self._process_resource_queue(resource_id)
                            
                    # For task dependency conflicts, check if blocked tasks can now proceed
                    elif conflict["type"] == ConflictType.TASK_DEPENDENCY_CONFLICT.value and conflict.get("task_ids"):
                        # Notify task manager to recheck dependencies
                        task_manager = getattr(self._team, "_tasks", None)
                        if task_manager:
                            for task_id in conflict["task_ids"]:
                                task = task_manager.get_task(task_id)
                                if task and task.status == TaskStatus.BLOCKED:
                                    # Check if dependencies are now satisfied
                                    if task_manager.check_dependencies(task_id):
                                        # Update task status
                                        task_manager.update_status(task_id, TaskStatus.PENDING)
                                        logger.info(f"Unblocked task {task_id} after conflict resolution")
                
                # Trigger event
                self.trigger_event(
                    CoordinationEvent.CONFLICT_RESOLVED,
                    {
                        "conflict_id": conflict_id,
                        "resolution": resolution,
                        "steps": resolution_steps,
                    }
                )
                
                return True
        
        logger.warning(f"Conflict {conflict_id} not found in team {self._team.id}")
        return False
    
    def update_conflict_status(
        self,
        conflict_id: str,
        status: Union[ConflictStatus, str],
        notes: Optional[str] = None
    ) -> bool:
        """Update the status of a conflict.
        
        Args:
            conflict_id: ID of the conflict
            status: New status
            notes: Optional notes about the status change
            
        Returns:
            True if status updated, False otherwise
        """
        # Normalize status
        if isinstance(status, str):
            try:
                status = ConflictStatus[status.upper()]
            except KeyError:
                logger.warning(f"Invalid conflict status: {status}")
                return False
        
        # Find the conflict
        for conflict in self._conflicts:
            if conflict["id"] == conflict_id:
                # Don't allow updates to resolved conflicts
                if conflict["status"] == ConflictStatus.RESOLVED.value:
                    logger.warning(f"Cannot update resolved conflict {conflict_id}")
                    return False
                
                # Update status
                conflict["status"] = status.value
                conflict["updated_at"] = datetime.now().isoformat()
                
                if notes:
                    if "notes" not in conflict:
                        conflict["notes"] = []
                    
                    conflict["notes"].append({
                        "timestamp": datetime.now().isoformat(),
                        "content": notes,
                    })
                
                logger.info(f"Updated conflict {conflict_id} status to {status.value}")
                return True
        
        logger.warning(f"Conflict {conflict_id} not found in team {self._team.id}")
        return False
    
    def _escalate_conflict(self, conflict_id: str, escalation_level: int = 1) -> bool:
        """Escalate a conflict to a higher authority.
        
        Args:
            conflict_id: ID of the conflict
            escalation_level: Level of escalation (higher = more severe)
            
        Returns:
            True if conflict was escalated, False otherwise
        """
        # Find the conflict
        for conflict in self._conflicts:
            if conflict["id"] == conflict_id:
                # Update escalation level
                conflict["escalation_level"] = escalation_level
                conflict["status"] = ConflictStatus.ESCALATED.value
                conflict["updated_at"] = datetime.now().isoformat()
                
                # For centralized teams, escalate to manager
                if self._strategy == CoordinationStrategy.CENTRALIZED:
                    membership = getattr(self._team, "_membership", None)
                    if membership and membership.manager:
                        manager_id = membership.manager.id
                        
                        # Create escalation message
                        message = TeamMessage(
                            sender_id="team",
                            receiver_id=manager_id,
                            message_type="CONFLICT_ESCALATION",
                            content=f"Conflict {conflict_id} has been escalated: {conflict['description']}",
                            team_id=self._team.id,
                            team_message_type=TeamMessageType.COORDINATION,
                            metadata={
                                "conflict_id": conflict_id,
                                "conflict_type": conflict.get("type"),
                                "agents": conflict.get("agents", []),
                                "escalation_level": escalation_level,
                            }
                        )
                        
                        # Send to manager
                        try:
                            messaging = getattr(self._team, "_messaging", None)
                            if messaging:
                                messaging.route_message(message)
                                logger.info(f"Escalated conflict {conflict_id} to manager {manager_id}")
                        except Exception as e:
                            logger.error(f"Error sending escalation message: {e}")
                
                return True
        
        logger.warning(f"Conflict {conflict_id} not found in team {self._team.id}")
        return False
    
    def _process_resource_queue(self, resource_id: str) -> None:
        """Process the queue for a resource.
        
        This grants the resource to the next agent in line.
        
        Args:
            resource_id: ID of the resource
        """
        if resource_id not in self._resource_requests:
            return
            
        if not self._resource_requests[resource_id]:
            return
            
        # Assign to next agent
        next_agent_id = self._resource_requests[resource_id].pop(0)
        self._resource_ownership[resource_id] = next_agent_id
        
        logger.info(f"Granted resource {resource_id} to next agent {next_agent_id}")
        
        # If queue is now empty, remove it
        if not self._resource_requests[resource_id]:
            del self._resource_requests[resource_id]
            
        # Trigger event
        self.trigger_event(
            CoordinationEvent.RESOURCE_REQUESTED,
            {
                "agent_id": next_agent_id,
                "resource_id": resource_id,
                "granted": True,
            }
        )
    
    def get_active_conflicts(self, conflict_type: Optional[Union[ConflictType, str]] = None) -> List[Dict[str, Any]]:
        """Get all active conflicts.
        
        Args:
            conflict_type: Optional type to filter by
            
        Returns:
            List of active conflict dictionaries
        """
        # Convert conflict_type to string if it's an enum
        type_str = None
        if isinstance(conflict_type, ConflictType):
            type_str = conflict_type.value
        elif isinstance(conflict_type, str):
            type_str = conflict_type
            
        # Filter conflicts
        active_conflicts = []
        for conflict in self._conflicts:
            # Skip resolved conflicts
            if conflict["status"] == ConflictStatus.RESOLVED.value:
                continue
                
            # Filter by type if specified
            if type_str and conflict.get("type") != type_str:
                continue
                
            active_conflicts.append(conflict)
        
        return active_conflicts
    
    def get_conflict_by_id(self, conflict_id: str) -> Optional[Dict[str, Any]]:
        """Get a conflict by ID.
        
        Args:
            conflict_id: ID of the conflict
            
        Returns:
            Conflict dictionary or None if not found
        """
        for conflict in self._conflicts:
            if conflict["id"] == conflict_id:
                return conflict
                
        return None
    
    def get_agent_conflicts(self, agent_id: str, include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Get all conflicts involving a specific agent.
        
        Args:
            agent_id: ID of the agent
            include_resolved: Whether to include resolved conflicts
            
        Returns:
            List of conflict dictionaries
        """
        agent_conflicts = []
        
        for conflict in self._conflicts:
            # Skip resolved conflicts unless requested
            if conflict["status"] == ConflictStatus.RESOLVED.value and not include_resolved:
                continue
                
            # Check if agent is involved
            if agent_id in conflict.get("agents", []):
                agent_conflicts.append(conflict)
                
        return agent_conflicts
    
    def get_resource_conflicts(self, resource_id: str, include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Get all conflicts involving a specific resource.
        
        Args:
            resource_id: ID of the resource
            include_resolved: Whether to include resolved conflicts
            
        Returns:
            List of conflict dictionaries
        """
        resource_conflicts = []
        
        for conflict in self._conflicts:
            # Skip resolved conflicts unless requested
            if conflict["status"] == ConflictStatus.RESOLVED.value and not include_resolved:
                continue
                
            # Check if resource is involved
            if conflict.get("resource_id") == resource_id:
                resource_conflicts.append(conflict)
                
        return resource_conflicts
    
    def get_task_conflicts(self, task_id: str, include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Get all conflicts involving a specific task.
        
        Args:
            task_id: ID of the task
            include_resolved: Whether to include resolved conflicts
            
        Returns:
            List of conflict dictionaries
        """
        task_conflicts = []
        
        for conflict in self._conflicts:
            # Skip resolved conflicts unless requested
            if conflict["status"] == ConflictStatus.RESOLVED.value and not include_resolved:
                continue
                
            # Check if task is involved
            if task_id in conflict.get("task_ids", []):
                task_conflicts.append(conflict)
                
        return task_conflicts
    
    def get_conflict_statistics(self) -> Dict[str, Any]:
        """Get statistics about conflicts in the team.
        
        Returns:
            Dictionary of conflict statistics
        """
        stats = {
            "total": len(self._conflicts),
            "active": len(self.get_active_conflicts()),
            "resolved": len([c for c in self._conflicts if c["status"] == ConflictStatus.RESOLVED.value]),
            "by_type": {},
            "by_status": {},
            "by_severity": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "average_resolution_time": None,
            "escalated": len([c for c in self._conflicts if c.get("escalation_level", 0) > 0]),
        }
        
        # Count by type
        for conflict in self._conflicts:
            conflict_type = conflict.get("type", "unknown")
            stats["by_type"][conflict_type] = stats["by_type"].get(conflict_type, 0) + 1
            
            # Count by status
            status = conflict.get("status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # Count by severity
            severity = conflict.get("severity", 1)
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
        
        # Calculate average resolution time for resolved conflicts
        resolved_conflicts = [c for c in self._conflicts if c["status"] == ConflictStatus.RESOLVED.value]
        if resolved_conflicts:
            total_resolution_time = 0
            count = 0
            
            for conflict in resolved_conflicts:
                if conflict.get("created_at") and conflict.get("resolved_at"):
                    try:
                        created = datetime.fromisoformat(conflict["created_at"])
                        resolved = datetime.fromisoformat(conflict["resolved_at"])
                        resolution_time = (resolved - created).total_seconds()
                        total_resolution_time += resolution_time
                        count += 1
                    except (ValueError, TypeError):
                        pass
            
            if count > 0:
                stats["average_resolution_time"] = total_resolution_time / count
        
        return stats
    
    def notify_task_status_change(
        self, 
        task: TeamTask, 
        old_status: TaskStatus, 
        new_status: TaskStatus
    ) -> None:
        """Notify about a task status change.
        
        Args:
            task: Task that changed
            old_status: Previous status
            new_status: New status
        """
        # Determine event type
        event = None
        
        if new_status == TaskStatus.IN_PROGRESS and old_status != TaskStatus.IN_PROGRESS:
            event = CoordinationEvent.TASK_STARTED
        elif new_status == TaskStatus.COMPLETED:
            event = CoordinationEvent.TASK_COMPLETED
        elif new_status == TaskStatus.FAILED:
            event = CoordinationEvent.TASK_FAILED
        elif new_status == TaskStatus.BLOCKED:
            event = CoordinationEvent.TASK_BLOCKED
        
        # Trigger event if applicable
        if event:
            self.trigger_event(
                event,
                {
                    "task_id": task.id,
                    "task_description": task.description,
                    "agent_id": task.assigned_to,
                    "old_status": old_status.name,
                    "new_status": new_status.name,
                }
            )
    
    def notify_task_assignment(
        self, 
        task: TeamTask, 
        agent_id: str
    ) -> None:
        """Notify about a task assignment.
        
        Args:
            task: Task that was assigned
            agent_id: ID of the agent the task was assigned to
        """
        self.trigger_event(
            CoordinationEvent.TASK_ASSIGNED,
            {
                "task_id": task.id,
                "task_description": task.description,
                "agent_id": agent_id,
            }
        )
    
    def notify_member_joined(
        self, 
        agent_id: str, 
        role: Any
    ) -> None:
        """Notify about a new team member.
        
        Args:
            agent_id: ID of the new agent
            role: Role of the new agent
        """
        self.trigger_event(
            CoordinationEvent.MEMBER_JOINED,
            {
                "agent_id": agent_id,
                "role": str(role),
            }
        )
    
    def notify_member_left(
        self, 
        agent_id: str
    ) -> None:
        """Notify about a team member leaving.
        
        Args:
            agent_id: ID of the leaving agent
        """
        self.trigger_event(
            CoordinationEvent.MEMBER_LEFT,
            {
                "agent_id": agent_id,
            }
        )
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get status of all resources.
        
        Returns:
            Dictionary of resource status information
        """
        return {
            "owned_resources": self._resource_ownership,
            "resource_requests": self._resource_requests,
            "conflicts": len(self.get_active_conflicts()),
        }
    
    async def coordinate_task(
        self, 
        task: TeamTask
    ) -> Optional[str]:
        """Coordinate a task execution.
        
        This finds the best agent for a task based on the current strategy.
        
        Args:
            task: Task to coordinate
            
        Returns:
            ID of the selected agent, or None if no agent was selected
        """
        # Get all members
        members = self._team.get_members()
        if not members:
            logger.warning(f"No members in team {self._team.id} to coordinate task")
            return None
        
        # Apply different strategies
        if self._strategy == CoordinationStrategy.CENTRALIZED:
            # Get manager
            manager = None
            membership_manager = getattr(self._team, "_membership", None)
            if membership_manager and hasattr(membership_manager, "manager"):
                manager = membership_manager.manager
            
            if manager:
                # Let manager decide
                logger.info(f"Using centralized strategy: delegating task {task.id} to manager {manager.id}")
                return manager.id
            else:
                # No manager, fall back to first member
                logger.info(f"No manager in team {self._team.id}, assigning task to first member")
                return members[0].id
        
        elif self._strategy == CoordinationStrategy.DECENTRALIZED:
            # Find agent with least tasks
            task_manager = getattr(self._team, "_tasks", None)
            if task_manager:
                agent_counts = {}
                
                for agent in members:
                    agent_tasks = task_manager.get_agent_tasks(agent.id)
                    active_tasks = [t for t in agent_tasks if t.status != TaskStatus.COMPLETED]
                    agent_counts[agent.id] = len(active_tasks)
                
                # Find agent with lowest count
                min_agent_id = min(agent_counts.items(), key=lambda x: x[1])[0]
                logger.info(f"Using decentralized strategy: assigning task {task.id} to least busy agent {min_agent_id}")
                return min_agent_id
        
        # Default: just return first agent
        logger.info(f"Using default strategy: assigning task {task.id} to first agent {members[0].id}")
        return members[0].id
