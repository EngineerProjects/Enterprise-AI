"""
Schema definitions for Enterprise AI.

This module provides the core data models used throughout the framework.
"""

from enterprise_ai.schema.message import Message
from enterprise_ai.schema.llm import ModelInfo, CompletionOptions, LLMResponse
from enterprise_ai.schema.memory import (
    ConversationMemory,
    InMemoryConversation,
    SlidingWindowConversation,
    ConversationMemoryFactory,
)

from enterprise_ai.schema.tool import ToolCall, Function, ToolChoice, TOOL_CHOICE_TYPE, TOOL_CHOICE_VALUES

__all__ = [
    # Message
    "Message",
    # LLM
    "ModelInfo",
    "CompletionOptions",
    "LLMResponse",
    # Memory
    "ConversationMemory",
    "InMemoryConversation",
    "SlidingWindowConversation",
    "ConversationMemoryFactory",
    # Tool
    "ToolCall",
    "Function",
    "ToolChoice",
    "TOOL_CHOICE_TYPE",
    "TOOL_CHOICE_VALUES",
]
