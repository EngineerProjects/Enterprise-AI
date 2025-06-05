"""
Enhanced base LLM provider interface focused solely on text generation.

This module defines the essential interface that all LLM providers must implement,
now focused exclusively on text generation and tool call extraction.
"""

import abc
import time
from typing import Any, Dict, List, Optional, Set, Union, Iterator, AsyncIterator, Callable

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ModelInfo, ToolCall
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.base")


class LLMProvider(abc.ABC):
    """
    Base class for LLM providers focused on text generation and tool call extraction.
    
    This class handles only text generation and tool call extraction. All tool execution
    is delegated to the MCP module for clean separation of concerns.
    """

    def __init__(
        self, 
        model_name: str,
        verbose: bool = False,
        **kwargs: Any
    ):
        """
        Initialize the provider.

        Args:
            model_name: Name of the model to use
            verbose: Whether to enable verbose logging
            **kwargs: Provider-specific parameters
        """
        self.model_name = model_name
        self.config = kwargs
        self.verbose = verbose
        
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

    def complete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """
        Generate completion and extract tool calls without executing them.
        
        This enables manual tool execution workflows via MCP.
        
        Args:
            messages: List of messages
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (response_message, extracted_tool_calls)
        """
        response = self.complete(messages, **kwargs)
        tool_calls = self._extract_tool_calls_from_response(response)
        return response, tool_calls

    async def acomplete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """
        Generate completion and extract tool calls without executing them (async).
        
        Args:
            messages: List of messages
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (response_message, extracted_tool_calls)
        """
        response = await self.acomplete(messages, **kwargs)
        tool_calls = self._extract_tool_calls_from_response(response)
        return response, tool_calls

    def _extract_tool_calls_from_response(self, response: MessageProtocol) -> List[ToolCall]:
        """
        Extract tool calls from a response message.
        
        Args:
            response: Response message from the model
            
        Returns:
            List of extracted tool calls
        """
        tool_calls = []
        
        if hasattr(response, 'metadata') and response.metadata:
            if 'tool_calls' in response.metadata:
                tool_calls_data = response.metadata['tool_calls']
                tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
        
        return tool_calls

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
            "verbose_logging": self.verbose,
        }

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose logging."""
        old_verbose = self.verbose
        self.verbose = verbose
        if old_verbose != verbose:
            logger.info(f"Verbose logging {'enabled' if verbose else 'disabled'}")