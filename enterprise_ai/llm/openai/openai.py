"""
OpenAI provider implementation with enhanced tool execution control.

This implementation uses the OpenAI Python SDK and follows patterns from OpenManus
while integrating with Enterprise AI schema classes and enhanced execution control.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Set, Iterator, AsyncIterator, Union, cast, Callable

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
from enterprise_ai.llm.tool_executor import ToolExecutor
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo, LLMResponse, ProviderInfo, ToolCall, ToolResult
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.base import ExecutionMode

from enterprise_ai.llm.openai.tools import OpenAIToolConverter
from enterprise_ai.llm.openai.helpers import (
    OpenAIMessageFormatter,
    OpenAIErrorHandler,
    OpenAIConfigHelper,
    TokenCounter,
)
from enterprise_ai.llm.openai.constants import REASONING_MODELS, MULTIMODAL_MODELS

logger = get_logger("llm.openai")


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider with enhanced tool execution control."""

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
        # Enhanced execution parameters (inherited from base)
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        approval_callback: Optional[Callable] = None,
        verbose: bool = False,
        max_tool_iterations: int = 5,
        tool_execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None,
        hybrid_danger_threshold: int = 2,
        **kwargs: Any,
    ):
        """Initialize the OpenAI provider with enhanced execution control."""
        # Configuration
        self.model_name = model_name or get_config("llm.openai.model", "gpt-4o-mini")
        self.api_type = api_type
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.api_version = api_version or os.getenv("OPENAI_API_VERSION")
        self._timeout = timeout or DEFAULT_TIMEOUT
        self.max_input_tokens = max_input_tokens

        # Initialize base class with enhanced parameters
        super().__init__(
            model_name=self.model_name,
            execution_mode=execution_mode,
            approval_callback=approval_callback,
            verbose=verbose,
            max_tool_iterations=max_tool_iterations,
            tool_execution_timeout=tool_execution_timeout,
            allowed_tools=allowed_tools,
            forbidden_tools=forbidden_tools,
            hybrid_danger_threshold=hybrid_danger_threshold,
            api_key=self.api_key,
            api_type=api_type,
            base_url=self.base_url,
            temperature=temperature or get_config("llm.openai.temperature", DEFAULT_TEMPERATURE),
            max_tokens=max_tokens or get_config("llm.openai.max_tokens", DEFAULT_MAX_TOKENS),
            top_p=top_p or get_config("llm.openai.top_p", DEFAULT_TOP_P),
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

        # Enhanced tool execution setup
        self._tool_executor = ToolExecutor(
            max_iterations=max_tool_iterations,
            execution_timeout=tool_execution_timeout,
            allowed_tools=allowed_tools,
            forbidden_tools=forbidden_tools,
            execution_mode=execution_mode,
            approval_callback=approval_callback,
            verbose=verbose,
            hybrid_danger_threshold=hybrid_danger_threshold,
        )

        # Initialize OpenAI client
        self._client = self._create_client()

        logger.info(f"Initialized OpenAI provider: {self.model_name} | API: {api_type} | Execution mode: {execution_mode}")

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

    # Tool Registration Methods (enhanced)
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool for execution."""
        self._tool_executor.register_tool(name, func)
        if self.verbose:
            logger.info(f"Registered tool: {name}")

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools for execution."""
        self._tool_executor.register_tools(tools)
        if self.verbose:
            logger.info(f"Registered {len(tools)} tools")

    # Enhanced completion methods
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate completion with execution mode support."""
        return asyncio.run(self.acomplete(messages, **kwargs))

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate async completion with execution mode support."""
        if self.execution_mode == ExecutionMode.AUTO:
            return await self._acomplete_with_auto_tools(messages, **kwargs)
        elif self.execution_mode == ExecutionMode.DISABLED:
            return await self._acomplete_standard(messages, **kwargs)
        else:  # MANUAL or HYBRID
            # For manual/hybrid modes, we can still auto-execute if no approval callback
            if self.approval_callback:
                return await self._acomplete_with_controlled_tools(messages, **kwargs)
            else:
                return await self._acomplete_with_auto_tools(messages, **kwargs)

    # Enhanced tool execution methods
    def complete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """Generate completion and extract tool calls without executing them."""
        return asyncio.run(self.acomplete_with_tool_calls(messages, **kwargs))

    async def acomplete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """Generate completion and extract tool calls without executing them (async)."""
        # Get response without executing tools
        response = await self._acomplete_standard(messages, **kwargs)
        tool_calls = self._extract_tool_calls_from_response(response)
        return response, tool_calls

    def execute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Execute tool calls manually with current execution settings."""
        return self._tool_executor.execute_tool_calls(tool_calls, context)

    async def aexecute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Execute tool calls manually with current execution settings (async)."""
        return await self._tool_executor.aexecute_tool_calls(tool_calls, context)

    # Standard completion (no auto tool execution)
    async def _acomplete_standard(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Standard async completion without auto tool execution."""
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

    # Auto tool execution (existing behavior)
    async def _acomplete_with_auto_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Async complete with automatic tool execution loop."""
        conversation = list(messages)
        iteration = 0
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = await self._acomplete_standard(conversation, **kwargs)
            
            # Check if model made tool calls
            if not self._has_tool_calls(response):
                if self.verbose:
                    logger.info(f"No tool calls found, returning response (iteration {iteration + 1})")
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            if self.verbose:
                logger.info(f"Auto-executing {len(tool_calls)} tool calls (iteration {iteration + 1})")
            
            # Execute tools with current executor settings
            tool_results = await self._tool_executor.aexecute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning(f"Reached maximum tool iterations ({self.max_tool_iterations})")
        return response

    # Controlled tool execution (manual/hybrid with approval)
    async def _acomplete_with_controlled_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Async complete with controlled tool execution based on execution mode."""
        conversation = list(messages)
        iteration = 0
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = await self._acomplete_standard(conversation, **kwargs)
            
            # Check if model made tool calls
            if not self._has_tool_calls(response):
                if self.verbose:
                    logger.info(f"No tool calls found, returning response (iteration {iteration + 1})")
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            if self.verbose:
                logger.info(f"Processing {len(tool_calls)} tool calls with {self.execution_mode} mode (iteration {iteration + 1})")
            
            # Execute tools with approval control
            tool_results = await self._tool_executor.aexecute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning(f"Reached maximum tool iterations ({self.max_tool_iterations})")
        return response

    def _has_tool_calls(self, response: MessageProtocol) -> bool:
        """Check if response contains tool calls."""
        return (
            hasattr(response, "metadata") and 
            response.metadata and 
            "tool_calls" in response.metadata and 
            response.metadata["tool_calls"]
        )

    # Token Management Methods (unchanged)
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

    # HTTP Request Execution Methods (unchanged)
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

    # Streaming Methods (unchanged, but could be enhanced similarly)
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

    # Model Information Methods (unchanged)
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
                "execution_mode": self.execution_mode,
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
            description=f"OpenAI GPT models via {self.api_type} API with enhanced execution control",
            base_url=self.base_url,
            supported_models=[self.model_name],
            features={ModelFeature.STREAMING, ModelFeature.FUNCTION_CALLING, ModelFeature.VISION},
            configuration={
                "api_type": self.api_type,
                "model": self.model_name,
                "execution_mode": self.execution_mode,
                "max_tool_iterations": self.max_tool_iterations,
                "verbose": self.verbose,
            },
            is_available=True,
        )

    # Enhanced execution control methods
    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Change the execution mode."""
        super().set_execution_mode(mode)
        self._tool_executor.set_execution_mode(mode)

    def set_approval_callback(self, callback: Optional[Callable]) -> None:
        """Set or update the approval callback."""
        super().set_approval_callback(callback)
        self._tool_executor.set_approval_callback(callback)

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose logging."""
        super().set_verbose(verbose)
        self._tool_executor.set_verbose(verbose)

    def get_tool_execution_stats(self) -> Optional[Dict[str, Any]]:
        """Get tool execution statistics."""
        return self._tool_executor.get_execution_stats()

    def get_token_stats(self) -> Dict[str, int]:
        """Get token usage statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_input_tokens + self.total_completion_tokens,
        }