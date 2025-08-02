"""
Core data models for the Enterprise AI team system.

Essential data classes used throughout the team module.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid

# Forward declaration for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from enterprise_ai.agent import Agent

from enterprise_ai.team.core.enums import TeamRole, TaskStatus, TaskPriority, AgentCapacity
from enterprise_ai.team.utils.agent_utils import AgentUtilities


@dataclass
class TeamTask:
    """Represents a task assigned to the team."""
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_agents: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamMetrics:
    """Team performance metrics."""
    task_completion_rate: float = 0.0
    average_response_time: float = 0.0
    active_agents: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    total_messages: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class TeamMember:
    """Team member representation."""
    agent_name: str
    role: TeamRole
    capacity: float = 1.0  # 0.0 to 1.0
    current_load: float = 0.0
    status: AgentCapacity = AgentCapacity.AVAILABLE
    
    @property
    def is_available(self) -> bool:
        """Check if member has capacity for new tasks."""
        return AgentUtilities.check_availability(self.capacity, self.current_load, self.status)


@dataclass
class AgentProfile:
    """Basic agent profile information."""
    name: str
    role: TeamRole
    available_tools: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    
    @property
    def has_tools(self) -> bool:
        """Check if agent has any tools."""
        return len(self.available_tools) > 0
