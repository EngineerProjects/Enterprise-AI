"""
LLM Helper for Enterprise AI Tools.

This module provides helper functions for tools that need to interact with LLMs
using the new LLM module structure.
"""

from typing import Any, Dict, List, Optional, Union

from enterprise_ai.llm import complete, LLMProvider, create_provider
from enterprise_ai.schema import Message, CompletionOptions
from enterprise_ai.logger import get_logger

logger = get_logger("tool.llm_helper")


class LLMHelper:
    """
    Helper class for tools that need LLM functionality.
    
    This provides a simple interface for tools to interact with LLMs
    without needing to manage provider details.
    """
    
    def __init__(
        self, 
        provider_name: str = "ollama",
        model_name: Optional[str] = None,
        default_options: Optional[CompletionOptions] = None
    ):
        """
        Initialize the LLM helper.
        
        Args:
            provider_name: Name of the LLM provider to use
            model_name: Optional specific model name
            default_options: Default completion options
        """
        self.provider_name = provider_name
        self.model_name = model_name
        self.default_options = default_options or CompletionOptions()
        self._provider: Optional[LLMProvider] = None
    
    def _get_provider(self) -> LLMProvider:
        """Get or create the LLM provider."""
        if self._provider is None:
            if self.model_name:
                self._provider = create_provider(self.provider_name, self.model_name)
            else:
                self._provider = create_provider(self.provider_name)
        return self._provider
    
    async def complete(
        self, 
        messages: Union[List[Message], List[str], str],
        options: Optional[CompletionOptions] = None,
        **kwargs: Any
    ) -> Message:
        """
        Generate a completion using the configured LLM.
        
        Args:
            messages: Messages to send to the LLM
            options: Optional completion options
            **kwargs: Additional parameters
            
        Returns:
            Generated message
        """
        # Ensure messages is a list
        if isinstance(messages, str):
            messages = [messages]
        
        # Convert strings to Messages if needed
        processed_messages = []
        for msg in messages:
            if isinstance(msg, str):
                processed_messages.append(Message.user_message(msg))
            else:
                processed_messages.append(msg)
        
        # Use provided options or defaults
        completion_options = options or self.default_options
        
        # Generate completion
        result = complete(
            messages=processed_messages,
            provider_name=self.provider_name,
            model_name=self.model_name,
            options=completion_options,
            **kwargs
        )
        
        return result
    
    async def complete_text(
        self, 
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[CompletionOptions] = None,
        **kwargs: Any
    ) -> str:
        """
        Generate a text completion from a simple prompt.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            options: Optional completion options
            **kwargs: Additional parameters
            
        Returns:
            Generated text content
        """
        messages = []
        
        if system_prompt:
            messages.append(Message.system_message(system_prompt))
        
        messages.append(Message.user_message(prompt))
        
        result = await self.complete(messages, options, **kwargs)
        
        # Extract text content
        if hasattr(result, 'content'):
            return result.content
        else:
            return str(result)


# Convenience function for simple LLM usage in tools
async def simple_llm_complete(
    prompt: str,
    system_prompt: Optional[str] = None,
    provider: str = "ollama",
    model: Optional[str] = None,
    **kwargs: Any
) -> str:
    """
    Simple function for tools to get LLM completions.
    
    Args:
        prompt: User prompt
        system_prompt: Optional system prompt
        provider: LLM provider name
        model: Optional model name
        **kwargs: Additional parameters
        
    Returns:
        Generated text
    """
    helper = LLMHelper(provider, model)
    return await helper.complete_text(prompt, system_prompt, **kwargs)