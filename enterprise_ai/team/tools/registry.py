"""
Tool registry for team-wide tool management.

Manages available tools, capabilities, and access permissions.
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enterprise_ai.team.core import TeamRole
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.tool_registry")


@dataclass
class ToolCapability:
    """Represents a tool capability."""
    name: str
    description: str
    required_role: Optional[TeamRole] = None
    required_permissions: Set[str] = None
    
    def __post_init__(self):
        if self.required_permissions is None:
            self.required_permissions = set()


@dataclass
class RegisteredTool:
    """Represents a registered tool with metadata."""
    name: str
    description: str
    capabilities: List[ToolCapability]
    owner: Optional[str] = None  # Member who registered the tool
    is_shared: bool = True
    access_restrictions: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.access_restrictions is None:
            self.access_restrictions = {}


class ToolRegistry:
    """Manages team-wide tool registry and access."""
    
    def __init__(self):
        self.tools: Dict[str, RegisteredTool] = {}
        self.member_tools: Dict[str, Set[str]] = {}  # member_id -> set of tool names
        self.role_tools: Dict[TeamRole, Set[str]] = {}  # role -> set of tool names
        self.tool_usage_stats: Dict[str, Dict[str, int]] = {}  # tool_name -> {member_id: usage_count}
        
    def register_tool(self, tool: RegisteredTool, registrar: str) -> bool:
        """Register a new tool."""
        if tool.name in self.tools:
            logger.warning(f"Tool {tool.name} already registered, updating")
        
        tool.owner = registrar
        self.tools[tool.name] = tool
        
        # Add to registrar's tools
        if registrar not in self.member_tools:
            self.member_tools[registrar] = set()
        self.member_tools[registrar].add(tool.name)
        
        # Initialize usage stats
        self.tool_usage_stats[tool.name] = {}
        
        logger.info(f"Registered tool '{tool.name}' by {registrar}")
        return True
    
    def unregister_tool(self, tool_name: str, requester: str) -> bool:
        """Unregister a tool."""
        if tool_name not in self.tools:
            return False
        
        tool = self.tools[tool_name]
        
        # Check if requester has permission to unregister
        if tool.owner != requester:
            logger.warning(f"User {requester} cannot unregister tool {tool_name} (not owner)")
            return False
        
        # Remove from all collections
        del self.tools[tool_name]
        
        for member_tools in self.member_tools.values():
            member_tools.discard(tool_name)
        
        for role_tools in self.role_tools.values():
            role_tools.discard(tool_name)
        
        self.tool_usage_stats.pop(tool_name, None)
        
        logger.info(f"Unregistered tool '{tool_name}'")
        return True
    
    def get_tools_for_member(self, member_id: str, member_role: TeamRole) -> List[RegisteredTool]:
        """Get all tools accessible to a member."""
        accessible_tools = []
        
        for tool_name, tool in self.tools.items():
            if self._can_access_tool(member_id, member_role, tool):
                accessible_tools.append(tool)
        
        return accessible_tools
    
    def get_tools_by_capability(self, capability_name: str, member_id: str, member_role: TeamRole) -> List[RegisteredTool]:
        """Get tools that provide specific capability."""
        matching_tools = []
        
        for tool in self.tools.values():
            if self._can_access_tool(member_id, member_role, tool):
                for capability in tool.capabilities:
                    if capability.name == capability_name:
                        matching_tools.append(tool)
                        break
        
        return matching_tools
    
    def grant_tool_access(self, tool_name: str, member_id: str, grantor: str) -> bool:
        """Grant tool access to a member."""
        if tool_name not in self.tools:
            return False
        
        tool = self.tools[tool_name]
        
        # Check if grantor has permission
        if tool.owner != grantor:
            logger.warning(f"User {grantor} cannot grant access to tool {tool_name}")
            return False
        
        if member_id not in self.member_tools:
            self.member_tools[member_id] = set()
        
        self.member_tools[member_id].add(tool_name)
        logger.info(f"Granted {member_id} access to tool {tool_name}")
        return True
    
    def revoke_tool_access(self, tool_name: str, member_id: str, revoker: str) -> bool:
        """Revoke tool access from a member."""
        if tool_name not in self.tools:
            return False
        
        tool = self.tools[tool_name]
        
        # Check if revoker has permission
        if tool.owner != revoker:
            logger.warning(f"User {revoker} cannot revoke access to tool {tool_name}")
            return False
        
        if member_id in self.member_tools:
            self.member_tools[member_id].discard(tool_name)
            logger.info(f"Revoked {member_id} access to tool {tool_name}")
            return True
        
        return False
    
    def record_tool_usage(self, tool_name: str, member_id: str) -> None:
        """Record tool usage by member."""
        if tool_name not in self.tool_usage_stats:
            self.tool_usage_stats[tool_name] = {}
        
        if member_id not in self.tool_usage_stats[tool_name]:
            self.tool_usage_stats[tool_name][member_id] = 0
        
        self.tool_usage_stats[tool_name][member_id] += 1
    
    def get_tool_usage_stats(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get tool usage statistics."""
        if tool_name:
            return self.tool_usage_stats.get(tool_name, {})
        
        # Return overall stats
        total_usage = {}
        for tool, usage in self.tool_usage_stats.items():
            total_usage[tool] = sum(usage.values())
        
        return total_usage
    
    def get_member_tool_usage(self, member_id: str) -> Dict[str, int]:
        """Get tool usage statistics for a specific member."""
        member_usage = {}
        
        for tool_name, usage_stats in self.tool_usage_stats.items():
            if member_id in usage_stats:
                member_usage[tool_name] = usage_stats[member_id]
        
        return member_usage
    
    def get_registry_summary(self) -> Dict[str, Any]:
        """Get registry summary."""
        return {
            "total_tools": len(self.tools),
            "shared_tools": len([t for t in self.tools.values() if t.is_shared]),
            "private_tools": len([t for t in self.tools.values() if not t.is_shared]),
            "members_with_tools": len(self.member_tools),
            "most_used_tools": self._get_most_used_tools(5)
        }
    
    def _can_access_tool(self, member_id: str, member_role: TeamRole, tool: RegisteredTool) -> bool:
        """Check if member can access tool."""
        # Tool owner always has access
        if tool.owner == member_id:
            return True
        
        # Check if tool is shared
        if not tool.is_shared:
            return False
        
        # Check explicit member access
        if member_id in self.member_tools and tool.name in self.member_tools[member_id]:
            return True
        
        # Check role-based access
        if member_role in self.role_tools and tool.name in self.role_tools[member_role]:
            return True
        
        # Check capability-based role restrictions
        for capability in tool.capabilities:
            if capability.required_role and capability.required_role != member_role:
                return False
        
        # Default: shared tools are accessible
        return tool.is_shared
    
    def _get_most_used_tools(self, limit: int) -> List[tuple]:
        """Get most used tools."""
        usage_totals = []
        
        for tool_name, usage_stats in self.tool_usage_stats.items():
            total_usage = sum(usage_stats.values())
            usage_totals.append((tool_name, total_usage))
        
        usage_totals.sort(key=lambda x: x[1], reverse=True)
        return usage_totals[:limit]
