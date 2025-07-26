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

# Legacy compatibility - try to import if exists
try:
    from .factory import (
        create_empty_team,
        create_agent_for_team,
        create_manager_agent
    )
    from .manager import ManagerAgent
    from .memory.distributed import DistributedMemory
    
    __all__.extend([
        'create_empty_team', 
        'create_agent_for_team',
        'create_manager_agent',
        'ManagerAgent',
        'DistributedMemory'
    ])
except ImportError:
    # Legacy components not available - that's fine
    pass
