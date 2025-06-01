"""
Memory management for conversations in Enterprise AI.

This module provides interfaces and implementations for managing
conversation history between users and AI assistants.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from enterprise_ai.schema.memory.base import ConversationMemory
from enterprise_ai.schema.memory.implementations import (
    ConversationMemoryFactory,
    InMemoryConversation,
    SlidingWindowConversation,
)


@dataclass
class MemoryConfig:
    """Configuration for conversation memory."""
    
    max_messages: Optional[int] = None
    max_tokens: Optional[int] = None
    preserve_system_messages: bool = True
    preserve_recent_messages: int = 10
    compression_strategy: str = "sliding_window"  # "sliding_window", "summarization", "none"
    extra_config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_messages": self.max_messages,
            "max_tokens": self.max_tokens,
            "preserve_system_messages": self.preserve_system_messages,
            "preserve_recent_messages": self.preserve_recent_messages,
            "compression_strategy": self.compression_strategy,
            "extra_config": self.extra_config,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryConfig":
        """Create from dictionary."""
        return cls(
            max_messages=data.get("max_messages"),
            max_tokens=data.get("max_tokens"),
            preserve_system_messages=data.get("preserve_system_messages", True),
            preserve_recent_messages=data.get("preserve_recent_messages", 10),
            compression_strategy=data.get("compression_strategy", "sliding_window"),
            extra_config=data.get("extra_config", {}),
        )


__all__ = [
    "ConversationMemory",
    "ConversationMemoryFactory", 
    "InMemoryConversation",
    "SlidingWindowConversation",
    "MemoryConfig",
]