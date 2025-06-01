"""
Factory functions for Enterprise AI LLM providers.

This module provides factory functions for creating LLM provider instances
with appropriate configurations.
"""

from typing import Any, Dict, Optional

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger

logger = get_logger("llm.factory")


def create_provider(provider_name: str, model_name: str, **kwargs: Any) -> LLMProvider:
    """
    Create an LLM provider instance.

    Args:
        provider_name: Name of the provider ("ollama", "openai", etc.)
        model_name: Name of the model to use
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider is not supported
        ImportError: If provider dependencies are not available
    """
    provider_lower = provider_name.lower()
    
    if provider_lower == "ollama":
        from enterprise_ai.llm.ollama import OllamaProvider
        return OllamaProvider(model_name=model_name, **kwargs)
    elif provider_lower == "openai":
        from enterprise_ai.llm.openai import OpenAIProvider
        return OpenAIProvider(model_name=model_name, **kwargs)
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


def list_available_providers() -> Dict[str, str]:
    """
    List available LLM providers.

    Returns:
        Dictionary mapping provider names to descriptions
    """
    return {
        "ollama": "Local Ollama inference server",
        "openai": "OpenAI GPT models with Azure and AWS support",
    }