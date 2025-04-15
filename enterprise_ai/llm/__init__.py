"""
LLM functionality for Enterprise AI.

This module provides a high-level API for interacting with language models.
"""

from typing import List, Optional, Union, cast

from enterprise_ai.config import get_config
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.providers import get_provider
from enterprise_ai.schema import Message, CompletionOptions
from enterprise_ai.types import MessageProtocol

# Default provider instance
_default_provider = None


def get_default_provider() -> LLMProvider:
    """
    Get the default LLM provider.

    Returns:
        Default provider instance
    """
    global _default_provider
    if _default_provider is None:
        provider_name = get_config("llm.default_provider", "ollama")
        _default_provider = get_provider(provider_name)
    return _default_provider


def complete(
    messages: List[Union[Message, str]],
    options: Optional[CompletionOptions] = None,
    provider: Optional[LLMProvider] = None,
) -> MessageProtocol:
    """
    Generate a completion for the given messages.

    Args:
        messages: List of messages or strings (strings are converted to user messages)
        options: Completion options
        provider: LLM provider to use (uses default if None)

    Returns:
        Generated assistant message
    """
    # Convert strings to user messages
    processed_messages: List[MessageProtocol] = []
    for msg in messages:
        if isinstance(msg, str):
            processed_messages.append(cast(MessageProtocol, Message.user_message(msg)))
        else:
            processed_messages.append(cast(MessageProtocol, msg))

    # Use specified provider or default
    llm_provider = provider or get_default_provider()

    # Get completion with options
    kwargs = {}
    if options:
        kwargs = {
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "top_p": options.top_p,
            **options.extra_params,
        }

    return llm_provider.complete(processed_messages, **kwargs)


# Export API
__all__ = ["complete", "get_provider", "get_default_provider", "LLMProvider"]
