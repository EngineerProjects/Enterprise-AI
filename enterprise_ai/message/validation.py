"""
Message validation for Enterprise AI.

This module provides comprehensive validation functionality for messages and message content
in the Enterprise AI framework. It includes validators for different message types, content
validation rules, and a registry system for managing and extending validators.

Validation ensures messages adhere to format requirements, size limits, and structural
constraints before they are processed by LLM providers or stored in memory.
"""

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, Role
from enterprise_ai.types import MessageProtocol, ToolCallProtocol, RoleType
from enterprise_ai.message.constants import (
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_MARKDOWN,
    CONTENT_TYPE_TOOL_CALL,
    CONTENT_TYPE_TOOL_RESULT,
    CONTENT_TYPE_FILE,
    MAX_MESSAGE_CONTENT_LENGTH,
    MAX_MESSAGE_NAME_LENGTH,
    MAX_TOOL_CALLS_PER_MESSAGE,
    MAX_CONTENT_OBJECTS_PER_MESSAGE,
    SUPPORTED_CONTENT_TYPES,
    SUPPORTED_IMAGE_FORMATS,
    PROVIDER_IMAGE_LIMITS,
)
from enterprise_ai.message.types import (
    ContentProtocol,
    MessageValidatorProtocol,
    TextContent,
    ImageContent,
    CodeContent,
    MarkdownContent,
    ToolCallContent,
    ToolResultContent,
    FileContent,
)
from enterprise_ai.message.exceptions import (
    MessageValidationError,
    MessageContentError,
    MessageImageError,
    InvalidImageError,
    ImageFormatError,
    ImageSizeError,
)
from enterprise_ai.message.image import validate_image, detect_image_format

# Initialize logger
logger = get_logger("message.validation")


# -----------------------------------------------------------------------------
# Base Validator Classes
# -----------------------------------------------------------------------------


class BaseValidator(MessageValidatorProtocol):
    """Base implementation of the message validator protocol.

    This class provides common validation functionality and implements
    the MessageValidatorProtocol interface.
    """

    def validate(self, message: MessageProtocol) -> Tuple[bool, Optional[str]]:
        """Validate a message.

        Args:
            message: The message to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not message.role:
            return False, "Message role is required"

        # Validate based on message role
        role_validator = ROLE_VALIDATORS.get(message.role)
        if role_validator:
            is_valid, error = role_validator(message)
            if not is_valid:
                return False, error

        # Validate content
        if hasattr(message, "content_objects") and getattr(message, "content_objects"):
            content_objects = getattr(message, "content_objects")

            # Check if too many content objects
            if len(content_objects) > MAX_CONTENT_OBJECTS_PER_MESSAGE:
                return (
                    False,
                    f"Message has too many content objects (maximum {MAX_CONTENT_OBJECTS_PER_MESSAGE})",
                )

            # Validate each content object
            for content_obj in content_objects:
                valid, error = self.validate_content(content_obj)
                if not valid:
                    return False, f"Invalid content: {error}"
        elif not message.content and not message.tool_calls and not message.base64_image:
            return False, "Message must have content, tool_calls, or base64_image"

        # Validate tool calls if present
        if message.tool_calls:
            if len(message.tool_calls) > MAX_TOOL_CALLS_PER_MESSAGE:
                return (
                    False,
                    f"Too many tool calls in message (maximum {MAX_TOOL_CALLS_PER_MESSAGE})",
                )

            for tool_call in message.tool_calls:
                valid, error = self._validate_tool_call(tool_call)
                if not valid:
                    return False, f"Invalid tool call: {error}"

        # Check content length
        if message.content and len(message.content) > MAX_MESSAGE_CONTENT_LENGTH:
            return (
                False,
                f"Message content exceeds maximum length ({MAX_MESSAGE_CONTENT_LENGTH} characters)",
            )

        # Check name length
        if message.name and len(message.name) > MAX_MESSAGE_NAME_LENGTH:
            return (
                False,
                f"Message name exceeds maximum length ({MAX_MESSAGE_NAME_LENGTH} characters)",
            )

        return True, None

    def validate_content(self, content: ContentProtocol) -> Tuple[bool, Optional[str]]:
        """Validate message content.

        Args:
            content: The content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        content_type = content.get_content_type()

        # Validate based on content type
        if content_type not in SUPPORTED_CONTENT_TYPES:
            return False, f"Unsupported content type: {content_type}"

        content_validator = CONTENT_VALIDATORS.get(content_type)
        if content_validator:
            return content_validator(content)

        return True, None

    def _validate_tool_call(self, tool_call: ToolCallProtocol) -> Tuple[bool, Optional[str]]:
        """Validate a tool call.

        Args:
            tool_call: The tool call to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not tool_call.id:
            return False, "Tool call ID is required"

        if not tool_call.function.name:
            return False, "Tool call function name is required"

        # Minimal validation for arguments - just check if it's present
        # More detailed schema validation would be done by the tool itself
        if not tool_call.function.arguments:
            return False, "Tool call function arguments are required"

        return True, None


class StrictValidator(BaseValidator):
    """Strict validator with more rigorous validation rules.

    This validator enforces stricter rules than the base validator,
    including content structure, formatting, and security checks.
    """

    def validate(self, message: MessageProtocol) -> Tuple[bool, Optional[str]]:
        """Validate a message with strict rules.

        Args:
            message: The message to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # First use the base validation
        is_valid, error = super().validate(message)
        if not is_valid:
            return False, error

        # Additional strict validations

        # Check for potentially unsafe content patterns
        if message.content:
            if self._contains_unsafe_patterns(message.content):
                return False, "Message content contains potentially unsafe patterns"

        # Strict validation of image content if present
        if message.base64_image:
            try:
                # More thorough image validation could be implemented here
                # For example, checking for specific image dimensions or content analysis
                pass
            except Exception as e:
                return False, f"Image validation failed: {e}"

        return True, None

    def _contains_unsafe_patterns(self, content: str) -> bool:
        """Check if content contains potentially unsafe patterns.

        Args:
            content: The content to check

        Returns:
            True if unsafe patterns are found, False otherwise
        """
        # Example basic patterns to check - in a real implementation,
        # this would be more comprehensive
        unsafe_patterns = [
            r"<script.*?>.*?</script>",  # Basic script tag check
            r"javascript:",  # JavaScript protocol
            r"data:text/html",  # Data URL with HTML
            r"<iframe.*?>",  # iframes
        ]

        for pattern in unsafe_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                return True

        return False


