"""
Base LLM provider implementation with improved resource management.

This module defines the base class for all LLM providers and provides a common interface
for interacting with language models. It includes methods for generating completions,
streaming completions, and tool calling, along with metrics tracking and model information retrieval.
"""

import abc
import time
import asyncio
import weakref
from typing import Any, Dict, List, Optional, Set, Union, AsyncGenerator

from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    ModelFeature,
)
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo
from enterprise_ai.schema.tool import TOOL_CHOICE_TYPE, ToolChoice
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.base")

# Global registry for cleanup
_active_providers = weakref.WeakSet()


class LLMProvider(abc.ABC):
    """
    Base class for LLM providers with improved resource management.

    This class defines the interface that all LLM providers must implement.
    """

    def __init__(self, model_name: str, **kwargs: Any):
        """
        Initialize the provider.

        Args:
            model_name: Name of the model to use
            **kwargs: Additional provider-specific parameters
        """
        self.model_name = model_name
        self.config = kwargs

        # Store start time for metrics
        self._start_time = time.time()
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0

        # Initialize model info
        self._model_info = None
        
        # Track if provider is closed
        self._closed = False
        
        # Add to global registry for cleanup
        _active_providers.add(self)

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name

    @abc.abstractmethod
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion for the given messages.

        Args:
            messages: List of messages
            **kwargs: Additional parameters for the completion

        Returns:
            Generated message
        """
        pass

    @abc.abstractmethod
    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion asynchronously for the given messages.

        Args:
            messages: List of messages
            **kwargs: Additional parameters for the completion

        Returns:
            Generated message
        """
        pass

    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Any:
        """
        Generate a streaming completion for the given messages.

        Args:
            messages: List of messages
            **kwargs: Additional parameters for the completion

        Returns:
            Generator yielding completion chunks
        """
        # Default implementation: providers should override if they support streaming
        raise NotImplementedError("Streaming not supported by this provider")

    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncGenerator[Any, None]:
        """
        Generate an async streaming completion for the given messages.

        Args:
            messages: List of messages
            **kwargs: Additional parameters for the completion

        Returns:
            Async generator yielding completion chunks
        """
        # Default implementation: providers should override if they support streaming
        raise NotImplementedError("Async streaming not supported by this provider")

    @abc.abstractmethod
    async def ask_tool(
        self,
        messages: List[MessageProtocol],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: TOOL_CHOICE_TYPE = ToolChoice.AUTO,
        timeout: int = 300,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[Any]:
        """
        Ask LLM using functions/tools and return the response.

        Args:
            messages: List of conversation messages
            tools: List of tools/functions available to the model
            tool_choice: Tool choice strategy
            timeout: Request timeout in seconds
            temperature: Sampling temperature for the response
            max_tokens: Maximum tokens to generate
            **kwargs: Additional completion arguments

        Returns:
            Provider-specific response object, or None if failed
        """
        pass

    @abc.abstractmethod
    def get_model_info(self) -> ModelInfo:
        """
        Get information about the model.

        Returns:
            ModelInfo object with capabilities and limitations
        """
        pass

    def get_model_features(self) -> Set[str]:
        """
        Get the set of features supported by the model.

        Returns:
            Set of feature strings
        """
        return self.get_model_info().features

    def supports_feature(self, feature: str) -> bool:
        """
        Check if the model supports a specific feature.

        Args:
            feature: Feature to check

        Returns:
            True if supported, False otherwise
        """
        return feature in self.get_model_features()

    def track_request(self, success: bool) -> None:
        """
        Track request metrics.

        Args:
            success: Whether the request was successful
        """
        self._request_count += 1
        if success:
            self._success_count += 1
        else:
            self._error_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get usage metrics for this provider.

        Returns:
            Dictionary of metrics
        """
        uptime = time.time() - self._start_time
        return {
            "provider": self.__class__.__name__,
            "model": self.model_name,
            "uptime_seconds": uptime,
            "request_count": self._request_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": self._success_count / max(1, self._request_count),
            "closed": self._closed,
        }

    def is_closed(self) -> bool:
        """Check if the provider has been closed."""
        return self._closed

    def close(self) -> None:
        """
        Close and cleanup provider resources.
        Providers should override this if they need cleanup.
        """
        if not self._closed:
            self._closed = True
            logger.debug(f"Closed {self.__class__.__name__} provider")

    async def aclose(self) -> None:
        """
        Async close and cleanup provider resources.
        Providers should override this if they need async cleanup.
        """
        if not self._closed:
            self._closed = True
            logger.debug(f"Async closed {self.__class__.__name__} provider")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()


def cleanup_all_providers() -> None:
    """
    Clean up all active providers.
    
    This function is useful for testing or when shutting down the application.
    """
    active_count = 0
    for provider in list(_active_providers):
        if not provider.is_closed():
            try:
                provider.close()
                active_count += 1
            except Exception as e:
                logger.warning(f"Error closing provider {provider}: {e}")
    
    if active_count > 0:
        logger.info(f"Cleaned up {active_count} active providers")


async def acleanup_all_providers() -> None:
    """
    Async clean up all active providers.
    
    This function is useful for testing or when shutting down the application.
    """
    active_count = 0
    for provider in list(_active_providers):
        if not provider.is_closed():
            try:
                await provider.aclose()
                active_count += 1
            except Exception as e:
                logger.warning(f"Error async closing provider {provider}: {e}")
    
    if active_count > 0:
        logger.info(f"Async cleaned up {active_count} active providers")