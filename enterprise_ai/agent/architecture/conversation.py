"""
Conversation management for agents.

This module handles message processing, history management,
and conversation state tracking for agents.
"""

import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.architecture.errors import AgentError, AgentErrorCode, ErrorManager
from enterprise_ai.agent.architecture.utils import truncate_text
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("agent.conversation")


class ConversationMode(str, Enum):
    """Different conversation modes an agent can operate in."""

    STANDARD = "standard"
    CONCISE = "concise"
    DETAILED = "detailed"
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    INSTRUCTIONAL = "instructional"


class MessageType(str, Enum):
    """Types of messages in a conversation."""

    STANDARD = "standard"
    SYSTEM = "system"
    INSTRUCTION = "instruction"
    QUERY = "query"
    RESPONSE = "response"
    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"
    ERROR = "error"
    STATUS = "status"


class ConversationManagerConfig:
    """Configuration for conversation manager."""

    def __init__(
        self,
        max_history: int = 100,
        message_filter: Optional[List[str]] = None,
        conversation_mode: ConversationMode = ConversationMode.STANDARD,
        include_timestamps: bool = True,
        include_system_messages: bool = True,
        include_tool_messages: bool = True,
    ):
        """Initialize conversation manager configuration.

        Args:
            max_history: Maximum number of messages to keep in history
            message_filter: Optional list of message roles to filter out
            conversation_mode: Conversation mode to use
            include_timestamps: Whether to include timestamps in messages
            include_system_messages: Whether to include system messages in history
            include_tool_messages: Whether to include tool messages in history
        """
        self.max_history = max_history
        self.message_filter = message_filter or []
        self.conversation_mode = conversation_mode
        self.include_timestamps = include_timestamps
        self.include_system_messages = include_system_messages
        self.include_tool_messages = include_tool_messages


