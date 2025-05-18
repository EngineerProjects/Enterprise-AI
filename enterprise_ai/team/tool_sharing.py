"""
Tool sharing utilities for Enterprise AI teams.

This module provides mechanisms for sharing tools between agents in a team,
implementing various sharing policies, routing strategies, and access control.
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Union, cast
from collections import defaultdict

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult, ToolFailure
from enterprise_ai.team.types import (
    ToolSharingPolicy,
    ToolRoutingStrategy,
    TeamToolAccessInfo,
)

logger = get_logger("team.tool_sharing")


class DefaultToolSharingPolicy(ToolSharingPolicy):
    """
    Default implementation of tool sharing policy.

    This policy allows unrestricted sharing within a team by default.
    """

    def __init__(
        self,
        allow_all_sharing: bool = True,
        restricted_tools: Optional[Set[str]] = None,
        agent_restrictions: Optional[Dict[str, Set[str]]] = None,
    ):
        """
        Initialize a default tool sharing policy.

        Args:
            allow_all_sharing: Whether to allow all sharing by default
            restricted_tools: Optional set of tool names that cannot be shared
            agent_restrictions: Optional mapping of agent IDs to sets of
                               restricted tool names they cannot share
        """
        self._allow_all_sharing = allow_all_sharing
        self._restricted_tools = restricted_tools or set()
        self._agent_restrictions = agent_restrictions or {}

    @property
    def allow_sharing(self) -> bool:
        """Whether tool sharing is enabled at all."""
        return self._allow_all_sharing

    def can_share_tool(self, agent_id: str, tool_name: str) -> bool:
        """
        Check if an agent can share a specific tool.

        Args:
            agent_id: ID of the agent that owns the tool
            tool_name: Name of the tool to share

        Returns:
            True if the agent can share the tool, False otherwise
        """
        if not self._allow_all_sharing:
            return False

        # Check if tool is in global restrictions
        if tool_name in self._restricted_tools:
            return False

        # Check if agent has specific restrictions
        agent_restricted_tools = self._agent_restrictions.get(agent_id, set())
        if tool_name in agent_restricted_tools:
            return False

        return True

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
        # First check if the owner can share the tool
        if not self.can_share_tool(owner_id, tool_name):
            return False

        # By default, any agent can access any shareable tool
        return True

    def get_shareable_tools(self, agent_id: str) -> List[str]:
        """
        Get list of tool names that an agent can share.

        Args:
            agent_id: ID of the agent

        Returns:
            List of shareable tool names (empty list if no tools can be shared)
        """
        # This would need to be implemented with actual tool information,
        # but since we don't track tools in the policy itself, this is a placeholder
        return []


class HierarchicalToolSharingPolicy(DefaultToolSharingPolicy):
    """
    Tool sharing policy that respects team hierarchy.

    This policy allows managers to access subordinates' tools but restricts
    access in the other direction unless explicitly allowed.
    """

    def __init__(
        self,
        manager_ids: Set[str],
        allow_lateral_sharing: bool = False,
        restricted_tools: Optional[Set[str]] = None,
    ):
        """
        Initialize a hierarchical tool sharing policy.

        Args:
            manager_ids: Set of agent IDs that have manager status
            allow_lateral_sharing: Whether to allow sharing between agents
                                  at the same level
            restricted_tools: Optional set of tool names that cannot be shared
        """
        super().__init__(allow_all_sharing=True, restricted_tools=restricted_tools)
        self._manager_ids = manager_ids
        self._allow_lateral_sharing = allow_lateral_sharing
        # Additional dictionary to track direct reports for each manager
        self._direct_reports: Dict[str, Set[str]] = defaultdict(set)

    def add_reporting_relationship(self, manager_id: str, subordinate_id: str) -> None:
        """
        Add a reporting relationship between a manager and subordinate.

        Args:
            manager_id: ID of the manager agent
            subordinate_id: ID of the subordinate agent
        """
        self._manager_ids.add(manager_id)
        self._direct_reports[manager_id].add(subordinate_id)

    def can_access_tool(self, agent_id: str, tool_name: str, owner_id: str) -> bool:
        """
        Check if an agent can access a tool owned by another agent.

        In a hierarchical policy:
        1. Managers can access subordinates' tools
        2. Subordinates cannot access managers' tools unless explicitly allowed
        3. Agents at the same level follow lateral sharing rules

        Args:
            agent_id: ID of the agent requesting access
            tool_name: Name of the tool to access
            owner_id: ID of the agent that owns the tool

        Returns:
            True if the agent can access the tool, False otherwise
        """
        # First check if the owner can share the tool at all
        if not self.can_share_tool(owner_id, tool_name):
            return False

        # If agent is the tool owner, allow access
        if agent_id == owner_id:
            return True

        # Managers can access subordinates' tools
        if agent_id in self._manager_ids:
            if owner_id in self._direct_reports.get(agent_id, set()):
                return True

        # Agents at the same level - both managers or both subordinates
        same_level = (agent_id in self._manager_ids) == (owner_id in self._manager_ids)
        if same_level and self._allow_lateral_sharing:
            return True

        # Default to restricted access
        return False


class SimpleToolRoutingStrategy(ToolRoutingStrategy):
    """
    Basic strategy for routing tool requests.

    This strategy uses a predefined mapping of tools to agent IDs.
    """

    def __init__(self, tool_map: Dict[str, List[str]], default_agent: Optional[str] = None):
        """
        Initialize a simple tool routing strategy.

        Args:
            tool_map: Mapping of tool names to lists of agent IDs that can handle them
            default_agent: Optional default agent ID to use as fallback
        """
        self._tool_map = tool_map
        self._default_agent = default_agent

    def get_agent_for_tool(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get the agent ID that should handle a specific tool request.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the agent that should handle the request, or None if no suitable agent
        """
        agents = self._tool_map.get(tool_name, [])

        # If requester can handle the tool, prioritize self-handling
        if requester_id in agents:
            return requester_id

        # Otherwise, return the first available agent
        if agents:
            return agents[0]

        # Fall back to default agent if available
        return self._default_agent

    def get_fallback_agent(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get a fallback agent if primary agent is unavailable.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the fallback agent, or None if no fallback available
        """
        agents = self._tool_map.get(tool_name, [])

        # Remove the primary agent and requester from consideration
        primary = self.get_agent_for_tool(tool_name, requester_id)
        if primary:
            agents = [a for a in agents if a != primary and a != requester_id]

        # Return first available fallback
        if agents:
            return agents[0]

        # No fallback available
        return None

    def prioritize_agents_for_tool(self, tool_name: str) -> List[str]:
        """
        Get prioritized list of agents that can handle a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of agent IDs in priority order
        """
        return self._tool_map.get(tool_name, [])

    def update_tool_mapping(self, tool_name: str, agent_ids: List[str]) -> None:
        """
        Update the mapping for a specific tool.

        Args:
            tool_name: Name of the tool
            agent_ids: List of agent IDs that can handle the tool
        """
        self._tool_map[tool_name] = agent_ids


class CapabilityBasedToolRoutingStrategy(ToolRoutingStrategy):
    """
    Strategy that routes based on agent capabilities and current load.

    This strategy considers both agent capabilities and current workload
    to distribute tool requests efficiently.
    """

    def __init__(self, capabilities_map: Dict[str, Dict[str, float]]):
        """
        Initialize a capability-based routing strategy.

        Args:
            capabilities_map: Mapping of tool names to dictionaries mapping
                             agent IDs to capability scores (0.0-1.0)
        """
        self._capabilities_map = capabilities_map
        self._agent_loads: Dict[str, int] = defaultdict(int)
        self._load_threshold = 5  # Number of active requests before considered loaded

    def get_agent_for_tool(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get the agent ID that should handle a specific tool request.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the agent that should handle the request, or None if no suitable agent
        """
        if tool_name not in self._capabilities_map:
            return None

        # Get capabilities for this tool
        capabilities = self._capabilities_map[tool_name]

        # If requester is capable, prioritize self-handling
        if requester_id in capabilities and capabilities[requester_id] > 0.5:
            return requester_id

        # Find the most capable agent with acceptable load
        best_agent = None
        best_score = 0.0

        for agent_id, score in capabilities.items():
            # Skip if agent has no capability
            if score <= 0:
                continue

            # Calculate an adjusted score based on capability and load
            load_factor = min(1.0, self._agent_loads[agent_id] / self._load_threshold)
            adjusted_score = score * (1.0 - 0.5 * load_factor)

            if adjusted_score > best_score:
                best_score = adjusted_score
                best_agent = agent_id

        return best_agent

    def get_fallback_agent(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get a fallback agent if primary agent is unavailable.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the fallback agent, or None if no fallback available
        """
        if tool_name not in self._capabilities_map:
            return None

        # Get capabilities for this tool
        capabilities = self._capabilities_map[tool_name]

        # Get primary agent to exclude
        primary = self.get_agent_for_tool(tool_name, requester_id)

        # Find the most capable fallback
        best_agent = None
        best_score = 0.0

        for agent_id, score in capabilities.items():
            # Skip if agent is the primary or requester or has no capability
            if agent_id == primary or agent_id == requester_id or score <= 0:
                continue

            if score > best_score:
                best_score = score
                best_agent = agent_id

        return best_agent

    def prioritize_agents_for_tool(self, tool_name: str) -> List[str]:
        """
        Get prioritized list of agents that can handle a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of agent IDs in priority order
        """
        if tool_name not in self._capabilities_map:
            return []

        # Sort agents by capability score
        capabilities = self._capabilities_map[tool_name]
        sorted_agents = sorted(capabilities.items(), key=lambda x: x[1], reverse=True)

        return [agent_id for agent_id, score in sorted_agents if score > 0]

    def update_agent_load(self, agent_id: str, delta: int = 1) -> None:
        """
        Update the current load for an agent.

        Args:
            agent_id: ID of the agent
            delta: Change in load (positive for increase, negative for decrease)
        """
        self._agent_loads[agent_id] += delta
        if self._agent_loads[agent_id] < 0:
            self._agent_loads[agent_id] = 0

    def update_capability(self, tool_name: str, agent_id: str, score: float) -> None:
        """
        Update capability score for an agent.

        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent
            score: New capability score (0.0-1.0)
        """
        if tool_name not in self._capabilities_map:
            self._capabilities_map[tool_name] = {}

        self._capabilities_map[tool_name][agent_id] = max(0.0, min(1.0, score))


class TeamToolRegistry(TeamToolAccessInfo):
    """
    Registry for tracking tool ownership and access within a team.
    """

    def __init__(self) -> None:
        """Initialize a team tool registry."""
        self._tool_owners: Dict[str, str] = {}  # tool_name -> owner_id
        self._agent_tools: Dict[str, Set[str]] = defaultdict(set)  # agent_id -> set of tool_names
        self._shared_access: Dict[str, Set[str]] = defaultdict(set)  # tool_name -> set of agent_ids
        self._tool_instances: Dict[str, Dict[str, BaseTool]] = defaultdict(
            dict
        )  # owner_id -> {tool_name -> tool}

    @property
    def available_tools(self) -> Dict[str, List[str]]:
        """Map of agent IDs to their available tools."""
        return {agent_id: list(tools) for agent_id, tools in self._agent_tools.items()}

    @property
    def shared_tools(self) -> Dict[str, Set[str]]:
        """Map of tool names to the agent IDs that can access them."""
        return self._shared_access.copy()

    def get_agents_with_tool(self, tool_name: str) -> List[str]:
        """
        Get all agents that have access to a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of agent IDs with access to the tool
        """
        agents = []

        # Add the owner if the tool is owned by someone
        if tool_name in self._tool_owners:
            agents.append(self._tool_owners[tool_name])

        # Add agents with shared access
        agents.extend(list(self._shared_access.get(tool_name, set())))

        # Remove duplicates and return
        return list(set(agents))

    def get_agent_tools(self, agent_id: str) -> List[str]:
        """
        Get all tools available to a specific agent.

        Args:
            agent_id: ID of the agent

        Returns:
            List of tool names the agent has access to
        """
        return list(self._agent_tools.get(agent_id, set()))

    def register_tool(self, tool: BaseTool, owner_id: str) -> bool:
        """
        Register a tool with a specific owner.

        Args:
            tool: Tool to register
            owner_id: ID of the agent that owns the tool

        Returns:
            True if registration was successful, False otherwise
        """
        tool_name = tool.name

        # Check if tool is already registered
        if tool_name in self._tool_owners:
            existing_owner = self._tool_owners[tool_name]
            if existing_owner != owner_id:
                logger.warning(f"Tool '{tool_name}' already registered to agent '{existing_owner}'")
                return False

        # Register tool ownership
        self._tool_owners[tool_name] = owner_id
        self._agent_tools[owner_id].add(tool_name)

        # Store tool instance
        self._tool_instances[owner_id][tool_name] = tool

        logger.debug(f"Registered tool '{tool_name}' for agent '{owner_id}'")
        return True

    def unregister_tool(self, tool_name: str, owner_id: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of the tool to unregister
            owner_id: ID of the agent that owns the tool

        Returns:
            True if unregistration was successful, False otherwise
        """
        # Check if tool exists and belongs to the specified owner
        if tool_name not in self._tool_owners or self._tool_owners[tool_name] != owner_id:
            logger.warning(f"Tool '{tool_name}' not registered to agent '{owner_id}'")
            return False

        # Remove ownership
        del self._tool_owners[tool_name]

        # Remove from agent's tools
        if owner_id in self._agent_tools:
            self._agent_tools[owner_id].discard(tool_name)

            # Remove empty sets
            if not self._agent_tools[owner_id]:
                del self._agent_tools[owner_id]

        # Remove shared access
        if tool_name in self._shared_access:
            del self._shared_access[tool_name]

        # Remove tool instance
        if owner_id in self._tool_instances and tool_name in self._tool_instances[owner_id]:
            del self._tool_instances[owner_id][tool_name]

            # Remove empty dictionaries
            if not self._tool_instances[owner_id]:
                del self._tool_instances[owner_id]

        logger.debug(f"Unregistered tool '{tool_name}' from agent '{owner_id}'")
        return True

    def share_tool(self, tool_name: str, owner_id: str, target_id: str) -> bool:
        """
        Share a tool with another agent.

        Args:
            tool_name: Name of the tool to share
            owner_id: ID of the agent that owns the tool
            target_id: ID of the agent to share with

        Returns:
            True if sharing was successful, False otherwise
        """
        # Check if tool exists and belongs to the specified owner
        if tool_name not in self._tool_owners or self._tool_owners[tool_name] != owner_id:
            logger.warning(f"Tool '{tool_name}' not registered to agent '{owner_id}'")
            return False

        # Add shared access
        self._shared_access[tool_name].add(target_id)

        # Add to target's available tools
        self._agent_tools[target_id].add(tool_name)

        logger.debug(f"Shared tool '{tool_name}' from '{owner_id}' to '{target_id}'")
        return True

    def revoke_access(self, tool_name: str, owner_id: str, target_id: str) -> bool:
        """
        Revoke a shared tool access.

        Args:
            tool_name: Name of the tool to revoke access to
            owner_id: ID of the agent that owns the tool
            target_id: ID of the agent to revoke access from

        Returns:
            True if revocation was successful, False otherwise
        """
        # Check if tool exists and belongs to the specified owner
        if tool_name not in self._tool_owners or self._tool_owners[tool_name] != owner_id:
            logger.warning(f"Tool '{tool_name}' not registered to agent '{owner_id}'")
            return False

        # Remove shared access
        if tool_name in self._shared_access:
            self._shared_access[tool_name].discard(target_id)

            # Remove empty sets
            if not self._shared_access[tool_name]:
                del self._shared_access[tool_name]

        # Remove from target's available tools
        if target_id in self._agent_tools:
            self._agent_tools[target_id].discard(tool_name)

            # Remove empty sets
            if not self._agent_tools[target_id]:
                del self._agent_tools[target_id]

        logger.debug(f"Revoked access to tool '{tool_name}' from '{target_id}'")
        return True

    def get_tool_instance(self, tool_name: str, agent_id: str) -> Optional[BaseTool]:
        """
        Get a tool instance from a specific agent.

        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent

        Returns:
            Tool instance if available, None otherwise
        """
        # Check if agent owns the tool directly
        if agent_id in self._tool_instances and tool_name in self._tool_instances[agent_id]:
            return self._tool_instances[agent_id][tool_name]

        # Check if the tool is owned by someone
        if tool_name in self._tool_owners:
            owner_id = self._tool_owners[tool_name]

            # Check if the agent has access to this tool
            if tool_name in self._agent_tools.get(agent_id, set()):
                # Return the owner's instance
                return self._tool_instances.get(owner_id, {}).get(tool_name)

        return None


async def execute_tool_with_registry(
    registry: TeamToolRegistry, tool_name: str, parameters: Dict[str, Any], requester_id: str
) -> ToolResult:
    """
    Execute a tool using the registry to find the appropriate instance.

    Args:
        registry: Tool registry to use
        tool_name: Name of the tool to execute
        parameters: Parameters for the tool execution
        requester_id: ID of the agent requesting the execution

    Returns:
        Result of the tool execution
    """
    tool = registry.get_tool_instance(tool_name, requester_id)

    if not tool:
        return ToolFailure(error=f"Tool '{tool_name}' not available to agent '{requester_id}'")

    try:
        result = await tool.execute(**parameters)
        return cast(ToolResult, result)
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {str(e)}")
        return ToolFailure(error=f"Tool execution failed: {str(e)}")


class ToolPoolManager:
    """
    Manager for tool pools in collaborative teams.

    Tool pools are named collections of tools that can be accessed
    by multiple agents based on access control.
    """

    def __init__(self, registry: TeamToolRegistry):
        """
        Initialize a tool pool manager.

        Args:
            registry: Tool registry to use for tool access
        """
        self._registry = registry
        self._pools: Dict[str, Set[str]] = defaultdict(set)  # pool_name -> set of tool_names
        self._pool_access: Dict[str, Set[str]] = defaultdict(set)  # pool_name -> set of agent_ids

    def create_pool(self, pool_name: str, tool_names: Optional[List[str]] = None) -> bool:
        """
        Create a new tool pool.

        Args:
            pool_name: Name of the pool
            tool_names: Optional list of tool names to add to the pool

        Returns:
            True if pool was created successfully, False otherwise
        """
        if pool_name in self._pools:
            logger.warning(f"Pool '{pool_name}' already exists")
            return False

        self._pools[pool_name] = set()

        # Add tools if provided
        if tool_names:
            for tool_name in tool_names:
                # Only add tools that exist in the registry
                if tool_name in self._registry._tool_owners:
                    self._pools[pool_name].add(tool_name)

        logger.debug(f"Created tool pool '{pool_name}'")
        return True

    def delete_pool(self, pool_name: str) -> bool:
        """
        Delete a tool pool.

        Args:
            pool_name: Name of the pool to delete

        Returns:
            True if pool was deleted successfully, False otherwise
        """
        if pool_name not in self._pools:
            logger.warning(f"Pool '{pool_name}' does not exist")
            return False

        # Remove pool
        del self._pools[pool_name]

        # Remove access
        if pool_name in self._pool_access:
            del self._pool_access[pool_name]

        logger.debug(f"Deleted tool pool '{pool_name}'")
        return True

    def add_tools_to_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Add tools to a pool.

        Args:
            pool_name: Name of the pool
            tool_names: List of tool names to add

        Returns:
            True if tools were added successfully, False otherwise
        """
        if pool_name not in self._pools:
            logger.warning(f"Pool '{pool_name}' does not exist")
            return False

        # Add tools
        for tool_name in tool_names:
            # Only add tools that exist in the registry
            if tool_name in self._registry._tool_owners:
                self._pools[pool_name].add(tool_name)

        logger.debug(f"Added tools to pool '{pool_name}'")
        return True

    def remove_tools_from_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Remove tools from a pool.

        Args:
            pool_name: Name of the pool
            tool_names: List of tool names to remove

        Returns:
            True if tools were removed successfully, False otherwise
        """
        if pool_name not in self._pools:
            logger.warning(f"Pool '{pool_name}' does not exist")
            return False

        # Remove tools
        for tool_name in tool_names:
            self._pools[pool_name].discard(tool_name)

        logger.debug(f"Removed tools from pool '{pool_name}'")
        return True

    def grant_pool_access(self, pool_name: str, agent_id: str) -> bool:
        """
        Grant an agent access to a pool.

        Args:
            pool_name: Name of the pool
            agent_id: ID of the agent to grant access

        Returns:
            True if access was granted successfully, False otherwise
        """
        if pool_name not in self._pools:
            logger.warning(f"Pool '{pool_name}' does not exist")
            return False

        # Grant access
        self._pool_access[pool_name].add(agent_id)

        # Update agent's access to all tools in the pool
        for tool_name in self._pools[pool_name]:
            owner_id = self._registry._tool_owners.get(tool_name)
            if owner_id:
                self._registry.share_tool(tool_name, owner_id, agent_id)

        logger.debug(f"Granted access to pool '{pool_name}' for agent '{agent_id}'")
        return True

    def revoke_pool_access(self, pool_name: str, agent_id: str) -> bool:
        """
        Revoke an agent's access to a pool.

        Args:
            pool_name: Name of the pool
            agent_id: ID of the agent to revoke access

        Returns:
            True if access was revoked successfully, False otherwise
        """
        if pool_name not in self._pools:
            logger.warning(f"Pool '{pool_name}' does not exist")
            return False

        # Revoke access
        if pool_name in self._pool_access:
            self._pool_access[pool_name].discard(agent_id)

        # Update agent's access to all tools in the pool
        for tool_name in self._pools[pool_name]:
            owner_id = self._registry._tool_owners.get(tool_name)
            if owner_id:
                self._registry.revoke_access(tool_name, owner_id, agent_id)

        logger.debug(f"Revoked access to pool '{pool_name}' for agent '{agent_id}'")
        return True

    def get_pool_tools(self, pool_name: str) -> List[str]:
        """
        Get the tools in a pool.

        Args:
            pool_name: Name of the pool

        Returns:
            List of tool names in the pool
        """
        return list(self._pools.get(pool_name, set()))

    def get_agent_pools(self, agent_id: str) -> List[str]:
        """
        Get the pools an agent has access to.

        Args:
            agent_id: ID of the agent

        Returns:
            List of pool names the agent has access to
        """
        return [pool_name for pool_name, agents in self._pool_access.items() if agent_id in agents]

    def get_pool_access(self, pool_name: str) -> List[str]:
        """
        Get the agents that have access to a pool.

        Args:
            pool_name: Name of the pool

        Returns:
            List of agent IDs with access to the pool
        """
        return list(self._pool_access.get(pool_name, set()))
