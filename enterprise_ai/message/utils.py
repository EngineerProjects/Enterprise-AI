"""
Utility functions for message handling in Enterprise AI.

This module provides helper functions for common message operations, including
conversion between formats, content extraction, message manipulation, and
other utilities that support the message handling system.
"""

import uuid
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Type, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, Role
from enterprise_ai.types import MessageProtocol, ToolCallProtocol, RoleType
from enterprise_ai.message.constants import (
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_MARKDOWN,
    CODE_BLOCK_START,
    CODE_BLOCK_END,
    MESSAGE_FORMAT_DEFAULT,
)

# Initialize logger
logger = get_logger("message.utils")


# -----------------------------------------------------------------------------
# Message Identification and Creation
# -----------------------------------------------------------------------------


def generate_message_id() -> str:
    """Generate a unique message ID.

    Returns:
        A unique identifier string for a message
    """
    return str(uuid.uuid4())


def create_timestamp() -> datetime:
    """Create a timestamp for message creation.

    Returns:
        Current datetime
    """
    return datetime.now()


def clone_message(message: MessageProtocol) -> MessageProtocol:
    """Create a deep copy of a message with a new ID.

    Args:
        message: The message to clone

    Returns:
        A new message with the same content but a new ID
    """
    message_dict = message.to_dict()

    # Generate a new ID if the message has one
    if hasattr(message, "id"):
        message_dict["id"] = generate_message_id()

    # Update timestamp if needed
    if hasattr(message, "timestamp"):
        message_dict["timestamp"] = create_timestamp()

    # Clone metadata if present
    if message.metadata:
        message_dict["metadata"] = message.metadata.copy()

    # Create a new message from the dict
    # We'll use the Message class directly to avoid potential circular imports
    return Message(**message_dict)


# -----------------------------------------------------------------------------
# Content Extraction and Formatting
# -----------------------------------------------------------------------------


def extract_code_blocks(content: str) -> List[Tuple[str, str]]:
    """Extract code blocks from message content.

    Args:
        content: Message content string

    Returns:
        List of tuples containing (language, code)
    """
    # Pattern to match code blocks with language specification
    pattern = rf"{CODE_BLOCK_START}(\w*)\n(.*?){CODE_BLOCK_END}"
    matches = re.findall(pattern, content, re.DOTALL)

    result = []
    for language, code in matches:
        # If no language specified, use "text"
        lang = language.strip() if language.strip() else "text"
        result.append((lang, code.strip()))

    return result


def extract_text_without_code_blocks(content: str) -> str:
    """Extract text content excluding code blocks.

    Args:
        content: Message content string

    Returns:
        Content with code blocks removed
    """
    # Replace code blocks with placeholders
    pattern = rf"{CODE_BLOCK_START}.*?{CODE_BLOCK_END}"
    return re.sub(pattern, "", content, flags=re.DOTALL).strip()


def get_message_summary(message: MessageProtocol, max_length: int = 50) -> str:
    """Generate a brief summary of a message.

    Args:
        message: The message to summarize
        max_length: Maximum length of content summary

    Returns:
        A brief summary string
    """
    role = message.role

    # Handle different types of message content
    if message.content:
        # Truncate content if needed
        content = message.content
        if len(content) > max_length:
            content = content[:max_length] + "..."
        summary = f"{role}: {content}"
    elif message.tool_calls:
        tool_names = [tc.function.name for tc in message.tool_calls]
        summary = f"{role}: [Tool calls: {', '.join(tool_names)}]"
    elif message.base64_image:
        summary = f"{role}: [Image]"
    else:
        summary = f"{role}: [Empty message]"

    # Add name if present
    if message.name:
        summary = f"{summary} (name: {message.name})"

    return summary


def format_message_for_display(message: MessageProtocol, include_metadata: bool = False) -> str:
    """Format a message for human-readable display.

    Args:
        message: The message to format
        include_metadata: Whether to include metadata

    Returns:
        Formatted message string
    """
    parts = []

    # Add role with formatting
    role_str = f"[{message.role.upper()}]"
    parts.append(role_str)

    # Add name if present
    if message.name:
        parts.append(f"Name: {message.name}")

    # Add timestamp if present
    if message.timestamp:
        time_str = message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        parts.append(f"Time: {time_str}")

    # Add content
    if message.content:
        parts.append(f"\n{message.content}")

    # Add tool calls if present
    if message.tool_calls:
        tool_call_strs = []
        for tc in message.tool_calls:
            tool_str = f"Function: {tc.function.name}\nArguments: {tc.function.arguments}"
            tool_call_strs.append(tool_str)
        parts.append("\nTool Calls:\n" + "\n\n".join(tool_call_strs))

    # Add image indicator if present
    if message.base64_image:
        parts.append("\n[Image included]")

    # Add metadata if requested
    if include_metadata and message.metadata:
        metadata_str = json.dumps(message.metadata, indent=2)
        parts.append(f"\nMetadata:\n{metadata_str}")

    return " ".join(parts)


