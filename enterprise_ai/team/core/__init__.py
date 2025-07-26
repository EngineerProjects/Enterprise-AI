"""
Enterprise AI Team Core Module.

Core types, models, and utilities for the team system.
"""

# Import all enums
from enterprise_ai.team.core.enums import (
    TeamRole,
    TeamStatus,
    CollaborationMode,
    TaskStatus,
    TaskPriority,
    MessageType,
    AgentCapacity,
    LifecycleEvent,
    Permission,
    AccessLevel
)

# Import all models
from enterprise_ai.team.core.models import (
    TeamTask,
    TeamMetrics,
    TeamMember,
    AgentProfile
)

# Import exceptions
from enterprise_ai.team.core.exceptions import (
    TeamError,
    AgentNotFoundError,
    TaskValidationError,
    CommunicationError,
    WorkflowError,
    PermissionError,
    CapacityError
)

# Import base team implementation
from enterprise_ai.team.core.base import Team

__all__ = [
    # Enums
    "TeamRole",
    "TeamStatus",
    "CollaborationMode",
    "TaskStatus",
    "TaskPriority",
    "MessageType",
    "AgentCapacity",
    "LifecycleEvent",
    "Permission",
    "AccessLevel",
    
    # Models
    "TeamTask",
    "TeamMetrics",
    "TeamMember",
    "AgentProfile",
    
    # Exceptions
    "TeamError",
    "AgentNotFoundError",
    "TaskValidationError",
    "CommunicationError",
    "WorkflowError",
    "PermissionError",
    "CapacityError",
    
    # Base implementation
    "Team"
]
