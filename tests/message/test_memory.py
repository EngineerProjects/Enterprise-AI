"""
Tests for the memory management system in Enterprise AI.

This file contains tests for the EnhancedMemory class and its specialized
subclasses: ConversationMemory, ShortTermMemory, and LongTermMemory. It covers
functionality related to message storage, retrieval, context management,
filtering, pruning, and persistence.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add project root to Python path (must come before enterprise_ai imports)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from enterprise_ai.message.memory import (  # noqa: E402
    ConversationMemory,
    EnhancedMemory,
    LongTermMemory,
    ShortTermMemory,
    create_conversation_memory,
    create_long_term_memory,
    create_short_term_memory,
)
from enterprise_ai.schema import Message, Role  # noqa: E402
from enterprise_ai.types import MessageProtocol  # noqa: E402


# ---- Fixtures ----


@pytest.fixture
def user_message() -> Message:
    """Create a simple user message."""
    return Message(
        role=Role.USER, content="Hello, this is a user message", timestamp=datetime.now()
    )


@pytest.fixture
def assistant_message() -> Message:
    """Create a simple assistant message."""
    return Message(
        role=Role.ASSISTANT, content="Hello! How can I help you today?", timestamp=datetime.now()
    )


@pytest.fixture
def system_message() -> Message:
    """Create a simple system message."""
    return Message(
        role=Role.SYSTEM, content="You are a helpful assistant.", timestamp=datetime.now()
    )


@pytest.fixture
def message_list(user_message, assistant_message, system_message) -> List[Message]:
    """Create a list of messages for testing."""
    return [system_message, user_message, assistant_message]


@pytest.fixture
def enhanced_memory(message_list) -> EnhancedMemory:
    """Create an EnhancedMemory instance with test messages."""
    memory = EnhancedMemory(
        messages=message_list,
        max_messages=10,
        metadata={"name": "test_memory", "token_limit": 1000},
    )
    return memory


@pytest.fixture
def conversation_memory(system_message) -> ConversationMemory:
    """Create a ConversationMemory instance."""
    memory = ConversationMemory(
        messages=[system_message],
        max_messages=10,
        metadata={"name": "test_conversation", "token_limit": 1000},
    )
    return memory


@pytest.fixture
def short_term_memory() -> ShortTermMemory:
    """Create a ShortTermMemory instance."""
    memory = ShortTermMemory(
        max_messages=10,
        metadata={"name": "test_short_term"},
    )
    # Set retention period via instantiation
    memory.retention_period = timedelta(hours=1)
    return memory


@pytest.fixture
def long_term_memory() -> LongTermMemory:
    """Create a LongTermMemory instance."""
    memory = LongTermMemory(
        max_messages=100,
        metadata={"name": "test_long_term"},
    )
    # Set summary interval via instantiation
    memory.summary_interval = 5
    return memory


@pytest.fixture
def temp_file_path(tmp_path) -> Path:
    """Create a temporary file path for testing file operations."""
    return tmp_path / "test_memory.json"


# ---- Test EnhancedMemory ----


class TestEnhancedMemory:
    """Test the EnhancedMemory base class functionality."""

    def test_initialization(self, message_list):
        """Test that memory initializes correctly."""
        memory = EnhancedMemory(messages=message_list, max_messages=10, metadata={"name": "test"})

        assert len(memory.messages) == 3
        assert memory.metadata["name"] == "test"
        assert memory.max_messages == 10
        assert hasattr(memory, "created_at")
        assert hasattr(memory, "last_accessed")

    def test_add_message(self, enhanced_memory, user_message):
        """Test adding a single message."""
        new_message = Message(role=Role.USER, content="New message")
        initial_count = len(enhanced_memory.messages)

        enhanced_memory.add_message(new_message)

        assert len(enhanced_memory.messages) == initial_count + 1
        assert enhanced_memory.messages[-1].content == "New message"
        assert "message_count" in enhanced_memory.metadata
        assert enhanced_memory.metadata["message_count"] == initial_count + 1

    def test_add_messages(self, enhanced_memory):
        """Test adding multiple messages."""
        new_messages = [
            Message(role=Role.USER, content="First new message"),
            Message(role=Role.ASSISTANT, content="Second new message"),
        ]
        initial_count = len(enhanced_memory.messages)

        enhanced_memory.add_messages(new_messages)

        assert len(enhanced_memory.messages) == initial_count + 2
        assert enhanced_memory.messages[-2].content == "First new message"
        assert enhanced_memory.messages[-1].content == "Second new message"

    def test_message_limit(self):
        """Test that max_messages limit is enforced."""
        memory = EnhancedMemory(max_messages=3)

        # Add 5 messages to exceed the limit
        for i in range(5):
            memory.add_message(Message(role=Role.USER, content=f"Message {i}"))

        # Should only keep the 3 most recent
        assert len(memory.messages) == 3
        assert memory.messages[0].content == "Message 2"
        assert memory.messages[1].content == "Message 3"
        assert memory.messages[2].content == "Message 4"

    def test_get_message(self, enhanced_memory, message_list):
        """Test retrieving messages by index."""
        assert enhanced_memory.get_message(0).content == message_list[0].content
        assert enhanced_memory.get_message(-1).content == message_list[-1].content
        assert enhanced_memory.get_message(999) is None  # Out of range

    def test_get_last_message(self, enhanced_memory, assistant_message):
        """Test retrieving the last message."""
        last_message = enhanced_memory.get_last_message()
        assert last_message is not None
        assert last_message.content == assistant_message.content

    def test_get_messages_by_role(self, enhanced_memory):
        """Test filtering messages by role."""
        user_messages = enhanced_memory.get_messages_by_role(Role.USER)
        assistant_messages = enhanced_memory.get_messages_by_role(Role.ASSISTANT)
        system_messages = enhanced_memory.get_messages_by_role(Role.SYSTEM)

        assert len(user_messages) == 1
        assert len(assistant_messages) == 1
        assert len(system_messages) == 1

        assert user_messages[0].role == Role.USER
        assert assistant_messages[0].role == Role.ASSISTANT
        assert system_messages[0].role == Role.SYSTEM

    def test_search(self, enhanced_memory):
        """Test searching messages by content."""
        # Should find the user message
        results = enhanced_memory.search("user message")
        assert len(results) == 1
        assert results[0].role == Role.USER

        # Case-insensitive search
        results = enhanced_memory.search("USER MESSAGE", case_sensitive=False)
        assert len(results) == 1

        # Case-sensitive search (should find nothing)
        results = enhanced_memory.search("USER MESSAGE", case_sensitive=True)
        assert len(results) == 0

        # Search term not found
        results = enhanced_memory.search("nonexistent")
        assert len(results) == 0

    def test_clear(self, enhanced_memory):
        """Test clearing messages."""
        # Clear but keep system messages
        enhanced_memory.clear(keep_system=True)
        assert len(enhanced_memory.messages) == 1
        assert enhanced_memory.messages[0].role == Role.SYSTEM

        # Add a message and clear everything
        enhanced_memory.add_message(Message(role=Role.USER, content="New message"))
        enhanced_memory.clear(keep_system=False)
        assert len(enhanced_memory.messages) == 0

    def test_prune(self, enhanced_memory):
        """Test pruning messages to a limit."""
        # Add more messages
        for i in range(5):
            enhanced_memory.add_message(Message(role=Role.USER, content=f"Extra message {i}"))

        # Prune to 4 messages
        removed = enhanced_memory.prune(max_messages=4)

        assert len(enhanced_memory.messages) == 4
        assert len(removed) == 4  # Removed the original 3 plus the first extra message
        assert removed[0].content == "You are a helpful assistant."  # First system message
        assert enhanced_memory.messages[0].content == "Extra message 1"

    def test_prune_by_token_count(self, enhanced_memory):
        """Test pruning messages based on token count."""

        # Mock token counter that counts each message as 10 tokens
        def token_counter(messages):
            return len(messages) * 10

        # Set token limit via metadata
        enhanced_memory.token_limit = 25  # should keep at most 2 messages

        # Add more messages
        for i in range(5):
            enhanced_memory.add_message(Message(role=Role.USER, content=f"Extra message {i}"))

        # Prune by token count
        removed = enhanced_memory.prune_by_token_count(token_counter=token_counter)

        # Should have removed all but 2-3 messages
        assert len(enhanced_memory.messages) <= 3
        assert len(removed) > 0

    def test_merge_consecutive(self):
        """Test merging consecutive messages from the same role."""
        memory = EnhancedMemory()

        # Add consecutive messages from the same role
        memory.add_message(Message(role=Role.USER, content="First user message"))
        memory.add_message(Message(role=Role.USER, content="Second user message"))
        memory.add_message(Message(role=Role.ASSISTANT, content="Assistant message"))
        memory.add_message(Message(role=Role.ASSISTANT, content="Another assistant message"))

        # Merge consecutive messages
        memory.merge_consecutive()

        # Should now have 2 messages instead of 4
        assert len(memory.messages) == 2
        assert "First user message\n\nSecond user message" in memory.messages[0].content
        assert "Assistant message\n\nAnother assistant message" in memory.messages[1].content

    @patch("json.dump")
    def test_save_to_file(self, mock_json_dump, enhanced_memory, temp_file_path):
        """Test saving memory to file."""
        # Use mock_open to avoid actually writing to disk
        with patch("builtins.open", mock_open()) as mock_file:
            enhanced_memory.save_to_file(temp_file_path)

            # Check that open was called with the right path and mode
            mock_file.assert_called_once_with(temp_file_path, "w", encoding="utf-8")

            # Check that json.dump was called with the memory data
            mock_json_dump.assert_called_once()
            # First arg should be the serialized data
            serialized_data = mock_json_dump.call_args[0][0]
            assert "messages" in serialized_data
            assert "metadata" in serialized_data
            assert len(serialized_data["messages"]) == len(enhanced_memory.messages)

    @patch("json.load")
    def test_load_from_file(self, mock_json_load, enhanced_memory, temp_file_path):
        """Test loading memory from file."""
        # Prepare mock data for json.load to return
        mock_data = {
            "name": "test_loaded",
            "max_messages": 20,
            "token_limit": 2000,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "metadata": {"test_key": "test_value"},
            "messages": [{"role": "user", "content": "Test message"}],
        }
        mock_json_load.return_value = mock_data

        # Create a real Message object instead of a mock
        real_message = Message(role=Role.USER, content="Test message")

        # Mock the file existence check
        with patch("pathlib.Path.exists", return_value=True):
            # Mock opening the file
            with patch("builtins.open", mock_open()):
                # Mock EnhancedMessage.from_dict to return a real Message
                with patch(
                    "enterprise_ai.message.memory.EnhancedMessage.from_dict",
                    return_value=real_message,
                ):
                    # Call load_from_file
                    loaded_memory = EnhancedMemory.load_from_file(temp_file_path)

                    # Verify the result
                    assert loaded_memory is not None
                    assert loaded_memory.metadata.get("test_key") == "test_value"


# ---- Test ConversationMemory ----


class TestConversationMemory:
    """Test the ConversationMemory specialized class."""

    def test_initialization_with_system_prompt(self):
        """Test initialization with a system prompt."""
        memory = ConversationMemory(system_prompt="You are a helpful assistant.")

        system_messages = memory.get_messages_by_role(Role.SYSTEM)
        assert len(system_messages) == 1
        assert system_messages[0].content == "You are a helpful assistant."

    def test_conversation_tracking(self, conversation_memory):
        """Test conversation state tracking."""
        # Initially no user or assistant messages
        assert conversation_memory.last_user_message is None
        assert conversation_memory.last_assistant_message is None
        assert conversation_memory.turn_count == 0

        # Add user message
        user_msg = Message(role=Role.USER, content="Hello")
        conversation_memory.add_message(user_msg)
        assert conversation_memory.last_user_message is not None
        assert conversation_memory.last_user_message.content == "Hello"
        assert conversation_memory.turn_count == 1

        # Add assistant message
        assistant_msg = Message(role=Role.ASSISTANT, content="Hi there!")
        conversation_memory.add_message(assistant_msg)
        assert conversation_memory.last_assistant_message is not None
        assert conversation_memory.last_assistant_message.content == "Hi there!"
        assert conversation_memory.turn_count == 1  # Still 1 turn

    def test_helper_methods(self, conversation_memory):
        """Test the helper methods for adding messages."""
        # Add user message
        user_msg = conversation_memory.add_user_message("User helper method")
        assert user_msg.role == Role.USER
        assert user_msg.content == "User helper method"
        assert conversation_memory.turn_count == 1

        # Add assistant message
        assistant_msg = conversation_memory.add_assistant_message("Assistant helper method")
        assert assistant_msg.role == Role.ASSISTANT
        assert assistant_msg.content == "Assistant helper method"

        # Add system message
        system_msg = conversation_memory.add_system_message("New system message")
        assert system_msg.role == Role.SYSTEM
        assert system_msg.content == "New system message"
        # System message should be at the beginning
        assert conversation_memory.messages[0].content == "New system message"

    def test_get_recent_conversation(self, conversation_memory):
        """Test getting recent conversation turns."""
        # Add several turns
        for i in range(5):
            conversation_memory.add_user_message(f"User message {i}")
            conversation_memory.add_assistant_message(f"Assistant message {i}")

        # Get 2 recent turns (should be 4 messages + system message)
        recent = conversation_memory.get_recent_conversation(turns=2)

        # Should have system message + 4 recent messages
        assert len(recent) == 5
        assert recent[0].role == Role.SYSTEM  # System message first
        assert recent[-4].content == "User message 3"  # Then recent messages
        assert recent[-3].content == "Assistant message 3"
        assert recent[-2].content == "User message 4"
        assert recent[-1].content == "Assistant message 4"

    def test_get_conversation_context(self, conversation_memory):
        """Test getting context optimized for LLM requests."""
        # Set token limit for this test
        conversation_memory.token_limit = 200

        # Add several messages
        for i in range(10):
            conversation_memory.add_user_message(
                f"User message {i}, with some extra text to increase token count."
            )
            conversation_memory.add_assistant_message(
                f"Assistant message {i}, with response text that's fairly lengthy."
            )

        # Get context with a token limit
        context = conversation_memory.get_conversation_context()

        # Should have system message + some recent messages
        assert len(context) > 1
        assert context[0].role == Role.SYSTEM  # System message first

        # Context should be in chronological order
        for i in range(1, len(context) - 1):
            msg1_time = context[i].timestamp or datetime.min
            msg2_time = context[i + 1].timestamp or datetime.min
            assert msg1_time <= msg2_time

    def test_factory_function(self):
        """Test the factory function for creating conversation memory."""
        memory = create_conversation_memory(
            system_prompt="Factory system prompt",
            max_messages=20,
            token_limit=2000,
            name="factory_test",
        )

        assert isinstance(memory, ConversationMemory)
        assert memory.metadata.get("conversation_id") == "factory_test"
        assert memory.max_messages == 20
        assert memory.token_limit == 2000
        assert len(memory.get_messages_by_role(Role.SYSTEM)) == 1
        assert memory.get_messages_by_role(Role.SYSTEM)[0].content == "Factory system prompt"


# ---- Test ShortTermMemory ----


class TestShortTermMemory:
    """Test the ShortTermMemory specialized class."""

    def test_retention_period(self, short_term_memory):
        """Test that retention period is applied correctly."""
        # Default retention is 1 hour
        assert short_term_memory.retention_period == timedelta(hours=1)

        # Add messages with different timestamps
        now = datetime.now()

        # Message from 30 minutes ago (within retention)
        recent_msg = Message(
            role=Role.USER, content="Recent message", timestamp=now - timedelta(minutes=30)
        )
        short_term_memory.add_message(recent_msg)

        # Message from 2 hours ago (outside retention)
        old_msg = Message(role=Role.USER, content="Old message", timestamp=now - timedelta(hours=2))
        short_term_memory.add_message(old_msg)

        # Should have both messages before cleanup
        assert len(short_term_memory.messages) == 2

        # Get active (non-expired) messages
        active = short_term_memory.get_active_messages()
        assert len(active) == 1
        assert active[0].content == "Recent message"

        # Clean up expired messages
        expired = short_term_memory.cleanup_expired()
        assert len(expired) == 1
        assert expired[0].content == "Old message"

        # After cleanup, only recent message remains
        assert len(short_term_memory.messages) == 1
        assert short_term_memory.messages[0].content == "Recent message"

    def test_factory_function(self):
        """Test the factory function for creating short-term memory."""
        memory = create_short_term_memory(
            retention_period=timedelta(minutes=30), max_messages=15, name="short_term_test"
        )

        assert isinstance(memory, ShortTermMemory)
        assert memory.metadata.get("name") == "short_term_test"
        assert memory.max_messages == 15
        assert memory.retention_period == timedelta(minutes=30)


# ---- Test LongTermMemory ----


class TestLongTermMemory:
    """Test the LongTermMemory specialized class."""

    def test_automatic_summarization(self, long_term_memory):
        """Test automatic summary creation."""
        # Configure for summarization after 5 messages
        assert long_term_memory.summary_interval == 5

        # Add enough messages to trigger summarization
        for i in range(5):
            long_term_memory.add_message(Message(role=Role.USER, content=f"Message {i}"))

        # Should have created a summary
        summaries = long_term_memory.get_summaries()
        assert len(summaries) == 1
        assert "Summary of 5 messages" in summaries[0]["text"]
        assert summaries[0]["type"] == "automatic"

    def test_manual_summary(self, long_term_memory):
        """Test manually adding summaries."""
        # Add a manual summary
        long_term_memory.add_summary("This is a manual summary.", metadata={"importance": "high"})

        # Check summary was added correctly
        summaries = long_term_memory.get_summaries()
        assert len(summaries) == 1
        assert summaries[0]["text"] == "This is a manual summary."
        assert summaries[0]["type"] == "manual"
        assert summaries[0]["metadata"]["importance"] == "high"

    def test_get_summaries_with_limit(self, long_term_memory):
        """Test retrieving a limited number of summaries."""
        # Add multiple summaries
        for i in range(5):
            long_term_memory.add_summary(f"Summary {i}")

        # Get all summaries
        all_summaries = long_term_memory.get_summaries()
        assert len(all_summaries) == 5

        # Get limited number of summaries
        recent_summaries = long_term_memory.get_summaries(count=2)
        assert len(recent_summaries) == 2
        assert recent_summaries[0]["text"] == "Summary 3"
        assert recent_summaries[1]["text"] == "Summary 4"

    def test_factory_function(self):
        """Test the factory function for creating long-term memory."""
        memory = create_long_term_memory(
            max_messages=200, summary_interval=10, name="long_term_test"
        )

        assert isinstance(memory, LongTermMemory)
        assert memory.metadata.get("name") == "long_term_test"
        assert memory.max_messages == 200
        assert memory.summary_interval == 10
