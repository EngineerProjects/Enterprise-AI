"""
Team protocols and type definitions for Enterprise AI.

This module defines the core protocols and type definitions for the team
management system, enabling team structure and coordination with support
for tool sharing and delegation.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Set, Union, Tuple, runtime_checkable

from enterprise_ai.agent.core.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult


class ToolSharingPolicy(Protocol):
    """Protocol defining how tools are shared within a team."""

    @property
    def allow_sharing(self) -> bool:
        """Whether tool sharing is enabled at all."""
        ...

    def can_share_tool(self, agent_id: str, tool_name: str) -> bool:
        """
        Check if an agent can share a specific tool.

        Args:
            agent_id: ID of the agent that owns the tool
            tool_name: Name of the tool to share

        Returns:
            True if the agent can share the tool, False otherwise
        """
        ...

    def can_access_tool(self, agent_id: str, tool_name: str, owner_id: str) -> bool:
        """
        Check if an agent can access a tool owned by another agent.

        Args:
            agent_id: ID of the agent requesting access
            tool_name: Name of the tool to access
            owner_id: ID of the agent that owns the tool

        Returns:
            True if the agent can access the tool, False otherwise
        """
        ...

    def get_shareable_tools(self, agent_id: str) -> List[str]:
        """
        Get list of tool names that an agent can share.

        Args:
            agent_id: ID of the agent

        Returns:
            List of shareable tool names
        """
        ...


class ToolRoutingStrategy(Protocol):
    """Protocol defining how tool requests are routed within a team."""

    def get_agent_for_tool(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get the agent ID that should handle a specific tool request.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the agent that should handle the request, or None if no suitable agent
        """
        ...

    def get_fallback_agent(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get a fallback agent if primary agent is unavailable.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the fallback agent, or None if no fallback available
        """
        ...

    def prioritize_agents_for_tool(self, tool_name: str) -> List[str]:
        """
        Get prioritized list of agents that can handle a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of agent IDs in priority order
        """
        ...


class TeamToolAccessInfo(Protocol):
    """Information about tool access within a team."""

    @property
    def available_tools(self) -> Dict[str, List[str]]:
        """Map of agent IDs to their available tools."""
        ...

    @property
    def shared_tools(self) -> Dict[str, Set[str]]:
        """Map of tool names to the agent IDs that can access them."""
        ...

    def get_agents_with_tool(self, tool_name: str) -> List[str]:
        """
        Get all agents that have access to a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of agent IDs with access to the tool
        """
        ...

    def get_agent_tools(self, agent_id: str) -> List[str]:
        """
        Get all tools available to a specific agent.

        Args:
            agent_id: ID of the agent

        Returns:
            List of tool names the agent has access to
        """
        ...


class TeamProtocol(Protocol):
    """Protocol defining team capabilities."""

    @property
    def id(self) -> str:
        """Get team ID."""
        ...

    @property
    def name(self) -> str:
        """Get team name."""
        ...

    @property
    def manager(self) -> AgentProtocol:
        """Get team manager agent."""
        ...

    @manager.setter
    def manager(self, agent: AgentProtocol) -> None:
        """Set team manager."""
        ...

    @property
    def members(self) -> Dict[str, AgentProtocol]:
        """Get team members (excluding manager)."""
        ...

    def add_member(self, agent: AgentProtocol, role: Optional[str] = None) -> bool:
        """Add a member to the team with an optional role."""
        ...

    def remove_member(self, agent_id: str) -> bool:
        """Remove a member from the team."""
        ...

    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID."""
        ...

    def assign_task(self, task: Task, agent_id: Optional[str] = None) -> bool:
        """Assign a task to a team member or let manager decide."""
        ...

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message sent to the team."""
        ...

    def broadcast_message(
        self, message_type: str, content: str, sender_id: str
    ) -> List[AgentMessage]:
        """Broadcast a message to all team members."""
        ...

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary."""
        ...

    # New tool-related methods

    def get_available_tools(self) -> Dict[str, List[str]]:
        """
        Get all tools available across the team.

        Returns:
            A dictionary mapping agent IDs to lists of available tool names
        """
        ...

    def route_tool_request(
        self, tool_name: str, parameters: Dict[str, Any], requester_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Route a tool request to the appropriate agent.

        Args:
            tool_name: Name of the requested tool
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool

        Returns:
            A tuple of (success, agent_id) where agent_id is the agent
            that will handle the request if successful
        """
        ...

    async def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], requester_id: str
    ) -> ToolResult:
        """
        Execute a tool using the appropriate team member.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool execution

        Returns:
            Result of the tool execution
        """
        ...

    def share_tool(self, tool_name: str, owner_id: str, target_id: Optional[str] = None) -> bool:
        """
        Share a tool with another team member or the whole team.

        Args:
            tool_name: Name of the tool to share
            owner_id: ID of the agent that owns the tool
            target_id: ID of the target agent, or None for team-wide sharing

        Returns:
            True if sharing was successful, False otherwise
        """
        ...

    def revoke_tool_access(
        self, tool_name: str, owner_id: str, target_id: Optional[str] = None
    ) -> bool:
        """
        Revoke tool access from a team member or the whole team.

        Args:
            tool_name: Name of the tool to revoke access to
            owner_id: ID of the agent that owns the tool
            target_id: ID of the target agent, or None for team-wide revocation

        Returns:
            True if revocation was successful, False otherwise
        """
        ...

    def find_agents_by_tool_capability(self, tool_name: str) -> List[str]:
        """
        Find agents that have capability to use a specific tool.

        Args:
            tool_name: Name of the tool to search for

        Returns:
            List of agent IDs that can use the specified tool
        """
        ...

    def get_tool_access_info(self) -> TeamToolAccessInfo:
        """
        Get information about tool access within the team.

        Returns:
            TeamToolAccessInfo with details about tool access
        """
        ...


class TeamMemberRole(Protocol):
    """Protocol for team member roles."""

    @property
    def team_id(self) -> str:
        """Get the associated team ID."""
        ...

    @property
    def position(self) -> str:
        """Get the position in the team (e.g., manager, lead, member)."""
        ...

    @property
    def responsibilities(self) -> List[str]:
        """Get the responsibilities associated with this role."""
        ...


@runtime_checkable
class ToolCapableTeamProtocol(TeamProtocol, Protocol):
    """Protocol for teams with enhanced tool capabilities."""

    def get_tool_sharing_policy(self) -> ToolSharingPolicy:
        """
        Get the tool sharing policy for this team.

        Returns:
            Tool sharing policy
        """
        ...

    def set_tool_sharing_policy(self, policy: ToolSharingPolicy) -> None:
        """
        Set the tool sharing policy for this team.

        Args:
            policy: New tool sharing policy
        """
        ...

    def get_tool_routing_strategy(self) -> ToolRoutingStrategy:
        """
        Get the tool routing strategy for this team.

        Returns:
            Tool routing strategy
        """
        ...

    def set_tool_routing_strategy(self, strategy: ToolRoutingStrategy) -> None:
        """
        Set the tool routing strategy for this team.

        Args:
            strategy: New tool routing strategy
        """
        ...

    def register_team_tool(self, tool: BaseTool, owner_id: str) -> bool:
        """
        Register a tool with the team.

        Args:
            tool: Tool to register
            owner_id: ID of the agent that owns the tool

        Returns:
            True if registration was successful, False otherwise
        """
        ...

    def unregister_team_tool(self, tool_name: str, owner_id: str) -> bool:
        """
        Unregister a tool from the team.

        Args:
            tool_name: Name of the tool to unregister
            owner_id: ID of the agent that owns the tool

        Returns:
            True if unregistration was successful, False otherwise
        """
        ...

    async def execute_tool_with_fallback(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        requester_id: str,
        max_attempts: int = 3,
    ) -> ToolResult:
        """
        Execute a tool with fallback mechanism.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool execution
            max_attempts: Maximum number of attempts before failing
            ,
        Returns:
            Result of the tool execution
        """
        ...

    async def execute_multi_tool_task(
        self,
        tool_sequence: List[Tuple[str, Dict[str, Any]]],
        requester_id: str,
    ) -> List[ToolResult]:
        """
        Execute a sequence of tool operations.

        Args:
            tool_sequence: List of (tool_name, parameters) tuples
            requester_id: ID of the agent requesting the tool executions

        Returns:
            List of tool execution results
        """
        ...


@runtime_checkable
class CollaborativeTeamProtocol(ToolCapableTeamProtocol, Protocol):
    """Protocol for collaborative teams with dynamic tool sharing."""

    def create_tool_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Create a named pool of tools for collaborative use.

        Args:
            pool_name: Name of the tool pool
            tool_names: Names of tools to include in the pool

        Returns:
            True if pool creation was successful, False otherwise
        """
        ...

    def get_pool_tools(self, pool_name: str) -> List[str]:
        """
        Get the tools in a specific pool.

        Args:
            pool_name: Name of the tool pool

        Returns:
            List of tool names in the pool
        """
        ...

    def add_tools_to_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Add tools to an existing pool.

        Args:
            pool_name: Name of the tool pool
            tool_names: Names of tools to add

        Returns:
            True if tools were added successfully, False otherwise
        """
        ...

    def remove_tools_from_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Remove tools from an existing pool.

        Args:
            pool_name: Name of the tool pool
            tool_names: Names of tools to remove

        Returns:
            True if tools were removed successfully, False otherwise
        """
        ...

    def grant_pool_access(self, pool_name: str, agent_id: str) -> bool:
        """
        Grant an agent access to a tool pool.

        Args:
            pool_name: Name of the tool pool
            agent_id: ID of the agent to grant access

        Returns:
            True if access was granted successfully, False otherwise
        """
        ...

    def revoke_pool_access(self, pool_name: str, agent_id: str) -> bool:
        """
        Revoke an agent's access to a tool pool.

        Args:
            pool_name: Name of the tool pool
            agent_id: ID of the agent to revoke access

        Returns:
            True if access was revoked successfully, False otherwise
        """
        ...

    def get_agent_pools(self, agent_id: str) -> List[str]:
        """
        Get the tool pools an agent has access to.

        Args:
            agent_id: ID of the agent

        Returns:
            List of pool names the agent has access to
        """
        ...
