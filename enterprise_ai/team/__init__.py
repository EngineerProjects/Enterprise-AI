"""
Team management for Enterprise AI.

This module provides functionality for creating and managing teams of agents,
enabling coordinated collaboration between specialized AI agents.
"""

from enterprise_ai.team.types import TeamProtocol, TeamMemberRole
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.hierarchical import HierarchicalTeam
from enterprise_ai.team.coordinator import TeamCoordinator, TaskResult
from enterprise_ai.team.registry import (
    RoleRegistry,
    TeamRegistry,
    get_role_registry,
    get_team_registry,
)
from enterprise_ai.team.factory import TeamFactory, get_team_factory

__all__ = [
    # Protocols
    "TeamProtocol",
    "TeamMemberRole",
    # Team implementations
    "BaseTeam",
    "HierarchicalTeam",
    # Coordination
    "TeamCoordinator",
    "TaskResult",
    # Registry
    "RoleRegistry",
    "TeamRegistry",
    "get_role_registry",
    "get_team_registry",
    # Factory
    "TeamFactory",
    "get_team_factory",
]