class ConversationManager:
    """Manager for agent conversations."""

    def __init__(self, agent: Any, config: Optional[ConversationManagerConfig] = None):
        """Initialize the conversation manager.

        Args:
            agent: The agent instance
            config: Optional conversation manager configuration
        """
        self.agent = agent
        self.agent_id = getattr(agent, "id", "unknown")
        self.config = config or ConversationManagerConfig()
        self._conversations: Dict[str, List[MessageProtocol]] = {"default": []}
        self._conversation_metadata: Dict[str, Dict[str, Any]] = {
            "default": {
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "message_count": 0,
            }
        }
        self._error_manager = ErrorManager(self.agent_id)
        self._default_system_message: Optional[MessageProtocol] = None

        logger.info(f"Initialized conversation manager for agent {self.agent_id}")

    def set_system_message(self, message: Union[str, MessageProtocol]) -> None:
        """Set the default system message for new conversations.

        Args:
            message: System message or content
        """
        if isinstance(message, str):
            self._default_system_message = Message.system_message(message)
        else:
            if message.role != "system":
                logger.warning(
                    f"Non-system message role provided: {message.role}, converting to system"
                )
                self._default_system_message = Message.system_message(message.content or "")
            else:
                self._default_system_message = message

    def add_message(
        self,
        message: Union[str, MessageProtocol],
        conversation_id: str = "default",
        role: str = "user",
        message_type: Optional[MessageType] = None,
    ) -> None:
        """Add a message to a conversation.

        Args:
            message: Message to add
            conversation_id: ID of conversation to add to
            role: Role of the message if string provided
            message_type: Optional message type for classification
        """
        # Create conversation if it doesn't exist
        if conversation_id not in self._conversations:
            self._create_conversation(conversation_id)

        # Convert string to message if needed
        if isinstance(message, str):
            if role == "user":
                processed_message = Message.user_message(message)
            elif role == "assistant":
                processed_message = Message.assistant_message(message)
            elif role == "system":
                processed_message = Message.system_message(message)
            else:
                processed_message = Message(role=role, content=message)
        else:
            processed_message = message

        # Add message type to metadata if provided
        if message_type and processed_message.metadata is not None:
            processed_message.metadata["message_type"] = message_type.value

        # Filter messages based on configuration
        if (
            (processed_message.role == "system" and not self.config.include_system_messages)
            or (processed_message.role == "tool" and not self.config.include_tool_messages)
            or (processed_message.role in self.config.message_filter)
        ):
            logger.debug(f"Filtered out message with role: {processed_message.role}")
            return

        # Add message to conversation
        self._conversations[conversation_id].append(processed_message)

        # Update conversation metadata
        meta = self._conversation_metadata[conversation_id]
        meta["updated_at"] = datetime.now()
        meta["message_count"] += 1

        # Trim history if needed
        if self.config.max_history > 0:
            self._trim_conversation(conversation_id)

    def get_messages(
        self,
        conversation_id: str = "default",
        limit: Optional[int] = None,
        include_roles: Optional[List[str]] = None,
    ) -> List[MessageProtocol]:
        """Get messages from a conversation.

        Args:
            conversation_id: ID of conversation to get messages from
            limit: Maximum number of messages to retrieve (most recent)
            include_roles: Optional list of roles to include

        Returns:
            List of messages
        """
        if conversation_id not in self._conversations:
            return []

        # Get messages
        messages = self._conversations[conversation_id]

        # Filter by roles if specified
        if include_roles:
            messages = [msg for msg in messages if msg.role in include_roles]

        # Apply limit if specified
        if limit and limit > 0:
            messages = messages[-limit:]

        return messages.copy()

    def create_conversation(
        self,
        conversation_id: Optional[str] = None,
        system_message: Optional[Union[str, MessageProtocol]] = None,
    ) -> str:
        """Create a new conversation.

        Args:
            conversation_id: Optional ID for the new conversation
            system_message: Optional system message for the conversation

        Returns:
            ID of the created conversation
        """
        # Generate ID if not provided
        if conversation_id is None:
            import uuid

            conversation_id = f"conv-{uuid.uuid4()}"

        # Create conversation
        self._create_conversation(conversation_id)

        # Add system message if provided or use default
        if system_message:
            if isinstance(system_message, str):
                self.add_message(
                    Message.system_message(system_message), conversation_id=conversation_id
                )
            else:
                self.add_message(system_message, conversation_id=conversation_id)
        elif self._default_system_message:
            self.add_message(self._default_system_message, conversation_id=conversation_id)

        return conversation_id

    def _create_conversation(self, conversation_id: str) -> None:
        """Create a new conversation with the given ID.

        Args:
            conversation_id: ID for the new conversation
        """
        if conversation_id in self._conversations:
            logger.warning(f"Conversation {conversation_id} already exists, overwriting")

        self._conversations[conversation_id] = []
        self._conversation_metadata[conversation_id] = {
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "message_count": 0,
        }

        logger.debug(f"Created conversation: {conversation_id}")

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation.

        Args:
            conversation_id: ID of conversation to delete

        Returns:
            True if conversation was deleted, False if not found
        """
        if conversation_id == "default":
            # Clear default conversation instead of deleting
            self.clear_conversation("default")
            return True

        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            if conversation_id in self._conversation_metadata:
                del self._conversation_metadata[conversation_id]

            logger.debug(f"Deleted conversation: {conversation_id}")
            return True

        return False

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear all messages from a conversation.

        Args:
            conversation_id: ID of conversation to clear

        Returns:
            True if conversation was cleared, False if not found
        """
        if conversation_id in self._conversations:
            self._conversations[conversation_id] = []

            # Reset message count but keep timestamps
            if conversation_id in self._conversation_metadata:
                self._conversation_metadata[conversation_id]["message_count"] = 0
                self._conversation_metadata[conversation_id]["updated_at"] = datetime.now()

            logger.debug(f"Cleared conversation: {conversation_id}")
            return True

        return False

    def _trim_conversation(self, conversation_id: str) -> None:
        """Trim a conversation to the maximum history size.

        Args:
            conversation_id: ID of conversation to trim
        """
        if conversation_id in self._conversations:
            conversation = self._conversations[conversation_id]

            if len(conversation) > self.config.max_history:
                # Find system messages to preserve
                system_messages = [
                    (i, msg) for i, msg in enumerate(conversation) if msg.role == "system"
                ]

                if system_messages:
                    # Extract most recent system messages
                    last_system_idx = system_messages[-1][0]
                    preserve_indices = set(i for i, _ in system_messages)

                    # Get non-system messages after the max history limit
                    remaining_count = self.config.max_history - len(preserve_indices)
                    if remaining_count > 0:
                        # Get indices of non-system messages to preserve
                        non_system_indices = [
                            i
                            for i, msg in enumerate(conversation)
                            if i > last_system_idx and msg.role != "system"
                        ][-remaining_count:]

                        preserve_indices.update(non_system_indices)

                    # Create new conversation with preserved messages
                    self._conversations[conversation_id] = [
                        msg for i, msg in enumerate(conversation) if i in preserve_indices
                    ]
                else:
                    # No system messages, just keep the most recent messages
                    self._conversations[conversation_id] = conversation[-self.config.max_history :]

    def set_conversation_mode(self, mode: ConversationMode) -> None:
        """Set the conversation mode.

        Args:
            mode: New conversation mode
        """
        self.config.conversation_mode = mode
        logger.debug(f"Set conversation mode to: {mode}")

    def get_conversation_summary(self, conversation_id: str = "default") -> str:
        """Get a summary of a conversation.

        Args:
            conversation_id: ID of conversation to summarize

        Returns:
            Conversation summary
        """
        if conversation_id not in self._conversations:
            return "Conversation not found"

        messages = self._conversations[conversation_id]
        meta = self._conversation_metadata[conversation_id]

        # Count messages by role
        role_counts: Dict[str, int] = {}
        for msg in messages:
            role_counts[msg.role] = role_counts.get(msg.role, 0) + 1

        # Calculate conversation duration
        duration = (
            (datetime.now() - meta["created_at"]).total_seconds() if meta["created_at"] else 0
        )

        # Format summary
        summary = (
            f"Conversation: {conversation_id}\n"
            f"Duration: {duration:.1f} seconds\n"
            f"Messages: {len(messages)}\n"
            f"Roles: {', '.join(f'{role}={count}' for role, count in role_counts.items())}\n"
        )

        # Add message previews
        if messages:
            summary += "\nRecent messages:\n"
            for msg in messages[-3:]:  # Show last 3 messages
                content_preview = truncate_text(msg.content or "", 50)
                summary += f"- [{msg.role}] {content_preview}\n"

        return summary

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations with metadata.

        Returns:
            List of conversation metadata
        """
        result = []

        for conv_id, meta in self._conversation_metadata.items():
            messages = self._conversations[conv_id]

            result.append(
                {
                    "conversation_id": conv_id,
                    "created_at": meta["created_at"].isoformat() if meta["created_at"] else None,
                    "updated_at": meta["updated_at"].isoformat() if meta["updated_at"] else None,
                    "message_count": meta["message_count"],
                    "last_message": (
                        messages[-1].content if messages and messages[-1].content else None
                    ),
                }
            )

        return result

    def format_message_for_mode(self, content: str, mode: Optional[ConversationMode] = None) -> str:
        """Format a message for the specified conversation mode.

        Args:
            content: Message content to format
            mode: Optional mode override

        Returns:
            Formatted message content
        """
        # Use specified mode or default
        current_mode = mode or self.config.conversation_mode

        if current_mode == ConversationMode.CONCISE:
            # Make message more concise
            # This is a simple implementation that could be enhanced
            lines = content.split("\n")
            result = []

            for line in lines:
                # Skip empty lines
                if not line.strip():
                    continue

                # Skip introductory phrases
                skip_phrases = ["I'll", "Let me", "Here's", "Sure,"]
                if any(line.strip().startswith(phrase) for phrase in skip_phrases):
                    continue

                result.append(line)

            return "\n".join(result)

        elif current_mode == ConversationMode.DETAILED:
            # Make message more detailed
            # This would typically involve instructions to the LLM
            return content

        elif current_mode == ConversationMode.FRIENDLY:
            # Make message more friendly
            # This would typically involve instructions to the LLM
            return content

        elif current_mode == ConversationMode.PROFESSIONAL:
            # Make message more professional
            # This would typically involve instructions to the LLM
            return content

        elif current_mode == ConversationMode.INSTRUCTIONAL:
            # Make message more instructional
            # This would typically involve instructions to the LLM
            return content

        # Default: return unmodified
        return content

    def get_conversation_context(self, conversation_id: str = "default") -> Dict[str, Any]:
        """Get context about a conversation for use in prompt engineering.

        Args:
            conversation_id: ID of conversation to get context for

        Returns:
            Dictionary of conversation context
        """
        if conversation_id not in self._conversations:
            return {}

        messages = self._conversations[conversation_id]
        meta = self._conversation_metadata[conversation_id]

        # Count user and assistant messages
        user_messages = [msg for msg in messages if msg.role == "user"]
        assistant_messages = [msg for msg in messages if msg.role == "assistant"]

        # Get conversation duration
        start_time = meta["created_at"]
        duration = (datetime.now() - start_time).total_seconds() if start_time else 0

        # Extract topics from user messages
        topics = []
        for msg in user_messages:
            topics.extend(self._extract_topics(msg.content or ""))

        # Count tool usage
        tool_counts: Dict[str, int] = {}
        for msg in messages:
            if msg.role == "tool" and msg.name:
                tool_counts[msg.name] = tool_counts.get(msg.name, 0) + 1

        # Get last N turn exchanges
        last_turns = []
        for i in range(min(3, len(user_messages))):
            if i < len(user_messages):
                user_msg = user_messages[-(i + 1)]

                # Find corresponding assistant message
                assistant_response = None
                for j, msg in enumerate(reversed(assistant_messages)):
                    if (
                        j >= i
                        and msg.timestamp
                        and user_msg.timestamp
                        and msg.timestamp > user_msg.timestamp
                    ):
                        assistant_response = msg
                        break

                if assistant_response:
                    last_turns.append(
                        {
                            "user": truncate_text(user_msg.content or "", 50),
                            "assistant": truncate_text(assistant_response.content or "", 50),
                        }
                    )

        return {
            "conversation_id": conversation_id,
            "message_count": len(messages),
            "user_message_count": len(user_messages),
            "assistant_message_count": len(assistant_messages),
            "duration_seconds": duration,
            "topics": topics[:5],  # Limit to top 5 topics
            "tools_used": tool_counts,
            "last_turns": last_turns,
            "mode": self.config.conversation_mode.value,
        }

    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text.

        This is a simple implementation that could be enhanced with NLP.

        Args:
            text: Text to extract topics from

        Returns:
            List of extracted topics
        """
        # Simple keyword extraction
        # In a real implementation, this would be more sophisticated
        import re

        # Remove punctuation and convert to lowercase
        text = re.sub(r"[^\w\s]", " ", text.lower())

        # Split into words
        words = text.split()

        # Remove common stop words
        stop_words = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "to",
            "of",
            "in",
            "on",
            "at",
            "by",
            "for",
            "with",
            "about",
            "as",
            "from",
            "is",
            "are",
            "am",
            "was",
            "were",
            "i",
            "me",
            "my",
            "mine",
            "you",
            "your",
            "yours",
            "he",
            "him",
            "his",
            "she",
            "her",
            "hers",
            "it",
            "its",
            "we",
            "us",
            "our",
            "ours",
            "they",
            "them",
            "their",
            "theirs",
            "this",
            "that",
            "these",
            "those",
            "do",
            "does",
            "did",
            "have",
            "has",
            "had",
            "will",
            "would",
            "shall",
            "should",
            "can",
            "could",
            "may",
            "might",
            "must",
        }

        filtered_words = [word for word in words if word not in stop_words and len(word) > 3]

        # Count word frequencies
        word_counts: Dict[str, int] = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Get top words by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        # Return top 10 words as topics
        return [word for word, _ in sorted_words[:10]]
