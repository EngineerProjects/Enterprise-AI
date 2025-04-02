"""
Tests for message validation functionality in Enterprise AI.

This file tests the validation rules for different message types and content formats,
focusing on the core validation logic while avoiding complex dependencies.
"""

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import constants and types first
from enterprise_ai.schema import Message, Role  # noqa: E402
from enterprise_ai.message.constants import (  # noqa: E402
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_CODE,
    MAX_MESSAGE_CONTENT_LENGTH,
    MAX_MESSAGE_NAME_LENGTH,
)

# Import validation module
from enterprise_ai.message.validation import (  # noqa: E402
    BaseValidator,
    validate_user_message,
    validate_system_message,
    validate_assistant_message,
    validate_text_content,
    validate_code_content,
    is_valid_message,
    get_validation_error,
)


@pytest.fixture
def valid_user_message():
    """Create a valid user message for testing."""
    return Message(role=Role.USER, content="Hello, this is a test message.")


@pytest.fixture
def valid_system_message():
    """Create a valid system message for testing."""
    return Message(role=Role.SYSTEM, content="You are a helpful assistant.")


@pytest.fixture
def valid_assistant_message():
    """Create a valid assistant message for testing."""
    return Message(role=Role.ASSISTANT, content="I'm here to help you with your questions.")


@pytest.fixture
def base_validator():
    """Create a BaseValidator instance."""
    return BaseValidator()


def test_valid_user_message(valid_user_message):
    """Test validation of a valid user message."""
    is_valid, error = validate_user_message(valid_user_message)
    assert is_valid is True
    assert error is None


def test_invalid_user_message():
    """Test validation of an invalid user message."""
    # User message without content or image
    invalid_message = Message(role=Role.USER, content=None)
    is_valid, error = validate_user_message(invalid_message)
    assert is_valid is False
    assert "must have content or an image" in error


def test_is_valid_message_function(valid_user_message):
    """Test is_valid_message utility function."""
    assert is_valid_message(valid_user_message) is True

    # Test invalid message
    invalid_message = Message(role=Role.USER, content=None)
    assert is_valid_message(invalid_message) is False


def test_validator_registry():
    """Test validator registry functionality."""
    from enterprise_ai.message.validation import ValidatorRegistry, StrictValidator

    # Get default validator
    validator = ValidatorRegistry.get_validator()
    assert isinstance(validator, BaseValidator)

    # Test getting strict validator
    strict_validator = ValidatorRegistry.get_validator("strict")
    assert isinstance(strict_validator, StrictValidator)

    # Test getting non-existent validator falls back to default
    fallback_validator = ValidatorRegistry.get_validator("non_existent")
    assert isinstance(fallback_validator, BaseValidator)
