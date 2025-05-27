"""
Simple LLM interface for tools in Enterprise AI.

This module provides a simplified interface for tools to interact
with LLM providers without dealing with provider-specific details.
"""

from typing import Any, Dict, List, Optional, Union

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.providers.factory import get_default_provider
from enterprise_ai.types import MessageProtocol


class LLM:
    """Simple LLM class for tools."""

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

    @property
    def provider(self) -> LLMProvider:
        """
        Get the provider instance, initializing if needed.

        Returns:
            Provider instance
        """
        if self._provider is None:
            if self.provider_name:
                from enterprise_ai.llm.providers.factory import create_provider

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
        """
        return self.provider.complete(messages, **kwargs)

    async def acomplete(self, messages: List[Any], **kwargs: Any) -> Any:
        """
        Generate a completion asynchronously.

        Args:
            messages: Input messages
            **kwargs: Additional completion parameters

        Returns:
            Provider-specific completion result
        """
        if hasattr(self.provider, "acomplete"):
            return await self.provider.acomplete(messages, **kwargs)

        # Fallback to synchronous completion
        return self.complete(messages, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """
        Forward attribute access to provider.

        Args:
            name: Attribute name

        Returns:
            Provider attribute value

        Raises:
            AttributeError: If attribute not found
        """
        # Initialize provider if needed
        if self._provider is None:
            _ = self.provider

        # Forward to provider
        if hasattr(self._provider, name):
            return getattr(self._provider, name)

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")
