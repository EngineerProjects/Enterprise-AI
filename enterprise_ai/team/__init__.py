"""
Enterprise AI Team Module.

This module provides a framework for creating and coordinating teams of AI agents
that collaborate to solve complex tasks.
"""

from enterprise_ai.team.base import Team
from enterprise_ai.team.factory import (
    create_team,
    create_empty_team,
    create_agent_for_team,
    create_manager_agent
)
from enterprise_ai.team.manager import ManagerAgent
from enterprise_ai.team.memory import SharedMemory, DistributedMemory
from enterprise_ai.team.communication import TeamMessage, CommunicationProtocol, MessageRouter

__all__ = [
    'Team',
    'create_team',
    'create_empty_team',
    'create_agent_for_team',
    'create_manager_agent',
    'ManagerAgent',
    'SharedMemory',
    'DistributedMemory',
    'TeamMessage',
    'CommunicationProtocol',
    'MessageRouter',
]