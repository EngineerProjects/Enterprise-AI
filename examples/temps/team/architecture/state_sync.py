"""
Team-agent state synchronization for Enterprise AI.

This module provides functionality for synchronizing state between
team components and individual agents, ensuring consistency across the system.
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, AgentState, Task
from enterprise_ai.agent.state.state import create_agent_state
from enterprise_ai.logger import get_logger
from enterprise_ai.team.core.types import TeamProtocol
from enterprise_ai.team.architecture.task_manager import TeamTask, TaskStatus

logger = get_logger("team.architecture.state_sync")


class SyncDirection(Enum):
    """Direction of state synchronization."""
    
    TEAM_TO_AGENT = "team_to_agent"  # Sync from team to agent
    AGENT_TO_TEAM = "agent_to_team"  # Sync from agent to team
    BIDIRECTIONAL = "bidirectional"  # Sync in both directions


class SyncMode(Enum):
    """Mode of state synchronization."""
    
    MANUAL = "manual"       # Sync only when explicitly requested
    PERIODIC = "periodic"   # Sync at regular intervals
    AUTOMATIC = "automatic" # Sync automatically on changes


class SyncComponent(Enum):
    """Components to synchronize."""
    
    TASKS = "tasks"            # Sync task assignments and status
    CAPABILITIES = "capabilities"  # Sync agent capabilities
    MEMORY = "memory"          # Sync agent memory
    TOOLS = "tools"            # Sync tool access and usage
    CONVERSATION = "conversation"  # Sync conversation history
    ROLES = "roles"            # Sync role assignments
    ALL = "all"                # Sync all components


class StateSyncManager:
    """Team-agent state synchronization manager.
    
    This component ensures that states remain consistent between
    team components and individual agents.
    """
    
    def __init__(
        self, 
        team: "TeamProtocol",
        sync_mode: SyncMode = SyncMode.AUTOMATIC,
        sync_interval: int = 60,  # seconds
        components: Optional[List[SyncComponent]] = None
    ):
        """Initialize the state synchronization manager.
        
        Args:
            team: Team to manage synchronization for
            sync_mode: Mode of synchronization
            sync_interval: Interval for periodic synchronization (seconds)
            components: Components to synchronize (default: all)
        """
        self._team = team
        self._sync_mode = sync_mode
        self._sync_interval = max(10, sync_interval)
        self._components = components or [SyncComponent.ALL]
        self._last_sync: Dict[str, Dict[SyncComponent, datetime]] = {}
        self._sync_errors: Dict[str, List[Dict[str, Any]]] = {}
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        self._agent_versions: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Initialized state sync manager for team {team.id} with mode {sync_mode.value}")
        
        # Auto-start periodic sync if in periodic mode
        if sync_mode == SyncMode.PERIODIC:
            self.start_periodic_sync()
    
    def start_periodic_sync(self) -> None:
        """Start periodic synchronization.
        
        This creates a background task that synchronizes
        state at regular intervals.
        """
        if self._sync_task is not None:
            logger.warning(f"Periodic sync already running for team {self._team.id}")
            return
        
        self._running = True
        self._sync_task = asyncio.create_task(self._periodic_sync_loop())
        logger.info(f"Started periodic sync for team {self._team.id} with interval {self._sync_interval}s")
    
    def stop_periodic_sync(self) -> None:
        """Stop periodic synchronization."""
        self._running = False
        
        if self._sync_task is not None:
            self._sync_task.cancel()
            self._sync_task = None
            
        logger.info(f"Stopped periodic sync for team {self._team.id}")
    
    async def sync_agent(
        self, 
        agent_id: str, 
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        components: Optional[List[SyncComponent]] = None
    ) -> Dict[str, Any]:
        """Synchronize state with a specific agent.
        
        Args:
            agent_id: ID of the agent to synchronize with
            direction: Direction of synchronization
            components: Components to synchronize (default: configured components)
            
        Returns:
            Dictionary with sync results
        """
        agent = self._team.get_member(agent_id)
        if not agent:
            logger.warning(f"Cannot sync with unknown agent {agent_id}")
            return {"success": False, "error": "Agent not found"}
        
        # Use configured components if none specified
        sync_components = components or self._components
        
        # Expand ALL to all components
        if SyncComponent.ALL in sync_components:
            sync_components = [c for c in SyncComponent if c != SyncComponent.ALL]
        
        results: Dict[SyncComponent, bool] = {}
        sync_time = datetime.now()
        
        try:
            # Perform sync for each component in specified direction
            for component in sync_components:
                if direction in [SyncDirection.TEAM_TO_AGENT, SyncDirection.BIDIRECTIONAL]:
                    # Team to agent
                    team_to_agent = await self._sync_team_to_agent(agent, component)
                    results[component] = team_to_agent
                
                if direction in [SyncDirection.AGENT_TO_TEAM, SyncDirection.BIDIRECTIONAL]:
                    # Agent to team
                    agent_to_team = await self._sync_agent_to_team(agent, component)
                    results[component] = results.get(component, True) and agent_to_team
            
            # Record successful sync
            if agent_id not in self._last_sync:
                self._last_sync[agent_id] = {}
                
            for component in sync_components:
                self._last_sync[agent_id][component] = sync_time
            
            # Update agent version info
            self._update_agent_version(agent)
            
            logger.info(f"Synchronized state with agent {agent_id} ({direction.value})")
            
            return {
                "success": True,
                "sync_time": sync_time.isoformat(),
                "agent_id": agent_id,
                "direction": direction.value,
                "components": {c.value: results.get(c, False) for c in sync_components}
            }
            
        except Exception as e:
            # Record error
            self._record_sync_error(agent_id, str(e))
            
            logger.error(f"Error synchronizing with agent {agent_id}: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "agent_id": agent_id,
                "direction": direction.value
            }
    
    async def sync_all_agents(
        self,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        components: Optional[List[SyncComponent]] = None
    ) -> Dict[str, Any]:
        """Synchronize state with all team members.
        
        Args:
            direction: Direction of synchronization
            components: Components to synchronize (default: configured components)
            
        Returns:
            Dictionary with sync results
        """
        members = self._team.get_members()
        if not members:
            logger.warning(f"No members to sync in team {self._team.id}")
            return {"success": True, "agents_synced": 0}
        
        sync_results = {}
        success_count = 0
        
        # Sync with each member
        for agent in members:
            result = await self.sync_agent(agent.id, direction, components)
            sync_results[agent.id] = result
            
            if result.get("success", False):
                success_count += 1
        
        logger.info(f"Synchronized {success_count}/{len(members)} agents in team {self._team.id}")
        
        return {
            "success": success_count == len(members),
            "agents_synced": success_count,
            "total_agents": len(members),
            "results": sync_results
        }
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get the current synchronization status.
        
        Returns:
            Dictionary with synchronization status
        """
        members = self._team.get_members()
        agent_status = {}
        
        for agent in members:
            agent_id = agent.id
            
            # Get last sync times
            last_sync = self._last_sync.get(agent_id, {})
            latest_sync = None
            
            if last_sync:
                latest_sync = max(last_sync.values())
            
            # Get error count
            error_count = len(self._sync_errors.get(agent_id, []))
            
            # Get agent version
            version = self._agent_versions.get(agent_id, {})
            
            # Calculate sync status
            status = "unknown"
            if latest_sync:
                seconds_since_sync = (datetime.now() - latest_sync).total_seconds()
                if seconds_since_sync < self._sync_interval * 2:
                    status = "synced"
                else:
                    status = "stale"
            
            agent_status[agent_id] = {
                "status": status,
                "last_sync": latest_sync.isoformat() if latest_sync else None,
                "error_count": error_count,
                "version": version
            }
        
        return {
            "mode": self._sync_mode.value,
            "interval": self._sync_interval,
            "components": [c.value for c in self._components],
            "running": self._running,
            "agent_status": agent_status
        }
    
    def _update_agent_version(self, agent: AgentProtocol) -> None:
        """Update agent version information.
        
        This tracks agent-specific version information for state comparison.
        
        Args:
            agent: Agent to update version for
        """
        agent_id = agent.id
        
        # Create version dictionary
        version = {
            "timestamp": datetime.now().isoformat()
        }
        
        # Add task information if available
        if hasattr(agent, "state") and hasattr(agent.state, "current_task"):
            current_task = agent.state.current_task
            if current_task:
                # Store task hash
                task_dict = getattr(current_task, "to_dict", lambda: {"id": str(current_task)})()
                version["task"] = task_dict.get("id", str(current_task))
        
        # Add capabilities if available
        if hasattr(agent, "capabilities"):
            capabilities = getattr(agent, "capabilities", set())
            version["capabilities"] = list(capabilities)
        
        # Add state hash if possible
        if hasattr(agent, "state") and hasattr(agent.state, "to_dict"):
            try:
                state_dict = agent.state.to_dict()
                # Use timestamp as a simple version indicator
                version["state_timestamp"] = state_dict.get("timestamps", {}).get("last_active")
            except Exception:
                pass
        
        # Store version
        self._agent_versions[agent_id] = version
    
    def _record_sync_error(self, agent_id: str, error: str) -> None:
        """Record a synchronization error.
        
        Args:
            agent_id: ID of the agent that had an error
            error: Error message
        """
        if agent_id not in self._sync_errors:
            self._sync_errors[agent_id] = []
            
        self._sync_errors[agent_id].append({
            "timestamp": datetime.now().isoformat(),
            "error": error
        })
        
        # Limit error history
        if len(self._sync_errors[agent_id]) > 10:
            self._sync_errors[agent_id] = self._sync_errors[agent_id][-10:]
    
    async def _periodic_sync_loop(self) -> None:
        """Background loop for periodic synchronization."""
        try:
            while self._running:
                # Perform sync with all agents
                try:
                    await self.sync_all_agents()
                except Exception as e:
                    logger.error(f"Error in periodic sync: {e}")
                
                # Wait for next sync interval
                await asyncio.sleep(self._sync_interval)
        except asyncio.CancelledError:
            logger.info(f"Periodic sync task cancelled for team {self._team.id}")
    
    async def _sync_team_to_agent(
        self, 
        agent: AgentProtocol,
        component: SyncComponent
    ) -> bool:
        """Synchronize state from team to agent.
        
        Args:
            agent: Agent to synchronize with
            component: Component to synchronize
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Skip if agent has no state
        if not hasattr(agent, "state"):
            logger.warning(f"Agent {agent_id} has no state, skipping sync")
            return False
            
        try:
            if component == SyncComponent.TASKS:
                # Sync tasks from team to agent
                return await self._sync_tasks_to_agent(agent)
            elif component == SyncComponent.TOOLS:
                # Sync tool access from team to agent
                return await self._sync_tools_to_agent(agent)
            elif component == SyncComponent.ROLES:
                # Sync roles from team to agent
                return await self._sync_roles_to_agent(agent)
            else:
                # Other components not yet implemented for team-to-agent sync
                logger.debug(f"Team-to-agent sync for {component.value} not implemented yet")
                return True
        except Exception as e:
            logger.error(f"Error in team-to-agent sync for {component.value}: {e}")
            return False
    
    async def _sync_agent_to_team(
        self, 
        agent: AgentProtocol,
        component: SyncComponent
    ) -> bool:
        """Synchronize state from agent to team.
        
        Args:
            agent: Agent to synchronize with
            component: Component to synchronize
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Skip if agent has no state
        if not hasattr(agent, "state"):
            logger.warning(f"Agent {agent_id} has no state, skipping sync")
            return False
            
        try:
            if component == SyncComponent.TASKS:
                # Sync tasks from agent to team
                return await self._sync_tasks_from_agent(agent)
            elif component == SyncComponent.CAPABILITIES:
                # Sync capabilities from agent to team
                return await self._sync_capabilities_from_agent(agent)
            else:
                # Other components not yet implemented for agent-to-team sync
                logger.debug(f"Agent-to-team sync for {component.value} not implemented yet")
                return True
        except Exception as e:
            logger.error(f"Error in agent-to-team sync for {component.value}: {e}")
            return False
    
    async def _sync_tasks_to_agent(self, agent: AgentProtocol) -> bool:
        """Synchronize tasks from team to agent.
        
        Args:
            agent: Agent to synchronize with
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Get team task manager
        task_manager = getattr(self._team, "_tasks", None)
        if not task_manager:
            logger.warning(f"Team {self._team.id} has no task manager, skipping task sync")
            return False
        
        # Get agent's current task
        agent_current_task = None
        if hasattr(agent.state, "current_task"):
            agent_current_task = agent.state.current_task
        
        # Get agent tasks from team
        agent_tasks = task_manager.get_agent_tasks(agent_id)
        
        # No tasks assigned, clear agent's current task if any
        if not agent_tasks:
            if agent_current_task:
                agent.state.current_task = None
                logger.info(f"Cleared current task for agent {agent_id} (no team tasks assigned)")
            return True
        
        # Find the highest priority active task
        active_tasks = [
            t for t in agent_tasks 
            if t.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]
        ]
        
        if not active_tasks:
            # No active tasks, clear agent's current task if any
            if agent_current_task:
                agent.state.current_task = None
                logger.info(f"Cleared current task for agent {agent_id} (no active team tasks)")
            return True
        
        # Sort by priority (higher first), then by creation time (newer first)
        sorted_tasks = sorted(
            active_tasks, 
            key=lambda t: (t.priority, t.created_at.timestamp() if t.created_at else 0),
            reverse=True
        )
        
        # Get highest priority task
        highest_priority_task = sorted_tasks[0]
        
        # Check if agent's current task is already the highest priority
        if agent_current_task and hasattr(agent_current_task, "id"):
            if agent_current_task.id == highest_priority_task.id:
                # Task already assigned, just ensure status is in sync
                if hasattr(agent_current_task, "status") and agent_current_task.status != highest_priority_task.status:
                    # Update task status
                    agent_current_task.status = highest_priority_task.status
                    logger.info(f"Updated task status for agent {agent_id}: {highest_priority_task.status.name}")
                return True
        
        # Assign the task to the agent
        try:
            # Convert TeamTask to agent Task
            agent_task = _convert_team_task_to_agent_task(highest_priority_task)
            
            # Assign to agent
            agent.state.current_task = agent_task
            logger.info(f"Assigned task {highest_priority_task.id} to agent {agent_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error assigning task to agent {agent_id}: {e}")
            return False
    
    async def _sync_tasks_from_agent(self, agent: AgentProtocol) -> bool:
        """Synchronize tasks from agent to team.
        
        Args:
            agent: Agent to synchronize with
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Get team task manager
        task_manager = getattr(self._team, "_tasks", None)
        if not task_manager:
            logger.warning(f"Team {self._team.id} has no task manager, skipping task sync")
            return False
        
        # Get agent's current task
        agent_current_task = None
        if hasattr(agent.state, "current_task"):
            agent_current_task = agent.state.current_task
        
        if not agent_current_task:
            # No current task in agent, nothing to sync
            return True
        
        # Get task ID
        task_id = None
        if hasattr(agent_current_task, "id"):
            task_id = agent_current_task.id
        
        if not task_id:
            logger.warning(f"Agent {agent_id} has task without ID, skipping sync")
            return False
        
        # Check if task exists in team
        team_task = task_manager.get_task(task_id)
        
        if not team_task:
            # Task doesn't exist in team, create it
            task_dict = {}
            
            if hasattr(agent_current_task, "to_dict"):
                task_dict = agent_current_task.to_dict()
            else:
                # Create minimal task dict
                task_dict = {
                    "id": task_id,
                    "description": getattr(agent_current_task, "description", "Task from agent"),
                    "status": getattr(agent_current_task, "status", TaskStatus.ASSIGNED.name),
                }
            
            # Create task in team
            team_task = task_manager.create_task(task_dict)
            
            # Assign to agent
            task_manager.assign_task(team_task.id, agent_id)
            
            logger.info(f"Created task {task_id} in team {self._team.id} from agent {agent_id}")
        else:
            # Task exists, update status if necessary
            agent_status = _get_task_status(agent_current_task)
            
            if agent_status and agent_status != team_task.status:
                # Update team task status
                task_manager.update_status(task_id, agent_status)
                logger.info(f"Updated task {task_id} status to {agent_status.name} from agent {agent_id}")
        
        return True
    
    async def _sync_tools_to_agent(self, agent: AgentProtocol) -> bool:
        """Synchronize tool access from team to agent.
        
        Args:
            agent: Agent to synchronize with
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Get team tool registry
        tool_registry = getattr(self._team, "_tool_registry", None)
        if not tool_registry:
            logger.warning(f"Team {self._team.id} has no tool registry, skipping tool sync")
            return False
        
        # Get accessible tools
        accessible_tools = tool_registry.get_accessible_tools(agent_id)
        
        # No tools accessible, nothing to sync
        if not accessible_tools:
            return True
        
        # Typically we would register these tools with the agent
        # but this depends on agent-specific implementation
        # For now, just log the accessible tools
        logger.debug(f"Agent {agent_id} has access to tools: {accessible_tools}")
        
        return True
    
    async def _sync_roles_to_agent(self, agent: AgentProtocol) -> bool:
        """Synchronize role from team to agent.
        
        Args:
            agent: Agent to synchronize with
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Get team membership manager
        membership = getattr(self._team, "_membership", None)
        if not membership:
            logger.warning(f"Team {self._team.id} has no membership manager, skipping role sync")
            return False
        
        # Get agent role in team
        team_role = membership.get_role(agent_id)
        
        if not team_role:
            # No role assigned in team
            return True
        
        # Typically we would update the agent's role
        # but this depends on agent-specific implementation
        # For now, just log the role
        logger.debug(f"Agent {agent_id} has role {team_role} in team {self._team.id}")
        
        return True
    
    async def _sync_capabilities_from_agent(self, agent: AgentProtocol) -> bool:
        """Synchronize capabilities from agent to team.
        
        Args:
            agent: Agent to synchronize with
            
        Returns:
            True if synchronization was successful, False otherwise
        """
        agent_id = agent.id
        
        # Get agent capabilities
        if not hasattr(agent, "capabilities"):
            logger.warning(f"Agent {agent_id} has no capabilities attribute, skipping sync")
            return False
        
        capabilities = agent.capabilities
        
        # Get team membership manager
        membership = getattr(self._team, "_membership", None)
        if not membership:
            logger.warning(f"Team {self._team.id} has no membership manager, skipping capabilities sync")
            return False
        
        # Just log capabilities for now
        logger.debug(f"Agent {agent_id} has capabilities: {capabilities}")
        
        return True


