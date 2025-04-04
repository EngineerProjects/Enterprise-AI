"""
Anthropic-specific message transformations for the Enterprise AI framework.

This module provides functionality for transforming messages between Enterprise AI's
internal format and the format expected by the Anthropic API (Claude models). It handles
the conversion of various message formats, roles, content types, and special features
like tool use/tool results and image handling.

Anthropic API Format Requirements:
---------------------------------
- Roles: Anthropic primarily supports "user" and "assistant" roles
         (system instructions are handled differently)
- Content: Anthropic uses an array-based content format for all message types
- Images: Images must be provided in a specific format with media_type and base64 data
- Tool Use: Anthropic has a unique tool_use/tool_result format different from OpenAI

"""

import json
import base64
from typing import Any, Dict, List, Optional, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol, ToolCallProtocol
from enterprise_ai.schema import Role
from enterprise_ai.message.constants import (
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_TOOL_CALL,
    CONTENT_TYPE_TOOL_RESULT,
    MESSAGE_FORMAT_ANTHROPIC,
    MessageFormatValue,
)
from enterprise_ai.message.transformers.base import (
    BaseTransformer,
    TransformerRegistry,
)
from enterprise_ai.message.image import prepare_image_for_provider
from enterprise_ai.message.utils import message_to_dict

# Initialize logger
logger = get_logger("message.transformers.anthropic")


