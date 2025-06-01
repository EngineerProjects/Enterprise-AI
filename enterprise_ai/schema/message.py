"""
Message schema for Enterprise AI.

This module defines the core message model used for LLM interactions.
Enhanced to support the new LLM provider architecture.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast

from enterprise_ai.types import MessageProtocol


class Message:
    """
    Represents a chat message in a conversation.

    This class implements the MessageProtocol and provides methods for
    creating different types of messages with enhanced metadata support.
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
            metadata: Additional metadata including tool_calls, images, etc.
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

    def has_tool_calls(self) -> bool:
        """Check if message contains tool calls."""
        return bool(self.metadata.get("tool_calls"))

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """Get tool calls from metadata."""
        return self.metadata.get("tool_calls", [])

    def has_images(self) -> bool:
        """Check if message contains images."""
        return bool(self.metadata.get("images"))

    def get_images(self) -> List[str]:
        """Get images from metadata."""
        return self.metadata.get("images", [])

    def is_partial(self) -> bool:
        """Check if this is a partial streaming message."""
        return self.metadata.get("is_partial", False)

    def get_provider(self) -> Optional[str]:
        """Get the provider that generated this message."""
        return self.metadata.get("provider")

    def get_model(self) -> Optional[str]:
        """Get the model that generated this message."""
        return self.metadata.get("model")

    def add_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Add a tool call to the message metadata."""
        if "tool_calls" not in self.metadata:
            self.metadata["tool_calls"] = []
        self.metadata["tool_calls"].append(tool_call)

    def add_image(self, image: str) -> None:
        """Add an image to the message metadata."""
        if "images" not in self.metadata:
            self.metadata["images"] = []
        self.metadata["images"].append(image)

    def set_partial(self, is_partial: bool = True) -> None:
        """Mark message as partial (for streaming)."""
        self.metadata["is_partial"] = is_partial

    def copy(self, **updates: Any) -> "Message":
        """Create a copy of the message with optional updates."""
        new_data = {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "metadata": self.metadata.copy() if self.metadata else {},
            "timestamp": self.timestamp,
        }
        new_data.update(updates)
        return Message(**new_data)

    @classmethod
    def user_message(
        cls, 
        content: str, 
        images: Optional[List[str]] = None,
        **kwargs: Any
    ) -> "Message":
        """Create a user message with optional images."""
        metadata = kwargs.pop("metadata", {})
        if images:
            metadata["images"] = images
        return cls(role="user", content=content, metadata=metadata, **kwargs)

    @classmethod
    def system_message(cls, content: str, **kwargs: Any) -> "Message":
        """Create a system message."""
        return cls(role="system", content=content, **kwargs)

    @classmethod
    def assistant_message(
        cls, 
        content: str, 
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any
    ) -> "Message":
        """Create an assistant message with optional tool calls."""
        metadata = kwargs.pop("metadata", {})
        if tool_calls:
            metadata["tool_calls"] = tool_calls
        return cls(role="assistant", content=content, metadata=metadata, **kwargs)

    @classmethod
    def tool_message(
        cls, 
        content: str, 
        name: str, 
        tool_call_id: str, 
        **kwargs: Any
    ) -> "Message":
        """Create a tool message."""
        return cls(
            role="tool", 
            content=content, 
            name=name, 
            tool_call_id=tool_call_id, 
            **kwargs
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create a message from a dictionary.

        Args:
            data: Dictionary with message data

        Returns:
            New Message instance
        """
        # Extract required fields
        role = data.get("role", "user")
        content = data.get("content")
        name = data.get("name")
        tool_call_id = data.get("tool_call_id")

        # Extract and convert timestamp if present
        timestamp = None
        if "timestamp" in data and data["timestamp"]:
            try:
                if isinstance(data["timestamp"], str):
                    timestamp = datetime.fromisoformat(data["timestamp"])
                elif isinstance(data["timestamp"], datetime):
                    timestamp = data["timestamp"]
                else:
                    timestamp = datetime.now()
            except (ValueError, TypeError):
                timestamp = datetime.now()

        # Extract metadata
        metadata = data.get("metadata", {})

        # Create and return message
        return cls(
            role=role,
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            metadata=metadata,
            timestamp=timestamp,
        )

    def __str__(self) -> str:
        """String representation for easier debugging."""
        role_display = f"[{self.role.upper()}]"
        if self.name:
            role_display += f" {self.name}"

        content_preview = (self.content or "")[:50]
        if len(content_preview) < len(self.content or ""):
            content_preview += "..."

        # Add indicators for special content
        indicators = []
        if self.has_tool_calls():
            indicators.append(f"tools:{len(self.get_tool_calls())}")
        if self.has_images():
            indicators.append(f"images:{len(self.get_images())}")
        if self.is_partial():
            indicators.append("partial")

        indicator_str = f" ({', '.join(indicators)})" if indicators else ""

        return f"{role_display}: {content_preview}{indicator_str}"

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        return (
            f"Message(role='{self.role}', content_length={len(self.content or '')}, "
            f"has_tool_calls={self.has_tool_calls()}, has_images={self.has_images()}, "
            f"metadata_keys={list(self.metadata.keys())})"
        )