# -----------------------------------------------------------------------------
# Message Conversion and Transformation
# -----------------------------------------------------------------------------


def message_to_dict(
    message: MessageProtocol, format: str = MESSAGE_FORMAT_DEFAULT
) -> Dict[str, Any]:
    """Convert a message to dictionary format.

    This is a wrapper around the message's to_dict or transform methods,
    with fallbacks for messages that don't implement the transform method.

    Args:
        message: The message to convert
        format: Output format (default, openai, anthropic, etc.)

    Returns:
        Dictionary representation of the message
    """
    # If message has a transform method, use it
    if hasattr(message, "transform") and callable(getattr(message, "transform")):
        return cast(Dict[str, Any], message.transform(format))

    # Otherwise use standard to_dict
    return message.to_dict()


def messages_to_dict_list(
    messages: List[MessageProtocol], format: str = MESSAGE_FORMAT_DEFAULT
) -> List[Dict[str, Any]]:
    """Convert a list of messages to list of dictionaries.

    Args:
        messages: List of messages to convert
        format: Output format (default, openai, anthropic, etc.)

    Returns:
        List of dictionary representations
    """
    return [message_to_dict(m, format) for m in messages]


def dict_to_message(message_dict: Dict[str, Any]) -> MessageProtocol:
    """Convert a dictionary to a message object.

    Args:
        message_dict: Dictionary representation of a message

    Returns:
        Message object
    """
    # Import here to avoid circular imports
    try:
        from enterprise_ai.message.base import EnhancedMessage

        return EnhancedMessage.from_dict(message_dict)
    except ImportError:
        # Fall back to standard Message
        return Message(**message_dict)


# -----------------------------------------------------------------------------
# Message Content Analysis
# -----------------------------------------------------------------------------


def contains_image(message: MessageProtocol) -> bool:
    """Check if a message contains an image.

    Args:
        message: The message to check

    Returns:
        True if the message contains an image, False otherwise
    """
    # Check for base64_image attribute
    if message.base64_image:
        return True

    # Check for content_objects if available
    if hasattr(message, "content_objects"):
        content_objects = getattr(message, "content_objects")
        for content in content_objects:
            if hasattr(content, "content_type") and content.content_type == CONTENT_TYPE_IMAGE:
                return True

    return False


def contains_code(message: MessageProtocol) -> bool:
    """Check if a message contains code.

    Args:
        message: The message to check

    Returns:
        True if the message contains code, False otherwise
    """
    # Check for content_objects if available
    if hasattr(message, "content_objects"):
        content_objects = getattr(message, "content_objects")
        for content in content_objects:
            if hasattr(content, "content_type") and content.content_type == CONTENT_TYPE_CODE:
                return True

    # Otherwise check for code blocks in content
    if message.content:
        return CODE_BLOCK_START in message.content

    return False


def get_message_type(message: MessageProtocol) -> str:
    """Get the primary content type of a message.

    Args:
        message: The message to analyze

    Returns:
        String indicating the primary content type
    """
    if message.tool_calls:
        return "tool_call"
    elif message.tool_call_id:
        return "tool_result"
    elif contains_image(message):
        return "image"
    elif contains_code(message):
        return "code"
    elif message.content:
        return "text"
    else:
        return "unknown"


# -----------------------------------------------------------------------------
# Message Filtering and Searching
# -----------------------------------------------------------------------------


def filter_messages_by_role(
    messages: List[MessageProtocol], role: Union[RoleType, str]
) -> List[MessageProtocol]:
    """Filter messages by role.

    Args:
        messages: List of messages to filter
        role: Role to filter by

    Returns:
        Filtered list of messages
    """
    role_str = role if isinstance(role, str) else role.value
    return [m for m in messages if m.role == role_str]


