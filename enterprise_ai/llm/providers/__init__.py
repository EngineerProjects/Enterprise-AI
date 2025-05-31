"""
LLM providers for Enterprise AI.

This module contains the provider implementations and registry.
"""

from enterprise_ai.llm.providers.registry import get_registry, register_provider

# Import provider classes to trigger registration
# This will automatically register them with the registry
available_providers = []

# Always import Ollama provider
try:
    from enterprise_ai.llm.providers.ollama import OllamaProvider
    available_providers.append("OllamaProvider")
except ImportError as e:
    import warnings
    warnings.warn(f"Ollama provider not available: {e}")

# Conditionally import OpenAI provider
try:
    from enterprise_ai.llm.providers.openai import OpenAIProvider
    available_providers.append("OpenAIProvider")
except ImportError as e:
    import warnings
    warnings.warn(f"OpenAI provider not available: {e}")

# Add other providers as they become available
# try:
#     from enterprise_ai.llm.providers.anthropic import AnthropicProvider
#     available_providers.append("AnthropicProvider")
# except ImportError:
#     pass

__all__ = [
    "get_registry",
    "register_provider",
] + available_providers
