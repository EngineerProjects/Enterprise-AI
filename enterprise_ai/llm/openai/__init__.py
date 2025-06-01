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