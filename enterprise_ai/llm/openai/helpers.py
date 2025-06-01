"""
Helper functions for OpenAI provider operations.
Adapted from OpenManus patterns with Enterprise AI schema integration.
"""

import math
from typing import Any, Dict, List, Optional, Union

import tiktoken
from openai import (
    APIError,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from enterprise_ai.exceptions import APIError as EnterpriseAPIError, TokenLimitExceeded
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.llm.openai.constants import REASONING_MODELS

logger = get_logger("llm.openai.helpers")


class TokenCounter:
    """Advanced token counting for OpenAI models (adapted from OpenManus)."""
    
    # Token constants
    BASE_MESSAGE_TOKENS = 4
    FORMAT_TOKENS = 2
    LOW_DETAIL_IMAGE_TOKENS = 85
    HIGH_DETAIL_TILE_TOKENS = 170

    # Image processing constants
    MAX_SIZE = 2048
    HIGH_DETAIL_TARGET_SHORT_SIDE = 768
    TILE_SIZE = 512

    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    def count_text(self, text: str) -> int:
        """Calculate tokens for a text string."""
        return 0 if not text else len(self.tokenizer.encode(text))

    def count_image(self, image_item: dict) -> int:
        """Calculate tokens for an image based on detail level and dimensions."""
        detail = image_item.get("detail", "medium")

        if detail == "low":
            return self.LOW_DETAIL_IMAGE_TOKENS

        if detail == "high" or detail == "medium":
            if "dimensions" in image_item:
                width, height = image_item["dimensions"]
                return self._calculate_high_detail_tokens(width, height)

        return self._calculate_high_detail_tokens(1024, 1024) if detail == "high" else 1024

    def _calculate_high_detail_tokens(self, width: int, height: int) -> int:
        """Calculate tokens for high detail images based on dimensions."""
        # Step 1: Scale to fit in MAX_SIZE x MAX_SIZE square
        if width > self.MAX_SIZE or height > self.MAX_SIZE:
            scale = self.MAX_SIZE / max(width, height)
            width = int(width * scale)
            height = int(height * scale)

        # Step 2: Scale so shortest side is HIGH_DETAIL_TARGET_SHORT_SIDE
        scale = self.HIGH_DETAIL_TARGET_SHORT_SIDE / min(width, height)
        scaled_width = int(width * scale)
        scaled_height = int(height * scale)

        # Step 3: Count number of 512px tiles
        tiles_x = math.ceil(scaled_width / self.TILE_SIZE)
        tiles_y = math.ceil(scaled_height / self.TILE_SIZE)
        total_tiles = tiles_x * tiles_y

        # Step 4: Calculate final token count
        return (total_tiles * self.HIGH_DETAIL_TILE_TOKENS) + self.LOW_DETAIL_IMAGE_TOKENS

    def count_content(self, content: Union[str, List[Union[str, dict]]]) -> int:
        """Calculate tokens for message content."""
        if not content:
            return 0

        if isinstance(content, str):
            return self.count_text(content)

        token_count = 0
        for item in content:
            if isinstance(item, str):
                token_count += self.count_text(item)
            elif isinstance(item, dict):
                if "text" in item:
                    token_count += self.count_text(item["text"])
                elif "image_url" in item:
                    token_count += self.count_image(item)
        return token_count

    def count_tool_calls(self, tool_calls: List[dict]) -> int:
        """Calculate tokens for tool calls."""
        token_count = 0
        for tool_call in tool_calls:
            if "function" in tool_call:
                function = tool_call["function"]
                token_count += self.count_text(function.get("name", ""))
                token_count += self.count_text(function.get("arguments", ""))
        return token_count

    def count_message_tokens(self, messages: List[dict]) -> int:
        """Calculate the total number of tokens in a message list."""
        total_tokens = self.FORMAT_TOKENS

        for message in messages:
            tokens = self.BASE_MESSAGE_TOKENS
            tokens += self.count_text(message.get("role", ""))

            if "content" in message:
                tokens += self.count_content(message["content"])

            if "tool_calls" in message:
                tokens += self.count_tool_calls(message["tool_calls"])

            tokens += self.count_text(message.get("name", ""))
            tokens += self.count_text(message.get("tool_call_id", ""))

            total_tokens += tokens

        return total_tokens


class OpenAIMessageFormatter:
    """Message formatting for OpenAI API (adapted from OpenManus)."""
    
    @staticmethod
    def format_messages(
        messages: List[Union[MessageProtocol, Dict]], 
        supports_images: bool = False
    ) -> List[Dict]:
        """Format messages for OpenAI API."""
        formatted_messages = []

        for message in messages:
            # Convert Message objects to dictionaries
            if hasattr(message, 'to_dict'):
                message_dict = message.to_dict()
            elif isinstance(message, dict):
                message_dict = message.copy()
            else:
                raise TypeError(f"Unsupported message type: {type(message)}")

            if "role" not in message_dict:
                raise ValueError("Message must contain 'role' field")

            # Process base64 images if present and model supports images
            if supports_images and message_dict.get("base64_image"):
                # Initialize or convert content to appropriate format
                if not message_dict.get("content"):
                    message_dict["content"] = []
                elif isinstance(message_dict["content"], str):
                    message_dict["content"] = [
                        {"type": "text", "text": message_dict["content"]}
                    ]
                elif isinstance(message_dict["content"], list):
                    # Convert string items to proper text objects
                    message_dict["content"] = [
                        (
                            {"type": "text", "text": item}
                            if isinstance(item, str)
                            else item
                        )
                        for item in message_dict["content"]
                    ]

                # Add the image to content
                message_dict["content"].append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{message_dict['base64_image']}"
                        },
                    }
                )

                # Remove the base64_image field
                del message_dict["base64_image"]
            elif not supports_images and message_dict.get("base64_image"):
                # Remove base64_image if model doesn't support images
                del message_dict["base64_image"]

            # Only include messages with content or tool_calls
            if "content" in message_dict or "tool_calls" in message_dict:
                # Clean up the message dict for OpenAI format
                clean_message = {
                    "role": message_dict["role"]
                }
                
                if "content" in message_dict:
                    clean_message["content"] = message_dict["content"]
                
                if "tool_calls" in message_dict:
                    clean_message["tool_calls"] = message_dict["tool_calls"]
                
                if "name" in message_dict:
                    clean_message["name"] = message_dict["name"]
                
                if "tool_call_id" in message_dict:
                    clean_message["tool_call_id"] = message_dict["tool_call_id"]
                
                formatted_messages.append(clean_message)

        return formatted_messages