# -----------------------------------------------------------------------------
# Role-Specific Validators
# -----------------------------------------------------------------------------


def validate_user_message(message: MessageProtocol) -> Tuple[bool, Optional[str]]:
    """Validate a user message."""
    # User messages must have content or an image
    if not message.content and not message.base64_image:
        return False, "User message must have content or an image"

    # User messages shouldn't have tool calls
    if message.tool_calls:
        return False, "User messages should not contain tool calls"

    # User messages shouldn't have a name
    if message.name:
        return False, "User messages should not have a name"

    # User messages shouldn't have a tool_call_id
    if message.tool_call_id:
        return False, "User messages should not have a tool_call_id"

    return True, None


def validate_system_message(message: MessageProtocol) -> Tuple[bool, Optional[str]]:
    """Validate a system message."""
    # System messages must have content
    if not message.content:
        return False, "System message must have content"

    # System messages shouldn't have tool calls
    if message.tool_calls:
        return False, "System messages should not contain tool calls"

    # System messages shouldn't have an image
    if message.base64_image:
        return False, "System messages should not contain images"

    # System messages shouldn't have a name
    if message.name:
        return False, "System messages should not have a name"

    # System messages shouldn't have a tool_call_id
    if message.tool_call_id:
        return False, "System messages should not have a tool_call_id"

    return True, None


def validate_assistant_message(message: MessageProtocol) -> Tuple[bool, Optional[str]]:
    """Validate an assistant message."""
    # Assistant messages should have content, tool calls, or an image
    if not message.content and not message.tool_calls and not message.base64_image:
        return False, "Assistant message must have content, tool calls, or an image"

    # Assistant messages shouldn't have a name
    if message.name:
        return False, "Assistant messages should not have a name"

    # Assistant messages shouldn't have a tool_call_id
    if message.tool_call_id:
        return False, "Assistant messages should not have a tool_call_id"

    return True, None


