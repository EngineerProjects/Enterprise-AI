"""
Schema definitions for Enterprise AI.

This module provides the core data models and type definitions used throughout
the framework, ensuring type safety and consistent data structures.
"""

# Core message types
from enterprise_ai.schema.message import Message

# LLM-related schemas
from enterprise_ai.schema.llm import (
    ModelInfo, 
    CompletionOptions, 
    LLMResponse,
    ProviderInfo,
    ModelCapabilities,
    StreamingResponse,
)

# Memory system schemas
from enterprise_ai.schema.memory import (
    ConversationMemory,
    InMemoryConversation,
    SlidingWindowConversation,
    MemoryConfig,
)

# Tool system schemas
from enterprise_ai.schema.tool import (
    ToolCall, 
    Function, 
    ToolChoice, 
    ToolDefinition,
    ToolResult,
    TOOL_CHOICE_TYPE, 
    TOOL_CHOICE_VALUES,
)

# Image handling schemas
from enterprise_ai.schema.image import (
    ImageInfo,
    ImageFormat,
    ImageMetadata,
)

# Agent profile schemas
from enterprise_ai.schema.agent_profile import (
    AgentProfile,
    AgentRoleInfo,
    AgentCapacity,
    AgentStatus,
)

from enterprise_ai.schema.tool_utils import ToolConverter

# Export all public schemas
__all__ = [
    # Core message
    "Message",
    
    # LLM schemas
    "ModelInfo",
    "CompletionOptions", 
    "LLMResponse",
    "ProviderInfo",
    "ModelCapabilities",
    "StreamingResponse",
    
    # Memory schemas
    "ConversationMemory",
    "InMemoryConversation", 
    "SlidingWindowConversation",
    "MemoryConfig",
    
    # Tool schemas
    "ToolCall",
    "Function",
    "ToolChoice",
    "ToolDefinition", 
    "ToolResult",
    "TOOL_CHOICE_TYPE",
    "TOOL_CHOICE_VALUES",
    
    # Image schemas
    "ImageInfo",
    "ImageFormat", 
    "ImageMetadata",
    
    # Agent profile schemas
    "AgentProfile",
    "AgentRoleInfo",
    "AgentCapacity", 
    "AgentStatus",

    # Utility classes
    "ToolConverter",
]

# Schema version for compatibility tracking
SCHEMA_VERSION = "1.0.0"