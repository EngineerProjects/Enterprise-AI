"""
Provider implementations for Enterprise AI.

This module manages available LLM providers and provides functions
for accessing and registering them.
"""

from typing import Any, Dict, List, Optional, Type

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.providers.registry import ProviderRegistry, get_registry
from enterprise_ai.llm.providers.factory import (
    create_provider,
    get_default_provider,
    list_available_providers,
)
from enterprise_ai.logger import get_logger

logger = get_logger("llm.providers")

# Automatically import available providers
# Each provider will register itself via the registry decorator
try:
    from enterprise_ai.llm.providers.ollama import OllamaProvider  # noqa
except ImportError:
    logger.debug("Ollama provider not available")

# Add other provider imports as they become available
# try:
#     from enterprise_ai.llm.providers.openai_provider import OpenAIProvider  # noqa
# except ImportError:
#     logger.debug("OpenAI provider not available")
#
# try:
#     from enterprise_ai.llm.providers.anthropic_provider import AnthropicProvider  # noqa
# except ImportError:
#     logger.debug("Anthropic provider not available")

__all__ = [
    # Registry and factory classes
    "ProviderRegistry",
    "get_registry",
    # Provider management functions
    "create_provider",
    "get_default_provider",
    "list_available_providers",
    # Provider classes
    "OllamaProvider",
]
