"""
Core enums for the Enterprise AI team system.

Essential enumerations used throughout the team module.
"""

from enum import Enum


class TeamRole(Enum):
    """Team member roles."""
    MANAGER = "manager"
    SPECIALIST = "specialist"
    COORDINATOR = "coordinator"


class TeamStatus(Enum):
    """Team operational status."""
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    PAUSED = "paused"
    TERMINATED = "terminated"


class CollaborationMode(Enum):
    """Team collaboration patterns."""
    HIERARCHICAL = "hierarchical"
    PEER_TO_PEER = "peer_to_peer"
    HYBRID = "hybrid"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    DELEGATED = "delegated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    URGENT = 3
    CRITICAL = 4


class MessageType(Enum):
    """Types of team messages."""
    MESSAGE = "message"
    TASK = "task"
    RESULT = "result"
    BROADCAST = "broadcast"
    PEER_MESSAGE = "peer_message"
    SYSTEM = "system"
    ERROR = "error"


class AgentCapacity(Enum):
    """Agent capacity status."""
    AVAILABLE = "available"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    OFFLINE = "offline"


# Architecture support enums (used by architecture modules)
class LifecycleEvent(Enum):
    """Team lifecycle events."""
    CREATED = "created"
    INITIALIZED = "initialized"
    ACTIVATED = "activated"
    MEMBER_ADDED = "member_added"
    MEMBER_REMOVED = "member_removed"
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    PAUSED = "paused"
    RESUMED = "resumed"
    TERMINATED = "terminated"
    ERROR = "error"


class Permission(Enum):
    """Access permissions."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELEGATE = "delegate"
    MANAGE = "manage"
    ADMIN = "admin"


class AccessLevel(Enum):
    """Access levels for team members."""
    RESTRICTED = "restricted"
    BASIC = "basic"
    STANDARD = "standard"
    ELEVATED = "elevated"
    ADMIN = "admin"
