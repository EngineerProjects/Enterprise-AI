"""
Team architecture module exports - essential components only.
"""

from .coordinator import TeamCoordinator
from .task_manager import TaskManager
from enterprise_ai.team.core import TaskStatus, TaskPriority

__all__ = [
    "TeamCoordinator",
    "TaskManager",
    "TaskStatus",
    "TaskPriority"
]
