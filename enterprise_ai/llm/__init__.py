"""
LLM functionality for Enterprise AI.

This module provides a comprehensive framework for interacting with language models
through a clean, provider-agnostic interface with high-performance implementations.
"""

from typing import Any, Dict, List, Optional, Union, cast

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.factory import create_provider, list_available_providers
from enterprise_ai.schema import Message, ModelInfo, CompletionOptions
from enterprise_ai.types import MessageProtocol
from enterprise_ai.llm.tool_executor import ToolExecutor


def complete(
    messages: List[Union[Message, str]],
    provider_name: str = "ollama",
    model_name: Optional[str] = None,
    options: Optional[CompletionOptions] = None,
    **kwargs
) -> MessageProtocol:
    """
    Generate a completion for the given messages using specified provider.

    Args:
        messages: List of messages or strings (strings are converted to user messages)
        provider_name: Name of the provider to use ("ollama", "openai", etc.)
        model_name: Name of the model to use (provider default if None)
        options: Completion options (temperature, max_tokens, etc.)
        **kwargs: Additional provider-specific parameters

    Returns:
        Generated assistant message

    Example:
        >>> result = complete("Hello, how are you?", provider_name="ollama", model_name="llama2")
        >>> print(result.content)
    """
    # Convert strings to user messages
    processed_messages: List[MessageProtocol] = []
    for msg in messages:
        if isinstance(msg, str):
            processed_messages.append(cast(MessageProtocol, Message.user_message(msg)))
        else:
            processed_messages.append(cast(MessageProtocol, msg))

    # Create provider
    provider_kwargs = kwargs.copy()
    if model_name:
        provider = create_provider(provider_name, model_name, **provider_kwargs)
    else:
        provider = create_provider(provider_name, **provider_kwargs)

    # Build completion parameters
    completion_kwargs = {}
    if options:
        completion_kwargs.update({
            "temperature": options.temperature,
            "max_tokens": options.max_tokens,
            "top_p": options.top_p,
            **options.extra_params,
        })

    return provider.complete(processed_messages, **completion_kwargs)


def inspect_model_capabilities(
    model_name: str,
    provider_name: str = "ollama", 
    **kwargs
) -> Dict[str, Any]:
    """
    Inspect detailed capabilities of a model.
    
    Args:
        model_name: Name of the model to inspect
        provider_name: Provider name (default: "ollama")
        **kwargs: Additional provider parameters
        
    Returns:
        Detailed capability information
        
    Example:
        >>> caps = inspect_model_capabilities("llama3.2")
        >>> print(caps["detected_features"])
        >>> print(caps["context_window"])
    """
    provider = create_provider(provider_name, model_name, **kwargs)
    
    if hasattr(provider, 'get_capability_details'):
        return provider.get_capability_details()
    else:
        # Fallback for providers without detailed capability inspection
        model_info = provider.get_model_info()
        return {
            "model_name": model_name,
            "provider": provider_name,
            "detected_features": list(model_info.features),
            "context_window": model_info.context_window,
            "max_tokens": model_info.max_tokens,
            "description": model_info.description,
        }

# Add to __all__
__all__ = [
    # High-level API
    "complete",
    "inspect_model_capabilities",  # New function
    
    # Core classes
    "LLMProvider",
    
    # Factory functions
    "create_provider",
    "list_available_providers",
    
    # Schema classes (re-exported for convenience)
    "Message",
    "ModelInfo", 
    "CompletionOptions",
    "MessageProtocol",

    # Executor for Ollama tools
    "ToolExecutor",
]