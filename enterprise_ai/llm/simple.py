"""
Simple LLM interface for tools in Enterprise AI.

This module provides a simplified interface for tools to interact
with LLM providers without dealing with provider-specific details.
"""

from typing import Any, Dict, List, Optional, Union, AsyncGenerator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.factory import get_default_provider
from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.simple")


class LLM:
    """Simple LLM class for tools with enhanced tool support and proper resource management."""

    def __init__(
        self,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        **kwargs: Any,
    ):
        """
        Initialize LLM.

        Args:
            provider_name: Provider name to use
            model_name: Model name to use
            provider: Explicit provider instance
            **kwargs: Additional provider parameters
        """
        self._provider = provider
        self.provider_name = provider_name
        self.model_name = model_name
        self.kwargs = kwargs
        self._closed = False

    @property
    def provider(self) -> LLMProvider:
        """
        Get the provider instance, initializing if needed.

        Returns:
            Provider instance
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
            
        if self._provider is None:
            if self.provider_name:
                from enterprise_ai.llm.factory import create_provider

                self._provider = create_provider(
                    self.provider_name, model_name=self.model_name, **self.kwargs
                )
            else:
                self._provider = get_default_provider(model_name=self.model_name, **self.kwargs)
        return self._provider

    def complete(self, messages: List[Any], **kwargs: Any) -> Any:
        """
        Generate a completion.

        Args:
            messages: Input messages
            **kwargs: Additional completion parameters

        Returns:
            Provider-specific completion result
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
        return self.provider.complete(messages, **kwargs)

    async def acomplete(self, messages: List[Any], **kwargs: Any) -> Any:
        """
        Generate a completion asynchronously.

        Args:
            messages: Input messages
            **kwargs: Additional completion parameters

        Returns:
            Provider-specific completion result
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
        return await self.provider.acomplete(messages, **kwargs)

    def complete_stream(self, messages: List[Any], **kwargs: Any) -> Any:
        """
        Generate a streaming completion.

        Args:
            messages: Input messages
            **kwargs: Additional completion parameters

        Returns:
            Generator yielding completion chunks
            
        Raises:
            RuntimeError: If LLM has been closed
            NotImplementedError: If streaming not supported
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
            
        if hasattr(self.provider, "complete_stream"):
            return self.provider.complete_stream(messages, **kwargs)
        else:
            raise NotImplementedError("Streaming not supported by this provider")

    async def acomplete_stream(self, messages: List[Any], **kwargs: Any) -> AsyncGenerator[Any, None]:
        """
        Generate an async streaming completion.

        Args:
            messages: Input messages
            **kwargs: Additional completion parameters

        Returns:
            Async generator yielding completion chunks
            
        Raises:
            RuntimeError: If LLM has been closed
            NotImplementedError: If async streaming not supported
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
            
        if hasattr(self.provider, "acomplete_stream"):
            async for chunk in self.provider.acomplete_stream(messages, **kwargs):
                yield chunk
        else:
            raise NotImplementedError("Async streaming not supported by this provider")

    async def ask_tool(self, messages: List[Any], **kwargs: Any) -> Any:
        """
        Ask LLM using tools/functions.

        Args:
            messages: Input messages
            **kwargs: Tool calling parameters

        Returns:
            Provider-specific response with tool calls
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
        return await self.provider.ask_tool(messages, **kwargs)

    def format_tools(self, tools: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Format tools for the current provider.

        Args:
            tools: List of tools in standard format
            **kwargs: Additional formatting options

        Returns:
            Formatted tools for this provider
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
            
        if hasattr(self.provider, "format_tools_for_provider"):
            formatted_tools, _ = self.provider.format_tools_for_provider(tools, **kwargs)
            return formatted_tools
        return tools

    def extract_tool_calls(self, response: Any) -> List[Dict[str, Any]]:
        """
        Extract tool calls from a response.

        Args:
            response: LLM response

        Returns:
            List of tool calls
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
            
        if hasattr(self.provider, "extract_tool_calls"):
            return self.provider.extract_tool_calls(response)
        return []

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get provider metrics.

        Returns:
            Dictionary of metrics
            
        Raises:
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
        return self.provider.get_metrics()

    def is_closed(self) -> bool:
        """Check if the LLM instance has been closed."""
        return self._closed

    def close(self) -> None:
        """Close the LLM and its provider."""
        if not self._closed:
            self._closed = True
            if self._provider:
                try:
                    self._provider.close()
                except Exception as e:
                    logger.warning(f"Error closing provider: {e}")
                finally:
                    self._provider = None

    async def aclose(self) -> None:
        """Async close the LLM and its provider."""
        if not self._closed:
            self._closed = True
            if self._provider:
                try:
                    await self._provider.aclose()
                except Exception as e:
                    logger.warning(f"Error async closing provider: {e}")
                finally:
                    self._provider = None

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

    def __getattr__(self, name: str) -> Any:
        """
        Forward attribute access to provider.

        Args:
            name: Attribute name

        Returns:
            Provider attribute value

        Raises:
            AttributeError: If attribute not found
            RuntimeError: If LLM has been closed
        """
        if self._closed:
            raise RuntimeError("LLM instance has been closed")
            
        # Initialize provider if needed
        if self._provider is None:
            _ = self.provider

        # Forward to provider
        if hasattr(self._provider, name):
            return getattr(self._provider, name)

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    def __del__(self):
        """Cleanup on deletion."""
        if not self._closed:
            try:
                self.close()
            except Exception:
                pass  # Ignore errors during cleanup