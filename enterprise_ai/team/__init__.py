"""
Team management for Enterprise AI.

This module provides functionality for creating and managing teams of agents,
enabling coordinated collaboration between specialized AI agents with
tool sharing and delegation capabilities.
"""

from enterprise_ai.team.types import (
    TeamProtocol,
    TeamMemberRole,
    ToolSharingPolicy,
    ToolRoutingStrategy,
    TeamToolAccessInfo,
    ToolCapableTeamProtocol,
    CollaborativeTeamProtocol,
)
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.hierarchical import HierarchicalTeam
from enterprise_ai.team.collaborative import CollaborativeTeam, CollaborativeToolSharingPolicy
from enterprise_ai.team.coordinator import TeamCoordinator, TaskResult, ToolRequirementTracker
from enterprise_ai.team.registry import (
    RoleRegistry,
    TeamRegistry,
    get_role_registry,
    get_team_registry,
)
from enterprise_ai.team.factory import TeamFactory, get_team_factory
from enterprise_ai.team.tool_sharing import (
    DefaultToolSharingPolicy,
    HierarchicalToolSharingPolicy,
    SimpleToolRoutingStrategy,
    CapabilityBasedToolRoutingStrategy,
    TeamToolRegistry,
    ToolPoolManager,
    execute_tool_with_registry,
)

__all__ = [
    # Protocols
    "TeamProtocol",
    "TeamMemberRole",
    "ToolSharingPolicy",
    "ToolRoutingStrategy",
    "TeamToolAccessInfo",
    "ToolCapableTeamProtocol",
    "CollaborativeTeamProtocol",
    # Team implementations
    "BaseTeam",
    "HierarchicalTeam",
    "CollaborativeTeam",
    # Coordination
    "TeamCoordinator",
    "TaskResult",
    "ToolRequirementTracker",
    # Registry
    "RoleRegistry",
    "TeamRegistry",
    "get_role_registry",
    "get_team_registry",
    # Factory
    "TeamFactory",
    "get_team_factory",
    # Tool sharing components
    "DefaultToolSharingPolicy",
    "HierarchicalToolSharingPolicy",
    "CollaborativeToolSharingPolicy",
    "SimpleToolRoutingStrategy",
    "CapabilityBasedToolRoutingStrategy",
    "TeamToolRegistry",
    "ToolPoolManager",
    "execute_tool_with_registry",
]
