"""
Factory functions for Enterprise AI LLM providers.

This module provides factory functions for creating LLM provider instances
with appropriate configurations.
"""

from typing import Any, Dict, List, Optional, Type, Union, cast

from enterprise_ai.config import get_config
from enterprise_ai.exceptions import ProviderNotSupportedError
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.providers.registry import get_registry
from enterprise_ai.logger import get_logger

logger = get_logger("llm.factory")


def create_provider(
    provider_name: str, model_name: Optional[str] = None, **kwargs: Any
) -> LLMProvider:
    """
    Create a provider instance with appropriate configuration.

    Args:
        provider_name: Name of the provider to create
        model_name: Name of the model to use (provider-dependent)
        **kwargs: Additional provider-specific parameters

    Returns:
        Provider instance

    Raises:
        ProviderNotSupportedError: If provider is not registered
    """
    registry = get_registry()
    provider_cls = registry.get_provider_class(provider_name.lower())

    if not provider_cls:
        logger.error(f"Provider not found: {provider_name}")
        raise ProviderNotSupportedError(provider_name)

    # Get provider configuration from settings
    provider_config = get_provider_config(provider_name.lower())

    # Merge configurations with kwargs taking precedence
    merged_config = {**provider_config, **kwargs}

    # Set model name if provided
    if model_name:
        merged_config["model_name"] = model_name

    # Create and return provider instance
    try:
        provider = provider_cls(**merged_config)
        logger.debug(f"Created provider: {provider_name}")
        return provider
    except Exception as e:
        logger.error(f"Failed to create provider {provider_name}: {e}")
        raise


def get_provider_config(provider_name: str) -> Dict[str, Any]:
    """
    Get configuration for a provider from settings.

    Args:
        provider_name: Provider name

    Returns:
        Provider configuration dictionary
    """
    # Get provider config from settings
    config = get_config(f"llm.providers.{provider_name}", {})

    # If no specific config, try general llm config
    if not config:
        config = get_config("llm", {})

    return dict(config)


def get_default_provider_name() -> str:
    """
    Get the default provider name from configuration.

    Returns:
        Default provider name
    """
    name = get_config("llm.default_provider", "ollama")
    return str(name).lower()


def get_default_provider(**kwargs: Any) -> LLMProvider:
    """
    Get the default provider instance.

    Args:
        **kwargs: Additional provider-specific parameters

    Returns:
        Default provider instance
    """
    provider_name = get_default_provider_name()
    return create_provider(provider_name, **kwargs)


def list_available_providers() -> List[str]:
    """
    Get list of available provider names.

    Returns:
        List of registered provider names
    """
    return list(get_registry().list_providers().keys())