def validate_tool_message(message: MessageProtocol) -> Tuple[bool, Optional[str]]:
    """Validate a tool message."""
    # Tool messages must have content
    if not message.content:
        return False, "Tool message must have content"

    # Tool messages must have a name
    if not message.name:
        return False, "Tool message must have a name"

    # Tool messages must have a tool_call_id
    if not message.tool_call_id:
        return False, "Tool message must have a tool_call_id"

    # Tool messages shouldn't have tool calls
    if message.tool_calls:
        return False, "Tool messages should not contain tool calls"

    return True, None


def validate_agent_message(message: MessageProtocol) -> Tuple[bool, Optional[str]]:
    """Validate an agent message."""
    # Agent messages must have content
    if not message.content:
        return False, "Agent message must have content"

    # Agent messages must have a name
    if not message.name:
        return False, "Agent message must have a name"

    # Agent messages shouldn't have a tool_call_id
    if message.tool_call_id:
        return False, "Agent messages should not have a tool_call_id"

    return True, None


# -----------------------------------------------------------------------------
# Content-Specific Validators
# -----------------------------------------------------------------------------


def validate_text_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate text content."""
    text_content = cast(TextContent, content)

    # Text content must have text
    if not text_content.text:
        return False, "Text content cannot be empty"

    # Check text length
    if len(text_content.text) > MAX_MESSAGE_CONTENT_LENGTH:
        return (
            False,
            f"Text content exceeds maximum length ({MAX_MESSAGE_CONTENT_LENGTH} characters)",
        )

    return True, None


def validate_image_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate image content."""
    image_content = cast(ImageContent, content)

    # Image content must have data
    if not image_content.data:
        return False, "Image data cannot be empty"

    # Check image format
    if image_content.format not in SUPPORTED_IMAGE_FORMATS:
        return False, f"Unsupported image format: {image_content.format}"

    try:
        # Convert to bytes if it's a string
        if isinstance(image_content.data, str):
            # Validation is already done within create_image_content
            # so we don't need to re-validate here
            return True, None

        # If it's bytes, validate directly
        is_valid, error = validate_image(
            image_content.data,
            max_size_bytes=PROVIDER_IMAGE_LIMITS.get("default", 4 * 1024 * 1024),
            allowed_formats=list(SUPPORTED_IMAGE_FORMATS),
        )

        if not is_valid:
            return False, error

    except Exception as e:
        return False, f"Error validating image: {e}"

    return True, None


def validate_code_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate code content."""
    code_content = cast(CodeContent, content)

    # Code content must have code
    if not code_content.code:
        return False, "Code content cannot be empty"

    # Code content must have a language
    if not code_content.language:
        return False, "Code language must be specified"

    # Check code length
    if len(code_content.code) > MAX_MESSAGE_CONTENT_LENGTH:
        return (
            False,
            f"Code content exceeds maximum length ({MAX_MESSAGE_CONTENT_LENGTH} characters)",
        )

    return True, None


def validate_markdown_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate markdown content."""
    markdown_content = cast(MarkdownContent, content)

    # Markdown content must have content
    if not markdown_content.markdown:
        return False, "Markdown content cannot be empty"

    # Check markdown length
    if len(markdown_content.markdown) > MAX_MESSAGE_CONTENT_LENGTH:
        return (
            False,
            f"Markdown content exceeds maximum length ({MAX_MESSAGE_CONTENT_LENGTH} characters)",
        )

    return True, None


def validate_tool_call_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate tool call content."""
    tool_call_content = cast(ToolCallContent, content)

    # Tool call content must have tool calls
    if not tool_call_content.tool_calls or len(tool_call_content.tool_calls) == 0:
        return False, "Tool call content must have at least one tool call"

    # Check number of tool calls
    if len(tool_call_content.tool_calls) > MAX_TOOL_CALLS_PER_MESSAGE:
        return False, f"Too many tool calls (maximum {MAX_TOOL_CALLS_PER_MESSAGE})"

    # Validate each tool call
    for tool_call in tool_call_content.tool_calls:
        if not tool_call.id:
            return False, "Tool call ID is required"

        if not tool_call.function.name:
            return False, "Tool call function name is required"

        if not tool_call.function.arguments:
            return False, "Tool call function arguments are required"

    return True, None


def validate_tool_result_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate tool result content."""
    tool_result_content = cast(ToolResultContent, content)

    # Tool result must have a tool_call_id
    if not tool_result_content.tool_call_id:
        return False, "Tool result must have a tool_call_id"

    # Tool result should have a result (could be empty dict but should exist)
    if tool_result_content.result is None:
        return False, "Tool result must have a result object"

    return True, None


