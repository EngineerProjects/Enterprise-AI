"""
Team tool registry for Enterprise AI.

This module provides the team tool registry that tracks tool ownership
and access across the team, building upon the agent tool manager.
"""

import asyncio
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.agent.tools.tooling import AgentToolManager
from enterprise_ai.logger import get_logger
from enterprise_ai.team.architecture.membership import MembershipManager
from enterprise_ai.team.core.types import TeamProtocol
from enterprise_ai.tool.core.base import BaseTool, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata

logger = get_logger("team.tools.registry")


class ToolAccessLevel(Enum):
    """Access levels for tools within a team."""
    
    OWNER_ONLY = auto()  # Only the owner can use the tool
    TEAM_READ = auto()   # Team members can view but not execute
    TEAM_EXECUTE = auto()  # Team members can execute the tool
    MANAGER_APPROVAL = auto()  # Execution requires manager approval


class ToolRegistration:
    """Registration for a tool within the team registry."""
    
    def __init__(
        self,
        tool_name: str,
        owner_id: str,
        access_level: ToolAccessLevel = ToolAccessLevel.OWNER_ONLY,
        capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        allowed_agents: Optional[List[str]] = None,
        registered_at: Optional[datetime] = None,
    ):
        """Initialize a tool registration.
        
        Args:
            tool_name: Name of the tool
            owner_id: ID of the agent that owns the tool
            access_level: Access level for the tool
            capabilities: Capabilities provided by the tool
            allowed_agents: Specific agents allowed to use the tool (if not all)
            registered_at: When the tool was registered
        """
        self.tool_name = tool_name
        self.owner_id = owner_id
        self.access_level = access_level
        self.capabilities = capabilities or []
        self.allowed_agents = allowed_agents or []
        self.registered_at = registered_at or datetime.now()
        self.last_accessed = None
        self.usage_count = 0
    
    def update_access_level(self, access_level: ToolAccessLevel) -> None:
        """Update the access level for this tool.
        
        Args:
            access_level: New access level
        """
        self.access_level = access_level
    
    def add_allowed_agent(self, agent_id: str) -> bool:
        """Add an agent to the allowed list.
        
        Args:
            agent_id: ID of the agent to allow
            
        Returns:
            True if agent was added, False if already present
        """
        if agent_id in self.allowed_agents:
            return False
        
        self.allowed_agents.append(agent_id)
        return True
    
    def remove_allowed_agent(self, agent_id: str) -> bool:
        """Remove an agent from the allowed list.
        
        Args:
            agent_id: ID of the agent to remove
            
        Returns:
            True if agent was removed, False if not found
        """
        if agent_id not in self.allowed_agents:
            return False
        
        self.allowed_agents.remove(agent_id)
        return True
    
    def record_access(self) -> None:
        """Record an access to this tool."""
        self.last_accessed = datetime.now()
        self.usage_count += 1
    
    def can_access(self, agent_id: str, is_team_manager: bool = False) -> bool:
        """Check if an agent can access this tool.
        
        Args:
            agent_id: ID of the agent requesting access
            is_team_manager: Whether the agent is a team manager
            
        Returns:
            True if the agent can access the tool, False otherwise
        """
        # Owner always has access
        if agent_id == self.owner_id:
            return True
        
        # Check access level
        if self.access_level == ToolAccessLevel.OWNER_ONLY:
            return False
        
        if self.access_level == ToolAccessLevel.MANAGER_APPROVAL and not is_team_manager:
            return False
        
        # Check allowed agents if specified
        if self.allowed_agents and agent_id not in self.allowed_agents:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of this registration
        """
        return {
            "tool_name": self.tool_name,
            "owner_id": self.owner_id,
            "access_level": self.access_level.name,
            "capabilities": [
                cap.value if hasattr(cap, "value") else str(cap) for cap in self.capabilities
            ],
            "allowed_agents": self.allowed_agents,
            "registered_at": self.registered_at.isoformat() if self.registered_at else None,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "usage_count": self.usage_count,
        }


class TeamToolRegistry:
    """Team tool registry.
    
    This component tracks tool ownership and access across the team:
    - Registering tools with owners
    - Tracking which agents have access to which tools
    - Maintaining tool access levels
    - Providing queries for tool capabilities and availability
    
    It delegates actual tool execution to the agent tool managers.
    """
    
    def __init__(self, team: "TeamProtocol", membership_manager: Optional[MembershipManager] = None):
        """Initialize the team tool registry.
        
        Args:
            team: Team that this registry belongs to
            membership_manager: Optional membership manager reference
        """
        self._team = team
        self._membership = membership_manager
        self._tools: Dict[str, ToolRegistration] = {}  # tool_name -> registration
        self._agent_tools: Dict[str, List[str]] = {}   # agent_id -> list of tool_names
        self._capability_index: Dict[str, List[str]] = {}  # capability -> list of tool_names
        
        logger.info(f"Initialized team tool registry for team {team.id}")
    
    def register_tool(
        self,
        tool_name: str,
        owner_id: str,
        access_level: ToolAccessLevel = ToolAccessLevel.OWNER_ONLY,
        capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        allowed_agents: Optional[List[str]] = None,
    ) -> bool:
        """Register a tool with the team.
        
        Args:
            tool_name: Name of the tool
            owner_id: ID of the agent that owns the tool
            access_level: Access level for the tool
            capabilities: Capabilities provided by the tool
            allowed_agents: Specific agents allowed to use the tool (if not all)
            
        Returns:
            True if tool was registered, False otherwise
        """
        # Check if tool is already registered
        if tool_name in self._tools:
            logger.warning(f"Tool {tool_name} is already registered in team {self._team.id}")
            return False
        
        # Check if owner is a team member
        if self._membership and not self._membership.is_member(owner_id):
            logger.warning(f"Owner {owner_id} is not a member of team {self._team.id}")
            return False
        
        # Create registration
        registration = ToolRegistration(
            tool_name=tool_name,
            owner_id=owner_id,
            access_level=access_level,
            capabilities=capabilities,
            allowed_agents=allowed_agents,
        )
        
        # Add to registry
        self._tools[tool_name] = registration
        
        # Update agent tools index
        if owner_id not in self._agent_tools:
            self._agent_tools[owner_id] = []
        self._agent_tools[owner_id].append(tool_name)
        
        # Update capability index
        if capabilities:
            for cap in capabilities:
                cap_str = cap.value if hasattr(cap, "value") else str(cap)
                if cap_str not in self._capability_index:
                    self._capability_index[cap_str] = []
                self._capability_index[cap_str].append(tool_name)
        
        logger.info(f"Registered tool {tool_name} owned by {owner_id} in team {self._team.id}")
        return True
    
    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool from the team.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if tool was unregistered, False otherwise
        """
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} is not registered in team {self._team.id}")
            return False
        
        registration = self._tools[tool_name]
        owner_id = registration.owner_id
        
        # Remove from registry
        del self._tools[tool_name]
        
        # Remove from agent tools index
        if owner_id in self._agent_tools and tool_name in self._agent_tools[owner_id]:
            self._agent_tools[owner_id].remove(tool_name)
        
        # Remove from capability index
        for cap in registration.capabilities:
            cap_str = cap.value if hasattr(cap, "value") else str(cap)
            if cap_str in self._capability_index and tool_name in self._capability_index[cap_str]:
                self._capability_index[cap_str].remove(tool_name)
        
        logger.info(f"Unregistered tool {tool_name} from team {self._team.id}")
        return True
    
    def set_access_level(self, tool_name: str, access_level: ToolAccessLevel) -> bool:
        """Set the access level for a tool.
        
        Args:
            tool_name: Name of the tool
            access_level: New access level
            
        Returns:
            True if access level was set, False otherwise
        """
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} is not registered in team {self._team.id}")
            return False
        
        registration = self._tools[tool_name]
        registration.update_access_level(access_level)
        
        logger.info(f"Set access level for tool {tool_name} to {access_level.name}")
        return True
    
    def add_allowed_agent(self, tool_name: str, agent_id: str) -> bool:
        """Add an agent to the allowed list for a tool.
        
        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent to allow
            
        Returns:
            True if agent was added, False otherwise
        """
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} is not registered in team {self._team.id}")
            return False
        
        # Check if agent is a team member
        if self._membership and not self._membership.is_member(agent_id):
            logger.warning(f"Agent {agent_id} is not a member of team {self._team.id}")
            return False
        
        registration = self._tools[tool_name]
        result = registration.add_allowed_agent(agent_id)
        
        if result:
            logger.info(f"Added agent {agent_id} to allowed list for tool {tool_name}")
        
        return result
    
    def remove_allowed_agent(self, tool_name: str, agent_id: str) -> bool:
        """Remove an agent from the allowed list for a tool.
        
        Args:
            tool_name: Name of the tool
            agent_id: ID of the agent to remove
            
        Returns:
            True if agent was removed, False otherwise
        """
        if tool_name not in self._tools:
            logger.warning(f"Tool {tool_name} is not registered in team {self._team.id}")
            return False
        
        registration = self._tools[tool_name]
        result = registration.remove_allowed_agent(agent_id)
        
        if result:
            logger.info(f"Removed agent {agent_id} from allowed list for tool {tool_name}")
        
        return result
    
    def get_tool_owner(self, tool_name: str) -> Optional[str]:
        """Get the ID of the agent that owns a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            ID of the owner agent, or None if tool not found
        """
        if tool_name not in self._tools:
            return None
        
        return self._tools[tool_name].owner_id
    
    def get_agent_tools(self, agent_id: str) -> List[str]:
        """Get all tools owned by an agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tool names owned by the agent
        """
        return self._agent_tools.get(agent_id, [])
    
    def get_accessible_tools(self, agent_id: str) -> List[str]:
        """Get all tools that an agent can access.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            List of tool names accessible to the agent
        """
        accessible_tools: List[str] = []
        
        # Check if agent is a team manager
        is_manager = False
        if self._membership and self._membership.manager:
            is_manager = agent_id == self._membership.manager.id
        
        # Check each tool
        for tool_name, registration in self._tools.items():
            if registration.can_access(agent_id, is_manager):
                accessible_tools.append(tool_name)
        
        return accessible_tools
    
    def get_tools_by_capability(self, capability: Union[str, ToolCapability]) -> List[str]:
        """Get all tools with a specific capability.
        
        Args:
            capability: Capability to filter by
            
        Returns:
            List of tool names with the specified capability
        """
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return self._capability_index.get(cap_str, [])
    
    def can_access_tool(self, agent_id: str, tool_name: str) -> bool:
        """Check if an agent can access a specific tool.
        
        Args:
            agent_id: ID of the agent
            tool_name: Name of the tool
            
        Returns:
            True if the agent can access the tool, False otherwise
        """
        if tool_name not in self._tools:
            return False
        
        # Check if agent is a team manager
        is_manager = False
        if self._membership and self._membership.manager:
            is_manager = agent_id == self._membership.manager.id
        
        return self._tools[tool_name].can_access(agent_id, is_manager)
    
    def get_tool_registration(self, tool_name: str) -> Optional[ToolRegistration]:
        """Get the registration for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Tool registration or None if not found
        """
        return self._tools.get(tool_name)
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get information about all registered tools.
        
        Returns:
            List of tool registration dictionaries
        """
        return [registration.to_dict() for registration in self._tools.values()]
    
    def record_tool_access(self, tool_name: str) -> bool:
        """Record an access to a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if access was recorded, False if tool not found
        """
        if tool_name not in self._tools:
            return False
        
        self._tools[tool_name].record_access()
        return True
    
    async def discover_agent_tools(self, agent: AgentProtocol) -> List[str]:
        """Discover tools available from an agent.
        
        This queries the agent's tool manager to find available tools.
        
        Args:
            agent: Agent to query for tools
            
        Returns:
            List of tool names available from the agent
        """
        tool_names: List[str] = []
        
        # Try to access agent's tool manager
        try:
            if hasattr(agent, "_tool_manager") and agent._tool_manager is not None:
                tool_manager = cast(AgentToolManager, agent._tool_manager)
                
                # Get local tool names
                local_tools = tool_manager.list_tools()
                tool_names.extend(local_tools)
                
                logger.info(f"Discovered {len(local_tools)} tools from agent {agent.id}")
            else:
                logger.warning(f"Agent {agent.id} does not have a tool manager")
        except Exception as e:
            logger.error(f"Error discovering tools from agent {agent.id}: {e}")
        
        return tool_names
    
    async def register_agent_tools(
        self, 
        agent: AgentProtocol, 
        access_level: ToolAccessLevel = ToolAccessLevel.OWNER_ONLY,
        allowed_agents: Optional[List[str]] = None,
    ) -> int:
        """Register all tools from an agent.
        
        Args:
            agent: Agent whose tools to register
            access_level: Default access level for the tools
            allowed_agents: Specific agents allowed to use the tools
            
        Returns:
            Number of tools registered
        """
        # Discover tools from agent
        tool_names = await self.discover_agent_tools(agent)
        
        # Register each tool
        count = 0
        for tool_name in tool_names:
            # Skip already registered tools
            if tool_name in self._tools:
                continue
            
            # Try to get tool capabilities
            capabilities: List[Union[str, ToolCapability]] = []
            try:
                if hasattr(agent, "_tool_manager") and agent._tool_manager is not None:
                    tool_manager = cast(AgentToolManager, agent._tool_manager)
                    
                    # Try to get capabilities for this tool
                    tool = tool_manager.get_tool(tool_name)
                    if tool and hasattr(tool, "capabilities"):
                        capabilities = list(tool.capabilities)
            except Exception as e:
                logger.warning(f"Error getting capabilities for tool {tool_name}: {e}")
            
            # Register the tool
            if self.register_tool(
                tool_name=tool_name,
                owner_id=agent.id,
                access_level=access_level,
                capabilities=capabilities,
                allowed_agents=allowed_agents,
            ):
                count += 1
        
        logger.info(f"Registered {count} tools from agent {agent.id}")
        return count
    
    async def execute_tool(
        self,
        agent_id: str,
        tool_name: str,
        timeout: Optional[float] = None,
        retry_count: int = 2,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool through the appropriate agent.
        
        Args:
            agent_id: ID of the agent requesting execution
            tool_name: Name of the tool to execute
            timeout: Optional timeout in seconds
            retry_count: Number of retries for transient errors
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        # Check if tool exists
        if tool_name not in self._tools:
            logger.error(f"Tool {tool_name} is not registered in team {self._team.id}")
            return ToolFailure(
                error=f"Tool not found: {tool_name}",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )
        
        # Check if agent can access tool
        if not self.can_access_tool(agent_id, tool_name):
            logger.error(f"Agent {agent_id} does not have access to tool {tool_name}")
            return ToolFailure(
                error=f"Access denied to tool: {tool_name}",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )
        
        # Get the tool owner
        owner_id = self._tools[tool_name].owner_id
        owner = self._team.get_member(owner_id)
        
        if not owner:
            logger.error(f"Tool owner {owner_id} is not a member of team {self._team.id}")
            return ToolFailure(
                error=f"Tool owner not found: {owner_id}",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )
        
        # Record the access
        self.record_tool_access(tool_name)
        
        # Execute the tool through the owner's tool manager
        try:
            result = await owner.execute_tool(
                tool_name=tool_name,
                timeout=timeout,
                retry_count=retry_count,
                **kwargs,
            )
            
            # Ensure metadata includes tool name
            if isinstance(result, ToolResult):
                if result.metadata is None:
                    result.metadata = ToolResultMetadata(tool_name=tool_name)
                elif result.metadata.tool_name is None:
                    result.metadata.tool_name = tool_name
            
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolFailure(
                error=f"Error executing tool: {str(e)}",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )
    
    async def discover_and_register_all_team_tools(
        self, 
        access_level: ToolAccessLevel = ToolAccessLevel.OWNER_ONLY
    ) -> int:
        """Discover and register tools from all team members.
        
        Args:
            access_level: Default access level for discovered tools
            
        Returns:
            Number of tools registered
        """
        if not self._membership:
            logger.warning("Cannot discover tools: no membership manager available")
            return 0
        
        members = self._membership.get_members()
        count = 0
        
        for agent in members:
            count += await self.register_agent_tools(agent, access_level)
        
        return count
