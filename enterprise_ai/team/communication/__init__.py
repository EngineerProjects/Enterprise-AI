"""
Enterprise AI Team - Communication Module.

Handles all communication between team agents including @mentions and context management.
"""

from enterprise_ai.team.communication.protocol import TeamMessage, CommunicationProtocol
from enterprise_ai.team.communication.router import MessageRouter
from enterprise_ai.team.communication.mentions import MentionParser, MentionInfo, ParsedMessage
from enterprise_ai.team.communication.context import TeamContextBuilder

__all__ = [
    'TeamMessage',
    'CommunicationProtocol',
    'MessageRouter',
    'MentionParser',
    'MentionInfo',
    'ParsedMessage',
    'TeamContextBuilder',
]