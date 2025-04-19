"""
Provider registry system for Enterprise AI.

This module provides a registry for LLM providers, allowing
registration and retrieval of provider classes.
"""

import inspect
from typing import Any, Callable, Dict, List, Optional, Type, cast

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger

logger = get_logger("llm.registry")


class ProviderRegistry:
    """Registry for LLM providers."""

    _instance = None
    _providers: Dict[str, Type[LLMProvider]] = {}

    def __new__(cls) -> "ProviderRegistry":
        """Create a singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
        return cls._instance

    def register(self, name: str, provider_cls: Type[LLMProvider]) -> None:
        """
        Register a provider class with the registry.

        Args:
            name: Name to register under
            provider_cls: Provider class to register
        """
        self._providers[name.lower()] = provider_cls
        logger.info(f"Registered LLM provider: {name}")

    def unregister(self, name: str) -> bool:
        """
        Remove a provider from the registry.

        Args:
            name: Name of provider to remove

        Returns:
            True if provider was removed, False if not found
        """
        name = name.lower()
        if name in self._providers:
            del self._providers[name]
            logger.info(f"Unregistered provider: {name}")
            return True
        return False

    def get_provider_class(self, name: str) -> Optional[Type[LLMProvider]]:
        """
        Get a provider class by name.

        Args:
            name: Provider name (case insensitive)

        Returns:
            Provider class if found, None otherwise
        """
        return self._providers.get(name.lower())

    def list_providers(self) -> Dict[str, Type[LLMProvider]]:
        """
        Get all registered providers.

        Returns:
            Dictionary mapping provider names to classes
        """
        return self._providers.copy()


# Singleton registry instance
_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """
    Get the global provider registry instance.

    Returns:
        ProviderRegistry instance
    """
    return _registry


def register_provider(name: str) -> Callable[[Type[LLMProvider]], Type[LLMProvider]]:
    """
    Decorator to register a provider class.

    Args:
        name: Name to register under

    Returns:
        Decorator function
    """

    def decorator(cls: Type[LLMProvider]) -> Type[LLMProvider]:
        """Register the decorated class."""
        # Verify this is a valid provider class
        if not inspect.isclass(cls) or not issubclass(cls, LLMProvider):
            raise TypeError(f"Expected LLMProvider subclass, got {cls}")

        # Register the provider
        registry = get_registry()
        registry.register(name, cls)
        return cls

    return decorator
