"""
OpenAI provider implementation focused solely on text generation.

This implementation handles only text generation and tool call extraction,
with all tool execution delegated to the MCP module.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Set, Iterator, AsyncIterator, Union, cast

import tiktoken
from openai import (
    APIError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from enterprise_ai.defaults import (
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OPENAI_TIMEOUT,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TOP_P,
    get_config_value
)
from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    DEFAULT_TIMEOUT,
    ModelFeature,
)
from enterprise_ai.exceptions import APIError as EnterpriseAPIError, TokenLimitExceeded
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import Message, ModelInfo, LLMResponse, ProviderInfo, ToolCall
from enterprise_ai.types import MessageProtocol

from enterprise_ai.llm.openai.tools import OpenAIToolConverter
from enterprise_ai.llm.openai.helpers import (
    OpenAIMessageFormatter,
    OpenAIErrorHandler,
    OpenAIConfigHelper,
    TokenCounter,
)
from enterprise_ai.llm.openai.constants import REASONING_MODELS, MULTIMODAL_MODELS

logger = get_optimized_logger("llm.openai")


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider focused on text generation and tool call extraction."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_type: str = "openai",  # "openai", "azure", "aws"
        base_url: Optional[str] = None,
        api_version: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        max_input_tokens: Optional[int] = None,
        verbose: bool = False,
        **kwargs: Any,
    ):
        """Initialize the OpenAI provider with package-friendly configuration."""
        # Use explicit parameters with smart defaults (no config file required)
        self.model_name = model_name or DEFAULT_OPENAI_MODEL
        self.api_type = api_type
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.api_version = api_version or os.getenv("OPENAI_API_VERSION")
        self._timeout = timeout or DEFAULT_OPENAI_TIMEOUT
        self.max_input_tokens = max_input_tokens

        # Initialize base class with explicit parameters
        super().__init__(
            model_name=self.model_name,
            verbose=verbose,
            api_key=self.api_key,
            api_type=api_type,
            base_url=self.base_url,
            temperature=temperature or DEFAULT_LLM_TEMPERATURE,
            max_tokens=max_tokens or DEFAULT_LLM_MAX_TOKENS,
            top_p=top_p or DEFAULT_LLM_TOP_P,
            **kwargs,
        )

        # Initialize components
        self._tool_converter = OpenAIToolConverter()
        self._message_formatter = OpenAIMessageFormatter()
        self._error_handler = OpenAIErrorHandler()
        self._config_helper = OpenAIConfigHelper()

        # Token tracking
        self.total_input_tokens = 0
        self.total_completion_tokens = 0
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model_name)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        self.token_counter = TokenCounter(self.tokenizer)

        # Initialize OpenAI client
        self._client = self._create_client()

        logger.info(f"Initialized OpenAI provider: {self.model_name} | API: {api_type}")

    def _create_client(self):
        """Create the appropriate OpenAI client based on API type."""
        if self.api_type == "azure":
            return AsyncAzureOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                api_version=self.api_version,
            )
        elif self.api_type == "aws":
            # Note: Would need to implement BedrockClient similar to OpenManus
            raise NotImplementedError("AWS Bedrock support not yet implemented")
        else:
            return AsyncOpenAI(
                api_key=self.api_key, 
                base_url=self.base_url
            )

    # Standard completion methods
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate completion without tool execution."""
        return asyncio.run(self.acomplete(messages, **kwargs))

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate async completion without tool execution."""
        try:
            # Format messages
            supports_images = self.model_name in MULTIMODAL_MODELS
            formatted_messages = self._message_formatter.format_messages(
                messages, supports_images=supports_images
            )

            # Check token limits
            input_tokens = self.count_message_tokens(formatted_messages)
            if not self.check_token_limit(input_tokens):
                raise TokenLimitExceeded(self.get_limit_error_message(input_tokens))

            # Build request parameters
            params = self._config_helper.build_completion_params(
                model=self.model_name,
                messages=formatted_messages,
                temperature=kwargs.get("temperature", self.config.get("temperature")),
                max_tokens=kwargs.get("max_tokens", self.config.get("max_tokens")),
                top_p=kwargs.get("top_p", self.config.get("top_p")),
                stream=kwargs.get("stream", False),
                tools=kwargs.get("tools"),
                tool_choice=kwargs.get("tool_choice"),
                **kwargs
            )

            if self.verbose:
                logger.info(f"Making OpenAI API call with {len(formatted_messages)} messages")

            # Execute request
            response = await self._execute_completion_request(params)
            
            # Convert to Enterprise AI format
            return self._convert_openai_response_to_message(response, input_tokens)

        except Exception as e:
            self.track_request(False)
            raise self._error_handler.handle_error(e)

    # Token Management Methods
    def count_tokens(self, text: str) -> int:
        """Calculate the number of tokens in a text."""
        return self.token_counter.count_text(text)

    def count_message_tokens(self, messages: List[Dict]) -> int:
        """Count tokens in messages."""
        return self.token_counter.count_message_tokens(messages)

    def update_token_count(self, input_tokens: int, completion_tokens: int = 0) -> None:
        """Update token counts."""
        self.total_input_tokens += input_tokens
        self.total_completion_tokens += completion_tokens
        if self.verbose:
            logger.info(
                f"Token usage: Input={input_tokens}, Completion={completion_tokens}, "
                f"Cumulative Total={self.total_input_tokens + self.total_completion_tokens}"
            )

    def check_token_limit(self, input_tokens: int) -> bool:
        """Check if token limits are exceeded."""
        if self.max_input_tokens is not None:
            return (self.total_input_tokens + input_tokens) <= self.max_input_tokens
        return True

    def get_limit_error_message(self, input_tokens: int) -> str:
        """Generate error message for token limit exceeded."""
        if self.max_input_tokens is not None:
            return f"Token limit exceeded (Current: {self.total_input_tokens}, Needed: {input_tokens}, Max: {self.max_input_tokens})"
        return "Token limit exceeded"

    # HTTP Request Execution Methods
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_exception_type((OpenAIError, Exception))
    )
    async def _execute_completion_request(self, params: Dict[str, Any]) -> ChatCompletion:
        """Execute OpenAI completion request with retries."""
        try:
            response = await self._client.chat.completions.create(**params)
            
            if not response.choices or not response.choices[0].message:
                raise ValueError("Empty or invalid response from OpenAI")
            
            self.track_request(True)
            return response
            
        except TokenLimitExceeded:
            raise  # Don't retry token limit errors
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def _convert_openai_response_to_message(
        self, 
        response: ChatCompletion, 
        input_tokens: int
    ) -> MessageProtocol:
        """Convert OpenAI response to Enterprise AI Message format."""
        message = response.choices[0].message
        content = message.content or ""
        
        # Update token counts
        if response.usage:
            self.update_token_count(response.usage.prompt_tokens, response.usage.completion_tokens)
        else:
            # Fallback for streaming or when usage is not available
            completion_tokens = self.count_tokens(content)
            self.update_token_count(input_tokens, completion_tokens)

        # Convert tool calls if present
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_call = ToolCall(
                    id=tc.id,
                    type="function",
                    function=tc.function
                )
                tool_calls.append(tool_call)

        # Build metadata
        metadata = {
            "provider": "openai",
            "model": self.model_name,
            "finish_reason": response.choices[0].finish_reason,
            "usage_metadata": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else input_tokens,
                "completion_tokens": response.usage.completion_tokens if response.usage else self.count_tokens(content),
                "total_tokens": response.usage.total_tokens if response.usage else input_tokens + self.count_tokens(content),
            },
        }
        
        if tool_calls:
            metadata["tool_calls"] = [tc.to_dict() for tc in tool_calls]

        return cast(MessageProtocol, Message(
            role="assistant", 
            content=content, 
            metadata=metadata
        ))

    # Streaming Methods
    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Iterator[MessageProtocol]:
        """Generate a streaming completion."""
        # Run async stream in sync context
        async def async_gen():
            async for msg in self.acomplete_stream(messages, **kwargs):
                yield msg
        
        # Convert async generator to sync
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_iterator = async_gen()
            while True:
                try:
                    yield loop.run_until_complete(async_iterator.__anext__())
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncIterator[MessageProtocol]:
        """Generate an async streaming completion."""
        try:
            # Format messages
            supports_images = self.model_name in MULTIMODAL_MODELS
            formatted_messages = self._message_formatter.format_messages(
                messages, supports_images=supports_images
            )

            # Check token limits
            input_tokens = self.count_message_tokens(formatted_messages)
            if not self.check_token_limit(input_tokens):
                raise TokenLimitExceeded(self.get_limit_error_message(input_tokens))

            # Build streaming parameters
            params = self._config_helper.build_completion_params(
                model=self.model_name,
                messages=formatted_messages,
                temperature=kwargs.get("temperature", self.config.get("temperature")),
                max_tokens=kwargs.get("max_tokens", self.config.get("max_tokens")),
                stream=True,
                **kwargs
            )

            # Update estimated token count for streaming
            self.update_token_count(input_tokens)

            # Execute streaming request
            response = await self._client.chat.completions.create(**params)

            content_buffer = ""
            chunk_index = 0

            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    content_buffer += chunk_content
                    
                    # Create partial message
                    partial_message = Message(
                        role="assistant",
                        content=content_buffer,
                        metadata={
                            "provider": "openai",
                            "model": self.model_name,
                            "is_partial": True,
                            "chunk_index": chunk_index,
                        }
                    )
                    
                    yield cast(MessageProtocol, partial_message)
                    chunk_index += 1

            # Final message
            if content_buffer:
                completion_tokens = self.count_tokens(content_buffer)
                self.total_completion_tokens += completion_tokens
                
                final_message = Message(
                    role="assistant",
                    content=content_buffer,
                    metadata={
                        "provider": "openai",
                        "model": self.model_name,
                        "is_partial": False,
                        "finish_reason": "completed",
                    }
                )
                yield cast(MessageProtocol, final_message)

        except Exception as e:
            raise self._error_handler.handle_error(e)

    # Model Information Methods
    def get_model_info(self) -> ModelInfo:
        """Get model information."""
        # Determine features based on model
        features = set()
        features.add("streaming")
        features.add("async")
        
        if self.model_name in MULTIMODAL_MODELS:
            features.add("vision")
        
        if self.model_name in REASONING_MODELS:
            features.add("reasoning")
        
        if "gpt" in self.model_name or "claude" in self.model_name:
            features.add("tools")

        # Estimate context window and max tokens based on model
        context_window, max_tokens = self._get_model_limits()

        return ModelInfo(
            id=self.model_name,
            provider="openai",
            max_tokens=max_tokens,
            features=features,
            context_window=context_window,
            description=f"OpenAI model: {self.model_name}",
            metadata={
                "api_type": self.api_type,
                "supports_vision": self.model_name in MULTIMODAL_MODELS,
                "supports_reasoning": self.model_name in REASONING_MODELS,
            }
        )

    def _get_model_limits(self) -> tuple[int, int]:
        """Get context window and max output tokens for model."""
        model_limits = {
            "gpt-4o": (128000, 4096),
            "gpt-4o-mini": (128000, 16384),
            "gpt-4-turbo": (128000, 4096),
            "gpt-4": (8192, 4096),
            "gpt-3.5-turbo": (16385, 4096),
            "o1": (200000, 100000),
            "o3-mini": (200000, 65536),
        }
        
        for model_prefix, (context, max_out) in model_limits.items():
            if self.model_name.startswith(model_prefix):
                return context, max_out
        
        # Default limits
        return 4096, 2048

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information."""
        return ProviderInfo(
            name="openai",
            description=f"OpenAI GPT models via {self.api_type} API for text generation",
            base_url=self.base_url,
            supported_models=[self.model_name],
            features={ModelFeature.STREAMING, ModelFeature.FUNCTION_CALLING, ModelFeature.VISION},
            configuration={
                "api_type": self.api_type,
                "model": self.model_name,
                "verbose": self.verbose,
            },
            is_available=True,
        )

    def get_token_stats(self) -> Dict[str, int]:
        """Get token usage statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_input_tokens + self.total_completion_tokens,
        }