def validate_file_content(content: ContentProtocol) -> Tuple[bool, Optional[str]]:
    """Validate file content."""
    file_content = cast(FileContent, content)

    # File content must have data
    if not file_content.data:
        return False, "File data cannot be empty"

    # File content must have a filename
    if not file_content.filename:
        return False, "File must have a filename"

    # File content must have a mime_type
    if not file_content.mime_type:
        return False, "File must have a mime_type"

    # Additional validations could check file size limits, allowed mime types, etc.

    return True, None


# -----------------------------------------------------------------------------
# Validator Registry
# -----------------------------------------------------------------------------


class ValidatorRegistry:
    """Registry for message validators."""

    _validators: Dict[str, MessageValidatorProtocol] = {
        "default": BaseValidator(),
        "strict": StrictValidator(),
    }

    @classmethod
    def register_validator(cls, name: str, validator: MessageValidatorProtocol) -> None:
        """Register a validator with the given name."""
        cls._validators[name] = validator
        logger.info(f"Registered validator: {name}")

    @classmethod
    def get_validator(cls, name: str = "default") -> MessageValidatorProtocol:
        """Get a validator by name."""
        if name not in cls._validators:
            logger.warning(f"Validator '{name}' not found, using default")
            return cls._validators["default"]

        return cls._validators[name]

    @classmethod
    def validate_message(
        cls, message: MessageProtocol, validator_name: str = "default"
    ) -> Tuple[bool, Optional[str]]:
        """Validate a message using the specified validator."""
        validator = cls.get_validator(validator_name)
        return validator.validate(message)


# -----------------------------------------------------------------------------
# Validator Mapping and Registration
# -----------------------------------------------------------------------------


# Map role types to their validation functions
ROLE_VALIDATORS: Dict[str, Callable[[MessageProtocol], Tuple[bool, Optional[str]]]] = {
    cast(str, Role.USER): validate_user_message,
    cast(str, Role.SYSTEM): validate_system_message,
    cast(str, Role.ASSISTANT): validate_assistant_message,
    cast(str, Role.TOOL): validate_tool_message,
    cast(str, Role.AGENT): validate_agent_message,
}

# Map content types to their validation functions
CONTENT_VALIDATORS: Dict[str, Callable[[ContentProtocol], Tuple[bool, Optional[str]]]] = {
    CONTENT_TYPE_TEXT: validate_text_content,
    CONTENT_TYPE_IMAGE: validate_image_content,
    CONTENT_TYPE_CODE: validate_code_content,
    CONTENT_TYPE_MARKDOWN: validate_markdown_content,
    CONTENT_TYPE_TOOL_CALL: validate_tool_call_content,
    CONTENT_TYPE_TOOL_RESULT: validate_tool_result_content,
    CONTENT_TYPE_FILE: validate_file_content,
}


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------


def validate_messages(messages: List[MessageProtocol]) -> Tuple[bool, Optional[str]]:
    """Validate a list of messages."""
    validator = ValidatorRegistry.get_validator()

    for i, message in enumerate(messages):
        is_valid, error = validator.validate(message)
        if not is_valid:
            return False, f"Message at index {i} is invalid: {error}"

    return True, None


def is_valid_message(message: MessageProtocol, strict: bool = False) -> bool:
    """Check if a message is valid."""
    validator_name = "strict" if strict else "default"
    is_valid, _ = ValidatorRegistry.validate_message(message, validator_name)
    return is_valid


def get_validation_error(message: MessageProtocol, strict: bool = False) -> Optional[str]:
    """Get validation error for a message."""
    validator_name = "strict" if strict else "default"
    is_valid, error = ValidatorRegistry.validate_message(message, validator_name)
    return error if not is_valid else None
