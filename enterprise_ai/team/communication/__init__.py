"""
Enterprise AI Team - Communication Module.

This module provides protocols and routing for inter-agent communication.
"""

from enterprise_ai.team.communication.protocol import TeamMessage, CommunicationProtocol
from enterprise_ai.team.communication.router import MessageRouter

__all__ = [
    'TeamMessage',
    'CommunicationProtocol',
    'MessageRouter',
]