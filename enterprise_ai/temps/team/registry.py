"""
Role and team registry system for Enterprise AI.

This module provides registries for managing agent roles and teams,
enabling centralized management, discovery, and assignment with
tool sharing capabilities.
"""

from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.types import AgentRole
from enterprise_ai.agent.role import create_role
from enterprise_ai.team.types import TeamProtocol, ToolCapableTeamProtocol
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.logger import get_logger

logger = get_logger("team.registry")


class RoleRegistry:
    """Registry for managing and retrieving agent roles.

    This class maintains a collection of roles that can be assigned to
    agents, supporting role lookup by ID, name, or capabilities.
    """

    def __init__(self) -> None:
        """Initialize a new role registry."""
        self._roles: Dict[str, AgentRole] = {}
        self._capabilities_index: Dict[str, Set[str]] = {}  # Capability to role IDs mapping
        logger.info("Initialized role registry")

    def register_role(self, role_id: str, role: AgentRole) -> None:
        """Register a role with the registry.

        Args:
            role_id: Unique identifier for the role
            role: Role to register

        Raises:
            ValueError: If a role with the same ID already exists
        """
        if role_id in self._roles:
            logger.warning(f"Role with ID {role_id} already exists in registry")
            raise ValueError(f"Role with ID {role_id} already exists")

        self._roles[role_id] = role

        # Update capability index
        for capability in role.capabilities:
            if capability not in self._capabilities_index:
                self._capabilities_index[capability] = set()
            self._capabilities_index[capability].add(role_id)

        logger.info(f"Registered role: {role_id} ({role.name})")

    def unregister_role(self, role_id: str) -> bool:
        """Remove a role from the registry.

        Args:
            role_id: ID of the role to remove

        Returns:
            True if role was removed, False if not found
        """
        if role_id not in self._roles:
            logger.warning(f"Role with ID {role_id} not found in registry")
            return False

        role = self._roles[role_id]

        # Update capability index
        for capability in role.capabilities:
            if capability in self._capabilities_index:
                self._capabilities_index[capability].discard(role_id)
                # Remove capability entry if empty
                if not self._capabilities_index[capability]:
                    del self._capabilities_index[capability]

        # Remove role
        del self._roles[role_id]
        logger.info(f"Unregistered role: {role_id}")
        return True

    def get_role(self, role_id: str) -> Optional[AgentRole]:
        """Get a role by ID.

        Args:
            role_id: ID of the role to get

        Returns:
            Role instance or None if not found
        """
        return self._roles.get(role_id)

    def get_all_roles(self) -> Dict[str, AgentRole]:
        """Get all registered roles.

        Returns:
            Dictionary of all roles
        """
        return self._roles.copy()

    def find_roles_by_capability(self, capability: str) -> List[AgentRole]:
        """Find roles that have a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of roles with the specified capability
        """
        if capability not in self._capabilities_index:
            return []

        role_ids = self._capabilities_index[capability]
        return [self._roles[role_id] for role_id in role_ids]

    def find_roles_by_capabilities(
        self, capabilities: List[str], require_all: bool = False
    ) -> List[AgentRole]:
        """Find roles that have the specified capabilities.

        Args:
            capabilities: List of capabilities to search for
            require_all: If True, roles must have all capabilities; if False, any capability

        Returns:
            List of matching roles
        """
        if not capabilities:
            return []

        # Get sets of role IDs for each capability
        role_id_sets = [self._capabilities_index.get(cap, set()) for cap in capabilities]

        if not role_id_sets:
            return []

        # Combine sets based on require_all flag
        if require_all:
            # Intersection: roles must have all capabilities
            result_role_ids = set.intersection(*role_id_sets)
        else:
            # Union: roles having any of the capabilities
            result_role_ids = set.union(*role_id_sets)

        return [self._roles[role_id] for role_id in result_role_ids]

    def create_and_register_role(self, role_id: str, role_type: str, **kwargs: Any) -> AgentRole:
        """Create a role and register it with the registry.

        Args:
            role_id: Unique identifier for the role
            role_type: Type of role to create
            **kwargs: Additional parameters for role creation

        Returns:
            Created role instance

        Raises:
            ValueError: If a role with the same ID already exists
        """
        if role_id in self._roles:
            logger.warning(f"Role with ID {role_id} already exists in registry")
            raise ValueError(f"Role with ID {role_id} already exists")

        role = create_role(role_type, **kwargs)
        self.register_role(role_id, role)
        return role