class AnthropicTransformer(BaseTransformer):
    """Transformer for Anthropic API format.

    This class handles the conversion of messages from Enterprise AI's internal format
    to the format expected by Anthropic's API endpoints (Claude models), including
    support for images, tool use, and appropriate role mapping.

    Anthropic expects messages in the following format:
    {
        "role": "user" | "assistant",
        "content": [
            {"type": "text", "text": "message content"},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": "base64-encoded-image"
                }
            },
            {
                "type": "tool_use",
                "id": "tool_use_id",
                "name": "tool_name",
                "input": {...}  # JSON object of tool parameters
            },
            {
                "type": "tool_result",
                "tool_use_id": "tool_use_id",
                "content": "tool execution result"
            }
        ]
    }

    Note: System messages in Anthropic are typically handled via the system parameter
    rather than as a message, but this transformer will convert them to assistant
    messages with the system content.
    """

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format.

        Args:
            format: The format identifier to check

        Returns:
            True if this transformer supports the format, False otherwise
        """
        return format == MESSAGE_FORMAT_ANTHROPIC

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to Anthropic API format.

        Converts the internal message representation to the format expected by
        Anthropic's API, handling role mapping, content formatting, and special
        fields like images and tool calls.

        Args:
            message: The message to transform
            target_format: The target format (should be MESSAGE_FORMAT_ANTHROPIC)

        Returns:
            Dictionary formatted for Anthropic API

        Raises:
            ValueError: If a required field is missing or invalid
        """
        # Validate the message has required fields
        if not message.role:
            raise ValueError("Message must have a role")

        # Map role for Anthropic - note that "system" becomes "assistant" in Anthropic's format
        anthropic_role = self._map_role_for_anthropic(message.role)

        # Create base message structure
        result: Dict[str, Any] = {"role": anthropic_role}

        # Initialize content array (Anthropic requires array-based content)
        result["content"] = []

        # Add text content if present
        if message.content:
            result["content"].append({"type": "text", "text": message.content})

        # Handle images - Anthropic has a specific format for images
        if message.base64_image is not None:
            self._add_image_to_content(result["content"], message.base64_image)

        # Handle tool calls (converted to tool_use in Anthropic format)
        if message.tool_calls:
            self._add_tool_use_to_content(result["content"], message.tool_calls)

        # Handle tool results (for tool messages)
        if message.role == Role.TOOL:
            if not message.tool_call_id:
                raise ValueError("Tool messages must have a tool_call_id")
            if not message.content:
                raise ValueError("Tool messages must have content")

            result["content"].append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            )

        # Handle content objects (enhanced messages with multiple content types)
        if hasattr(message, "content_objects") and getattr(message, "content_objects"):
            self._handle_content_objects(result["content"], message)

        # If content is empty, add an empty text object to fulfill Anthropic's requirements
        if not result["content"]:
            result["content"].append({"type": "text", "text": ""})

        logger.debug(f"Transformed message to Anthropic format: {result['role']}")
        return result

    def transform_batch(
        self, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to Anthropic format.

        Args:
            messages: List of messages to transform
            target_format: The target format (should be MESSAGE_FORMAT_ANTHROPIC)

        Returns:
            List of dictionaries formatted for Anthropic API
        """
        return [self.transform(msg, target_format) for msg in messages]

    def _map_role_for_anthropic(self, role: Union[str, Role]) -> str:
        """Map internal role to Anthropic role.

        Anthropic primarily supports two roles:
        - "user": User messages/inputs
        - "assistant": Assistant/AI responses

        Args:
            role: The internal role representation (string or Role enum)

        Returns:
            Anthropic-compatible role string

        Notes:
            - "system" role is mapped to "assistant" for Anthropic compatibility
            - "tool" role is kept as "assistant" but with tool_result content
            - "agent" role is mapped to "assistant" for Anthropic compatibility
            - Unknown roles default to "user" for safety
        """
        # Convert Role enum to string if needed
        role_str = role.value if hasattr(role, "value") else str(role)

        # Anthropic role mapping
        role_mapping = {
            "user": "user",
            "assistant": "assistant",
            "system": "assistant",  # Anthropic doesn't use system role in messages
            "tool": "assistant",  # Tool results come from assistant
            "agent": "assistant",  # Map "agent" to "assistant" for Anthropic
        }

        mapped_role = role_mapping.get(role_str.lower(), "user")
        logger.debug(f"Mapped role {role_str} to {mapped_role} for Anthropic format")
        return mapped_role

    def _add_image_to_content(self, content_array: List[Dict[str, Any]], base64_image: str) -> None:
        """Add an image to an Anthropic content array.

        Anthropic expects images in the following format:
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": "base64-encoded-image"
            }
        }

        Args:
            content_array: The content array being built
            base64_image: Base64-encoded image data

        Notes:
            - Assumes PNG format if not otherwise specified
        """
        content_array.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": base64_image},
            }
        )

    def _add_tool_use_to_content(
        self, content_array: List[Dict[str, Any]], tool_calls: List[ToolCallProtocol]
    ) -> None:
        """Add tool calls as tool_use objects to Anthropic content array.

        Anthropic expects tool use in the following format:
        {
            "type": "tool_use",
            "id": "tool_use_id",
            "name": "tool_name",
            "input": {...}  # JSON object of tool parameters
        }

        Args:
            content_array: The content array being built
            tool_calls: List of tool calls to convert to tool_use format

        Notes:
            - Attempts to parse string arguments as JSON
            - Falls back to empty object if parsing fails
            - Validates tool calls have required fields
        """
        for tc in tool_calls:
            # Validate the tool call
            if not tc.id:
                logger.warning("Tool call missing ID, skipping")
                continue

            if not tc.function.name:
                logger.warning("Tool call missing function name, skipping")
                continue

            # Parse arguments to get a proper JSON object
            try:
                if isinstance(tc.function.arguments, str):
                    input_obj = json.loads(tc.function.arguments)
                else:
                    input_obj = tc.function.arguments
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, use empty object
                logger.warning("Could not parse tool call arguments as JSON, using empty object")
                input_obj = {}

            # Add the tool_use content item
            content_array.append(
                {"type": "tool_use", "id": tc.id, "name": tc.function.name, "input": input_obj}
            )

    def _handle_content_objects(
        self, content_array: List[Dict[str, Any]], message: MessageProtocol
    ) -> None:
        """Process content objects from an enhanced message.

        Handles various content types, including text, images, tool calls, and tool results,
        converting them to Anthropic's expected format.

        Args:
            content_array: The content array being built
            message: The original message with content_objects

        Notes:
            - Processes each content object based on its type
            - Converts everything to Anthropic's content array format
        """
        content_objects = getattr(message, "content_objects")

        # Process each content object
        for content in content_objects:
            content_type = content.get_content_type()

            if content_type == CONTENT_TYPE_TEXT:
                # Add text content
                content_array.append({"type": "text", "text": content.text})

            elif content_type == CONTENT_TYPE_IMAGE:
                # Add image content
                try:
                    # Get image properties
                    data = None
                    media_type = "image/png"  # Default to PNG

                    if hasattr(content, "data"):
                        if isinstance(content.data, str):
                            data = content.data  # Already base64
                        elif isinstance(content.data, bytes):
                            data = base64.b64encode(content.data).decode("utf-8")

                    if hasattr(content, "format") and content.format:
                        media_type = f"image/{content.format}"

                    # Add to content array if we have data
                    if data:
                        content_array.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": data,
                                },
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to process image for Anthropic: {e}")

            elif content_type == CONTENT_TYPE_TOOL_CALL:
                # Handle tool calls - convert to tool_use format
                if not hasattr(content, "tool_calls"):
                    logger.warning("Tool call content missing tool_calls attribute")
                    continue

                self._add_tool_use_to_content(content_array, content.tool_calls)

            elif content_type == CONTENT_TYPE_TOOL_RESULT:
                # Handle tool results
                if not hasattr(content, "tool_call_id") or not hasattr(content, "result"):
                    logger.warning("Tool result missing required attributes")
                    continue

                # Format varies based on result type
                result_content = content.result
                if isinstance(result_content, dict):
                    result_content = json.dumps(result_content)
                elif not isinstance(result_content, str):
                    result_content = str(result_content)

                content_array.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content.tool_call_id,
                        "content": result_content,
                    }
                )


# Register the Anthropic transformer with the registry
TransformerRegistry.register(
    cast(MessageFormatValue, MESSAGE_FORMAT_ANTHROPIC), AnthropicTransformer()
)
