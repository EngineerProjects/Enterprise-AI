"""
Core team functionality for Enterprise AI.

This module provides the foundation for team implementations,
including the base team class and team creation factory.
"""

from enterprise_ai.team.core.types import TeamProtocol
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.factory import create_team, TeamBuilder

__all__ = [
    "TeamProtocol",
    "BaseTeam",
    "create_team",
    "TeamBuilder",
]
