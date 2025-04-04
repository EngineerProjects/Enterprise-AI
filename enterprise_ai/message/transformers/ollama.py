"""
Ollama-specific message transformations for the Enterprise AI framework.

This module provides functionality for transforming messages between Enterprise AI's
internal format and the format expected by the Ollama API. It leverages existing
message handling utilities to ensure proper message format conversion.

Ollama API Format Requirements:
------------------------------
- Roles: Ollama supports "system", "user", "assistant", and "tool" roles
- Content: Ollama expects a text string in the "content" field
- Images: For vision models, Ollama accepts an array of base64-encoded images
- Tool Calls: Ollama supports function calling with a specific format
"""

import json
from typing import Any, Dict, List, Optional, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol, ToolCallProtocol
from enterprise_ai.schema import Role
from enterprise_ai.message.constants import (
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TEXT,
    MESSAGE_FORMAT_OLLAMA,
    MessageFormatValue,
)
from enterprise_ai.message.transformers.base import (
    BaseTransformer,
    TransformerRegistry,
)
from enterprise_ai.message.image import prepare_image_for_provider
from enterprise_ai.message.utils import message_to_dict

# Initialize logger
logger = get_logger("message.transformers.ollama")


class OllamaTransformer(BaseTransformer):
    """Transformer for Ollama API format.

    This class handles the conversion of messages from Enterprise AI's internal format
    to the format expected by Ollama's API endpoints, including support for images,
    tool calls, and various message roles.

    Ollama expects messages in the following format:
    {
        "role": "user" | "assistant" | "system" | "tool",
        "content": "message content",
        "images": ["base64-encoded-image1", "base64-encoded-image2"],  # Optional
        "tool_calls": [{                                              # Optional
            "function": {
                "name": "function_name",
                "arguments": { ... }
            }
        }],
        "name": "tool_name",                                          # For tool messages
        "tool_call_id": "id123"                                       # For tool messages
    }
    """

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format.

        Args:
            format: The format identifier to check

        Returns:
            True if this transformer supports the format, False otherwise
        """
        return format == MESSAGE_FORMAT_OLLAMA

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to Ollama API format.

        Converts the internal message representation to the format expected by
        Ollama's API, handling role mapping, content formatting, and special
        fields like images and tool calls.

        Args:
            message: The message to transform
            target_format: The target format (should be MESSAGE_FORMAT_OLLAMA)

        Returns:
            Dictionary formatted for Ollama API

        Raises:
            ValueError: If a required field is missing or invalid
        """
        # Validate the message has required fields
        if not message.role:
            raise ValueError("Message must have a role")

        # Create base message structure
        result: Dict[str, Any] = {
            "role": self._map_role_for_ollama(message.role),
            "content": message.content or "",
        }

        # Process images if present either in base64_image or content_objects
        images = self._extract_images(message)
        if images:
            result["images"] = images

        # Handle name for tool messages
        if message.role == Role.TOOL:
            if not message.name:
                raise ValueError("Tool messages must have a name")
            result["name"] = message.name

        # Handle tool_call_id for tool messages
        if message.role == Role.TOOL:
            if not message.tool_call_id:
                raise ValueError("Tool messages must have a tool_call_id")
            result["tool_call_id"] = message.tool_call_id

        # Handle tool calls for assistant messages
        if message.tool_calls:
            result["tool_calls"] = self._format_tool_calls(message.tool_calls)

        logger.debug(f"Transformed message to Ollama format: {result['role']}")
        return result

    def transform_batch(
        self, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to Ollama format.

        Args:
            messages: List of messages to transform
            target_format: The target format (should be MESSAGE_FORMAT_OLLAMA)

        Returns:
            List of dictionaries formatted for Ollama API
        """
        return [self.transform(msg, target_format) for msg in messages]

    def _map_role_for_ollama(self, role: Union[str, Role]) -> str:
        """Map internal role to Ollama role.

        Ollama supports the following roles:
        - "system": System messages that set context or instructions
        - "user": User messages/inputs
        - "assistant": Assistant/AI responses
        - "tool": Tool execution results

        Args:
            role: The internal role representation (string or Role enum)

        Returns:
            Ollama-compatible role string

        Notes:
            - "agent" role is mapped to "assistant" for Ollama compatibility
            - Unknown roles default to "user" for safety
        """
        # Convert Role enum to string if needed
        role_str = role.value if hasattr(role, "value") else str(role)

        # Ollama supports: "system", "user", "assistant", "tool"
        role_mapping = {
            "user": "user",
            "assistant": "assistant",
            "system": "system",
            "tool": "tool",
            "agent": "assistant",  # Map "agent" to "assistant" for Ollama
        }

        mapped_role = role_mapping.get(role_str.lower(), "user")
        logger.debug(f"Mapped role {role_str} to {mapped_role} for Ollama format")
        return mapped_role

    def _extract_images(self, message: MessageProtocol) -> List[str]:
        """Extract images from a message for Ollama API.

        Ollama expects images as an array of base64-encoded strings without
        metadata or MIME type prefixes.

        Args:
            message: Message containing images

        Returns:
            List of base64-encoded image strings

        Notes:
            - Handles both basic base64_image and content_objects approaches
            - Uses the prepare_image_for_provider utility for formatting
            - Logs warnings for images that fail to process but continues execution
        """
        images = []

        # Use base64_image if present
        if message.base64_image:
            images.append(message.base64_image)

        # Check for image content in content_objects if available
        if hasattr(message, "content_objects"):
            content_objects = getattr(message, "content_objects")
            for content in content_objects:
                if hasattr(content, "content_type") and content.content_type == CONTENT_TYPE_IMAGE:
                    # Use existing prepare_image_for_provider utility for proper formatting
                    try:
                        image_data = prepare_image_for_provider(content, "ollama")
                        # Ollama expects just the base64 string in the images array
                        if "data" in image_data:
                            images.append(image_data["data"])
                    except Exception as e:
                        logger.warning(f"Failed to prepare image for Ollama: {e}")
                        # Continue processing other images instead of failing completely

        return images

    def _format_tool_calls(self, tool_calls: List[ToolCallProtocol]) -> List[Dict[str, Any]]:
        """Format tool calls for Ollama API.

        Ollama expects tool calls in the following format:
        [
            {
                "function": {
                    "name": "function_name",
                    "arguments": {...}  # JSON object
                }
            }
        ]

        Args:
            tool_calls: List of tool calls to format

        Returns:
            List of formatted tool calls for Ollama API

        Notes:
            - Attempts to parse string arguments as JSON
            - Falls back to using arguments as-is if JSON parsing fails
        """
        result = []

        for tc in tool_calls:
            # Validate the tool call has required fields
            if not tc.function.name:
                logger.warning("Tool call missing function name, skipping")
                continue

            # Try to parse arguments as JSON if they're a string
            try:
                if isinstance(tc.function.arguments, str):
                    args = json.loads(tc.function.arguments)
                else:
                    args = tc.function.arguments
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, use as-is
                logger.debug("Could not parse tool call arguments as JSON, using as-is")
                args = tc.function.arguments

            tool_call = {"function": {"name": tc.function.name, "arguments": args}}

            result.append(tool_call)

        return result


# Register the Ollama transformer with the registry
TransformerRegistry.register(cast(MessageFormatValue, MESSAGE_FORMAT_OLLAMA), OllamaTransformer())
