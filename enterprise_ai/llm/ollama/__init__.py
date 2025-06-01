"""
Ollama LLM provider package.

This package provides a high-performance Ollama implementation with comprehensive
tool support, async operations, streaming capabilities, and enhanced reliability.

Features:
- Fast HTTP-based communication
- Robust tool calling support extracted from official ollama-python
- Complete async/await support
- Streaming capabilities
- Automatic capability detection
- Comprehensive error handling
"""

from enterprise_ai.llm.ollama.ollama import OllamaProvider
from enterprise_ai.llm.ollama.tools import OllamaToolConverter, OllamaToolExtractor
from enterprise_ai.llm.ollama.capabilities import OllamaCapabilities
from enterprise_ai.llm.ollama.helpers import (
    OllamaMessageFormatter,
    OllamaErrorHandler,
    OllamaConfigHelper,
    OllamaStreamProcessor,
)

# Export main provider class
__all__ = [
    # Main provider
    "OllamaProvider",
    
    # Tool handling
    "OllamaToolConverter", 
    "OllamaToolExtractor",
    
    # Capabilities detection
    "OllamaCapabilities",
    
    # Helper classes
    "OllamaMessageFormatter",
    "OllamaErrorHandler", 
    "OllamaConfigHelper",
    "OllamaStreamProcessor",
]

# Provider metadata
PROVIDER_NAME = "ollama"
PROVIDER_DESCRIPTION = "High-performance local Ollama inference server"
DEFAULT_MODEL = "llama2"
SUPPORTED_FEATURES = [
    "streaming",
    "async", 
    "tools",
    "vision",
    "batch",
]