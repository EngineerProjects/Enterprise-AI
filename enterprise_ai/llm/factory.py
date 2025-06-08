"""
Factory functions for Enterprise AI LLM providers.

This module provides factory functions for creating LLM provider instances
with appropriate configurations for the MCP-based architecture.
"""

from typing import Any, Dict, Optional, Set

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger

logger = get_logger("llm.factory")


def create_provider(
    provider_name: str, 
    model_name: str,
    verbose: bool = False,
    **kwargs: Any
) -> LLMProvider:
    """
    Create an LLM provider instance for the MCP-based architecture.

    Args:
        provider_name: Name of the provider ("ollama", "openai", etc.)
        model_name: Name of the model to use
        verbose: Whether to enable verbose logging
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
        return OllamaProvider(
            model_name=model_name, 
            verbose=verbose,
            **kwargs
        )
    elif provider_lower == "openai":
        from enterprise_ai.llm.openai import OpenAIProvider
        return OpenAIProvider(
            model_name=model_name,
            verbose=verbose,
            **kwargs
        )
    else:
        raise ValueError(f"Unsupported provider: {provider_name}")


def list_available_providers() -> Dict[str, str]:
    """
    List available LLM providers.

    Returns:
        Dictionary mapping provider names to descriptions
    """
    return {
        "ollama": "Local Ollama inference server with MCP integration",
        "openai": "OpenAI GPT models with MCP integration",
    }