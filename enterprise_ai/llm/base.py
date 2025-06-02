"""
Enhanced base LLM provider interface with tool execution control.

This module defines the essential interface that all LLM providers must implement,
now with support for manual tool execution and approval workflows.
"""

import abc
import time
from typing import Any, Dict, List, Optional, Set, Union, Iterator, AsyncIterator, Callable

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ModelInfo, ToolCall, ToolResult
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.base import ExecutionMode

logger = get_logger("llm.base")


class LLMProvider(abc.ABC):
    """
    Enhanced base class for LLM providers with manual tool execution support.
    
    Includes methods that ALL providers must have, plus optional enhanced
    functionality for tool execution control.
    """

    def __init__(
        self, 
        model_name: str,
        # Enhanced execution parameters
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        approval_callback: Optional[Callable] = None,
        verbose: bool = False,
        max_tool_iterations: int = 5,
        tool_execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None,
        hybrid_danger_threshold: int = 2,
        **kwargs: Any
    ):
        """
        Initialize the provider with enhanced execution control.

        Args:
            model_name: Name of the model to use
            execution_mode: How tools should be executed
            approval_callback: Function for human approval of tool calls
            verbose: Whether to enable verbose logging
            max_tool_iterations: Maximum tool execution rounds
            tool_execution_timeout: Timeout for individual tool execution
            allowed_tools: Set of allowed tool names
            forbidden_tools: Set of forbidden tool names
            hybrid_danger_threshold: Danger level threshold for hybrid mode
            **kwargs: Provider-specific parameters
        """
        self.model_name = model_name
        self.config = kwargs
        
        # Enhanced execution control
        self.execution_mode = execution_mode
        self.approval_callback = approval_callback
        self.verbose = verbose
        self.max_tool_iterations = max_tool_iterations
        self.tool_execution_timeout = tool_execution_timeout
        self.allowed_tools = allowed_tools
        self.forbidden_tools = forbidden_tools
        self.hybrid_danger_threshold = hybrid_danger_threshold
        
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

    # Enhanced tool execution methods
    def complete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """
        Generate completion and extract tool calls without executing them.
        
        This enables manual tool execution workflows.
        
        Args:
            messages: List of messages
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (response_message, extracted_tool_calls)
        """
        # Default implementation - providers should override for optimization
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
        # Default implementation - providers should override for optimization
        response = await self.acomplete(messages, **kwargs)
        tool_calls = self._extract_tool_calls_from_response(response)
        return response, tool_calls

    def execute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Execute tool calls manually with current execution settings.
        
        Args:
            tool_calls: List of tool calls to execute
            context: Optional context for tool execution
            
        Returns:
            List of tool execution results
        """
        # This method should be implemented by concrete providers
        # that have tool executors available
        raise NotImplementedError("Provider does not support manual tool execution")

    async def aexecute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Execute tool calls manually with current execution settings (async).
        
        Args:
            tool_calls: List of tool calls to execute
            context: Optional context for tool execution
            
        Returns:
            List of tool execution results
        """
        # This method should be implemented by concrete providers
        # that have tool executors available
        raise NotImplementedError("Provider does not support async manual tool execution")

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
            "execution_mode": self.execution_mode,
            "verbose_logging": self.verbose,
        }

    # Enhanced execution control methods
    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Change the execution mode for this provider."""
        old_mode = self.execution_mode
        self.execution_mode = mode
        if self.verbose:
            logger.info(f"Provider execution mode changed from {old_mode} to {mode}")

    def set_approval_callback(self, callback: Optional[Callable]) -> None:
        """Set or update the approval callback."""
        self.approval_callback = callback
        if self.verbose:
            logger.info(f"Approval callback {'set' if callback else 'removed'}")

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose logging."""
        old_verbose = self.verbose
        self.verbose = verbose
        if old_verbose != verbose:
            logger.info(f"Verbose logging {'enabled' if verbose else 'disabled'}")

    def get_execution_config(self) -> Dict[str, Any]:
        """Get current execution configuration."""
        return {
            "execution_mode": self.execution_mode,
            "has_approval_callback": self.approval_callback is not None,
            "verbose": self.verbose,
            "max_tool_iterations": self.max_tool_iterations,
            "tool_execution_timeout": self.tool_execution_timeout,
            "allowed_tools": list(self.allowed_tools) if self.allowed_tools else None,
            "forbidden_tools": list(self.forbidden_tools) if self.forbidden_tools else None,
            "hybrid_danger_threshold": self.hybrid_danger_threshold,
        }

    # Tool registration methods (optional, for providers that support it)
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool for execution (if supported by provider)."""
        if self.verbose:
            logger.info(f"Tool registration not supported by {self.__class__.__name__}")

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools for execution (if supported by provider)."""
        if self.verbose:
            logger.info(f"Tool registration not supported by {self.__class__.__name__}")