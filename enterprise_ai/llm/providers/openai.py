"""
OpenAI provider implementation for Enterprise AI.

This module provides an LLM provider that interfaces with OpenAI's API
with full tool calling support.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set, Union, cast

from openai import AsyncOpenAI, OpenAI, OpenAIError, APIError, AuthenticationError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from enterprise_ai.config import get_config
from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    DEFAULT_TIMEOUT,
    ModelFeature,
)
from enterprise_ai.exceptions import APIError as EnterpriseAPIError, TokenLimitExceeded
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.providers.registry import register_provider
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo
from enterprise_ai.schema.tool import ToolCall, Function, TOOL_CHOICE_TYPE, ToolChoice, TOOL_CHOICE_VALUES
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.providers.openai")


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider with full tool calling support.
    
    Based on the OpenManus LLM implementation for simplicity and reliability.
    """

    def __init__(
        self,
        model_name: str = "gpt-4",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        max_input_tokens: Optional[int] = None,
        **kwargs: Any,
    ):
        """
        Initialize the OpenAI provider.

        Args:
            model_name: OpenAI model name (e.g., "gpt-4", "gpt-3.5-turbo")
            api_key: OpenAI API key
            base_url: Custom base URL for API calls
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            max_input_tokens: Maximum input tokens limit
            **kwargs: Additional parameters
        """
        super().__init__(
            model_name=model_name,
            api_key=api_key or get_config("llm.openai.api_key"),
            base_url=base_url or get_config("llm.openai.base_url"),
            temperature=temperature or get_config("llm.openai.temperature", DEFAULT_TEMPERATURE),
            max_tokens=max_tokens or get_config("llm.openai.max_tokens", DEFAULT_MAX_TOKENS),
            timeout=timeout or get_config("llm.openai.timeout", DEFAULT_TIMEOUT),
            max_input_tokens=max_input_tokens,
            **kwargs,
        )

        # Initialize OpenAI clients
        client_kwargs = {
            "api_key": self.config["api_key"],
            "timeout": self.config["timeout"],
        }
        
        if self.config.get("base_url"):
            client_kwargs["base_url"] = self.config["base_url"]

        self._sync_client = OpenAI(**client_kwargs)
        self._async_client = AsyncOpenAI(**client_kwargs)

        # Token tracking (like OpenManus)
        self.total_input_tokens = 0
        self.total_completion_tokens = 0

        logger.info(f"Initialized OpenAI provider with model: {self.model_name}")

    def update_token_count(self, input_tokens: int, completion_tokens: int = 0) -> None:
        """Update token counts."""
        self.total_input_tokens += input_tokens
        self.total_completion_tokens += completion_tokens
        logger.debug(
            f"Token usage: Input={input_tokens}, Completion={completion_tokens}, "
            f"Total Input={self.total_input_tokens}, Total Completion={self.total_completion_tokens}"
        )

    def check_token_limit(self, input_tokens: int) -> bool:
        """Check if token limits are exceeded."""
        if self.config.get("max_input_tokens"):
            return (self.total_input_tokens + input_tokens) <= self.config["max_input_tokens"]
        return True

    def get_limit_error_message(self, input_tokens: int) -> str:
        """Generate error message for token limit exceeded."""
        max_tokens = self.config.get("max_input_tokens")
        if max_tokens and (self.total_input_tokens + input_tokens) > max_tokens:
            return f"Request may exceed input token limit (Current: {self.total_input_tokens}, Needed: {input_tokens}, Max: {max_tokens})"
        return "Token limit exceeded"

    @staticmethod
    def format_messages(messages: List[Union[dict, MessageProtocol]]) -> List[dict]:
        """
        Format messages for OpenAI API.

        Args:
            messages: List of messages

        Returns:
            List of formatted messages in OpenAI format
        """
        formatted_messages = []

        for message in messages:
            # Convert Message objects to dictionaries
            if hasattr(message, 'to_dict'):
                message_dict = message.to_dict()
            elif isinstance(message, dict):
                message_dict = message
            else:
                raise TypeError(f"Unsupported message type: {type(message)}")

            # Basic message structure
            formatted_msg = {"role": message_dict["role"]}
            
            # Add content if present
            if "content" in message_dict and message_dict["content"] is not None:
                formatted_msg["content"] = message_dict["content"]

            # Add tool-specific fields
            if "tool_call_id" in message_dict and message_dict["tool_call_id"]:
                formatted_msg["tool_call_id"] = message_dict["tool_call_id"]
                
            if "name" in message_dict and message_dict["name"]:
                formatted_msg["name"] = message_dict["name"]

            # Add tool calls from metadata if present
            if "metadata" in message_dict and message_dict["metadata"]:
                metadata = message_dict["metadata"]
                if "tool_calls" in metadata:
                    formatted_msg["tool_calls"] = metadata["tool_calls"]

            formatted_messages.append(formatted_msg)

        return formatted_messages

    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion synchronously."""
        return asyncio.run(self.acomplete(messages, **kwargs))

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion using OpenAI API."""
        # Format messages for OpenAI
        formatted_messages = self.format_messages(messages)
        
        # Prepare parameters
        params = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": kwargs.get("temperature", self.config["temperature"]),
            "max_tokens": kwargs.get("max_tokens", self.config["max_tokens"]),
        }
        
        # Add tools if provided
        if "tools" in kwargs and kwargs["tools"]:
            params["tools"] = kwargs["tools"]
            params["tool_choice"] = kwargs.get("tool_choice", "auto")

        try:
            response = await self._async_client.chat.completions.create(**params)
            
            message = response.choices[0].message
            content = message.content or ""
            
            # Track tokens
            if response.usage:
                self.update_token_count(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )
            
            # Handle tool calls
            metadata = {
                "provider": "openai", 
                "model": self.model_name,
                "finish_reason": response.choices[0].finish_reason
            }
            
            if message.tool_calls:
                metadata["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            
            self.track_request(True)
            return cast(MessageProtocol, Message(
                role="assistant",
                content=content,
                metadata=metadata
            ))
            
        except OpenAIError as e:
            self.track_request(False)
            logger.error(f"OpenAI API error: {e}")
            raise EnterpriseAPIError(f"OpenAI API error: {e}")

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type((OpenAIError, Exception)),
    )
    async def ask_tool(
        self,
        messages: List[MessageProtocol],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: TOOL_CHOICE_TYPE = ToolChoice.AUTO,
        timeout: int = 300,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[ChatCompletionMessage]:
        """
        Ask OpenAI LLM using functions/tools and return the response.
        
        This method follows the OpenManus approach for simplicity.

        Args:
            messages: List of conversation messages
            tools: List of tools/functions available to the model
            tool_choice: Tool choice strategy ("none", "auto", "required")
            timeout: Request timeout in seconds
            temperature: Sampling temperature for the response
            max_tokens: Maximum tokens to generate
            **kwargs: Additional completion arguments

        Returns:
            ChatCompletionMessage from OpenAI, or None if failed

        Raises:
            TokenLimitExceeded: If token limits are exceeded
            ValueError: If tools, tool_choice, or messages are invalid
            OpenAIError: If API call fails after retries
            Exception: For unexpected errors
        """
        try:
            # Validate tool_choice
            if tool_choice not in TOOL_CHOICE_VALUES and not isinstance(tool_choice, dict):
                raise ValueError(f"Invalid tool_choice: {tool_choice}")

            # Format messages for OpenAI
            formatted_messages = self.format_messages(messages)

            # Calculate input token count (simplified estimation)
            input_tokens = sum(len(str(msg)) // 4 for msg in formatted_messages)
            if tools:
                input_tokens += sum(len(str(tool)) // 4 for tool in tools)

            # Check token limits
            if not self.check_token_limit(input_tokens):
                error_message = self.get_limit_error_message(input_tokens)
                raise TokenLimitExceeded(error_message)

            # Validate tools if provided
            if tools:
                for tool in tools:
                    if not isinstance(tool, dict) or "type" not in tool:
                        raise ValueError("Each tool must be a dict with 'type' field")

            # Set up the completion request
            params = {
                "model": self.model_name,
                "messages": formatted_messages,
                "temperature": temperature or self.config["temperature"],
                "max_tokens": max_tokens or self.config["max_tokens"],
                "timeout": timeout,
                **kwargs,
            }

            # Add tools if provided
            if tools:
                params["tools"] = tools
                params["tool_choice"] = tool_choice

            # Make API call
            response: ChatCompletion = await self._async_client.chat.completions.create(**params)

            # Check if response is valid
            if not response.choices or not response.choices[0].message:
                logger.warning("Invalid or empty response from OpenAI")
                return None

            # Update token counts
            if response.usage:
                self.update_token_count(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens
                )

            self.track_request(True)
            return response.choices[0].message

        except TokenLimitExceeded:
            # Re-raise token limit errors without logging
            raise
        except ValueError as ve:
            logger.error(f"Validation error in ask_tool: {ve}")
            raise
        except OpenAIError as oe:
            logger.error(f"OpenAI API error: {oe}")
            self.track_request(False)
            if isinstance(oe, AuthenticationError):
                logger.error("Authentication failed. Check API key.")
            elif isinstance(oe, RateLimitError):
                logger.error("Rate limit exceeded. Consider increasing retry attempts.")
            elif isinstance(oe, APIError):
                logger.error(f"API error: {oe}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask_tool: {e}")
            self.track_request(False)
            raise

    def get_model_info(self) -> ModelInfo:
        """Get model information."""
        # Set context window based on model
        context_windows = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-turbo": 128000,
            "gpt-4o": 128000,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
        }
        
        context_window = context_windows.get(self.model_name, 4096)
        
        return ModelInfo(
            name=self.model_name,
            provider="openai",
            features={ModelFeature.TOOL_CALLING, ModelFeature.STREAMING, ModelFeature.ASYNC},
            context_window=context_window,
            max_output_tokens=self.config["max_tokens"],
        )