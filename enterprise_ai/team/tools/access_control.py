"""
Enhanced tool access control for team collaboration.

This module provides sophisticated tool access control mechanisms
that enable secure and flexible tool sharing between team members.
"""

from enum import Enum, Flag, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.team.tools.registry import TeamToolRegistry, ToolAccessLevel, ToolRegistration
from enterprise_ai.team.tools.sharing import ToolSharingPolicy, SharingApproval, SharingRequest

logger = get_logger("team.tools.access_control")


class ToolPermissionFlag(Flag):
    """Fine-grained tool permission flags.
    
    These flags allow for precise control over what 
    operations agents can perform on tools.
    """
    
    NONE = 0
    EXECUTE = auto()  # Can execute the tool
    VIEW = auto()     # Can view the tool information
    SHARE = auto()    # Can share the tool with others
    MODIFY = auto()   # Can modify the tool
    REGISTER = auto() # Can register a new tool
    REVOKE = auto()   # Can revoke access
    DELEGATE = auto() # Can delegate sharing decisions
    
    # Common permission combinations
    READ_ONLY = VIEW
    STANDARD = VIEW | EXECUTE
    OWNER = VIEW | EXECUTE | SHARE | MODIFY
    ADMIN = VIEW | EXECUTE | SHARE | MODIFY | REGISTER | REVOKE | DELEGATE