class OpenAIConfigHelper:
    """Configuration helper for OpenAI requests."""
    
    @staticmethod
    def build_completion_params(
        model: str,
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        tool_choice: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build OpenAI completion parameters."""
        params = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        # Add reasoning model specific parameters
        if model in REASONING_MODELS:
            if max_tokens:
                params["max_completion_tokens"] = max_tokens
        else:
            if max_tokens:
                params["max_tokens"] = max_tokens
            if temperature is not None:
                params["temperature"] = temperature
            if top_p is not None:
                params["top_p"] = top_p

        # Add tool parameters
        if tools:
            params["tools"] = tools
        if tool_choice:
            params["tool_choice"] = tool_choice

        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in params and value is not None:
                params[key] = value

        return params


class OpenAIErrorHandler:
    """Error handling for OpenAI operations."""
    
    @staticmethod
    def handle_error(error: Exception) -> Exception:
        """Convert OpenAI errors to Enterprise AI exceptions."""
        if isinstance(error, TokenLimitExceeded):
            return error
        elif isinstance(error, AuthenticationError):
            return EnterpriseAPIError(401, "Authentication failed. Check API key.")
        elif isinstance(error, RateLimitError):
            return EnterpriseAPIError(429, "Rate limit exceeded. Consider reducing request frequency.")
        elif isinstance(error, APIError):
            return EnterpriseAPIError(error.status_code or 500, f"OpenAI API error: {error}")
        elif isinstance(error, OpenAIError):
            return EnterpriseAPIError(message=f"OpenAI error: {error}")
        elif isinstance(error, ValueError):
            return ValueError(f"Validation error: {error}")
        else:
            return EnterpriseAPIError(message=f"Unexpected error: {error}")