"""
Team architecture components for Enterprise AI.

This package contains managers and components that handle different aspects
of team functionality through composition and delegation.
"""

from enterprise_ai.team.architecture.coordinator import CoordinationManager
from enterprise_ai.team.architecture.lifecycle import LifecycleManager
from enterprise_ai.team.architecture.membership import MembershipManager
from enterprise_ai.team.architecture.messaging import MessagingManager, TeamMessage
from enterprise_ai.team.architecture.task_manager import TaskManager, TeamTask, TaskStatus

__all__ = [
    "CoordinationManager",
    "LifecycleManager",
    "MembershipManager",
    "MessagingManager",
    "TeamMessage",
    "TaskManager",
    "TeamTask",
    "TaskStatus",
]
