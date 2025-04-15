"""
Core type definitions for Enterprise AI.

This module defines Protocol classes and type aliases that form the foundation
of the type system, enabling proper static type checking.
"""

import abc
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Union,
    Iterator,
    AsyncIterator,
    runtime_checkable,
)


@runtime_checkable
class Serializable(Protocol):
    """Protocol for serializable objects."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        ...


@runtime_checkable
class MessageProtocol(Serializable, Protocol):
    """Protocol for chat messages in conversations."""

    role: str
    content: Optional[str]
    name: Optional[str]
    timestamp: Optional[datetime]
    metadata: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        ...

    @classmethod
    def user_message(cls, content: str, **kwargs: Any) -> "MessageProtocol":
        """Create a user message."""
        ...

    @classmethod
    def system_message(cls, content: str, **kwargs: Any) -> "MessageProtocol":
        """Create a system message."""
        ...

    @classmethod
    def assistant_message(cls, content: str, **kwargs: Any) -> "MessageProtocol":
        """Create an assistant message."""
        ...


@runtime_checkable
class ProviderProtocol(Protocol):
    """Base protocol for LLM providers."""

    def get_model_name(self) -> str:
        """Get the model name."""
        ...

    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion for the given messages."""
        ...

    def get_model_features(self) -> Set[str]:
        """Get the model's supported features."""
        ...

    def supports_feature(self, feature: str) -> bool:
        """Check if the model supports a specific feature."""
        ...


@runtime_checkable
class AsyncProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for async LLM providers."""

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion asynchronously."""
        ...


@runtime_checkable
class StreamingProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for streaming LLM providers."""

    def complete_stream(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> Iterator[MessageProtocol]:
        """Generate a streaming completion."""
        ...


@runtime_checkable
class AsyncStreamingProviderProtocol(AsyncProviderProtocol, Protocol):
    """Protocol for async streaming LLM providers."""

    async def acomplete_stream(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> AsyncIterator[MessageProtocol]:
        """Generate a streaming completion asynchronously."""
        ...
