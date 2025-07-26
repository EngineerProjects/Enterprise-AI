"""
Concrete implementations for conversation memory management.

This module provides implementations of the ConversationMemory interface
for different use cases and storage mechanisms.
"""

from typing import Any, Dict, List, Optional, Type, Union, cast

from enterprise_ai.schema.memory.base import ConversationMemory
from enterprise_ai.types import MessageProtocol


class InMemoryConversation(ConversationMemory):
    """
    Simple in-memory implementation of conversation memory.

    This class stores conversation history in memory and is suitable for
    short-lived conversations or testing.
    """

    def __init__(self, system_prompt: Optional[str] = None):
        """
        Initialize in-memory conversation storage.

        Args:
            system_prompt: Optional system prompt to begin the conversation
        """
        self.messages: List[MessageProtocol] = []

        # Add system prompt if provided
        if system_prompt:
            self.add_system_message(system_prompt)

    def add_message(self, message: MessageProtocol) -> None:
        """
        Add a message to the conversation history.

        Args:
            message: The message to add
        """
        self.messages.append(message)

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
        filtered_messages = self.messages

        # Filter out system messages if requested
        if not include_system:
            filtered_messages = [m for m in filtered_messages if m.role != "system"]

        # Apply limit if specified
        if limit is not None and limit > 0:
            filtered_messages = filtered_messages[-limit:]

        return filtered_messages

    def clear(self) -> None:
        """Clear all messages from the conversation history."""
        self.messages = []

    def get_token_count(self) -> int:
        """
        Get a rough estimate of the token count for the conversation.

        This uses a simple heuristic - approximately 4 characters per token.
        For accurate counts, use a proper tokenizer.

        Returns:
            Estimated token count
        """
        chars = sum(len(m.content or "") for m in self.messages)
        # Approximate tokens: 4 chars per token on average
        return chars // 4


class SlidingWindowConversation(InMemoryConversation):
    """
    Conversation memory that maintains a sliding window of messages.

    This implementation automatically limits the conversation history
    to a maximum number of messages or tokens, keeping the most recent
    messages and always retaining system messages.
    """

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        max_messages: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize sliding window conversation memory.

        Args:
            system_prompt: Optional system prompt to begin the conversation
            max_messages: Maximum number of non-system messages to retain
            max_tokens: Maximum number of tokens to retain (approximate)
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens

        super().__init__(system_prompt)

    def add_message(self, message: MessageProtocol) -> None:
        """
        Add a message to the conversation history and enforce limits.

        This method adds the message and then trims the history if
        necessary to stay within the configured limits.

        Args:
            message: The message to add
        """
        # Add the message
        super().add_message(message)

        # Enforce limits
        self._enforce_limits()

    def _enforce_limits(self) -> None:
        """
        Enforce message and token limits.

        This method trims the conversation history to stay within
        the configured limits, always preserving system messages.
        """
        if not self.max_messages and not self.max_tokens:
            return

        # Separate system and non-system messages
        system_messages = [m for m in self.messages if m.role == "system"]
        non_system_messages = [m for m in self.messages if m.role != "system"]

        # Enforce max_messages limit
        if self.max_messages and len(non_system_messages) > self.max_messages:
            # Keep only the most recent messages up to max_messages
            non_system_messages = non_system_messages[-self.max_messages :]

        # Enforce max_tokens limit (very approximate)
        if self.max_tokens:
            # Calculate system message tokens
            system_tokens = sum(len(m.content or "") for m in system_messages) // 4
            remaining_tokens = self.max_tokens - system_tokens

            if remaining_tokens > 0:
                # Remove oldest messages until we're under the token limit
                while non_system_messages:
                    tokens = sum(len(m.content or "") for m in non_system_messages) // 4
                    if tokens <= remaining_tokens:
                        break
                    # Remove the oldest non-system message
                    non_system_messages.pop(0)

        # Recombine messages
        self.messages = system_messages + non_system_messages