class TeamRegistry:
    """Registry for managing and retrieving teams.

    This class maintains a collection of teams that can be accessed and
    managed throughout the system, supporting team lookup by ID, capability,
    or tool requirements.
    """

    def __init__(self) -> None:
        """Initialize a new team registry."""
        self._teams: Dict[str, TeamProtocol] = {}
        self._capabilities_index: Dict[str, Set[str]] = {}  # Capability to team IDs mapping
        self._tags_index: Dict[str, Set[str]] = {}  # Tag to team IDs mapping
        self._tool_index: Dict[str, Set[str]] = {}  # Tool name to team IDs mapping
        logger.info("Initialized team registry")

    def register_team(
        self, team: TeamProtocol, tags: Optional[List[str]] = None, register_tools: bool = True
    ) -> None:
        """Register a team with the registry.

        Args:
            team: Team to register
            tags: Optional list of tags for categorizing the team
            register_tools: Whether to index the team's tools

        Raises:
            ValueError: If a team with the same ID already exists
        """
        if team.id in self._teams:
            logger.warning(f"Team with ID {team.id} already exists in registry")
            raise ValueError(f"Team with ID {team.id} already exists")

        self._teams[team.id] = team

        # Index by tags if provided
        if tags:
            for tag in tags:
                if tag not in self._tags_index:
                    self._tags_index[tag] = set()
                self._tags_index[tag].add(team.id)

        # Index team's tool capabilities
        if register_tools and hasattr(team, "get_available_tools"):
            try:
                tool_map = team.get_available_tools()
                for agent_tools in tool_map.values():
                    for tool_name in agent_tools:
                        if tool_name not in self._tool_index:
                            self._tool_index[tool_name] = set()
                        self._tool_index[tool_name].add(team.id)
            except Exception as e:
                logger.warning(f"Error indexing tools for team {team.id}: {e}")

        logger.info(f"Registered team: {team.id} ({team.name})")

    def unregister_team(self, team_id: str) -> bool:
        """Remove a team from the registry.

        Args:
            team_id: ID of the team to remove

        Returns:
            True if team was removed, False if not found
        """
        if team_id not in self._teams:
            logger.warning(f"Team with ID {team_id} not found in registry")
            return False

        # Remove from capability index
        for capability_set in self._capabilities_index.values():
            capability_set.discard(team_id)

        # Remove from tags index
        for tag_set in self._tags_index.values():
            tag_set.discard(team_id)

        # Remove from tool index
        for tool_set in self._tool_index.values():
            tool_set.discard(team_id)

        # Remove team
        del self._teams[team_id]
        logger.info(f"Unregistered team: {team_id}")
        return True

    def get_team(self, team_id: str) -> Optional[TeamProtocol]:
        """Get a team by ID.

        Args:
            team_id: ID of the team to get

        Returns:
            Team instance or None if not found
        """
        return self._teams.get(team_id)

    def get_all_teams(self) -> Dict[str, TeamProtocol]:
        """Get all registered teams.

        Returns:
            Dictionary of all teams
        """
        return self._teams.copy()

    def find_teams_by_tag(self, tag: str) -> List[TeamProtocol]:
        """Find teams with a specific tag.

        Args:
            tag: Tag to search for

        Returns:
            List of teams with the specified tag
        """
        if tag not in self._tags_index:
            return []

        team_ids = self._tags_index[tag]
        return [self._teams[team_id] for team_id in team_ids if team_id in self._teams]

    def find_teams_by_capability(self, capability: str) -> List[TeamProtocol]:
        """Find teams that have a member with a specific capability.

        This searches through all team members to find those with the
        specified capability.

        Args:
            capability: Capability to search for

        Returns:
            List of teams with a member having the specified capability
        """
        result = []

        for team_id, team in self._teams.items():
            # Check if any member has this capability
            has_capability = False

            # Check manager if available
            try:
                manager = team.manager
                # Use hasattr() to check if the agent has a role attribute
                if hasattr(manager, "role"):
                    manager_role = getattr(manager, "role")
                    if manager_role and capability in manager_role.capabilities:
                        has_capability = True
            except (RuntimeError, AttributeError):
                # No manager or no manager role
                pass

            # Check members
            if not has_capability:
                for member in team.members.values():
                    # Use hasattr() to check if the agent has a role attribute
                    if hasattr(member, "role"):
                        member_role = getattr(member, "role")
                        if member_role and capability in member_role.capabilities:
                            has_capability = True
                            break

            if has_capability:
                result.append(team)

        return result

    def find_teams_by_tool(self, tool_name: str) -> List[TeamProtocol]:
        """
        Find teams that have access to a specific tool.

        Args:
            tool_name: Name of the tool to search for

        Returns:
            List of teams with access to the specified tool
        """
        if tool_name not in self._tool_index:
            return []

        team_ids = self._tool_index[tool_name]
        return [self._teams[team_id] for team_id in team_ids if team_id in self._teams]

    def update_team_tools(self, team_id: str) -> bool:
        """
        Update the tool index for a specific team.

        Args:
            team_id: ID of the team to update

        Returns:
            True if update was successful, False otherwise
        """
        if team_id not in self._teams:
            logger.warning(f"Team with ID {team_id} not found in registry")
            return False

        team = self._teams[team_id]

        # Remove team from all tool entries
        for tool_teams in self._tool_index.values():
            tool_teams.discard(team_id)

        # Re-index team's tools
        if hasattr(team, "get_available_tools"):
            try:
                tool_map = team.get_available_tools()
                for agent_tools in tool_map.values():
                    for tool_name in agent_tools:
                        if tool_name not in self._tool_index:
                            self._tool_index[tool_name] = set()
                        self._tool_index[tool_name].add(team_id)

                logger.info(f"Updated tool index for team {team_id}")
                return True
            except Exception as e:
                logger.warning(f"Error updating tool index for team {team_id}: {e}")

        return False

    def add_team_tags(self, team_id: str, tags: List[str]) -> bool:
        """Add tags to a team.

        Args:
            team_id: ID of the team
            tags: List of tags to add

        Returns:
            True if successful, False if team not found
        """
        if team_id not in self._teams:
            logger.warning(f"Team with ID {team_id} not found in registry")
            return False

        for tag in tags:
            if tag not in self._tags_index:
                self._tags_index[tag] = set()
            self._tags_index[tag].add(team_id)

        logger.info(f"Added tags {tags} to team {team_id}")
        return True

    def remove_team_tags(self, team_id: str, tags: List[str]) -> bool:
        """Remove tags from a team.

        Args:
            team_id: ID of the team
            tags: List of tags to remove

        Returns:
            True if successful, False if team not found
        """
        if team_id not in self._teams:
            logger.warning(f"Team with ID {team_id} not found in registry")
            return False

        for tag in tags:
            if tag in self._tags_index:
                self._tags_index[tag].discard(team_id)
                # Remove tag entry if empty
                if not self._tags_index[tag]:
                    del self._tags_index[tag]

        logger.info(f"Removed tags {tags} from team {team_id}")
        return True

    def register_tool_with_team(self, team_id: str, tool: BaseTool, owner_id: str) -> bool:
        """
        Register a tool with a specific team.

        Args:
            team_id: ID of the team
            tool: Tool to register
            owner_id: ID of the agent that owns the tool

        Returns:
            True if registration was successful, False otherwise
        """
        if team_id not in self._teams:
            logger.warning(f"Team with ID {team_id} not found in registry")
            return False

        team = self._teams[team_id]

        # Check if team supports tool registration
        if hasattr(team, "register_team_tool"):
            try:
                success = team.register_team_tool(tool, owner_id)

                if success:
                    # Update tool index
                    if tool.name not in self._tool_index:
                        self._tool_index[tool.name] = set()
                    self._tool_index[tool.name].add(team_id)

                    logger.info(f"Registered tool {tool.name} with team {team_id}")
                    return True
                else:
                    logger.warning(f"Failed to register tool {tool.name} with team {team_id}")
            except Exception as e:
                logger.error(f"Error registering tool {tool.name} with team {team_id}: {e}")
        else:
            logger.warning(f"Team {team_id} does not support tool registration")

        return False


# Singleton instances for global registries
_global_role_registry: Optional[RoleRegistry] = None
_global_team_registry: Optional[TeamRegistry] = None


def get_role_registry() -> RoleRegistry:
    """Get the global role registry instance.

    Returns:
        Global role registry
    """
    global _global_role_registry
    if _global_role_registry is None:
        _global_role_registry = RoleRegistry()
    return _global_role_registry


def get_team_registry() -> TeamRegistry:
    """Get the global team registry instance.

    Returns:
        Global team registry
    """
    global _global_team_registry
    if _global_team_registry is None:
        _global_team_registry = TeamRegistry()
    return _global_team_registry
