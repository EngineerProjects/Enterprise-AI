"""
Team-specific types and protocols for Enterprise AI.

This module defines the core type definitions, enums, and protocols
that form the foundation of the team system.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple, Union

from enterprise_ai.agent.core.types import AgentProtocol, Task, MessageProtocol
from enterprise_ai.tool.core.result import ToolResult


class TeamMemberRole(Enum):
    """Enumeration of standard team member roles."""

    MANAGER = auto()
    SPECIALIST = auto()
    COORDINATOR = auto()
    MEMBER = auto()  # Generic team member with no special role


class TeamMessageType(str, Enum):
    """Types of team-specific messages."""

    BROADCAST = "broadcast"  # Message to all team members
    DIRECT = "direct"  # Message to a specific team member
    TASK_ASSIGNMENT = "task_assignment"  # Task assignment message
    TASK_UPDATE = "task_update"  # Task status update message
    TASK_COMPLETION = "task_completion"  # Task completion message
    TASK_FAILURE = "task_failure"  # Task failure message
    TASK_DECOMPOSITION = "task_decomposition"  # Task breakdown message
    STATUS_UPDATE = "status_update"  # Status update message
    TOOL_REQUEST = "tool_request"  # Request to use a tool
    TOOL_RESPONSE = "tool_response"  # Response from a tool execution
    COORDINATION = "coordination"  # Team coordination message


class TeamProtocol(ABC):
    """Interface that all team implementations must follow."""
    
    @property
    @abstractmethod
    def id(self) -> str:
        """Get the team's unique identifier."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the team's human-readable name."""
        pass
    
    #
    # Member Management
    #
    
    @abstractmethod
    def add_member(self, agent: AgentProtocol, role: Optional[Any] = None) -> bool:
        """Add an agent to the team.
        
        Args:
            agent: Agent to add to the team
            role: Optional role for the agent in the team
            
        Returns:
            True if agent was added successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def remove_member(self, agent_id: str) -> bool:
        """Remove an agent from the team.
        
        Args:
            agent_id: ID of the agent to remove
            
        Returns:
            True if agent was removed successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_members(self) -> List[AgentProtocol]:
        """Get all team members.
        
        Returns:
            List of all agents in the team
        """
        pass
    
    @abstractmethod
    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID.
        
        Args:
            agent_id: ID of the agent to retrieve
            
        Returns:
            Agent with the specified ID, or None if not found
        """
        pass
    
    #
    # Task Management
    #
    
    @abstractmethod
    def assign_task(self, task: Union[Task, Dict[str, Any]], agent_id: Optional[str] = None) -> bool:
        """Assign a task to the team or a specific team member.
        
        Args:
            task: Task to assign
            agent_id: Optional ID of the specific agent to assign the task to
            
        Returns:
            True if task was assigned successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Any]:
        """Get a task by ID.
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Task with the specified ID, or None if not found
        """
        pass
    
    @abstractmethod
    def get_all_tasks(self) -> List[Any]:
        """Get all tasks managed by the team.
        
        Returns:
            List of all tasks
        """
        pass
    
    @abstractmethod
    def update_task_status(self, task_id: str, status: Any) -> bool:
        """Update the status of a task.
        
        Args:
            task_id: ID of the task to update
            status: New status
            
        Returns:
            True if status was updated, False otherwise
        """
        pass
    
    #
    # Messaging
    #
    
    @abstractmethod
    def process_message(self, message: Union[str, MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Process a message directed to the team.
        
        Args:
            message: Message to process
            **kwargs: Additional parameters for processing
            
        Returns:
            Response message
        """
        pass
    
    @abstractmethod
    async def aprocess_message(self, message: Union[str, MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Process a message asynchronously.
        
        Args:
            message: Message to process
            **kwargs: Additional parameters for processing
            
        Returns:
            Response message
        """
        pass
    
    @abstractmethod
    def broadcast_message(self, message: Union[str, MessageProtocol]) -> List[MessageProtocol]:
        """Broadcast a message to all team members.
        
        Args:
            message: Message to broadcast
            
        Returns:
            List of response messages from team members
        """
        pass
    
    @abstractmethod
    async def abroadcast_message(self, message: Union[str, MessageProtocol]) -> List[MessageProtocol]:
        """Broadcast a message asynchronously.
        
        Args:
            message: Message to broadcast
            
        Returns:
            List of response messages from team members
        """
        pass
    
    #
    # Tool Management
    #
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def discover_and_register_tools(self, access_level: Any = None) -> int:
        """Discover and register tools from all team members.
        
        Args:
            access_level: Default access level for discovered tools
            
        Returns:
            Number of tools registered
        """
        pass
    
    @abstractmethod
    def get_tools_by_capability(self, capability: Any) -> List[str]:
        """Get all tools with a specific capability.
        
        Args:
            capability: Capability to filter by
            
        Returns:
            List of tool names with the specified capability
        """
        pass
    
    @abstractmethod
    def get_agent_tools(self, agent_id: str) -> List[str]:
        """Get all tools owned by an agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tool names owned by the agent
        """
        pass
    
    @abstractmethod
    def get_accessible_tools(self, agent_id: str) -> List[str]:
        """Get all tools that an agent can access.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tool names accessible to the agent
        """
        pass
    
    #
    # Team Status and Lifecycle
    #
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get team status information.
        
        Returns:
            Dictionary of status information
        """
        pass
    
    @abstractmethod
    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the team.
        
        Args:
            **kwargs: Initialization parameters
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        pass
    
    @abstractmethod
    async def terminate(self) -> bool:
        """Terminate the team and clean up resources.
        
        Returns:
            True if termination succeeded, False otherwise
        """
        pass
