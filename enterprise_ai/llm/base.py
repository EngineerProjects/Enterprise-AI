"""
Base functionality and abstractions for LLM providers in Enterprise AI.

This module defines the core interfaces, abstract classes, and utility functions for
integrating with Large Language Model providers. It establishes a common interface that
all provider implementations must adhere to, enabling consistent interaction patterns
regardless of the underlying provider (OpenAI, Anthropic, Ollama, etc.).

The module includes:
- Abstract base classes for synchronous and asynchronous LLM providers
- Configuration handling for provider settings
- Response and error handling utilities
- Common interface for streaming and non-streaming operations
"""

import abc
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    AsyncIterator,
    cast,
    overload,
    runtime_checkable,
)

from enterprise_ai.logger import get_logger
from enterprise_ai.exceptions import (
    LLMError,
    APIError,
    ModelNotAvailable,
    TokenLimitExceeded,
    ModelCapabilityError,
    ContextWindowExceededError,
    ProviderNotSupportedError,
)
from enterprise_ai.schema import Message, Role
from enterprise_ai.types import MessageProtocol, ProviderProtocol, StreamingProviderProtocol
from enterprise_ai.message.constants import (
    MESSAGE_FORMAT_OPENAI,
    MESSAGE_FORMAT_ANTHROPIC,
    MESSAGE_FORMAT_OLLAMA,
    MessageFormatValue,
)
from enterprise_ai.message.transformers.base import TransformerRegistry

# Initialize logger
logger = get_logger("llm.base")

# Type variables for generic typing
T = TypeVar("T")
P = TypeVar("P", bound="BaseLLMProvider")

# Common constants for LLM operations
DEFAULT_TIMEOUT = 60.0  # Default timeout in seconds
DEFAULT_MAX_RETRIES = 3  # Default retry limit
DEFAULT_TEMPERATURE = 0.7  # Default temperature
DEFAULT_TOP_P = 1.0  # Default top_p value
DEFAULT_MAX_TOKENS = 1024  # Default max tokens to generate

# Response type definitions
LLMResponseDict = Dict[str, Any]  # Generic response dictionary
LLMCompletionResponse = MessageProtocol  # Completion response
LLMStreamingResponse = Iterator[MessageProtocol]  # Synchronous streaming response
LLMAsyncStreamingResponse = AsyncIterator[MessageProtocol]  # Async streaming response


class ProviderType(str, Enum):
    """Enumeration of supported LLM provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    CUSTOM = "custom"


class ModelFeature(str, Enum):
    """Enumeration of model features and capabilities."""

    VISION = "vision"  # Vision/image understanding capability
    FUNCTION_CALLING = "function_calling"  # Function/tool calling
    STREAMING = "streaming"  # Streaming response capability
    CODE = "code"  # Code generation/understanding
    JSON_MODE = "json_mode"  # Structured JSON output mode
    MULTI_MODAL = "multi_modal"  # Support for multiple content types


class LLMOptions(Dict[str, Any]):
    """Type for LLM request options."""

    pass


class ProviderConfig(Dict[str, Any]):
    """Type for provider configuration."""

    pass


class ModelInfo:
    """Information about an LLM model's capabilities and constraints."""

    def __init__(
        self,
        id: str,
        provider: str,
        max_tokens: int,
        features: Optional[Set[ModelFeature]] = None,
        cost_per_1k_tokens: Optional[float] = None,
        context_window: Optional[int] = None,
        description: Optional[str] = None,
    ):
        """Initialize model information.

        Args:
            id: Model identifier
            provider: Provider identifier
            max_tokens: Maximum tokens for generation
            features: Set of supported features
            cost_per_1k_tokens: Cost per 1000 tokens (input + output)
            context_window: Maximum context window size
            description: Model description
        """
        self.id = id
        self.provider = provider
        self.max_tokens = max_tokens
        self.features = features or set()
        self.cost_per_1k_tokens = cost_per_1k_tokens
        self.context_window = context_window or max_tokens * 4  # Estimate if not provided
        self.description = description

    def supports_feature(self, feature: ModelFeature) -> bool:
        """Check if the model supports a specific feature.

        Args:
            feature: Feature to check

        Returns:
            True if the feature is supported, False otherwise
        """
        return feature in self.features

    def to_dict(self) -> Dict[str, Any]:
        """Convert model info to dictionary.

        Returns:
            Dictionary representation of model info
        """
        return {
            "id": self.id,
            "provider": self.provider,
            "max_tokens": self.max_tokens,
            "features": [f.value for f in self.features],
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "context_window": self.context_window,
            "description": self.description,
        }


