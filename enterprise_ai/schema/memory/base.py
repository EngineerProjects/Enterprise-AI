"""
Base interfaces for conversation memory management.

This module defines the abstract base classes for conversation memory
implementations in the Enterprise AI framework.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional, TypeVar, cast

from enterprise_ai.schema.message import Message
from enterprise_ai.types import MessageProtocol

T = TypeVar("T", bound=MessageProtocol)


class ConversationMemory(ABC):
    """
    Abstract base class for conversation memory implementations.

    This defines the interface that all conversation memory implementations
    must adhere to, allowing for different storage backends.
    """

    @abstractmethod
    def add_message(self, message: MessageProtocol) -> None:
        """
        Add a message to the conversation history.

        Args:
            message: The message to add
        """
        pass

    def add_user_message(self, content: str, **kwargs: Any) -> MessageProtocol:
        """
        Add a user message to the conversation history.

        Args:
            content: The message content
            **kwargs: Additional message parameters

        Returns:
            The created message
        """
        message = Message.user_message(content, **kwargs)
        self.add_message(cast(MessageProtocol, message))
        return cast(MessageProtocol, message)

    def add_assistant_message(self, content: str, **kwargs: Any) -> MessageProtocol:
        """
        Add an assistant message to the conversation history.

        Args:
            content: The message content
            **kwargs: Additional message parameters

        Returns:
            The created message
        """
        message = Message.assistant_message(content, **kwargs)
        self.add_message(cast(MessageProtocol, message))
        return cast(MessageProtocol, message)

    def add_system_message(self, content: str, **kwargs: Any) -> MessageProtocol:
        """
        Add a system message to the conversation history.

        Args:
            content: The message content
            **kwargs: Additional message parameters

        Returns:
            The created message
        """
        message = Message.system_message(content, **kwargs)
        self.add_message(cast(MessageProtocol, message))
        return cast(MessageProtocol, message)

    @abstractmethod
    def get_messages(
        self, limit: Optional[int] = None, include_system: bool = True
    ) -> List[MessageProtocol]:
        """
        Get messages from the conversation history.

        Args:
            limit: Maximum number of most recent messages to retrieve
            include_system: Whether to include system messages

        Returns:
            List of messages
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all messages from the conversation history."""
        pass

    @abstractmethod
    def get_token_count(self) -> int:
        """
        Get an estimate of the total token count for the conversation.

        Returns:
            Estimated token count
        """
        pass
