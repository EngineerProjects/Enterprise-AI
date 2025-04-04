"""
Memory management for message histories in Enterprise AI.

This module provides specialized memory implementations for storing, retrieving,
and managing conversation histories and message collections. It extends the base
Memory class from the schema module with enhanced functionality for context
management, filtering, summarization, and efficient storage.

Memory instances serve as the conversation history for agents, providing the
necessary context for LLM interactions and agent-to-agent communication while
ensuring efficient token usage and semantic retrieval capabilities.
"""

import json
import time
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
    TypeVar,
    Generic,
    Sequence,
    TypedDict,
    overload,
)

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Memory, Message, Role
from enterprise_ai.types import MessageProtocol, MemoryProtocol, RoleType
from enterprise_ai.message.base import EnhancedMessage
from enterprise_ai.message.utils import (
    filter_messages_by_role,
    filter_messages_by_timestamp,
    get_conversation_summary,
    merge_consecutive_messages,
    extract_structured_content,
)
from enterprise_ai.message.formatter import format_messages

# Initialize logger
logger = get_logger("message.memory")

# Type variable for generic typing - bound ensures type compatibility with MessageProtocol
M = TypeVar("M", bound=MessageProtocol)


# Summary object type for type checking
class SummaryDict(TypedDict):
    """Type definition for summary dictionary."""

    text: str
    created_at: str
    message_count: int
    type: str
    metadata: Dict[str, Any]