def _convert_team_task_to_agent_task(team_task: TeamTask) -> Task:
    """Convert a team task to an agent task.
    
    Args:
        team_task: Team task to convert
        
    Returns:
        Agent task
    """
    # Get task data
    task_dict = team_task.to_dict()
    
    # Convert status enum to agent TaskStatus enum
    status_str = task_dict.get("status", "PENDING")
    
    # Create agent task
    return Task(
        id=team_task.id,
        description=team_task.description,
        status=getattr(task_module_status, status_str, task_module_status.PENDING),
        created_at=team_task.created_at,
        updated_at=team_task.updated_at,
        dependencies=team_task.dependencies,
        metadata=team_task.metadata
    )


def _get_task_status(task: Any) -> Optional[TaskStatus]:
    """Get TaskStatus from any task object.
    
    Args:
        task: Task object
        
    Returns:
        TaskStatus enum value or None if unknown
    """
    # If task already has team TaskStatus
    if hasattr(task, "status") and isinstance(task.status, TaskStatus):
        return task.status
    
    # If task has status as string or agent TaskStatus enum
    if hasattr(task, "status"):
        status = task.status
        
        # Convert string to TeamTask status
        if isinstance(status, str):
            try:
                return TaskStatus[status.upper()]
            except KeyError:
                pass
        
        # Convert agent TaskStatus to TeamTask status
        if hasattr(status, "name"):
            status_name = status.name
            try:
                return TaskStatus[status_name]
            except KeyError:
                # Map agent status names to team status names if different
                status_map = {
                    "PENDING": TaskStatus.PENDING,
                    "IN_PROGRESS": TaskStatus.IN_PROGRESS,
                    "COMPLETED": TaskStatus.COMPLETED,
                    "FAILED": TaskStatus.FAILED,
                    "BLOCKED": TaskStatus.BLOCKED,
                    "CANCELED": TaskStatus.BLOCKED,  # Map to closest equivalent
                }
                
                return status_map.get(status_name)
    
    return None


# Import task status here to avoid circular import
from enterprise_ai.agent.core.types import TaskStatus as task_module_status
