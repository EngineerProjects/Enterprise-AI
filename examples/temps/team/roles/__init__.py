"""
Team role definitions for Enterprise AI.

This package provides team-specific role implementations that extend
the agent role system for team coordination capabilities.
"""

from enterprise_ai.team.roles.base import (
    BaseTeamRole,
    SimpleTeamRole,
    TemplatedTeamRole,
    TeamManagerRole,
    TeamSpecialistRole,
    TeamCoordinatorRole,
    create_team_role,
)

# Import specialized roles for collaboration patterns
try:
    from enterprise_ai.team.roles.manager import (
        HierarchicalManagerRole,
        PeerCoordinatorRole,
    )
    from enterprise_ai.team.roles.specialist import (
        HierarchicalSpecialistRole,
        PeerSpecialistRole,
    )
    COLLABORATION_ROLES_AVAILABLE = True
except ImportError:
    COLLABORATION_ROLES_AVAILABLE = False

__all__ = [
    # Core role types
    "BaseTeamRole",
    "SimpleTeamRole",
    "TemplatedTeamRole",
    "TeamManagerRole",
    "TeamSpecialistRole",
    "TeamCoordinatorRole",
    "create_team_role",
]

# Add collaboration roles if available
if COLLABORATION_ROLES_AVAILABLE:
    __all__.extend([
        # Specialized manager roles
        "HierarchicalManagerRole",
        "PeerCoordinatorRole",
        # Specialized specialist roles
        "HierarchicalSpecialistRole",
        "PeerSpecialistRole",
    ])
