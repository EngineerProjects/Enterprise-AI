"""
LLM functionality for Enterprise AI.

This module provides a high-level API for interacting with language models.
"""

from typing import List, Optional, Union, cast

from enterprise_ai.config import get_config
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.simple import LLM  # Import the LLM class
from enterprise_ai.llm.providers.factory import (
    create_provider,
    get_default_provider,
)  # Use correct imports
from enterprise_ai.schema import Message, CompletionOptions
from enterprise_ai.types import MessageProtocol


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
__all__ = [
    "complete",
    "create_provider",  # Changed from get_provider
    "get_default_provider",
    "LLMProvider",
    "LLM",  # Export LLM class
]
