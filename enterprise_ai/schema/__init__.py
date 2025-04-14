"""
Schema definitions for Enterprise AI.

This module provides the core data models used throughout the framework.
"""

from enterprise_ai.schema.message import Message
from enterprise_ai.schema.llm import ModelInfo, CompletionOptions
from enterprise_ai.schema.memory import (
    ConversationMemory,
    InMemoryConversation,
    SlidingWindowConversation,
    ConversationMemoryFactory,
)

__all__ = [
    # Message
    "Message",
    # LLM
    "ModelInfo",
    "CompletionOptions",
    # Memory
    "ConversationMemory",
    "InMemoryConversation",
    "SlidingWindowConversation",
    "ConversationMemoryFactory",
]
