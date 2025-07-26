"""
Custom exceptions for the Enterprise AI team system.
"""


class TeamError(Exception):
    """Base exception for team operations."""
    pass


class AgentNotFoundError(TeamError):
    """Raised when an agent is not found in the team."""
    pass


class TaskValidationError(TeamError):
    """Raised when task validation fails."""
    pass


class CommunicationError(TeamError):
    """Raised when communication between agents fails."""
    pass


class WorkflowError(TeamError):
    """Raised when workflow execution fails."""
    pass


class PermissionError(TeamError):
    """Raised when permission check fails."""
    pass


class CapacityError(TeamError):
    """Raised when agent capacity is exceeded."""
    pass
