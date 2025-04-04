"""
Base transformer functionality for message formats.

This module provides the core interfaces and base classes for message format transformers,
which convert between Enterprise AI's internal message format and provider-specific formats
for different LLM providers (OpenAI, Anthropic, Ollama, etc.).
"""

import json
from typing import Any, Dict, List, Optional, Type, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol, ToolCallProtocol
from enterprise_ai.schema import Role
from enterprise_ai.message.constants import (
    MESSAGE_FORMAT_DEFAULT,
    MESSAGE_FORMAT_OPENAI,
    MESSAGE_FORMAT_ANTHROPIC,
    MESSAGE_FORMAT_OLLAMA,
    MessageFormatValue,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_MARKDOWN,
    CONTENT_TYPE_TOOL_CALL,
    CONTENT_TYPE_TOOL_RESULT,
)

# Initialize logger
logger = get_logger("message.transformers.base")


class BaseTransformer:
    """Base class for message format transformers.

    This class defines the interface and default behavior for message transformers
    that convert between Enterprise AI's internal message format and provider-specific
    formats required by different LLM backends.
    """

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to the target format.

        Args:
            message: The message to transform
            target_format: The target format

        Returns:
            The transformed message as a dictionary
        """
        # Default implementation returns standard dictionary format
        if isinstance(message, dict):
            return message  # type: ignore
        return message.to_dict()

    def transform_batch(
        self, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to the target format.

        Args:
            messages: List of messages to transform
            target_format: The target format

        Returns:
            List of transformed messages as dictionaries
        """
        return [self.transform(m, target_format) for m in messages]

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format.

        Args:
            format: The format to check

        Returns:
            True if the format is supported, False otherwise
        """
        return format == MESSAGE_FORMAT_DEFAULT

    # Utility methods for subclasses

    def _get_base_message_dict(self, message: MessageProtocol) -> Dict[str, Any]:
        """Create a base message dictionary with common properties.

        Args:
            message: The message to transform

        Returns:
            Base message dictionary with role and common properties
        """
        result: Dict[str, Any] = {"role": message.role}

        # Add basic text content if present
        if message.content is not None:
            result["content"] = message.content

        # Add name if present (for tools/functions)
        if message.name is not None:
            result["name"] = message.name

        return result

    def _transform_content_to_array_format(
        self, message: MessageProtocol, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform message content to array format if needed.

        This is a helper for formats that use array-based content
        (e.g., OpenAI and Anthropic).

        Args:
            message: The original message
            result: Current result dictionary being built

        Returns:
            Updated result dictionary with content in array format if needed
        """
        # Skip if no content or already in array format
        if "content" not in result or is_multimodal_content(result["content"]):
            return result

        # Convert string content to array format
        if isinstance(result["content"], str):
            result["content"] = [{"type": "text", "text": result["content"]}]

        return result

    def _has_enhanced_content(self, message: MessageProtocol) -> bool:
        """Check if a message has enhanced content objects.

        Args:
            message: The message to check

        Returns:
            True if the message has content_objects attribute and it's not empty
        """
        return hasattr(message, "content_objects") and bool(getattr(message, "content_objects", []))

    def _get_image_content(self, message: MessageProtocol) -> Optional[Dict[str, Any]]:
        """Extract image content from a message if present.

        This checks both base64_image and content_objects for image content.

        Args:
            message: The message to check

        Returns:
            Dictionary with image information if found, None otherwise
        """
        # Check for base64_image
        if message.base64_image:
            return {
                "data": message.base64_image,
                "format": "png",  # Assume PNG format for base64_image
                "alt_text": None,
            }

        # Check for image content in content_objects
        if self._has_enhanced_content(message):
            content_objects = getattr(message, "content_objects")
            for content in content_objects:
                if hasattr(content, "content_type") and content.content_type == CONTENT_TYPE_IMAGE:
                    # Check if data is bytes or string
                    data = content.data
                    if isinstance(data, bytes):
                        import base64

                        data = base64.b64encode(data).decode("utf-8")

                    return {
                        "data": data,
                        "format": getattr(content, "format", "png"),
                        "alt_text": getattr(content, "alt_text", None),
                    }

        return None

    def _get_code_content(self, message: MessageProtocol) -> List[Dict[str, Any]]:
        """Extract code content from a message if present.

        Args:
            message: The message to check

        Returns:
            List of dictionaries with code information
        """
        code_blocks = []

        # Check for code content in content_objects
        if self._has_enhanced_content(message):
            content_objects = getattr(message, "content_objects")
            for content in content_objects:
                if hasattr(content, "content_type") and content.content_type == CONTENT_TYPE_CODE:
                    code_blocks.append(
                        {
                            "code": content.code,
                            "language": content.language,
                        }
                    )

        return code_blocks

    def _get_all_text_content(self, message: MessageProtocol) -> str:
        """Extract and combine all text content from a message.

        This is useful for providers that don't support mixed content types.

        Args:
            message: The message to check

        Returns:
            Combined text content
        """
        parts = []

        # Add main content if present
        if message.content:
            parts.append(message.content)

        # Add text from content_objects
        if self._has_enhanced_content(message):
            content_objects = getattr(message, "content_objects")
            for content in content_objects:
                if hasattr(content, "content_type"):
                    content_type = content.content_type

                    if content_type == CONTENT_TYPE_TEXT:
                        parts.append(content.text)
                    elif content_type == CONTENT_TYPE_CODE:
                        parts.append(f"```{content.language}\n{content.code}\n```")
                    elif content_type == CONTENT_TYPE_MARKDOWN:
                        parts.append(content.markdown)
                    elif content_type == CONTENT_TYPE_IMAGE:
                        alt_text = getattr(content, "alt_text", "Image")
                        parts.append(f"[{alt_text}]")

        return "\n\n".join(parts)

    def _handle_tool_calls(
        self, message: MessageProtocol, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle tool calls in a message.

        This is a default implementation that simply adds tool_calls to the result.
        Provider-specific transformers should override this method.

        Args:
            message: The message with tool calls
            result: Current result dictionary being built

        Returns:
            Updated result dictionary with tool call information
        """
        if message.tool_calls:
            result["tool_calls"] = [tc.to_dict() for tc in message.tool_calls]

        return result


class TransformerRegistry:
    """Registry for message format transformers.

    This class manages the registration and retrieval of message transformers
    for different target formats.
    """

    _transformers: Dict[MessageFormatValue, BaseTransformer] = {}
    _default_transformer: BaseTransformer = BaseTransformer()

    @classmethod
    def register(cls, format: MessageFormatValue, transformer: BaseTransformer) -> None:
        """Register a transformer for a specific format.

        Args:
            format: The format the transformer handles
            transformer: The transformer instance
        """
        cls._transformers[format] = transformer
        logger.debug(f"Registered transformer for format: {format}")

    @classmethod
    def get(cls, format: MessageFormatValue) -> BaseTransformer:
        """Get a transformer for a specific format.

        Args:
            format: The desired format

        Returns:
            The appropriate transformer for the format, or the default transformer
            if none is registered for the specified format
        """
        transformer = cls._transformers.get(format)
        if transformer is None:
            logger.warning(f"No transformer found for format {format}, using default")
            return cls._default_transformer
        return transformer

    @classmethod
    def transform(
        cls, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to the target format.

        This is a convenience method that retrieves the appropriate transformer
        and performs the transformation.

        Args:
            message: The message to transform
            target_format: The target format

        Returns:
            The transformed message as a dictionary
        """
        transformer = cls.get(target_format)
        return transformer.transform(message, target_format)

    @classmethod
    def transform_batch(
        cls, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to the target format.

        Args:
            messages: List of messages to transform
            target_format: The target format

        Returns:
            List of transformed messages as dictionaries
        """
        transformer = cls.get(target_format)
        return transformer.transform_batch(messages, target_format)


# Utility functions


def transform_content_to_text_array(content: Optional[str]) -> List[Dict[str, Any]]:
    """Transform message content to array format with text entries.

    This utility helps with formats that represent content as arrays of
    different content types (like OpenAI and Anthropic).

    Args:
        content: Text content (if any)

    Returns:
        List of content entries in array format
    """
    result = []

    # Add text content if present
    if content:
        result.append({"type": "text", "text": content})

    return result


def is_multimodal_content(content: Any) -> bool:
    """Check if content is in multimodal array format.

    Args:
        content: Content to check

    Returns:
        True if content is a list of content objects, False otherwise
    """
    if not isinstance(content, list):
        return False

    # Check if all items have a 'type' field
    return all(isinstance(item, dict) and "type" in item for item in content)


def map_role_name(role: Union[str, Role], provider: str) -> str:
    """Map internal role names to provider-specific role names.

    Args:
        role: Internal role name (string or enum)
        provider: Provider name ('openai', 'anthropic', 'ollama')

    Returns:
        Provider-specific role name
    """
    # Convert Role enum to string if needed
    role_str: str
    if hasattr(role, "value"):
        # Cast to string to ensure type safety
        role_str = cast(str, getattr(role, "value"))
    else:
        role_str = str(role)

    if provider == "openai":
        # OpenAI mapping
        if role_str == cast(str, Role.TOOL.value):
            return "function"
        return role_str
    elif provider == "anthropic":
        # Anthropic mapping
        if role_str == cast(str, Role.SYSTEM.value):
            return "assistant"
        return role_str

    # Default: return the original role
    return role_str


# Register the default transformer
TransformerRegistry.register(cast(MessageFormatValue, MESSAGE_FORMAT_DEFAULT), BaseTransformer())
