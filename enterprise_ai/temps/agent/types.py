"""
Agent-specific types and protocols for Enterprise AI.

This module defines the core type definitions, enums, and protocols
that form the foundation of the agent system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Protocol, Union, Set

from enterprise_ai.types import MessageProtocol, Serializable


class TaskStatus(Enum):
    """Task execution status enum."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()


@dataclass
class Task(Serializable):
    """Represents a task to be executed by an agent."""

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    dependencies: List[str] = field(default_factory=list)  # IDs of tasks this task depends on
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "dependencies": self.dependencies or [],
            "metadata": self.metadata or {},
        }


class AgentMemory(Protocol):
    """Protocol for agent memory implementations."""

    def add(self, key: str, value: Any) -> None:
        """Add an item to memory."""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """Get an item from memory."""
        ...

    def forget(self, key: str) -> None:
        """Remove an item from memory."""
        ...

    def clear(self) -> None:
        """Clear all memory."""
        ...


class AgentRole(Protocol):
    """Protocol defining an agent's role."""

    @property
    def name(self) -> str:
        """Get role name."""
        ...

    @property
    def description(self) -> str:
        """Get role description."""
        ...

    @property
    def capabilities(self) -> List[str]:
        """Get role capabilities."""
        ...

    def get_instructions(self) -> str:
        """Get role-specific instructions."""
        ...


class AgentState(Protocol):
    """Protocol for agent state implementations."""

    @property
    def agent_id(self) -> str:
        """Get agent ID."""
        ...

    @property
    def current_task(self) -> Optional[Task]:
        """Get current task."""
        ...

    @current_task.setter
    def current_task(self, task: Optional[Task]) -> None:
        """Set current task."""
        ...

    @property
    def memory(self) -> AgentMemory:
        """Get agent memory."""
        ...

    @property
    def role(self) -> AgentRole:
        """Get agent role."""
        ...

    @role.setter
    def role(self, role: AgentRole) -> None:
        """Set agent role."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        ...

    def save(self) -> None:
        """Save state."""
        ...

    def load(self) -> None:
        """Load state."""
        ...


class AgentMessage(MessageProtocol):
    """Protocol for agent-to-agent messages."""

    sender_id: str
    receiver_id: Optional[str]
    message_type: str  # e.g., "task_assignment", "response", "request"

    @property
    @abstractmethod
    def is_broadcast(self) -> bool:
        """Check if message is a broadcast (no specific receiver)."""
        ...


class AgentProtocol(Protocol):
    """Protocol defining agent capabilities."""

    @property
    def id(self) -> str:
        """Get agent ID."""
        ...

    @property
    def name(self) -> str:
        """Get agent name."""
        ...

    @property
    def state(self) -> AgentState:
        """Get agent state."""
        ...

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message and optionally return a response."""
        ...

    def assign_task(self, task: Task) -> bool:
        """Assign a task to the agent."""
        ...

    def process_task(self) -> TaskStatus:
        """Process the current task."""
        ...

    def get_status(self) -> Dict[str, Any]:
        """Get agent status summary."""
        ...
