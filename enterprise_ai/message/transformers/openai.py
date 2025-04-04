"""
OpenAI-specific message transformations for the Enterprise AI framework.

This module provides functionality for transforming messages between Enterprise AI's
internal format and the format expected by the OpenAI API. It handles the conversion
of various message formats, roles, content types, and special features like
function/tool calling and image handling.

OpenAI API Format Requirements:
------------------------------
- Roles: OpenAI supports "system", "user", "assistant", and "function" roles
- Content: OpenAI accepts both string content and array-based content objects
- Images: For vision models, images must be in a specific content array format
- Tool Calls: OpenAI has a specific format for function/tool calling

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
    MESSAGE_FORMAT_OPENAI,
    MessageFormatValue,
)
from enterprise_ai.message.transformers.base import (
    BaseTransformer,
    TransformerRegistry,
)
from enterprise_ai.message.image import prepare_image_for_provider
from enterprise_ai.message.utils import message_to_dict

# Initialize logger
logger = get_logger("message.transformers.openai")


class OpenAITransformer(BaseTransformer):
    """Transformer for OpenAI API format.

    This class handles the conversion of messages from Enterprise AI's internal format
    to the format expected by OpenAI's API endpoints, including support for images,
    tool calls, and various message roles.

    OpenAI expects messages in the following format:
    {
        "role": "system" | "user" | "assistant" | "function",
        "content": "message content" | [
            {"type": "text", "text": "message content"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,base64-encoded-image",
                    "detail": "auto" | "low" | "high"
                }
            }
        ],
        "name": "name",                     # Optional, for function/tool messages
        "tool_calls": [{                    # Optional, for assistant messages
            "id": "call_id",
            "type": "function",
            "function": {
                "name": "function_name",
                "arguments": "{\\"key\\": \\"value\\"}"
            }
        }],
        "function_call": {                  # Legacy format, optional
            "name": "function_name",
            "arguments": "{\\"key\\": \\"value\\"}"
        }
    }
    """

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format.

        Args:
            format: The format identifier to check

        Returns:
            True if this transformer supports the format, False otherwise
        """
        return format == MESSAGE_FORMAT_OPENAI

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to OpenAI API format.

        Converts the internal message representation to the format expected by
        OpenAI's API, handling role mapping, content formatting, and special
        fields like images and tool calls.

        Args:
            message: The message to transform
            target_format: The target format (should be MESSAGE_FORMAT_OPENAI)

        Returns:
            Dictionary formatted for OpenAI API

        Raises:
            ValueError: If a required field is missing or invalid
        """
        # Validate the message has required fields
        if not message.role:
            raise ValueError("Message must have a role")

        # Map role for OpenAI - note that "tool" becomes "function" in OpenAI's format
        openai_role = self._map_role_for_openai(message.role)

        # Create base message structure
        result: Dict[str, Any] = {"role": openai_role}

        # Handle content
        if message.content is not None:
            result["content"] = message.content

        # Handle name for function messages
        if message.name is not None:
            result["name"] = message.name

        # Handle tool calls for assistant messages
        if message.tool_calls:
            # Format tool calls for OpenAI
            result["tool_calls"] = self._format_tool_calls(message.tool_calls)

        # Handle function messages (former "tool" role in our system)
        if openai_role == "function":
            # Ensure required fields are present
            if not message.name:
                raise ValueError("Function messages must have a name")
            if not message.tool_call_id:
                raise ValueError("Function messages must have a tool_call_id")

            # OpenAI doesn't use tool_call_id in the same way, but we can add it to metadata
            if "metadata" not in result:
                result["metadata"] = {}
            result["metadata"]["function_call_id"] = message.tool_call_id

        # Handle images - OpenAI uses a specific content format for images
        if message.base64_image is not None:
            self._add_image_to_message(result, message.base64_image)

        # Handle content objects (enhanced messages with multiple content types)
        if hasattr(message, "content_objects") and getattr(message, "content_objects"):
            self._handle_content_objects(result, message)

        logger.debug(f"Transformed message to OpenAI format: {result['role']}")
        return result

    def transform_batch(
        self, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to OpenAI format.

        Args:
            messages: List of messages to transform
            target_format: The target format (should be MESSAGE_FORMAT_OPENAI)

        Returns:
            List of dictionaries formatted for OpenAI API
        """
        return [self.transform(msg, target_format) for msg in messages]

    def _map_role_for_openai(self, role: Union[str, Role]) -> str:
        """Map internal role to OpenAI role.

        OpenAI supports the following roles:
        - "system": System messages that set context or instructions
        - "user": User messages/inputs
        - "assistant": Assistant/AI responses
        - "function": Function/tool execution results (maps to our "tool" role)

        Args:
            role: The internal role representation (string or Role enum)

        Returns:
            OpenAI-compatible role string

        Notes:
            - "tool" role is mapped to "function" for OpenAI compatibility
            - "agent" role is mapped to "assistant" for OpenAI compatibility
            - Unknown roles default to "user" for safety
        """
        # Convert Role enum to string if needed
        role_str = role.value if hasattr(role, "value") else str(role)

        # OpenAI role mapping
        role_mapping = {
            "user": "user",
            "assistant": "assistant",
            "system": "system",
            "tool": "function",  # OpenAI uses "function" instead of "tool"
            "agent": "assistant",  # Map "agent" to "assistant" for OpenAI
        }

        mapped_role = role_mapping.get(role_str.lower(), "user")
        logger.debug(f"Mapped role {role_str} to {mapped_role} for OpenAI format")
        return mapped_role

    def _add_image_to_message(self, result: Dict[str, Any], base64_image: str) -> None:
        """Add an image to an OpenAI message.

        For OpenAI, images must be in a specific content array format:
        "content": [
            {"type": "text", "text": "text content"},
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64,base64-encoded-image",
                    "detail": "auto"
                }
            }
        ]

        Args:
            result: The message dictionary being built
            base64_image: Base64-encoded image data

        Notes:
            - Converts string content to array format if needed
            - Adds image as an image_url object
        """
        # If there's no content field or it's empty, initialize with an empty array
        if "content" not in result or not result["content"]:
            result["content"] = []
        elif isinstance(result["content"], str):
            # Convert string content to array format
            result["content"] = [{"type": "text", "text": result["content"]}]
        elif not isinstance(result["content"], list):
            # If content exists but isn't a list, create a new list with text content
            text_content = str(result["content"])
            result["content"] = [{"type": "text", "text": text_content}]

        # Add image content
        result["content"].append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64_image}",
                    "detail": "auto",
                },
            }
        )

    def _handle_content_objects(self, result: Dict[str, Any], message: MessageProtocol) -> None:
        """Process content objects from an enhanced message.

        Handles various content types, including text, images, and tool calls, converting
        them to OpenAI's expected format.

        Args:
            result: The message dictionary being built
            message: The original message with content_objects

        Notes:
            - Processes each content object based on its type
            - Converts everything to OpenAI's array-based content format
        """
        content_objects = getattr(message, "content_objects")

        # Initialize content array if needed
        if "content" not in result:
            result["content"] = []
        elif isinstance(result["content"], str) and result["content"]:
            # Convert string content to array format
            result["content"] = [{"type": "text", "text": result["content"]}]
        elif not isinstance(result["content"], list):
            result["content"] = []

        # Process each content object
        for content in content_objects:
            content_type = content.get_content_type()

            if content_type == CONTENT_TYPE_TEXT:
                # Add text content
                result["content"].append({"type": "text", "text": content.text})

            elif content_type == CONTENT_TYPE_IMAGE:
                # Add image content
                try:
                    image_data = prepare_image_for_provider(content, "openai")
                    if image_data and "image_url" in image_data:
                        result["content"].append(
                            {"type": "image_url", "image_url": image_data["image_url"]}
                        )
                except Exception as e:
                    logger.warning(f"Failed to prepare image for OpenAI: {e}")

            elif content_type == CONTENT_TYPE_TOOL_CALL:
                # Handle tool calls - these go in the tool_calls field, not content
                if not hasattr(content, "tool_calls"):
                    logger.warning("Tool call content missing tool_calls attribute")
                    continue

                if "tool_calls" not in result:
                    result["tool_calls"] = []

                # Format tool calls for OpenAI
                for tc in content.tool_calls:
                    formatted_call = {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    result["tool_calls"].append(formatted_call)

    def _format_tool_calls(self, tool_calls: List[ToolCallProtocol]) -> List[Dict[str, Any]]:
        """Format tool calls for OpenAI API.

        OpenAI expects tool calls in the following format:
        [
            {
                "id": "call_id",
                "type": "function",
                "function": {
                    "name": "function_name",
                    "arguments": "{\\"key\\": \\"value\\"}"
                }
            }
        ]

        Args:
            tool_calls: List of tool calls to format

        Returns:
            List of formatted tool calls for OpenAI API

        Notes:
            - Ensures all tool calls have the required fields
            - Formats arguments as a JSON string if they're not already
        """
        result = []

        for tc in tool_calls:
            # Validate the tool call has required fields
            if not tc.id:
                logger.warning("Tool call missing ID, generating a new one")
                import uuid

                tc_id = str(uuid.uuid4())
            else:
                tc_id = tc.id

            if not tc.function.name:
                logger.warning("Tool call missing function name, skipping")
                continue

            # Format arguments as needed
            if isinstance(tc.function.arguments, dict):
                arguments = json.dumps(tc.function.arguments)
            else:
                arguments = tc.function.arguments

            # Create the formatted tool call
            formatted_call = {
                "id": tc_id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": arguments},
            }

            result.append(formatted_call)

        return result


# Register the OpenAI transformer with the registry
TransformerRegistry.register(cast(MessageFormatValue, MESSAGE_FORMAT_OPENAI), OpenAITransformer())
