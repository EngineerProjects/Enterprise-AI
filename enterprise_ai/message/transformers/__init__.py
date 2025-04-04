"""
Message transformer system for Enterprise AI.

This module provides functionality for transforming messages between Enterprise AI's
internal format and provider-specific formats required by different LLM backends.
"""

from enterprise_ai.message.transformers.base import (
    BaseTransformer,
    TransformerRegistry,
    transform_content_to_text_array,
    is_multimodal_content,
    map_role_name,
)

# Import provider-specific transformers to register them
# These will be implemented separately:
# from enterprise_ai.message.transformers.openai import OpenAITransformer
# from enterprise_ai.message.transformers.anthropic import AnthropicTransformer
# from enterprise_ai.message.transformers.ollama import OllamaTransformer

__all__ = [
    # Base classes
    "BaseTransformer",
    "TransformerRegistry",
    # Utility functions
    "transform_content_to_text_array",
    "is_multimodal_content",
    "map_role_name",
    # Provider transformers (to be added)
    "OpenAITransformer",
    "AnthropicTransformer",
    "OllamaTransformer",
]

# Convenience functions
transform = TransformerRegistry.transform
transform_batch = TransformerRegistry.transform_batch
register_transformer = TransformerRegistry.register
get_transformer = TransformerRegistry.get

# Add convenience functions to exports
__all__.extend(
    [
        "transform",
        "transform_batch",
        "register_transformer",
        "get_transformer",
    ]
)
