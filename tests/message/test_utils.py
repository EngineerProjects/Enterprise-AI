"""
Tests for message utility functions in Enterprise AI.
"""

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch
import pytest
from datetime import datetime

from enterprise_ai.types import MessageProtocol

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import required modules
from enterprise_ai.schema import Message, Role  # noqa: E402
from enterprise_ai.message.utils import (  # noqa: E402
    extract_code_blocks,
    extract_text_without_code_blocks,
    message_to_dict,
    contains_code,
    get_message_type,
    filter_messages_by_role,
    search_messages,
)


# Test fixtures
@pytest.fixture
def sample_message():
    return Message(role=Role.USER, content="This is a test message", timestamp=datetime.now())


@pytest.fixture
def code_message():
    return Message(
        role=Role.USER,
        content="Here is some code:\n```python\nprint('hello world')\n```\nEnd of code.",
        timestamp=datetime.now(),
    )


# Test core conversion functions
def test_message_to_dict(sample_message):
    result = message_to_dict(sample_message)
    assert isinstance(result, dict)
    assert result["role"] == "user"
    assert result["content"] == "This is a test message"


def dict_to_message(message_dict: Dict[str, Any]) -> MessageProtocol:
    """Convert a dictionary to a message object."""
    # Try to use EnhancedMessage if available
    try:
        from enterprise_ai.message.base import EnhancedMessage

        # Try to create object and verify it works as expected
        try:
            return EnhancedMessage.from_dict(message_dict)
        except Exception:
            # If enhanced message creation fails, fall back
            pass
    except ImportError:
        pass

    # Fall back to standard Message
    return Message(**message_dict)


# Test content extraction
def test_extract_code_blocks(code_message):
    blocks = extract_code_blocks(code_message.content)
    assert len(blocks) == 1
    assert blocks[0][0] == "python"
    assert blocks[0][1] == "print('hello world')"


def test_extract_text_without_code(code_message):
    text = extract_text_without_code_blocks(code_message.content)
    assert "Here is some code:" in text
    assert "End of code." in text
    assert "print('hello world')" not in text


# Test content analysis
def test_contains_code(code_message, sample_message):
    assert contains_code(code_message) is True
    assert contains_code(sample_message) is False


def test_get_message_type(sample_message, code_message):
    assert get_message_type(sample_message) == "text"
    assert get_message_type(code_message) == "code"
