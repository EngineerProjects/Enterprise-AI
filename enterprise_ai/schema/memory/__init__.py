"""
Memory management for conversations in Enterprise AI.

This module provides interfaces and implementations for managing
conversation history between users and AI assistants.
"""

from enterprise_ai.schema.memory.base import ConversationMemory
from enterprise_ai.schema.memory.implementations import (
    ConversationMemoryFactory,
    InMemoryConversation,
    SlidingWindowConversation,
)

__all__ = [
    "ConversationMemory",
    "ConversationMemoryFactory",
    "InMemoryConversation",
    "SlidingWindowConversation",
]
