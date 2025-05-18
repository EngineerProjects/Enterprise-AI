"""
Role definitions for Enterprise AI agents.

This module provides role implementations that define an agent's
capabilities, responsibilities, and specialized instructions.
"""

from enterprise_ai.agent.role.role import (
    BaseAgentRole,
    SimpleRole,
    TemplatedRole,
    DeveloperRole,
    ManagerRole,
    ResearcherRole,
    create_role,
)

__all__ = [
    "BaseAgentRole",
    "SimpleRole",
    "TemplatedRole",
    "DeveloperRole",
    "ManagerRole",
    "ResearcherRole",
    "create_role",
]