def filter_messages_by_timestamp(
    messages: List[MessageProtocol],
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> List[MessageProtocol]:
    """Filter messages by timestamp range.

    Args:
        messages: List of messages to filter
        start_time: Start of time range (inclusive)
        end_time: End of time range (inclusive)

    Returns:
        Filtered list of messages
    """
    result = []

    for message in messages:
        if not message.timestamp:
            continue

        # Check start time if specified
        if start_time and message.timestamp < start_time:
            continue

        # Check end time if specified
        if end_time and message.timestamp > end_time:
            continue

        result.append(message)

    return result


def search_messages(
    messages: List[MessageProtocol], query: str, case_sensitive: bool = False
) -> List[MessageProtocol]:
    """Search messages for content matching a query.

    Args:
        messages: List of messages to search
        query: Search query string
        case_sensitive: Whether search should be case sensitive

    Returns:
        List of messages matching the query
    """
    result = []

    # Prepare query
    if not case_sensitive:
        query = query.lower()

    for message in messages:
        # Skip messages without content
        if not message.content:
            continue

        # Check content
        content = message.content
        if not case_sensitive:
            content = content.lower()

        if query in content:
            result.append(message)

    return result


# -----------------------------------------------------------------------------
# Message Content Transformation
# -----------------------------------------------------------------------------


def extract_structured_content(message: MessageProtocol) -> Dict[str, Any]:
    """Extract structured content from a message.

    Breaks down content into text, code, metadata, etc.

    Args:
        message: The message to process

    Returns:
        Dictionary of structured content
    """
    result: Dict[str, Any] = {
        "role": message.role,
        "text": None,
        "code_blocks": [],
        "has_image": False,
        "tool_calls": None,
        "metadata": message.metadata.copy() if message.metadata else {},
    }

    # Extract text content
    if message.content:
        result["text"] = extract_text_without_code_blocks(message.content)
        result["code_blocks"] = extract_code_blocks(message.content)

    # Check for image
    result["has_image"] = contains_image(message)

    # Add tool calls if present
    if message.tool_calls:
        result["tool_calls"] = [tc.to_dict() for tc in message.tool_calls]

    return result


def normalize_message_content(content: str) -> str:
    """Normalize message content by fixing common formatting issues.

    Args:
        content: Message content to normalize

    Returns:
        Normalized content string
    """
    if not content:
        return ""

    # Fix inconsistent line endings
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")

    # Fix code block formatting
    # Ensure code blocks have newlines before and after
    code_block_pattern = rf"({CODE_BLOCK_START}.*?{CODE_BLOCK_END})"
    normalized = re.sub(
        code_block_pattern, lambda m: f"\n{m.group(1)}\n", normalized, flags=re.DOTALL
    )

    # Remove excessive blank lines (more than 2 in a row)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    # Trim leading/trailing whitespace
    normalized = normalized.strip()

    return normalized


# -----------------------------------------------------------------------------
# Message History & Thread Management
# -----------------------------------------------------------------------------


def get_conversation_summary(messages: List[MessageProtocol], max_messages: int = 5) -> str:
    """Generate a brief summary of a conversation.

    Args:
        messages: List of messages in the conversation
        max_messages: Maximum number of messages to include in summary

    Returns:
        Summary of the conversation
    """
    if not messages:
        return "Empty conversation"

    # Get most recent messages (limited by max_messages)
    recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages

    # Generate summary lines
    summary_lines = [get_message_summary(msg) for msg in recent_messages]

    # Add message count if truncated
    if len(messages) > max_messages:
        message_count = len(messages)
        hidden_count = message_count - max_messages
        summary_lines.insert(
            0,
            f"Conversation with {message_count} messages (showing last {max_messages}, {hidden_count} earlier messages hidden)",
        )
    else:
        summary_lines.insert(0, f"Conversation with {len(messages)} messages:")

    return "\n".join(summary_lines)


def merge_consecutive_messages(messages: List[MessageProtocol]) -> List[MessageProtocol]:
    """Merge consecutive messages from the same role.

    Args:
        messages: List of messages to process

    Returns:
        List with consecutive same-role messages merged
    """
    if not messages:
        return []

    result = []
    current_message = None

    for message in messages:
        # Skip messages without content
        if not message.content:
            result.append(message)
            continue

        # If no current message or different role, start a new message
        if (
            current_message is None
            or current_message.role != message.role
            or current_message.name != message.name
        ):
            # Add current message to result if it exists
            if current_message is not None:
                result.append(current_message)

            # Start with a clone of the current message
            current_message = clone_message(message)
            continue

        # Same role, merge content
        assert current_message is not None  # For type checker
        current_message.content = f"{current_message.content}\n\n{message.content}"

        # Update timestamp to the latest
        if message.timestamp and current_message.timestamp:
            if message.timestamp > current_message.timestamp:
                current_message.timestamp = message.timestamp

    # Add the last message if it exists
    if current_message is not None:
        result.append(current_message)

    return result
