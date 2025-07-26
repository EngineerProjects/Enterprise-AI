"""
Enterprise AI Team Module.

Clean team management with essential components only.
"""

# Import everything from core
from .core import (
    # Main team class
    Team,
    
    # Enums
    TeamRole,
    TeamStatus,
    CollaborationMode,
    TaskStatus,
    TaskPriority,
    MessageType,
    AgentCapacity,
    LifecycleEvent,
    Permission,
    AccessLevel,
    
    # Models
    TeamTask,
    TeamMetrics,
    TeamMember,
    AgentProfile,
    
    # Exceptions
    TeamError,
    AgentNotFoundError,
    TaskValidationError,
    CommunicationError,
    WorkflowError,
    PermissionError,
    CapacityError
)

# Essential roles
from .roles import (
    BaseTeamRole,
    SpecialistRole,
    ManagerRole
)

# Memory components
from .memory.shared import SharedMemory

# Communication components  
from .communication.protocol import TeamMessage, CommunicationProtocol
from .communication.router import MessageRouter
from .communication.context import TeamContextBuilder

# Simple factory function
def create_team(name: str, manager, members: list = None):
    """Simple team creation function."""
    team = Team(name, manager)
    if members:
        for member in members:
            team.add_member(member)
    return team


# Clean exports
__all__ = [
    # Main team class
    "Team",
    
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
    
    # Roles
    "BaseTeamRole",
    "SpecialistRole",
    "ManagerRole",
    
    # Memory
    "SharedMemory",
    
    # Communication
    "TeamMessage",
    "CommunicationProtocol",
    "MessageRouter",
    "TeamContextBuilder",
    
    # Factory
    "create_team"
]

# Note: Legacy factory module has been replaced by the simple create_team function above
