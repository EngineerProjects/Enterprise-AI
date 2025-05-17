"""
Messaging system for Enterprise AI agents.

This module provides message implementations for agent-to-agent
communication, including task assignments, queries, and notifications.
"""

from enterprise_ai.agent.messaging.message import (
    BaseAgentMessage,
    TaskAssignmentMessage,
    TaskUpdateMessage,
    QueryMessage,
    ResponseMessage,
    BroadcastMessage,
    NotificationMessage,
    ErrorMessage,
    create_message,
)

__all__ = [
    "BaseAgentMessage",
    "TaskAssignmentMessage",
    "TaskUpdateMessage",
    "QueryMessage",
    "ResponseMessage",
    "BroadcastMessage",
    "NotificationMessage",
    "ErrorMessage",
    "create_message",
]