class EnhancedMemory(Memory, Generic[M]):
    """Enhanced memory implementation with advanced features.

    This class extends the base Memory class with additional functionality
    for message filtering, summarization, token management, and persistence.
    """

    def __init__(
        self,
        messages: Optional[List[M]] = None,
        max_messages: int = 100,
        metadata: Optional[Dict[str, Any]] = None,
        name: str = "default",
        token_limit: Optional[int] = None,
    ):
        """Initialize enhanced memory.

        Args:
            messages: Initial messages list
            max_messages: Maximum number of messages to store
            metadata: Additional metadata
            name: Memory instance name
            token_limit: Maximum token count (for LLM context windows)
        """
        # Convert generic messages to MessageProtocol for parent class
        parent_messages: List[MessageProtocol] = []
        if messages is not None:
            parent_messages = [cast(MessageProtocol, msg) for msg in messages]

        super().__init__(
            messages=parent_messages,
            max_messages=max_messages,
            metadata=metadata or {},
        )
        self.name = name
        self.token_limit = token_limit
        self.last_accessed = datetime.now()
        self.created_at = datetime.now()

        # Store typed messages internally
        self._typed_messages: List[M] = []
        if messages is not None:
            self._typed_messages = messages.copy()

    def add_message(self, message: MessageProtocol) -> None:
        """Add a message to memory with enhanced tracking.

        Args:
            message: Message to add
        """
        # Add to parent's messages
        super().add_message(message)

        # Also add to our typed collection if it matches the type
        if isinstance(message, MessageProtocol):
            self._typed_messages.append(cast(M, message))

        self.last_accessed = datetime.now()

        # Limit the number of messages if needed
        if len(self.messages) > self.max_messages:
            logger.debug(
                f"Memory '{self.name}' exceeded max_messages ({self.max_messages}). "
                f"Removing oldest messages."
            )
            self.messages = self.messages[-self.max_messages :]
            self._typed_messages = self._typed_messages[-self.max_messages :]

        # Update metadata
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()

    def add_messages(self, messages: List[MessageProtocol]) -> None:
        """Add multiple messages to memory.

        Args:
            messages: List of messages to add
        """
        # Add to parent's messages
        super().add_messages(messages)

        # Also add to our typed collection
        for message in messages:
            self._typed_messages.append(cast(M, message))

        self.last_accessed = datetime.now()

        # Limit the number of messages if needed
        if len(self.messages) > self.max_messages:
            logger.debug(
                f"Memory '{self.name}' exceeded max_messages ({self.max_messages}). "
                f"Removing oldest messages."
            )
            self.messages = self.messages[-self.max_messages :]
            self._typed_messages = self._typed_messages[-self.max_messages :]

        # Update metadata
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()

    def get_message(self, index: int) -> Optional[M]:
        """Get a message by index.

        Args:
            index: Index of the message (negative indices supported)

        Returns:
            Message at the specified index or None if out of bounds
        """
        self.last_accessed = datetime.now()
        try:
            return self._typed_messages[index]
        except IndexError:
            return None

    def get_last_message(self) -> Optional[M]:
        """Get the most recent message.

        Returns:
            The most recent message or None if memory is empty
        """
        if not self._typed_messages:
            return None
        return self.get_message(-1)

    def get_messages_by_role(self, role: Union[RoleType, str]) -> List[M]:
        """Get all messages with a specific role.

        Args:
            role: Role to filter by

        Returns:
            List of messages with the specified role
        """
        self.last_accessed = datetime.now()

        # Handle different representations of role
        role_str = role.value if hasattr(role, "value") else str(role)

        result = []
        for msg in self._typed_messages:
            # Get the message role as string, handling both Enum and str cases
            msg_role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            if msg_role == role_str:
                result.append(msg)

        return result

    def get_messages_by_timeframe(
        self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[M]:
        """Get messages within a specific timeframe.

        Args:
            start_time: Start of the time range (inclusive)
            end_time: End of the time range (inclusive)

        Returns:
            List of messages within the specified timeframe
        """
        self.last_accessed = datetime.now()

        # Filter messages directly from our typed list
        result: List[M] = []
        for msg in self._typed_messages:
            if not msg.timestamp:
                continue

            if start_time and msg.timestamp < start_time:
                continue

            if end_time and msg.timestamp > end_time:
                continue

            result.append(msg)

        return result

    def search(self, query: str, case_sensitive: bool = False) -> List[M]:
        """Search messages for content matching the query.

        Args:
            query: Search query string
            case_sensitive: Whether to perform case-sensitive search

        Returns:
            List of messages matching the query
        """
        self.last_accessed = datetime.now()
        results: List[M] = []

        search_query = query if case_sensitive else query.lower()

        for message in self._typed_messages:
            if message.content:
                content = message.content if case_sensitive else message.content.lower()
                if search_query in content:
                    results.append(message)

        return results

    def clear(self, keep_system: bool = True) -> None:
        """Clear memory, optionally preserving system messages.

        Args:
            keep_system: Whether to keep system messages
        """
        if keep_system:
            system_messages = self.get_messages_by_role(cast(RoleType, Role.SYSTEM))
            self._typed_messages = system_messages

            # Update parent messages
            self.messages.clear()
            for msg in system_messages:
                self.messages.append(cast(MessageProtocol, msg))
        else:
            self._typed_messages = []
            self.messages.clear()

        self.last_accessed = datetime.now()
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()
        self.metadata["cleared_at"] = self.last_accessed.isoformat()

    def prune(self, max_messages: Optional[int] = None) -> List[M]:
        """Prune messages to the specified maximum.

        Args:
            max_messages: Maximum number of messages to keep (defaults to self.max_messages)

        Returns:
            List of removed messages
        """
        limit = max_messages or self.max_messages
        if len(self._typed_messages) <= limit:
            return []

        removed = self._typed_messages[:-limit]
        self._typed_messages = self._typed_messages[-limit:]

        # Update parent messages
        self.messages = [cast(MessageProtocol, msg) for msg in self._typed_messages]

        self.last_accessed = datetime.now()
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()
        self.metadata["pruned_at"] = self.last_accessed.isoformat()

        return removed

    def prune_by_token_count(
        self,
        max_tokens: Optional[int] = None,
        token_counter: Optional[Callable[[List[M]], int]] = None,
    ) -> List[M]:
        """Prune messages to fit within token limit.

        Args:
            max_tokens: Maximum tokens to allow (defaults to self.token_limit)
            token_counter: Function to count tokens (if None, uses a simple estimation)

        Returns:
            List of removed messages
        """
        limit = max_tokens or self.token_limit
        if limit is None:
            logger.warning("No token limit specified for prune_by_token_count")
            return []

        # Default token counter uses a simple heuristic
        def simple_token_counter(msgs: List[M]) -> int:
            total = 0
            for msg in msgs:
                # Roughly 4 chars per token
                if msg.content:
                    total += len(msg.content) // 4
            return total

        counter = token_counter or simple_token_counter

        # If we're already under the limit, no pruning needed
        current_tokens = counter(self._typed_messages)
        if current_tokens <= limit:
            return []

        # Find the cutoff point
        removed: List[M] = []
        while self._typed_messages and counter(self._typed_messages) > limit:
            if self._typed_messages:
                removed.append(self._typed_messages.pop(0))

        # Update parent messages to match
        self.messages = [cast(MessageProtocol, msg) for msg in self._typed_messages]

        self.last_accessed = datetime.now()
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()
        self.metadata["token_pruned_at"] = self.last_accessed.isoformat()

        return removed

    def get_formatted_history(self, format_name: str = "default") -> str:
        """Get formatted conversation history.

        Args:
            format_name: Format to use for messages

        Returns:
            Formatted conversation history
        """
        self.last_accessed = datetime.now()
        return format_messages(
            [cast(MessageProtocol, msg) for msg in self._typed_messages], format_name
        )

    def get_summary(self, max_messages: int = 5) -> str:
        """Get a summary of the conversation.

        Args:
            max_messages: Maximum number of recent messages to include

        Returns:
            Conversation summary
        """
        self.last_accessed = datetime.now()
        return get_conversation_summary(
            [cast(MessageProtocol, msg) for msg in self._typed_messages], max_messages
        )

    def merge_consecutive(self) -> None:
        """Merge consecutive messages from the same role."""
        original_count = len(self._typed_messages)

        # Convert to MessageProtocol for utility function
        merged_msgs = merge_consecutive_messages(
            [cast(MessageProtocol, msg) for msg in self._typed_messages]
        )

        # Update both message collections
        self._typed_messages = [cast(M, msg) for msg in merged_msgs]
        self.messages = [cast(MessageProtocol, msg) for msg in self._typed_messages]

        merged_count = original_count - len(self._typed_messages)
        if merged_count > 0:
            logger.debug(f"Merged {merged_count} consecutive messages in memory '{self.name}'")

        self.last_accessed = datetime.now()
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()
        self.metadata["merged_at"] = self.last_accessed.isoformat()

    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save memory to a file.

        Args:
            file_path: Path to save the memory
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert messages to dictionaries
        messages_dict = [msg.to_dict() for msg in self._typed_messages]

        # Prepare data for serialization
        data = {
            "name": self.name,
            "max_messages": self.max_messages,
            "token_limit": self.token_limit,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "metadata": self.metadata,
            "messages": messages_dict,
        }

        # Save to file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Memory '{self.name}' saved to {path}")

    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> "EnhancedMemory[MessageProtocol]":
        """Load memory from a file.

        Args:
            file_path: Path to load the memory from

        Returns:
            Loaded memory instance
        """
        path = Path(file_path)

        if not path.exists():
            logger.warning(f"Memory file not found: {path}")
            # Use explicit cast to ensure correct return type
            return cast(EnhancedMemory[MessageProtocol], cls())

        # Load data from file
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Convert dictionaries back to messages
        messages: List[MessageProtocol] = []
        for msg_dict in data.get("messages", []):
            try:
                # Try to use EnhancedMessage if appropriate
                # Explicit type annotation to avoid confusion
                msg_enhanced: MessageProtocol = EnhancedMessage.from_dict(msg_dict)
                messages.append(msg_enhanced)
            except Exception:
                # Fall back to standard Message
                try:
                    # Explicit type annotation to prevent type confusion
                    msg_standard: MessageProtocol = Message(**msg_dict)
                    messages.append(msg_standard)
                except Exception as e:
                    logger.warning(f"Failed to parse message: {e}")

        # Create instance with explicit cast to ensure correct return type
        memory = cast(
            EnhancedMemory[MessageProtocol],
            cls(
                messages=cast(List[M], messages),
                max_messages=data.get("max_messages", 100),
                metadata=data.get("metadata", {}),
                name=data.get("name", "default"),
                token_limit=data.get("token_limit"),
            ),
        )

        # Set additional attributes
        memory.created_at = datetime.fromisoformat(
            data.get("created_at", datetime.now().isoformat())
        )
        memory.last_accessed = datetime.now()

        logger.info(f"Loaded memory '{memory.name}' from {path} with {len(messages)} messages")
        return memory


class ConversationMemory(EnhancedMemory[M]):
    """Specialized memory for conversational contexts.

    This memory type is optimized for agent conversations, providing methods
    to track conversation state, extract information, and manage context.
    """

    def __init__(
        self,
        messages: Optional[List[M]] = None,
        max_messages: int = 100,
        metadata: Optional[Dict[str, Any]] = None,
        name: str = "conversation",
        token_limit: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize conversation memory.

        Args:
            messages: Initial messages list
            max_messages: Maximum number of messages to store
            metadata: Additional metadata
            name: Memory instance name
            token_limit: Maximum token count
            system_prompt: System prompt for the conversation
        """
        super().__init__(
            messages=messages,
            max_messages=max_messages,
            metadata=metadata or {},
            name=name,
            token_limit=token_limit,
        )

        # Add system message if provided
        if system_prompt and not self.get_messages_by_role(cast(RoleType, Role.SYSTEM)):
            system_message = Message(role=cast(RoleType, Role.SYSTEM), content=system_prompt)
            # Add to both collections
            self.messages.insert(0, system_message)
            self._typed_messages.insert(0, cast(M, system_message))

        # Initialize conversation tracking
        self.last_user_message: Optional[M] = None
        self.last_assistant_message: Optional[M] = None
        self.turn_count = 0

        # Update metadata
        self.metadata["conversation_id"] = name
        self.metadata["turn_count"] = self.turn_count

    def add_message(self, message: MessageProtocol) -> None:
        """Add a message with conversation state tracking.

        Args:
            message: Message to add
        """
        super().add_message(message)

        # Update conversation tracking
        if message.role == Role.USER:
            self.last_user_message = cast(M, message)
            self.turn_count += 1
        elif message.role == Role.ASSISTANT:
            self.last_assistant_message = cast(M, message)

        # Update metadata
        self.metadata["turn_count"] = self.turn_count

    def add_user_message(self, content: str) -> M:
        """Add a user message to the conversation.

        Args:
            content: Message content

        Returns:
            The created message
        """
        msg: MessageProtocol = Message.user_message(content=content)
        self.add_message(msg)
        return cast(M, msg)

    def add_assistant_message(self, content: str) -> M:
        """Add an assistant message to the conversation.

        Args:
            content: Message content

        Returns:
            The created message
        """
        msg: MessageProtocol = Message.assistant_message(content=content)
        self.add_message(msg)
        return cast(M, msg)

    def add_system_message(self, content: str) -> M:
        """Add a system message to the conversation.

        Args:
            content: Message content

        Returns:
            The created message
        """
        msg: MessageProtocol = Message.system_message(content=content)

        # Add at the beginning for system messages
        self.messages.insert(0, msg)
        self._typed_messages.insert(0, cast(M, msg))

        # Update metadata
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = datetime.now().isoformat()

        return cast(M, msg)

    def get_recent_conversation(self, turns: int = 3) -> List[M]:
        """Get the most recent conversation turns.

        Args:
            turns: Number of conversation turns to retrieve

        Returns:
            List of messages from recent conversation turns
        """
        # Always include system messages
        system_messages = self.get_messages_by_role(cast(RoleType, Role.SYSTEM))

        # Get recent messages (excluding system messages)
        non_system = [msg for msg in self._typed_messages if msg.role != Role.SYSTEM]

        # Calculate how many messages to include for the requested turns
        # Each turn typically has a user message and an assistant message
        messages_per_turn = 2
        recent_count = min(len(non_system), turns * messages_per_turn)
        recent_messages = non_system[-recent_count:]

        # Combine system messages with recent messages
        return system_messages + recent_messages

    def get_conversation_context(self, max_tokens: Optional[int] = None) -> List[M]:
        """Get conversation context optimized for LLM requests.

        Args:
            max_tokens: Maximum token count

        Returns:
            List of messages optimized for context
        """
        # Start with system messages
        context = self.get_messages_by_role(cast(RoleType, Role.SYSTEM))

        # If no token limit, return all messages
        if max_tokens is None and self.token_limit is None:
            return context + [msg for msg in self._typed_messages if msg.role != Role.SYSTEM]

        limit = max_tokens or self.token_limit
        if limit is None:
            logger.warning("No token limit specified for get_conversation_context")
            return context + [msg for msg in self._typed_messages if msg.role != Role.SYSTEM]

        # Simple token estimation
        def estimate_tokens(msgs: List[M]) -> int:
            total = 0
            for msg in msgs:
                # Roughly 4 chars per token
                if msg.content:
                    total += len(msg.content) // 4
            return total

        # Calculate system message tokens
        system_tokens = estimate_tokens(context)
        remaining_tokens = limit - system_tokens

        if remaining_tokens <= 0:
            logger.warning(
                "System messages exceed token limit, returning truncated system messages"
            )
            return context

        # Get non-system messages
        non_system = [msg for msg in self._typed_messages if msg.role != Role.SYSTEM]

        # Add messages from newest to oldest until we hit the token limit
        result = context.copy()
        token_count = system_tokens

        for msg in reversed(non_system):
            # Estimate tokens for this message
            msg_tokens = estimate_tokens([msg])

            # If adding this message would exceed the limit, stop
            if token_count + msg_tokens > remaining_tokens:
                break

            # Add message to the result (at the beginning of non-system messages)
            result.append(msg)
            token_count += msg_tokens

        # Sort messages back into chronological order
        # This sorts only the non-system messages and adds them after system messages
        non_system_sorted = sorted(
            [m for m in result if m.role != Role.SYSTEM], key=lambda x: x.timestamp or datetime.min
        )

        return context + non_system_sorted


class ShortTermMemory(EnhancedMemory[M]):
    """Short-term memory with automatic expiration.

    This memory type automatically expires old messages after a specified
    time period, simulating limited short-term recall.
    """

    def __init__(
        self,
        messages: Optional[List[M]] = None,
        max_messages: int = 100,
        metadata: Optional[Dict[str, Any]] = None,
        name: str = "short_term",
        token_limit: Optional[int] = None,
        retention_period: timedelta = timedelta(hours=1),
    ):
        """Initialize short-term memory.

        Args:
            messages: Initial messages list
            max_messages: Maximum number of messages to store
            metadata: Additional metadata
            name: Memory instance name
            token_limit: Maximum token count
            retention_period: How long to keep messages before expiration
        """
        super().__init__(
            messages=messages,
            max_messages=max_messages,
            metadata=metadata or {},
            name=name,
            token_limit=token_limit,
        )
        self.retention_period = retention_period

        # Update metadata
        self.metadata["memory_type"] = "short_term"
        self.metadata["retention_period"] = str(retention_period)

    def get_active_messages(self) -> List[M]:
        """Get messages that haven't expired.

        Returns:
            List of non-expired messages
        """
        cutoff_time = datetime.now() - self.retention_period
        return self.get_messages_by_timeframe(start_time=cutoff_time)

    def cleanup_expired(self) -> List[M]:
        """Remove expired messages.

        Args:
            None

        Returns:
            List of expired messages that were removed
        """
        cutoff_time = datetime.now() - self.retention_period

        # Separate active and expired messages
        active: List[M] = []
        expired: List[M] = []

        for msg in self._typed_messages:
            if msg.timestamp and msg.timestamp >= cutoff_time:
                active.append(msg)
            else:
                expired.append(msg)

        # Update messages list
        self._typed_messages = active
        self.messages = [cast(MessageProtocol, msg) for msg in active]

        # Update metadata
        self.last_accessed = datetime.now()
        self.metadata["message_count"] = len(self.messages)
        self.metadata["last_updated"] = self.last_accessed.isoformat()
        self.metadata["last_cleanup"] = self.last_accessed.isoformat()
        self.metadata["expired_count"] = len(expired)

        return expired


class LongTermMemory(EnhancedMemory[M]):
    """Long-term memory with summarization capabilities.

    This memory type maintains detailed summaries of past conversations and
    important information, allowing agents to recall information over longer periods.
    """

    def __init__(
        self,
        messages: Optional[List[M]] = None,
        max_messages: int = 1000,
        metadata: Optional[Dict[str, Any]] = None,
        name: str = "long_term",
        token_limit: Optional[int] = None,
        summary_interval: int = 50,  # Summarize every 50 messages
    ):
        """Initialize long-term memory.

        Args:
            messages: Initial messages list
            max_messages: Maximum number of messages to store
            metadata: Additional metadata
            name: Memory instance name
            token_limit: Maximum token count
            summary_interval: How often to create summaries
        """
        super().__init__(
            messages=messages,
            max_messages=max_messages,
            metadata=metadata or {},
            name=name,
            token_limit=token_limit,
        )
        self.summary_interval = summary_interval
        self.summaries: List[SummaryDict] = []

        # Update metadata
        self.metadata["memory_type"] = "long_term"
        self.metadata["summary_interval"] = summary_interval
        self.metadata["summary_count"] = 0

    def add_message(self, message: MessageProtocol) -> None:
        """Add a message with automatic summarization.

        Args:
            message: Message to add
        """
        super().add_message(message)

        # Check if we need to create a summary
        if (
            len(self.messages) % self.summary_interval == 0
            and len(self.messages) >= self.summary_interval
        ):
            self._create_summary()

    def add_summary(self, summary_text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a manual summary to long-term memory.

        Args:
            summary_text: Summary content
            metadata: Additional summary metadata
        """
        summary: SummaryDict = {
            "text": summary_text,
            "created_at": datetime.now().isoformat(),
            "message_count": len(self.messages),
            "type": "manual",
            "metadata": metadata or {},
        }

        self.summaries.append(summary)

        # Update metadata
        self.metadata["summary_count"] = len(self.summaries)
        self.metadata["last_summary"] = summary["created_at"]

    def get_summaries(self, count: Optional[int] = None) -> List[SummaryDict]:
        """Get memory summaries.

        Args:
            count: Number of recent summaries to retrieve (None for all)

        Returns:
            List of summary objects
        """
        if count is None:
            return self.summaries
        return self.summaries[-count:]

    def _create_summary(self) -> None:
        """Create an automatic summary of recent messages."""
        # In a real implementation, this would use an LLM to generate a summary
        # For now, we'll just create a simple count-based summary
        recent_messages = self._typed_messages[-self.summary_interval :]

        # Create simple summary
        summary_text = (
            f"Summary of {len(recent_messages)} messages: "
            f"{len([m for m in recent_messages if m.role == Role.USER])} user messages, "
            f"{len([m for m in recent_messages if m.role == Role.ASSISTANT])} assistant messages."
        )

        # Add summary
        summary: SummaryDict = {
            "text": summary_text,
            "created_at": datetime.now().isoformat(),
            "message_count": len(self.messages),
            "type": "automatic",
            "metadata": {
                "start_index": len(self.messages) - self.summary_interval,
                "end_index": len(self.messages) - 1,
            },
        }

        self.summaries.append(summary)

        # Update metadata
        self.metadata["summary_count"] = len(self.summaries)
        self.metadata["last_summary"] = summary["created_at"]

        logger.debug(f"Created automatic summary in memory '{self.name}'")


# Factory functions for common memory types
def create_conversation_memory(
    system_prompt: Optional[str] = None,
    max_messages: int = 100,
    token_limit: Optional[int] = None,
    name: Optional[str] = None,
) -> ConversationMemory[MessageProtocol]:
    """Create a conversation memory instance.

    Args:
        system_prompt: System prompt for the conversation
        max_messages: Maximum number of messages to store
        token_limit: Maximum token count
        name: Memory instance name

    Returns:
        Conversation memory instance
    """
    memory_name = name or f"conversation_{int(time.time())}"
    return ConversationMemory(
        max_messages=max_messages,
        token_limit=token_limit,
        name=memory_name,
        system_prompt=system_prompt,
    )


def create_short_term_memory(
    retention_period: Optional[timedelta] = None,
    max_messages: int = 100,
    name: Optional[str] = None,
) -> ShortTermMemory[MessageProtocol]:
    """Create a short-term memory instance.

    Args:
        retention_period: How long to keep messages before expiration
        max_messages: Maximum number of messages to store
        name: Memory instance name

    Returns:
        Short-term memory instance
    """
    memory_name = name or f"short_term_{int(time.time())}"
    retention = retention_period or timedelta(hours=1)

    # Include name in metadata
    metadata = {"name": memory_name, "memory_type": "short_term"}

    return ShortTermMemory(
        max_messages=max_messages,
        name=memory_name,
        metadata=metadata,  # Pass metadata with name included
        retention_period=retention,
    )


def create_long_term_memory(
    max_messages: int = 1000,
    summary_interval: int = 50,
    name: Optional[str] = None,
) -> LongTermMemory[MessageProtocol]:
    """Create a long-term memory instance.

    Args:
        max_messages: Maximum number of messages to store
        summary_interval: How often to create summaries
        name: Memory instance name

    Returns:
        Long-term memory instance
    """
    memory_name = name or f"long_term_{int(time.time())}"

    # Include name in metadata
    metadata = {"name": memory_name, "memory_type": "long_term"}

    return LongTermMemory(
        max_messages=max_messages,
        name=memory_name,
        metadata=metadata,  # Pass metadata with name included
        summary_interval=summary_interval,
    )
