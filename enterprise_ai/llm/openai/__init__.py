"""
OpenAI LLM provider package.

This package provides a high-performance OpenAI implementation with comprehensive
tool support, async operations, streaming capabilities, and enhanced reliability.
Adapted from OpenManus patterns with Enterprise AI schema integration.

Features:
- OpenAI, Azure OpenAI, and AWS Bedrock support
- Robust tool calling with auto execution
- Complete async/await support
- Streaming capabilities
- Advanced token counting and limits
- Comprehensive error handling
"""

from enterprise_ai.llm.openai.openai import OpenAIProvider
from enterprise_ai.llm.openai.tools import OpenAIToolConverter
from enterprise_ai.llm.openai.helpers import (
    OpenAIMessageFormatter,
    OpenAIErrorHandler,
    OpenAIConfigHelper,
    TokenCounter,
)

# Export main provider class
__all__ = [
    # Main provider
    "OpenAIProvider",
    
    # Tool handling
    "OpenAIToolConverter",
    
    # Helper classes
    "OpenAIMessageFormatter",
    "OpenAIErrorHandler", 
    "OpenAIConfigHelper",
    "TokenCounter",
]

# Provider metadata
PROVIDER_NAME = "openai"
PROVIDER_DESCRIPTION = "OpenAI GPT models with Azure and AWS Bedrock support"
DEFAULT_MODEL = "gpt-4o-mini"
SUPPORTED_FEATURES = [
    "streaming",
    "async", 
    "tools",
    "vision",
    "reasoning",
]

# Model categories
REASONING_MODELS = ["o1", "o3-mini"]
MULTIMODAL_MODELS = [
    "gpt-4-vision-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]