class BaseLLMProvider(abc.ABC):
    """Abstract base class for LLM providers.

    This class defines the common interface that all LLM providers must implement,
    providing methods for message completion, token counting, and model information.
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        **kwargs: Any,
    ):
        """Initialize the LLM provider.

        Args:
            model: Model identifier
            api_key: API key for authentication
            api_base: Base URL for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            **kwargs: Additional provider-specific parameters
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout
        self.max_retries = max_retries
        self.options = kwargs

        # Store start time for latency tracking
        self._start_time = time.time()

        # Initialize request counters
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._token_usage = {"prompt": 0, "completion": 0, "total": 0}

        # Validate and prepare provider
        self._initialize_provider()

    def _initialize_provider(self) -> None:
        """Initialize and validate the provider configuration.

        This method is called during initialization to perform any necessary
        setup and validation of the provider configuration.

        Raises:
            ProviderNotSupportedError: If the provider is not supported
            ConfigValueError: If required configuration values are missing
        """
        # Implement provider-specific initialization
        pass

    @property
    def provider_name(self) -> str:
        """Get the provider name.

        Returns:
            Provider name string
        """
        return self.__class__.__name__

    @abc.abstractmethod
    def complete(
        self,
        messages: List[MessageProtocol],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> MessageProtocol:
        """Generate a completion for the given messages.

        Args:
            messages: List of messages to generate a completion for
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Completion message

        Raises:
            APIError: If the API request fails
            LLMError: For other LLM-related errors
        """
        raise NotImplementedError("Subclasses must implement complete()")

    @abc.abstractmethod
    def complete_stream(
        self,
        messages: List[MessageProtocol],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[MessageProtocol]:
        """Generate a streaming completion for the given messages.

        Args:
            messages: List of messages to generate a completion for
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Iterator of partial completion messages

        Raises:
            APIError: If the API request fails
            LLMError: For other LLM-related errors
        """
        raise NotImplementedError("Subclasses must implement complete_stream()")

    @abc.abstractmethod
    def count_tokens(self, messages: List[MessageProtocol]) -> int:
        """Count the number of tokens in the messages.

        Args:
            messages: List of messages to count tokens for

        Returns:
            Token count
        """
        raise NotImplementedError("Subclasses must implement count_tokens()")

    @abc.abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Get information about the current model.

        Returns:
            ModelInfo object with model capabilities and constraints
        """
        raise NotImplementedError("Subclasses must implement get_model_info()")

    def supports_vision(self) -> bool:
        """Check if the model supports vision/images.

        Returns:
            True if vision is supported, False otherwise
        """
        return self.get_model_info().supports_feature(ModelFeature.VISION)

    def supports_functions(self) -> bool:
        """Check if the model supports function/tool calling.

        Returns:
            True if function calling is supported, False otherwise
        """
        return self.get_model_info().supports_feature(ModelFeature.FUNCTION_CALLING)

    def supports_streaming(self) -> bool:
        """Check if the model supports streaming responses.

        Returns:
            True if streaming is supported, False otherwise
        """
        return self.get_model_info().supports_feature(ModelFeature.STREAMING)

    def get_max_tokens(self) -> int:
        """Get the maximum token limit for the model.

        Returns:
            Maximum token limit
        """
        return self.get_model_info().max_tokens

    def get_context_window(self) -> int:
        """Get the context window size for the model.

        Returns:
            Context window size in tokens
        """
        return self.get_model_info().context_window

    def transform_messages(
        self, messages: List[MessageProtocol], target_format: str
    ) -> List[Dict[str, Any]]:
        """Transform messages to the target format for the provider.

        Args:
            messages: Messages to transform
            target_format: Target format identifier

        Returns:
            Transformed messages as list of dictionaries
        """
        # Cast target_format to the expected MessageFormatValue type
        format_value = cast(MessageFormatValue, target_format)
        return [TransformerRegistry.transform(msg, format_value) for msg in messages]

    def _track_request(self, success: bool, tokens_in: int = 0, tokens_out: int = 0) -> None:
        """Track request metrics.

        Args:
            success: Whether the request was successful
            tokens_in: Number of input tokens
            tokens_out: Number of output tokens
        """
        self._request_count += 1
        if success:
            self._success_count += 1
        else:
            self._error_count += 1

        self._token_usage["prompt"] += tokens_in
        self._token_usage["completion"] += tokens_out
        self._token_usage["total"] += tokens_in + tokens_out

    def get_metrics(self) -> Dict[str, Any]:
        """Get usage metrics for the provider.

        Returns:
            Dictionary of usage metrics
        """
        uptime = time.time() - self._start_time
        return {
            "provider": self.provider_name,
            "model": self.model,
            "uptime_seconds": uptime,
            "request_count": self._request_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": self._success_count / max(1, self._request_count),
            "token_usage": self._token_usage,
        }


class AsyncLLMProvider(BaseLLMProvider):
    """Abstract base class for asynchronous LLM providers.

    This class extends BaseLLMProvider with async versions of its methods
    for use in async/await contexts.
    """

    @abc.abstractmethod
    async def acomplete(
        self,
        messages: List[MessageProtocol],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> MessageProtocol:
        """Generate a completion asynchronously.

        Args:
            messages: List of messages to generate a completion for
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Completion message

        Raises:
            APIError: If the API request fails
            LLMError: For other LLM-related errors
        """
        raise NotImplementedError("Subclasses must implement acomplete()")

    @abc.abstractmethod
    async def acomplete_stream(
        self,
        messages: List[MessageProtocol],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[MessageProtocol]:
        """Generate a streaming completion asynchronously.

        Args:
            messages: List of messages to generate a completion for
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Async iterator of partial completion messages

        Raises:
            APIError: If the API request fails
            LLMError: For other LLM-related errors
        """
        raise NotImplementedError("Subclasses must implement acomplete_stream()")

    # Default implementations that delegate to synchronous methods
    def complete(
        self,
        messages: List[MessageProtocol],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> MessageProtocol:
        """Synchronous complete implementation that runs the async version.

        This default implementation runs the async version in a new event loop.
        Subclasses should override this with a proper synchronous implementation
        for better performance.

        Args:
            messages: List of messages to generate a completion for
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Completion message
        """
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self.acomplete(messages, temperature, max_tokens, **kwargs)
            )
        finally:
            loop.close()

    def complete_stream(
        self,
        messages: List[MessageProtocol],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[MessageProtocol]:
        """Synchronous streaming complete that runs the async version.

        This default implementation materializes the entire async stream.
        Subclasses should override this with a proper synchronous implementation
        for better performance.

        Args:
            messages: List of messages to generate a completion for
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            Iterator of partial completion messages
        """
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            # Materialize the async stream
            stream_results = []

            async def collect_stream() -> None:
                # Cast to help type checker understand this is an async iterator
                stream = cast(
                    AsyncIterator[MessageProtocol],
                    self.acomplete_stream(messages, temperature, max_tokens, **kwargs),
                )
                async for chunk in stream:
                    stream_results.append(chunk)

            loop.run_until_complete(collect_stream())
            return iter(stream_results)
        finally:
            loop.close()


class LLMProviderRegistry:
    """Registry for LLM providers.

    This class maintains a mapping of provider types to their implementation classes,
    allowing for dynamic registration and retrieval of provider implementations.
    """

    _providers: Dict[str, Type[BaseLLMProvider]] = {}

    @classmethod
    def register(
        cls,
        provider_type: Union[str, ProviderType],
        provider_class: Type[BaseLLMProvider],
    ) -> None:
        """Register a provider implementation.

        Args:
            provider_type: Provider type identifier
            provider_class: Provider implementation class
        """
        if isinstance(provider_type, ProviderType):
            provider_type = provider_type.value

        cls._providers[provider_type.lower()] = provider_class
        logger.info(f"Registered LLM provider: {provider_type}")

    @classmethod
    def get_provider_class(cls, provider_type: Union[str, ProviderType]) -> Type[BaseLLMProvider]:
        """Get a provider implementation class.

        Args:
            provider_type: Provider type identifier

        Returns:
            Provider implementation class

        Raises:
            ProviderNotSupportedError: If the provider is not supported
        """
        if isinstance(provider_type, ProviderType):
            provider_type = provider_type.value

        provider_key = provider_type.lower()
        if provider_key not in cls._providers:
            raise ProviderNotSupportedError(provider_type)

        return cls._providers[provider_key]

    @classmethod
    def create_provider(
        cls,
        provider_type: Union[str, ProviderType],
        model: str,
        **kwargs: Any,
    ) -> BaseLLMProvider:
        """Create a provider instance.

        Args:
            provider_type: Provider type identifier
            model: Model identifier
            **kwargs: Additional provider-specific parameters

        Returns:
            Provider instance

        Raises:
            ProviderNotSupportedError: If the provider is not supported
        """
        provider_class = cls.get_provider_class(provider_type)
        return provider_class(model=model, **kwargs)

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all registered provider types.

        Returns:
            List of provider type identifiers
        """
        return list(cls._providers.keys())


# Utility functions for working with LLM providers


def get_provider_for_model(model: str) -> Optional[str]:
    """Determine the provider type for a given model identifier.

    This function uses model name patterns to identify the appropriate provider.

    Args:
        model: Model identifier

    Returns:
        Provider type identifier or None if unknown
    """
    model_lower = model.lower()

    # OpenAI models
    if (
        model_lower.startswith(("gpt-", "davinci", "curie", "babbage", "ada"))
        or "turbo" in model_lower
        or "instruct" in model_lower
    ):
        return ProviderType.OPENAI.value

    # Anthropic models
    if model_lower.startswith(("claude-", "claude/")):
        return ProviderType.ANTHROPIC.value

    # Ollama models
    if (
        model_lower.startswith(("llama", "mistral", "phi", "orca", "vicuna"))
        or "/" in model_lower  # Typically Ollama models are namespaced
    ):
        return ProviderType.OLLAMA.value

    # Unknown model
    return None


def get_message_format_for_provider(provider: Union[str, ProviderType]) -> MessageFormatValue:
    """Get the appropriate message format for a provider.

    Args:
        provider: Provider type identifier

    Returns:
        Message format identifier
    """
    if isinstance(provider, ProviderType):
        provider = provider.value

    provider_lower = provider.lower()

    if provider_lower == ProviderType.OPENAI.value:
        return cast(MessageFormatValue, MESSAGE_FORMAT_OPENAI)

    if provider_lower == ProviderType.ANTHROPIC.value:
        return cast(MessageFormatValue, MESSAGE_FORMAT_ANTHROPIC)

    if provider_lower == ProviderType.OLLAMA.value:
        return cast(MessageFormatValue, MESSAGE_FORMAT_OLLAMA)

    # Default to OpenAI format
    return cast(MessageFormatValue, MESSAGE_FORMAT_OPENAI)


def create_provider(
    provider_type: Optional[Union[str, ProviderType]] = None,
    model: Optional[str] = None,
    **kwargs: Any,
) -> BaseLLMProvider:
    """Create a provider instance with automatic provider detection.

    If provider_type is not specified, it will be determined from the model name.
    If model is not specified, a default model for the provider will be used.

    Args:
        provider_type: Provider type identifier (optional)
        model: Model identifier (optional)
        **kwargs: Additional provider-specific parameters

    Returns:
        Provider instance

    Raises:
        ProviderNotSupportedError: If the provider cannot be determined or is not supported
        ValueError: If neither provider_type nor model is specified
    """
    if provider_type is None and model is None:
        raise ValueError("Either provider_type or model must be specified")

    # Determine provider from model if not specified
    if provider_type is None and model is not None:
        detected_provider = get_provider_for_model(model)
        if detected_provider is None:
            raise ProviderNotSupportedError(f"Unknown model: {model}")
        provider_type = detected_provider

    assert provider_type is not None  # For type checking

    # Get default model if not specified
    if model is None:
        # These defaults would be better placed in a configuration file
        if provider_type.lower() == ProviderType.OPENAI.value:
            model = "gpt-4o"
        elif provider_type.lower() == ProviderType.ANTHROPIC.value:
            model = "claude-3-opus"
        elif provider_type.lower() == ProviderType.OLLAMA.value:
            model = "llama3"
        else:
            raise ValueError(f"No default model for provider {provider_type}")

    return LLMProviderRegistry.create_provider(provider_type, model, **kwargs)
