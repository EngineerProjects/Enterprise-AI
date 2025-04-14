"""
Custom exception classes for Enterprise AI.

This module provides a detailed hierarchy of exception types for different error scenarios.
"""

class EnterpriseAIError(Exception):
    """Base exception for all Enterprise AI errors."""
    def __init__(self, message: str = "An error occurred in Enterprise AI") -> None:
        self.message = message
        super().__init__(self.message)

# Configuration errors
class ConfigError(EnterpriseAIError):
    """Error in configuration."""
    pass

class ConfigFileError(ConfigError):
    """Error loading configuration file."""
    pass

# LLM errors
class LLMError(EnterpriseAIError):
    """Base class for LLM-related errors."""
    pass

class ProviderNotSupportedError(LLMError):
    """Exception raised when a requested provider is not supported."""
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Provider not supported: {provider}")

class ModelNotFoundError(LLMError):
    """Exception raised when a model is not found."""
    def __init__(self, model: str) -> None:
        self.model = model
        super().__init__(f"Model not found: {model}")

class APIError(LLMError):
    """Exception raised when an API error occurs."""
    def __init__(self, status_code: int = None, message: str = None) -> None:
        self.status_code = status_code
        msg = f"API error occurred (status {status_code})" if status_code else "API error occurred"
        if message:
            msg = f"{msg}: {message}"
        super().__init__(msg)

class TokenLimitExceeded(LLMError):
    """Exception raised when the token limit is exceeded."""
    def __init__(self, model: str = None, message: str = None) -> None:
        self.model = model
        msg = message or f"Token limit exceeded for model {model}"
        super().__init__(msg)

class ModelCapabilityError(LLMError):
    """Exception raised when a model doesn't support a requested capability."""
    def __init__(self, model: str, capability: str) -> None:
        self.model = model
        self.capability = capability
        super().__init__(f"Model {model} does not support capability: {capability}")