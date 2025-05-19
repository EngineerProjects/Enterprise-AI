"""
Team module for Enterprise AI.

This module provides functionality for organizing agents into collaborative 
teams with specialized roles and responsibilities.
"""

# Core types and base implementations
from enterprise_ai.team.core.types import TeamProtocol, TeamMemberRole, TeamMessageType
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.factory import (
    create_team, 
    TeamBuilder, 
    create_hierarchical_team, 
    create_peer_team
)

# Architecture components
from enterprise_ai.team.architecture.coordinator import (
    CoordinationManager,
    CoordinationStrategy,
    CoordinationEvent,
    ConflictType,
    ConflictStatus
)
from enterprise_ai.team.architecture.lifecycle import LifecycleManager, TeamState
from enterprise_ai.team.architecture.membership import MembershipManager
from enterprise_ai.team.architecture.messaging import MessagingManager, TeamMessage
from enterprise_ai.team.architecture.task_manager import TaskManager, TeamTask, TaskStatus
from enterprise_ai.team.architecture.state_sync import (
    StateSyncManager,
    SyncDirection,
    SyncMode,
    SyncComponent
)

# Role system
from enterprise_ai.team.roles.base import (
    BaseTeamRole,
    SimpleTeamRole,
    TemplatedTeamRole,
    TeamManagerRole,
    TeamSpecialistRole,
    TeamCoordinatorRole,
    create_team_role,
)

# Enhanced messaging
from enterprise_ai.team.messaging import (
    EnhancedMessagingManager,
    MessageRouterStrategy,
    DirectRoutingStrategy,
    HierarchicalRoutingStrategy,
    GroupRoutingStrategy
)

# Import collaboration patterns
try:
    from enterprise_ai.team.collaboration.hierarchical import HierarchicalTeam, DecisionMode
    from enterprise_ai.team.collaboration.peer import PeerTeam, ConsensusMode
    COLLABORATION_PATTERNS_AVAILABLE = True
except ImportError:
    COLLABORATION_PATTERNS_AVAILABLE = False

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

# Tool integration components
from enterprise_ai.team.tools.registry import TeamToolRegistry, ToolAccessLevel, ToolRegistration
from enterprise_ai.team.tools.sharing import (
    ToolSharingPolicy,
    DefaultSharingPolicy,
    HierarchicalSharingPolicy,
    TaskBasedSharingPolicy,
    CapabilityBasedSharingPolicy,
    ToolSharingManager,
    SharingApproval,
)
from enterprise_ai.team.tools.access_control import (
    ToolPermissionFlag,
    ToolAccessRule,
    EnhancedAccessControl,
    EnhancedSharingPolicy,
)

__all__ = [
    # Core types
    "TeamProtocol",
    "TeamMemberRole",
    "TeamMessageType",
    "BaseTeam",
    "create_team",
    "TeamBuilder",
    
    # Architecture components
    "CoordinationManager",
    "CoordinationStrategy",
    "CoordinationEvent",
    "ConflictType",
    "ConflictStatus",
    "LifecycleManager",
    "TeamState",
    "MembershipManager",
    "MessagingManager",
    "TeamMessage",
    "TaskManager",
    "TeamTask",
    "TaskStatus",
    "StateSyncManager",
    "SyncDirection",
    "SyncMode",
    "SyncComponent",
    
    # Role system
    "BaseTeamRole",
    "SimpleTeamRole",
    "TemplatedTeamRole",
    "TeamManagerRole",
    "TeamSpecialistRole",
    "TeamCoordinatorRole",
    "create_team_role",
    
    # Enhanced messaging
    "EnhancedMessagingManager",
    "MessageRouterStrategy",
    "DirectRoutingStrategy",
    "HierarchicalRoutingStrategy",
    "GroupRoutingStrategy",
    
    # Factory functions
    "create_hierarchical_team",
    "create_peer_team",
    
    # Tool integration
    "TeamToolRegistry",
    "ToolAccessLevel",
    "ToolRegistration",
    "ToolSharingPolicy",
    "DefaultSharingPolicy",
    "HierarchicalSharingPolicy",
    "TaskBasedSharingPolicy",
    "CapabilityBasedSharingPolicy",
    "ToolSharingManager",
    "SharingApproval",
    "ToolPermissionFlag",
    "ToolAccessRule",
    "EnhancedAccessControl",
    "EnhancedSharingPolicy",
]

# Add collaboration patterns if available
if COLLABORATION_PATTERNS_AVAILABLE:
    __all__.extend([
        # Collaboration patterns
        "HierarchicalTeam",
        "DecisionMode",
        "PeerTeam",
        "ConsensusMode",
    ])

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
