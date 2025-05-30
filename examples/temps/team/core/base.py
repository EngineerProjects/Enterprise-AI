"""
Core team implementation for Enterprise AI.

This module provides the foundational team class with delegation
to specialized manager components for different responsibilities.
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from enterprise_ai.agent.architecture.utils import generate_id
from enterprise_ai.agent.core.types import AgentProtocol, MessageProtocol, Task
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.team.architecture.coordinator import CoordinationManager
from enterprise_ai.team.architecture.lifecycle import LifecycleManager
from enterprise_ai.team.architecture.membership import MembershipManager
from enterprise_ai.team.architecture.messaging import MessagingManager
from enterprise_ai.team.architecture.task_manager import TaskManager, TeamTask
from enterprise_ai.team.core.types import TeamProtocol, TeamMemberRole
from enterprise_ai.team.roles.base import BaseTeamRole
from enterprise_ai.team.tools.registry import TeamToolRegistry, ToolAccessLevel
from enterprise_ai.team.tools.sharing import (
    ToolSharingManager, 
    ToolSharingPolicy,
    DefaultSharingPolicy
)
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.tool.core.result import ToolResult

logger = get_logger("team.base")


class BaseTeam(TeamProtocol):
    """Base team implementation.
    
    This class provides a foundation for all team types with common
    functionality. It implements the TeamProtocol interface.
    """
    
    def __init__(
        self,
        team_id: Optional[str] = None,
        name: Optional[str] = None,
        max_members: Optional[int] = None,
        **kwargs: Any,
    ):
        """Initialize the team.
        
        Args:
            team_id: Optional unique identifier
            name: Optional human-readable name
            max_members: Optional maximum number of team members
            **kwargs: Additional team-specific parameters
        """
        # Basic team properties
        self._id = team_id or generate_id("team-")
        self._name = name or f"Team-{self._id[-4:]}"
        self._max_members = max_members
        
        # Initialize manager components
        self._membership = MembershipManager(self, max_members=max_members)
        self._messaging = MessagingManager(self)
        self._tasks = TaskManager(self)
        self._lifecycle = LifecycleManager(self)
        self._coordinator = CoordinationManager(self)
        
        # Initialize tool components
        self._tool_registry = TeamToolRegistry(self, self._membership)
        sharing_policy = kwargs.get("sharing_policy", DefaultSharingPolicy(self))
        self._tool_sharing = ToolSharingManager(
            self, 
            self._tool_registry, 
            self._membership, 
            self._tasks, 
            sharing_policy
        )
        
        # Initialize state synchronization component
        from enterprise_ai.team.architecture.state_sync import StateSyncManager, SyncMode
        
        # Handle sync_mode as string or enum
        sync_mode_param = kwargs.get("sync_mode", SyncMode.AUTOMATIC)
        if isinstance(sync_mode_param, str):
            try:
                sync_mode = SyncMode[sync_mode_param.upper()]
            except KeyError:
                logger.warning(f"Invalid sync mode: {sync_mode_param}, defaulting to AUTOMATIC")
                sync_mode = SyncMode.AUTOMATIC
        else:
            sync_mode = sync_mode_param
            
        sync_interval = kwargs.get("sync_interval", 60)
        self._state_sync = StateSyncManager(self, sync_mode, sync_interval)
        
        logger.info(f"Initialized team {self._id} ({self._name})")
    
    @property
    def id(self) -> str:
        """Get the team's unique identifier."""
        return self._id
    
    @property
    def name(self) -> str:
        """Get the team's human-readable name."""
        return self._name
    
    @property
    def max_members(self) -> Optional[int]:
        """Get the team's maximum number of members."""
        return self._max_members
    
    def add_member(self, agent: AgentProtocol, role: Optional[Any] = None) -> bool:
        """Add an agent to the team.
        
        Args:
            agent: Agent to add to the team
            role: Optional role for the agent in the team
            
        Returns:
            True if agent was added successfully, False otherwise
        """
        result = self._membership.add_member(agent, role)
        
        # Notify coordinator of new member
        if result:
            resolved_role = role or TeamMemberRole.MEMBER
            self._coordinator.notify_member_joined(agent.id, resolved_role)
        
        return result
    
    def remove_member(self, agent_id: str) -> bool:
        """Remove an agent from the team.
        
        Args:
            agent_id: ID of the agent to remove
            
        Returns:
            True if agent was removed successfully, False otherwise
        """
        result = self._membership.remove_member(agent_id)
        
        # Notify coordinator of member leaving
        if result:
            self._coordinator.notify_member_left(agent_id)
        
        return result
    
    def get_members(self) -> List[AgentProtocol]:
        """Get all team members.
        
        Returns:
            List of all agents in the team
        """
        return self._membership.get_members()
    
    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID.
        
        Args:
            agent_id: ID of the agent to retrieve
            
        Returns:
            Agent with the specified ID, or None if not found
        """
        return self._membership.get_member(agent_id)
    
    def assign_task(self, task: Union[Task, Dict[str, Any]], agent_id: Optional[str] = None) -> bool:
        """Assign a task to the team or a specific team member.
        
        Args:
            task: Task to assign
            agent_id: Optional ID of the specific agent to assign the task to
            
        Returns:
            True if task was assigned successfully, False otherwise
        """
        # Create or convert to team task
        team_task = self._tasks.create_task(task)
        
        # If agent_id is provided, assign directly to that agent
        if agent_id:
            return self._tasks.assign_task(team_task.id, agent_id)
        
        # Otherwise, find the most appropriate agent
        best_agent_id = self._tasks.find_agent_for_task(team_task)
        
        if best_agent_id:
            return self._tasks.assign_task(team_task.id, best_agent_id)
        
        # If no specific agent found and team has manager, assign to manager
        manager = self._membership.manager
        if manager:
            return self._tasks.assign_task(team_task.id, manager.id)
        
        # Otherwise, auto-balance across team
        self._tasks.assign_available_tasks()
        
        # Task was created but may be waiting for assignment
        logger.info(f"Task {team_task.id} created in team {self.id}, waiting for assignment")
        return True
    
    def process_message(self, message: Union[str, MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Process a message directed to the team.
        
        Args:
            message: Message to process
            **kwargs: Additional parameters for processing
            
        Returns:
            Response message
        """
        # This is a basic implementation - process message at team level
        if isinstance(message, str):
            # Create a user message from the string
            message = Message.user_message(message)
        
        # Create simple response
        response = Message.assistant_message(
            f"Hello, I am team {self.name}. I've received your message, but advanced team processing is not yet implemented."
        )
        
        return response
    
    async def aprocess_message(self, message: Union[str, MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Process a message asynchronously.
        
        Args:
            message: Message to process
            **kwargs: Additional parameters for processing
            
        Returns:
            Response message
        """
        # Basic implementation - just calls sync version
        return self.process_message(message, **kwargs)
    
    def broadcast_message(self, message: Union[str, MessageProtocol]) -> List[MessageProtocol]:
        """Broadcast a message to all team members.
        
        Args:
            message: Message to broadcast
            
        Returns:
            List of response messages from team members
        """
        responses: List[MessageProtocol] = []
        
        if isinstance(message, str):
            # Create a user message from the string
            message = Message.user_message(message)
        
        # Send to each member and collect responses
        for agent in self._membership.get_members():
            try:
                response = agent.process_message(message)
                responses.append(response)
            except Exception as e:
                logger.error(f"Error broadcasting to agent {agent.id}: {e}")
                # Create an error response
                error_response = Message.assistant_message(
                    f"Error processing message for agent {agent.id}: {str(e)}"
                )
                responses.append(error_response)
        
        return responses
    
    async def abroadcast_message(self, message: Union[str, MessageProtocol]) -> List[MessageProtocol]:
        """Broadcast a message asynchronously.
        
        Args:
            message: Message to broadcast
            
        Returns:
            List of response messages from team members
        """
        responses: List[MessageProtocol] = []
        
        if isinstance(message, str):
            # Create a user message from the string
            message = Message.user_message(message)
        
        # Get all members
        members = self._membership.get_members()
        
        # Send to each member concurrently and collect responses
        tasks = []
        for agent in members:
            tasks.append(self._process_agent_message(agent, message))
        
        # Wait for all processing to complete
        agent_responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle responses, including errors
        for agent, response in zip(members, agent_responses):
            if isinstance(response, Exception):
                logger.error(f"Error broadcasting to agent {agent.id}: {response}")
                # Create an error response
                error_response = Message.assistant_message(
                    f"Error processing message for agent {agent.id}: {str(response)}"
                )
                responses.append(error_response)
            else:
                responses.append(response)
        
        return responses
    
    async def _process_agent_message(self, agent: AgentProtocol, message: MessageProtocol) -> MessageProtocol:
        """Process a message with an agent asynchronously.
        
        Helper method for abroadcast_message.
        
        Args:
            agent: Agent to process the message
            message: Message to process
            
        Returns:
            Response message
        """
        try:
            # Check if agent has async processing
            if hasattr(agent, "aprocess_message"):
                return await agent.aprocess_message(message)
            else:
                # Fall back to sync processing
                return agent.process_message(message)
        except Exception as e:
            # Re-raise to be caught in abroadcast_message
            raise e
    
    def get_status(self) -> Dict[str, Any]:
        """Get team status information.
        
        Returns:
            Dictionary of status information
        """
        # Basic status information
        status = {
            "id": self.id,
            "name": self.name,
            "member_count": self._membership.count,
            "max_members": self._max_members,
            "members": {},
            "tasks": {},
            "lifecycle": {},
            "coordination": {},
            "tools": {},
            "state_sync": {},
        }
        
        # Add manager information if available
        manager = self._membership.manager
        if manager:
            status["manager"] = manager.id
        
        # Add basic member information
        for agent in self._membership.get_members():
            role = self._membership.get_role(agent.id)
            role_name = role.name if hasattr(role, "name") else str(role)
            
            status["members"][agent.id] = {
                "name": getattr(agent, "name", agent.id),
                "role": role_name,
            }
        
        # Add task summary
        task_summary = self._tasks.get_task_summary()
        status["tasks"] = task_summary
        
        # Add lifecycle information
        lifecycle_status = self._lifecycle.get_status()
        status["lifecycle"] = lifecycle_status
        
        # Add coordination information
        status["coordination"] = {
            "strategy": self._coordinator.strategy.value,
            "resources": self._coordinator.get_resource_status(),
            "active_conflicts": len(self._coordinator.get_active_conflicts())
        }
        
        # Add tool information
        tools = self._tool_registry.get_all_tools()
        status["tools"] = {
            "count": len(tools),
            "sharing_policy": self._tool_sharing.get_policy().get_policy_description(),
            "pending_requests": len(self._tool_sharing.get_pending_requests())
        }
        
        # Add state sync information if available
        if hasattr(self, "_state_sync"):
            try:
                # Get sync status asynchronously
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context
                    future = asyncio.ensure_future(self._state_sync.get_sync_status())
                    if hasattr(future, "_asyncio_future_blocking"):
                        # This is a real async future, not just a coroutine
                        status["state_sync"] = {"status": "running"}
                    else:
                        # Limited info since we can't get full status synchronously
                        status["state_sync"] = {
                            "mode": self._state_sync._sync_mode.value,
                            "running": getattr(self._state_sync, "_running", False)
                        }
                else:
                    # We're not in an async context, use limited info
                    status["state_sync"] = {
                        "mode": self._state_sync._sync_mode.value,
                        "running": getattr(self._state_sync, "_running", False)
                    }
            except Exception as e:
                # Handle any errors
                status["state_sync"] = {"error": str(e)}
        
        return status
        
    async def sync_agent_state(self, agent_id: str) -> Dict[str, Any]:
        """Synchronize state with a specific agent.
        
        Args:
            agent_id: ID of the agent to synchronize with
            
        Returns:
            Dictionary with sync results
        """
        if not hasattr(self, "_state_sync"):
            return {"success": False, "error": "State sync not initialized"}
        
        return await self._state_sync.sync_agent(agent_id)
    
    async def sync_all_agent_states(self) -> Dict[str, Any]:
        """Synchronize state with all team members.
        
        Returns:
            Dictionary with sync results
        """
        if not hasattr(self, "_state_sync"):
            return {"success": False, "error": "State sync not initialized"}
        
        return await self._state_sync.sync_all_agents()
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get the current state synchronization status.
        
        Returns:
            Dictionary with synchronization status
        """
        if not hasattr(self, "_state_sync"):
            return {"success": False, "error": "State sync not initialized"}
        
        return await self._state_sync.get_sync_status()
    
    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the team.
        
        Args:
            **kwargs: Initialization parameters
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        # Delegate to lifecycle manager
        success = await self._lifecycle.initialize(kwargs)
        
        return success
    
    async def terminate(self) -> bool:
        """Terminate the team and clean up resources.
        
        Returns:
            True if termination succeeded, False otherwise
        """
        # Delegate to lifecycle manager
        return await self._lifecycle.terminate()
        
    # Task management methods
    
    def get_task(self, task_id: str) -> Optional[Any]:
        """Get a task by ID.
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Task with the specified ID, or None if not found
        """
        return self._tasks.get_task(task_id)
    
    def get_all_tasks(self) -> List[Any]:
        """Get all tasks managed by the team.
        
        Returns:
            List of all tasks
        """
        return self._tasks.get_all_tasks()
    
    def get_agent_tasks(self, agent_id: str) -> List[Any]:
        """Get all tasks assigned to a specific agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tasks assigned to the agent
        """
        return self._tasks.get_agent_tasks(agent_id)
    
    def decompose_task(self, task_id: str, subtasks: List[Any]) -> List[Any]:
        """Decompose a task into subtasks.
        
        Args:
            task_id: ID of the parent task
            subtasks: List of subtask descriptions or data
            
        Returns:
            List of created subtask objects
        """
        return self._tasks.decompose_task(task_id, subtasks)
    
    def update_task_status(self, task_id: str, status: Any) -> bool:
        """Update the status of a task.
        
        Args:
            task_id: ID of the task to update
            status: New status
            
        Returns:
            True if status was updated, False otherwise
        """
        return self._tasks.update_status(task_id, status)
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get a summary of all tasks by status.
        
        Returns:
            Dictionary with task summary information
        """
        return self._tasks.get_task_summary()
    
    def get_task_tree(self, root_task_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a hierarchical tree of tasks.
        
        Args:
            root_task_id: Optional root task ID to start from, or None for all root tasks
            
        Returns:
            Dictionary with hierarchical task structure
        """
        return self._tasks.get_task_tree(root_task_id)
        
    # Coordination methods
    
    def set_coordination_strategy(self, strategy: Any) -> None:
        """Set the coordination strategy.
        
        Args:
            strategy: Coordination strategy to use
        """
        self._coordinator.set_strategy(strategy)
    
    async def request_resource(self, agent_id: str, resource_id: str, priority: int = 1) -> bool:
        """Request a shared resource.
        
        Args:
            agent_id: ID of the requesting agent
            resource_id: ID of the resource
            priority: Priority of the request
            
        Returns:
            True if resource granted, False otherwise
        """
        return await self._coordinator.request_resource(agent_id, resource_id, priority)
    
    def release_resource(self, agent_id: str, resource_id: str) -> bool:
        """Release a shared resource.
        
        Args:
            agent_id: ID of the releasing agent
            resource_id: ID of the resource
            
        Returns:
            True if resource released, False otherwise
        """
        return self._coordinator.release_resource(agent_id, resource_id)
    
    def register_conflict(self, description: str, agents: List[str], resource_id: Optional[str] = None) -> str:
        """Register a conflict between agents.
        
        Args:
            description: Description of the conflict
            agents: List of agent IDs involved in the conflict
            resource_id: Optional ID of the resource in conflict
            
        Returns:
            ID of the registered conflict
        """
        return self._coordinator.register_conflict(description, agents, resource_id)
    
    def resolve_conflict(self, conflict_id: str, resolution: str) -> bool:
        """Resolve a registered conflict.
        
        Args:
            conflict_id: ID of the conflict
            resolution: Description of the resolution
            
        Returns:
            True if conflict resolved, False otherwise
        """
        return self._coordinator.resolve_conflict(conflict_id, resolution)
    
    def get_active_conflicts(self) -> List[Dict[str, Any]]:
        """Get all active conflicts.
        
        Returns:
            List of active conflict dictionaries
        """
        return self._coordinator.get_active_conflicts()
    
    # Tool management methods
    
    @property
    def tool_registry(self) -> TeamToolRegistry:
        """Get the team tool registry.
        
        Returns:
            Team tool registry
        """
        return self._tool_registry
    
    @property
    def tool_sharing(self) -> ToolSharingManager:
        """Get the team tool sharing manager.
        
        Returns:
            Team tool sharing manager
        """
        return self._tool_sharing
    
    def set_sharing_policy(self, policy: ToolSharingPolicy) -> None:
        """Set the tool sharing policy.
        
        Args:
            policy: New sharing policy
        """
        self._tool_sharing.set_policy(policy)
    
    async def execute_tool(
        self,
        agent_id: str,
        tool_name: str,
        timeout: Optional[float] = None,
        retry_count: int = 2,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool through the team registry.
        
        Args:
            agent_id: ID of the agent requesting tool execution
            tool_name: Name of the tool to execute
            timeout: Optional timeout in seconds
            retry_count: Number of retries for transient errors
            **kwargs: Tool parameters
            
        Returns:
            Tool execution result
        """
        return await self._tool_registry.execute_tool(
            agent_id=agent_id,
            tool_name=tool_name,
            timeout=timeout,
            retry_count=retry_count,
            **kwargs
        )
    
    async def request_tool_access(
        self,
        agent_id: str,
        tool_name: str,
        reason: Optional[str] = None,
        task_id: Optional[str] = None,
        temporary: bool = False,
        expiration: Optional[int] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Request access to a tool.
        
        Args:
            agent_id: ID of the agent requesting access
            tool_name: Name of the tool
            reason: Optional reason for the request
            task_id: Optional ID of the related task
            temporary: Whether this is a temporary share
            expiration: Optional expiration time in seconds
            
        Returns:
            Tuple of (success, message, request_id)
        """
        return await self._tool_sharing.request_tool_access(
            agent_id=agent_id,
            tool_name=tool_name,
            reason=reason,
            task_id=task_id,
            temporary=temporary,
            expiration=expiration,
        )
    
    async def discover_and_register_tools(
        self, 
        access_level: ToolAccessLevel = ToolAccessLevel.OWNER_ONLY
    ) -> int:
        """Discover and register tools from all team members.
        
        Args:
            access_level: Default access level for discovered tools
            
        Returns:
            Number of tools registered
        """
        return await self._tool_registry.discover_and_register_all_team_tools(access_level)
    
    def get_tools_by_capability(self, capability: Union[str, ToolCapability]) -> List[str]:
        """Get all tools with a specific capability.
        
        Args:
            capability: Capability to filter by
            
        Returns:
            List of tool names with the specified capability
        """
        return self._tool_registry.get_tools_by_capability(capability)
    
    def get_agent_tools(self, agent_id: str) -> List[str]:
        """Get all tools owned by an agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tool names owned by the agent
        """
        return self._tool_registry.get_agent_tools(agent_id)
    
    def get_accessible_tools(self, agent_id: str) -> List[str]:
        """Get all tools that an agent can access.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tool names accessible to the agent
        """
        return self._tool_registry.get_accessible_tools(agent_id)
