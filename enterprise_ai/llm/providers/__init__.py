"""
LLM provider implementations.

This module manages the available LLM providers.
"""

from typing import Dict, Optional

from enterprise_ai.exceptions import ProviderNotSupportedError
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger

logger = get_logger("llm.providers")

# Provider registry
_providers: Dict[str, LLMProvider] = {}

def register_provider(name: str, provider: LLMProvider) -> None:
    """
    Register a provider.
    
    Args:
        name: Provider name
        provider: Provider instance
    """
    _providers[name.lower()] = provider
    logger.debug(f"Registered provider: {name}")

def get_provider(name: str) -> LLMProvider:
    """
    Get a provider by name.
    
    Args:
        name: Provider name
        
    Returns:
        Provider instance
        
    Raises:
        ProviderNotSupportedError: If the provider is not supported
    """
    name = name.lower()
    
    # Lazy import to avoid circular imports
    if name == "ollama" and name not in _providers:
        from enterprise_ai.llm.providers.ollama import OllamaProvider
        register_provider("ollama", OllamaProvider())
    
    if name not in _providers:
        raise ProviderNotSupportedError(name)
        
    return _providers[name]

# Export Ollama provider for direct imports
from enterprise_ai.llm.providers.ollama import OllamaProvider

__all__ = ["get_provider", "register_provider", "OllamaProvider"]