class ToolAccessRule:
    """A rule specifying tool access permissions.
    
    Rules can be applied to specific agents, roles,
    or entire teams to control tool access.
    """
    
    def __init__(
        self,
        permissions: ToolPermissionFlag,
        tool_pattern: str = "*",
        agent_id: Optional[str] = None,
        role_name: Optional[str] = None,
        team_id: Optional[str] = None,
        description: Optional[str] = None,
        priority: int = 0,
        expiration: Optional[int] = None,  # Seconds until expiration, or None for never
    ):
        """Initialize an access rule.
        
        Args:
            permissions: Permission flags for this rule
            tool_pattern: Pattern matching tool names (e.g., "file_*")
            agent_id: Optional agent ID this rule applies to
            role_name: Optional role name this rule applies to
            team_id: Optional team ID this rule applies to
            description: Optional description of this rule
            priority: Rule priority (higher overrides lower)
            expiration: Optional expiration time in seconds
        """
        self.permissions = permissions
        self.tool_pattern = tool_pattern
        self.agent_id = agent_id
        self.role_name = role_name
        self.team_id = team_id
        self.description = description or ""
        self.priority = priority
        self.expiration = expiration
        
        # Validate rule
        self._validate()
    
    def _validate(self) -> None:
        """Validate that the rule is properly constructed."""
        # Ensure at least one target is specified
        if not any([self.agent_id, self.role_name, self.team_id]):
            raise ValueError("Rule must specify at least one of: agent_id, role_name, team_id")
    
    def matches_tool(self, tool_name: str) -> bool:
        """Check if this rule applies to a specific tool.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if rule applies to this tool, False otherwise
        """
        if self.tool_pattern == "*":
            return True
            
        if "*" not in self.tool_pattern:
            # Exact match
            return tool_name == self.tool_pattern
        
        # Simple wildcard matching
        if self.tool_pattern.startswith("*") and self.tool_pattern.endswith("*"):
            # *contains*
            pattern = self.tool_pattern[1:-1]
            return pattern in tool_name
        elif self.tool_pattern.startswith("*"):
            # *suffix
            suffix = self.tool_pattern[1:]
            return tool_name.endswith(suffix)
        elif self.tool_pattern.endswith("*"):
            # prefix*
            prefix = self.tool_pattern[:-1]
            return tool_name.startswith(prefix)
            
        return False
    
    def matches_agent(self, agent_id: str, role_name: Optional[str], team_id: Optional[str]) -> bool:
        """Check if this rule applies to a specific agent.
        
        Args:
            agent_id: ID of the agent to check
            role_name: Optional role name of the agent
            team_id: Optional team ID the agent belongs to
            
        Returns:
            True if rule applies to this agent, False otherwise
        """
        # Check agent ID
        if self.agent_id and self.agent_id == agent_id:
            return True
            
        # Check role name
        if self.role_name and role_name and self.role_name == role_name:
            return True
            
        # Check team ID
        if self.team_id and team_id and self.team_id == team_id:
            return True
            
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary representation.
        
        Returns:
            Dictionary representation of the rule
        """
        return {
            "permissions": self.permissions.value,
            "tool_pattern": self.tool_pattern,
            "agent_id": self.agent_id,
            "role_name": self.role_name,
            "team_id": self.team_id,
            "description": self.description,
            "priority": self.priority,
            "expiration": self.expiration,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolAccessRule":
        """Create a rule from dictionary representation.
        
        Args:
            data: Dictionary to create rule from
            
        Returns:
            Created rule
        """
        return cls(
            permissions=ToolPermissionFlag(data["permissions"]),
            tool_pattern=data.get("tool_pattern", "*"),
            agent_id=data.get("agent_id"),
            role_name=data.get("role_name"),
            team_id=data.get("team_id"),
            description=data.get("description"),
            priority=data.get("priority", 0),
            expiration=data.get("expiration"),
        )


class EnhancedAccessControl:
    """Enhanced access control system for tool sharing.
    
    Provides fine-grained control over tool access,
    with a rule-based permission system.
    """
    
    def __init__(self, tool_registry: TeamToolRegistry):
        """Initialize the access control system.
        
        Args:
            tool_registry: Team tool registry to control access for
        """
        self._registry = tool_registry
        self._rules: List[ToolAccessRule] = []
        
        # Define default rules
        self._add_default_rules()
    
    def _add_default_rules(self) -> None:
        """Add default access rules.
        
        These provide a baseline level of access control.
        """
        # Rule 1: Tool owners have full access to their tools
        owner_rule = ToolAccessRule(
            permissions=ToolPermissionFlag.OWNER,
            tool_pattern="*",
            description="Tool owners have full access to their tools",
            priority=100  # High priority
        )
        
        # Rule 2: Team members can view all team tools
        team_view_rule = ToolAccessRule(
            permissions=ToolPermissionFlag.VIEW,
            tool_pattern="*",
            team_id=self._registry._team.id,
            description="Team members can view all team tools",
            priority=1  # Low priority
        )
        
        self._rules.append(owner_rule)
        self._rules.append(team_view_rule)
    
    def add_rule(self, rule: ToolAccessRule) -> None:
        """Add an access rule.
        
        Args:
            rule: Rule to add
        """
        self._rules.append(rule)
        
        # Sort rules by priority (highest first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        
        logger.info(f"Added access rule: {rule.description}")
    
    def remove_rule(self, index: int) -> Optional[ToolAccessRule]:
        """Remove a rule by index.
        
        Args:
            index: Index of the rule to remove
            
        Returns:
            Removed rule or None if index invalid
        """
        if 0 <= index < len(self._rules):
            rule = self._rules.pop(index)
            logger.info(f"Removed access rule: {rule.description}")
            return rule
        
        return None
    
    def get_rules(self) -> List[ToolAccessRule]:
        """Get all access rules.
        
        Returns:
            List of all rules
        """
        return self._rules.copy()
    
    def check_permission(
        self, 
        agent_id: str, 
        tool_name: str, 
        permission: ToolPermissionFlag
    ) -> bool:
        """Check if an agent has a specific permission for a tool.
        
        Args:
            agent_id: ID of the agent
            tool_name: Name of the tool
            permission: Permission to check
            
        Returns:
            True if agent has permission, False otherwise
        """
        # Get information needed for permission check
        tool_registration = self._registry.get_tool_registration(tool_name)
        if not tool_registration:
            return False
            
        # Special case: tool owner always has OWNER permissions
        if tool_registration.owner_id == agent_id:
            if ToolPermissionFlag.OWNER & permission:
                return True
        
        # Get agent information
        agent = self._registry._membership.get_member(agent_id)
        if not agent:
            return False
            
        role_name = None
        if hasattr(agent, "role"):
            role = getattr(agent, "role", None)
            if role and hasattr(role, "name"):
                role_name = getattr(role, "name", None)
        
        team_id = self._registry._team.id
        
        # Check against rules
        for rule in self._rules:
            if rule.matches_tool(tool_name) and rule.matches_agent(agent_id, role_name, team_id):
                # Rule applies, check permission
                if rule.permissions & permission:
                    return True
        
        return False
    
    def get_agent_permissions(
        self,
        agent_id: str,
        tool_name: str
    ) -> ToolPermissionFlag:
        """Get all permissions an agent has for a tool.
        
        Args:
            agent_id: ID of the agent
            tool_name: Name of the tool
            
        Returns:
            Permission flags the agent has
        """
        # Get information needed for permission check
        tool_registration = self._registry.get_tool_registration(tool_name)
        if not tool_registration:
            return ToolPermissionFlag.NONE
            
        # Special case: tool owner always has OWNER permissions
        if tool_registration.owner_id == agent_id:
            return ToolPermissionFlag.OWNER
        
        # Get agent information
        agent = self._registry._membership.get_member(agent_id)
        if not agent:
            return ToolPermissionFlag.NONE
            
        role_name = None
        if hasattr(agent, "role"):
            role = getattr(agent, "role", None)
            if role and hasattr(role, "name"):
                role_name = getattr(role, "name", None)
        
        team_id = self._registry._team.id
        
        # Combine permissions from all matching rules
        permissions = ToolPermissionFlag.NONE
        
        for rule in self._rules:
            if rule.matches_tool(tool_name) and rule.matches_agent(agent_id, role_name, team_id):
                permissions |= rule.permissions
        
        return permissions
    
    def get_agents_with_permission(
        self,
        tool_name: str,
        permission: ToolPermissionFlag
    ) -> List[str]:
        """Get all agents with a specific permission for a tool.
        
        Args:
            tool_name: Name of the tool
            permission: Permission to check
            
        Returns:
            List of agent IDs with the permission
        """
        agents_with_permission = []
        
        # Get all team members
        all_members = self._registry._membership.get_members()
        
        # Check each member
        for agent in all_members:
            if self.check_permission(agent.id, tool_name, permission):
                agents_with_permission.append(agent.id)
        
        return agents_with_permission
    
    def get_accessible_tools(
        self,
        agent_id: str,
        permission: ToolPermissionFlag = ToolPermissionFlag.EXECUTE
    ) -> List[str]:
        """Get all tools an agent has a specific permission for.
        
        Args:
            agent_id: ID of the agent
            permission: Permission to check
            
        Returns:
            List of tool names the agent has permission for
        """
        accessible_tools = []
        
        # Get all tools
        all_tools = self._registry.get_all_tools()
        
        # Check each tool
        for tool_name in all_tools:
            if self.check_permission(agent_id, tool_name, permission):
                accessible_tools.append(tool_name)
        
        return accessible_tools
    
    def get_agent_tool_permissions(
        self,
        agent_id: str
    ) -> Dict[str, ToolPermissionFlag]:
        """Get permissions for all tools an agent has access to.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Dictionary mapping tool names to permissions
        """
        permissions = {}
        
        # Get all tools
        all_tools = self._registry.get_all_tools()
        
        # Check each tool
        for tool_name in all_tools:
            tool_permissions = self.get_agent_permissions(agent_id, tool_name)
            
            # Only include tools with some permissions
            if tool_permissions != ToolPermissionFlag.NONE:
                permissions[tool_name] = tool_permissions
        
        return permissions


class EnhancedSharingPolicy(ToolSharingPolicy):
    """Enhanced tool sharing policy.
    
    Integrates with the enhanced access control system
    to provide more sophisticated sharing decisions.
    """
    
    def __init__(self, team, access_control: EnhancedAccessControl):
        """Initialize the enhanced sharing policy.
        
        Args:
            team: Team this policy belongs to
            access_control: Access control system to use
        """
        super().__init__(team)
        self._access_control = access_control
    
    async def evaluate_request(
        self,
        request: SharingRequest,
        registry: TeamToolRegistry,
        membership=None,
        task_manager=None,
    ) -> Tuple[SharingApproval, Optional[str]]:
        """Evaluate a sharing request.
        
        Args:
            request: The sharing request to evaluate
            registry: Tool registry for looking up tool information
            membership: Optional membership manager for role checks
            task_manager: Optional task manager for task-based checks
            
        Returns:
            Tuple of (approval status, optional reason)
        """
        # Check if requester has SHARE permission
        if self._access_control.check_permission(
            request.requester_id, request.tool_name, ToolPermissionFlag.SHARE
        ):
            return (
                SharingApproval.APPROVED, 
                f"Agent {request.requester_id} has explicit SHARE permission for tool {request.tool_name}"
            )
        
        # Check if requester has DELEGATE permission
        if self._access_control.check_permission(
            request.requester_id, request.tool_name, ToolPermissionFlag.DELEGATE
        ):
            return (
                SharingApproval.APPROVED, 
                f"Agent {request.requester_id} has DELEGATE permission for tool {request.tool_name}"
            )
        
        # Check if owner requesting
        if request.requester_id == request.owner_id:
            return (SharingApproval.APPROVED, "Owner can share their own tools")
        
        # Default to requiring explicit approval
        return (SharingApproval.PENDING, "Requires explicit approval from tool owner or manager")
    
    def get_policy_description(self) -> str:
        """Get a description of this policy.
        
        Returns:
            Policy description string
        """
        return (
            "Enhanced Sharing Policy:\n"
            "- Agents with SHARE permission can share tools\n"
            "- Agents with DELEGATE permission can approve sharing requests\n"
            "- Tool owners can share their own tools\n"
            "- All other sharing requires explicit approval\n"
        )
