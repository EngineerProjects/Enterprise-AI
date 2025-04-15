"""
Message schema for Enterprise AI.

This module defines the core message model used for LLM interactions.
"""

from datetime import datetime
from typing import Any, Dict, Optional, cast

from enterprise_ai.types import MessageProtocol


class Message:
    """
    Represents a chat message in a conversation.

    This class implements the MessageProtocol and provides methods for
    creating different types of messages.
    """

    def __init__(
        self,
        role: str,
        content: Optional[str] = None,
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """
        Initialize a message.

        Args:
            role: Message role ("user", "assistant", "system", "tool")
            content: Message content
            name: Optional name (for tool messages)
            tool_call_id: Optional tool call ID (for tool messages)
            metadata: Additional metadata
            timestamp: Message timestamp
        """
        self.role = role
        self.content = content
        self.name = name
        self.tool_call_id = tool_call_id
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        result: Dict[str, Any] = {"role": self.role}

        if self.content is not None:
            result["content"] = self.content

        if self.name is not None:
            result["name"] = self.name

        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id

        # Timestamp needs special handling for serialization
        if self.timestamp:
            result["timestamp"] = self.timestamp.isoformat()

        # Add metadata if not empty
        if self.metadata:
            result["metadata"] = self.metadata

        return result

    @classmethod
    def user_message(cls, content: str, **kwargs: Any) -> "Message":
        """Create a user message."""
        return cls(role="user", content=content, **kwargs)

    @classmethod
    def system_message(cls, content: str, **kwargs: Any) -> "Message":
        """Create a system message."""
        return cls(role="system", content=content, **kwargs)

    @classmethod
    def assistant_message(cls, content: str, **kwargs: Any) -> "Message":
        """Create an assistant message."""
        return cls(role="assistant", content=content, **kwargs)

    @classmethod
    def tool_message(cls, content: str, name: str, tool_call_id: str, **kwargs: Any) -> "Message":
        """Create a tool message."""
        return cls(role="tool", content=content, name=name, tool_call_id=tool_call_id, **kwargs)

    def __str__(self) -> str:
        """String representation for easier debugging."""
        role_display = f"[{self.role.upper()}]"
        if self.name:
            role_display += f" {self.name}"

        content_preview = (self.content or "")[:50]
        if len(content_preview) < len(self.content or ""):
            content_preview += "..."

        return f"{role_display}: {content_preview}"
