"""
Shared error handling utilities for Enterprise AI LLM providers.

CREATED: New shared module to eliminate error handling duplication
across Ollama, OpenAI, and future LLM providers.
"""

import httpx
from typing import Any, Dict, Optional

from enterprise_ai.exceptions import APIError, ModelNotFoundError, TokenLimitExceeded
from enterprise_ai.logger import get_logger

logger = get_logger("llm.shared.errors")


class BaseErrorHandler:
    """Base error handler with common patterns for all LLM providers."""
    
    # Common HTTP status code mappings
    COMMON_STATUS_MESSAGES = {
        400: "Bad request - check parameters",
        401: "Authentication failed",
        403: "Access forbidden", 
        404: "Resource not found",
        422: "Validation error",
        429: "Rate limited",
        500: "Internal server error",
        502: "Bad gateway",
        503: "Service unavailable",
        504: "Gateway timeout"
    }
    
    @classmethod
    def handle_http_status_error(
        cls, 
        error: httpx.HTTPStatusError,
        provider_specific_messages: Optional[Dict[int, str]] = None
    ) -> Exception:
        """
        Handle HTTP status errors with provider-specific context.
        
        Args:
            error: HTTP status error from httpx
            provider_specific_messages: Provider-specific status code messages
            
        Returns:
            Appropriate Enterprise AI exception
        """
        status_code = error.response.status_code
        response_text = error.response.text
        
        # Check provider-specific messages first
        if provider_specific_messages and status_code in provider_specific_messages:
            base_message = provider_specific_messages[status_code]
        else:
            base_message = cls.COMMON_STATUS_MESSAGES.get(
                status_code, f"HTTP {status_code} error"
            )
        
        # Handle specific common cases
        if status_code == 404 and "model" in response_text.lower():
            return ModelNotFoundError(f"Model not found. {base_message}")
        
        if status_code == 422:
            return APIError(status_code, f"Validation failed: {response_text[:300]}")
        
        if status_code == 429:
            return APIError(status_code, f"Rate limited: {base_message}")
        
        # General error with truncated response
        full_message = f"{base_message}: {response_text[:500]}" if response_text else base_message
        return APIError(status_code, full_message)
    
    @classmethod
    def handle_connection_error(
        cls, 
        error: httpx.ConnectError, 
        provider_context: str = "service"
    ) -> Exception:
        """Handle connection errors with provider context."""
        return APIError(
            message=f"Failed to connect to {provider_context}. "
                   f"Please check if the service is running and accessible."
        )
    
    @classmethod
    def handle_timeout_error(
        cls, 
        error: httpx.ReadTimeout, 
        timeout: float,
        provider_recommendations: Optional[str] = None
    ) -> Exception:
        """Handle timeout errors with recommendations."""
        base_message = f"Request timed out after {timeout}s."
        
        if provider_recommendations:
            full_message = f"{base_message} {provider_recommendations}"
        else:
            full_message = f"{base_message} Consider increasing timeout for complex requests."
        
        return APIError(message=full_message)


class OllamaErrorHandler(BaseErrorHandler):
    """Ollama-specific error handler using shared base functionality."""
    
    OLLAMA_STATUS_MESSAGES = {
        404: "Model not found - use 'ollama pull <model>' to download",
        503: "Ollama service unavailable - may be starting up or overloaded"
    }
    
    @classmethod
    def handle_http_error(cls, error: httpx.HTTPStatusError) -> Exception:
        """Handle Ollama HTTP errors with specific context."""
        return cls.handle_http_status_error(error, cls.OLLAMA_STATUS_MESSAGES)
    
    @classmethod
    def handle_connection_error(cls, error: httpx.ConnectError) -> Exception:
        """Handle Ollama connection errors with troubleshooting."""
        return APIError(
            message="Failed to connect to Ollama server. "
                   "Troubleshooting steps:\n"
                   "1. Start Ollama: 'ollama serve'\n"
                   "2. Check if port 11434 is accessible\n"
                   "3. Verify OLLAMA_HOST environment variable"
        )
    
    @classmethod
    def handle_timeout_error(cls, error: httpx.ReadTimeout, timeout: float) -> Exception:
        """Handle Ollama timeout with model-specific recommendations."""
        recommendations = (
            "Recommendations:\n"
            "• Vision models: increase timeout to 120s+\n"
            "• Large models (70B+): increase timeout to 90s+\n"
            "• Tool calling: increase timeout to 60s+\n"
            "• Set ENTERPRISE_AI_OLLAMA_TIMEOUT environment variable"
        )
        return cls.handle_timeout_error(error, timeout, recommendations)


class OpenAIErrorHandler(BaseErrorHandler):
    """OpenAI-specific error handler using shared base functionality."""
    
    OPENAI_STATUS_MESSAGES = {
        401: "Authentication failed - check API key",
        429: "Rate limit exceeded - consider reducing request frequency",
        503: "OpenAI service temporarily unavailable"
    }
    
    @classmethod
    def handle_openai_error(cls, error: Exception) -> Exception:
        """Handle OpenAI SDK errors."""
        from openai import (
            APIError as OpenAIAPIError,
            AuthenticationError,
            RateLimitError,
            OpenAIError,
        )
        
        if isinstance(error, TokenLimitExceeded):
            return error
        elif isinstance(error, AuthenticationError):
            return APIError(401, "Authentication failed. Check API key.")
        elif isinstance(error, RateLimitError):
            return APIError(429, "Rate limit exceeded. Consider reducing request frequency.")
        elif isinstance(error, OpenAIAPIError):
            status_code = getattr(error, 'status_code', None)
            return APIError(status_code or 500, f"OpenAI API error: {error}")
        elif isinstance(error, OpenAIError):
            return APIError(message=f"OpenAI error: {error}")
        else:
            return APIError(message=f"Unexpected OpenAI error: {error}")
    
    @classmethod
    def handle_http_error(cls, error: httpx.HTTPStatusError) -> Exception:
        """Handle OpenAI HTTP errors with specific context."""
        return cls.handle_http_status_error(error, cls.OPENAI_STATUS_MESSAGES)


# Convenience functions for backward compatibility
def handle_ollama_error(error: Exception) -> Exception:
    """Handle Ollama errors using appropriate handler."""
    if isinstance(error, httpx.HTTPStatusError):
        return OllamaErrorHandler.handle_http_error(error)
    elif isinstance(error, httpx.ConnectError):
        return OllamaErrorHandler.handle_connection_error(error)
    elif isinstance(error, httpx.ReadTimeout):
        return OllamaErrorHandler.handle_timeout_error(error, 30.0)
    else:
        return APIError(message=f"Unexpected Ollama error: {error}")


def handle_openai_error(error: Exception) -> Exception:
    """Handle OpenAI errors using appropriate handler."""
    return OpenAIErrorHandler.handle_openai_error(error)
