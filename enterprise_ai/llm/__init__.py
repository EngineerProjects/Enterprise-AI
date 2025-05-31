"""
LLM functionality for Enterprise AI.
"""

from typing import List, Optional, Union, cast

from enterprise_ai.config import get_config
from enterprise_ai.llm.base import LLMProvider, cleanup_all_providers, acleanup_all_providers
from enterprise_ai.llm.simple import LLM
from enterprise_ai.llm.factory import (
    create_provider,
    get_default_provider,
    list_available_providers,
)
from enterprise_ai.schema import Message, CompletionOptions
from enterprise_ai.types import MessageProtocol

from enterprise_ai.schema.tool import ToolCall, Function, ToolChoice
from enterprise_ai.schema.llm import LLMResponse

# Import production utilities
from enterprise_ai.llm.utils import (
    managed_provider,
    amanaged_provider,
    format_conversation,
    emergency_cleanup,
    aemergency_cleanup,
)


def complete(
    messages: List[Union[Message, str]],
    options: Optional[CompletionOptions] = None,
    provider: Optional[LLMProvider] = None,
) -> MessageProtocol:
    """Generate a completion for the given messages."""
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


__all__ = [
    # Core functionality
    "complete",
    "create_provider",
    "get_default_provider",
    "list_available_providers",
    "LLMProvider",
    "LLM",
    
    # Tool support
    "ToolCall",
    "Function",
    "ToolChoice", 
    "LLMResponse",
    
    # Resource management
    "cleanup_all_providers",
    "acleanup_all_providers",
    "emergency_cleanup",
    "aemergency_cleanup",
    
    # Production utilities
    "managed_provider",
    "amanaged_provider",
    "format_conversation",
    "emergency_cleanup",
    "aemergency_cleanup",
]
