"""
Minimal base LLM provider interface with enhanced tool support.

This module defines the essential interface that all LLM providers must implement.
Only includes methods that are truly universal across all providers.
"""

import abc
import time
from typing import Any, Dict, List, Optional, Set, Union, Iterator, AsyncIterator

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ModelInfo
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.base")


class LLMProvider(abc.ABC):
    """
    Minimal base class for LLM providers with enhanced functionality.
    
    Only includes methods that ALL providers must have.
    Provider-specific features should be in the concrete implementations.
    """

    def __init__(self, model_name: str, **kwargs: Any):
        """
        Initialize the provider.

        Args:
            model_name: Name of the model to use
            **kwargs: Provider-specific parameters
        """
        self.model_name = model_name
        self.config = kwargs
        
        # Metrics tracking
        self._start_time = time.time()
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        
        # Cache for model info
        self._model_info = None

    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_name

    @abc.abstractmethod
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion for the given messages.

        Args:
            messages: List of messages
            **kwargs: Additional parameters

        Returns:
            Generated message
        """
        pass

    @abc.abstractmethod
    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion asynchronously.

        Args:
            messages: List of messages  
            **kwargs: Additional parameters

        Returns:
            Generated message
        """
        pass

    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Iterator[MessageProtocol]:
        """
        Generate a streaming completion (optional implementation).

        Args:
            messages: List of messages
            **kwargs: Additional parameters

        Returns:
            Iterator of partial messages
        """
        # Default implementation calls complete once
        result = self.complete(messages, **kwargs)
        yield result

    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncIterator[MessageProtocol]:
        """
        Generate an async streaming completion (optional implementation).

        Args:
            messages: List of messages
            **kwargs: Additional parameters

        Returns:
            Async iterator of partial messages
        """
        # Default implementation calls acomplete once
        result = await self.acomplete(messages, **kwargs)
        yield result

    @abc.abstractmethod
    def get_model_info(self) -> ModelInfo:
        """
        Get basic model information.

        Returns:
            ModelInfo with capabilities and limits
        """
        pass

    def supports_feature(self, feature: str) -> bool:
        """
        Check if model supports a feature.

        Args:
            feature: Feature to check (streaming, vision, etc.)

        Returns:
            True if supported, False otherwise
        """
        try:
            return feature in self.get_model_info().features
        except Exception:
            return False

    def get_context_window(self) -> Optional[int]:
        """
        Get context window size if available.

        Returns:
            Context window size or None if unknown
        """
        try:
            return self.get_model_info().context_window
        except Exception:
            return None

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
        }