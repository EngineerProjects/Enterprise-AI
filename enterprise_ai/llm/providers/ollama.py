"""
Ollama provider implementation.

This module provides an LLM provider for the Ollama API.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Set, Iterator, AsyncIterator

import httpx

from enterprise_ai.config import get_config
from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE, 
    DEFAULT_MAX_TOKENS, 
    DEFAULT_TOP_P,
    OLLAMA_API_BASE,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TIMEOUT,
    ModelFeature
)
from enterprise_ai.exceptions import APIError, ModelNotFoundError
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.providers.ollama")

class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider.
    
    This provider interfaces with the Ollama API for local LLM inference,
    automatically detecting model capabilities.
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        **kwargs: Any
    ):
        """
        Initialize the Ollama provider.
        
        Args:
            model_name: Name of the model to use
            base_url: Ollama base URL (with or without /api)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            timeout: HTTP request timeout in seconds
            **kwargs: Additional parameters
        """
        # Get config values or use defaults
        model = model_name or get_config("llm.ollama.model", DEFAULT_OLLAMA_MODEL)
        url = base_url or get_config("llm.ollama.base_url", OLLAMA_API_BASE)
        
        # Normalize the base URL to ensure consistent format
        # We work with base_url without trailing /api
        if url.endswith("/api"):
            url = url[:-4]
        if url.endswith("/"):
            url = url[:-1]
            
        # Set a reasonable timeout, defaulting to configuration value or DEFAULT_TIMEOUT
        default_timeout = get_config("llm.ollama.timeout", DEFAULT_TIMEOUT)
        self._timeout = timeout or default_timeout
        
        # Initialize base class
        super().__init__(
            model_name=model,
            base_url=url,
            temperature=temperature or get_config("llm.ollama.temperature", DEFAULT_TEMPERATURE),
            max_tokens=max_tokens or get_config("llm.ollama.max_tokens", DEFAULT_MAX_TOKENS),
            top_p=top_p or get_config("llm.ollama.top_p", DEFAULT_TOP_P),
            **kwargs
        )
        
        logger.info(f"Initialized Ollama provider with model {model}, timeout {self._timeout}s")
        
        # Cache for model info
        self._model_info = None
        
        # Create HTTP clients with configured timeout
        self._client = httpx.Client(timeout=self._timeout)
        self._async_client = None  # Lazy initialization for async client
    
    def __del__(self):
        """Clean up resources when the provider is deleted."""
        if hasattr(self, '_client') and self._client:
            self._client.close()
        if hasattr(self, '_async_client') and self._async_client:
            # We can't await close() in __del__, but we can ensure it's closed
            self._async_client.aclose()

    def _get_api_url(self, endpoint: str) -> str:
        """
        Get the full API URL for a given endpoint.
        
        Args:
            endpoint: API endpoint (e.g., 'chat', 'show')
            
        Returns:
            Full API URL
        """
        # Ensure endpoint doesn't start with a slash
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        
        return f"{self.config['base_url']}/api/{endpoint}"

    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion using Ollama API.
        
        Args:
            messages: List of messages
            **kwargs: Additional parameters for the completion
            
        Returns:
            Generated message
            
        Raises:
            APIError: If there's an issue with the API request
            ModelNotFoundError: If the model is not found
        """
        # Get request timeout - allow override via kwargs or use the instance default
        request_timeout = kwargs.pop("timeout", self._timeout)
        
        # Check if this is a vision model or if any message contains images
        has_images = False
        for msg in messages:
            if hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata:
                has_images = True
                break
        
        # If this is a vision model or images are included, increase timeout if needed
        if "vision" in self.model_name.lower() or has_images:
            # For vision tasks, use a longer timeout (at least 120 seconds)
            vision_timeout = max(request_timeout, 120.0)
            logger.debug(f"Using extended timeout ({vision_timeout}s) for vision model or image input")
            request_timeout = vision_timeout
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": [self._format_message(msg) for msg in messages],
            "stream": False,
            "temperature": kwargs.get("temperature", self.config.get("temperature", DEFAULT_TEMPERATURE)),
            "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens", DEFAULT_MAX_TOKENS)),
            "top_p": kwargs.get("top_p", self.config.get("top_p", DEFAULT_TOP_P)),
        }
        
        # Add any extra parameters
        for key, value in kwargs.items():
            if key not in payload and key not in ("stream", "timeout"):
                payload[key] = value
        
        # Make the API request
        logger.debug(f"Sending request to Ollama API: {self.model_name} with timeout {request_timeout}s")
        try:
            response = self._client.post(
                self._get_api_url("chat"),
                json=payload,
                timeout=request_timeout  # Use the determined timeout
            )
            
            # Handle HTTP errors
            if response.status_code != 200:
                self.track_request(False)
                if response.status_code == 404:
                    raise ModelNotFoundError(self.model_name)
                raise APIError(
                    response.status_code,
                    f"Ollama API error: {response.text}"
                )
                
            # Parse the response
            result = response.json()
            self.track_request(True)
            
            # Create and return the assistant message
            content = result.get("message", {}).get("content", "")
            return Message(
                role="assistant",
                content=content,
                metadata={
                    "provider": "ollama",
                    "model": self.model_name,
                    "response_metadata": {
                        key: value for key, value in result.items()
                        if key != "message"
                    }
                }
            )
            
        except httpx.ReadTimeout as e:
            self.track_request(False)
            logger.error(f"Request to Ollama API timed out after {request_timeout}s: {e}")
            raise APIError(message=f"Request to Ollama API timed out after {request_timeout}s. Your model may require more processing time. Try increasing the timeout value.")
        
        except httpx.RequestError as e:
            self.track_request(False)
            logger.error(f"Request to Ollama API failed: {e}")
            raise APIError(message=f"Failed to connect to Ollama API: {e}")
    
    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Iterator[MessageProtocol]:
        """
        Generate a streaming completion for the given messages.
        
        Args:
            messages: List of messages to generate a completion for
            **kwargs: Additional parameters for the completion
            
        Returns:
            Iterator of partial completion messages
        """
        # Get request timeout - allow override via kwargs or use the instance default
        request_timeout = kwargs.pop("timeout", self._timeout)
        
        # Check for vision model or images
        has_images = False
        for msg in messages:
            if hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata:
                has_images = True
                break
        
        # For vision models or images, use a longer timeout
        if "vision" in self.model_name.lower() or has_images:
            vision_timeout = max(request_timeout, 120.0)
            logger.debug(f"Using extended timeout ({vision_timeout}s) for vision model streaming")
            request_timeout = vision_timeout
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": [self._format_message(msg) for msg in messages],
            "stream": True,
            "temperature": kwargs.get("temperature", self.config.get("temperature", DEFAULT_TEMPERATURE)),
            "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens", DEFAULT_MAX_TOKENS)),
            "top_p": kwargs.get("top_p", self.config.get("top_p", DEFAULT_TOP_P)),
        }
        
        # Make the API request
        logger.debug(f"Sending streaming request to Ollama API: {self.model_name} with timeout {request_timeout}s")
        try:
            with self._client.stream(
                "POST",
                self._get_api_url("chat"),
                json=payload,
                timeout=request_timeout  # Use the determined timeout
            ) as response:
                # Handle HTTP errors
                if response.status_code != 200:
                    self.track_request(False)
                    if response.status_code == 404:
                        raise ModelNotFoundError(self.model_name)
                    raise APIError(
                        response.status_code,
                        f"Ollama API error: {response.text}"
                    )
                
                # Track the request as successful
                self.track_request(True)
                
                # Process the streaming response
                content_buffer = ""
                
                for chunk in response.iter_lines():
                    if not chunk:
                        continue
                    
                    try:
                        chunk_data = json.loads(chunk)
                        if "message" in chunk_data:
                            # Extract the content from the chunk
                            chunk_content = chunk_data["message"].get("content", "")
                            content_buffer += chunk_content
                            
                            # Create a partial message for this chunk
                            yield Message(
                                role="assistant",
                                content=content_buffer,
                                metadata={
                                    "provider": "ollama",
                                    "model": self.model_name,
                                    "is_partial": True,
                                }
                            )
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse streaming chunk: {e}")
                        continue
                
                # Final message with complete content
                yield Message(
                    role="assistant",
                    content=content_buffer,
                    metadata={
                        "provider": "ollama",
                        "model": self.model_name,
                        "is_partial": False,
                    }
                )
        
        except httpx.ReadTimeout as e:
            self.track_request(False)
            logger.error(f"Streaming request to Ollama API timed out after {request_timeout}s: {e}")
            raise APIError(message=f"Streaming request to Ollama API timed out after {request_timeout}s. Try increasing the timeout value.")
        
        except httpx.RequestError as e:
            self.track_request(False)
            logger.error(f"Streaming request to Ollama API failed: {e}")
            raise APIError(message=f"Failed to connect to Ollama API: {e}")
    
    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """
        Generate a completion asynchronously.
        
        Args:
            messages: List of messages to generate a completion for
            **kwargs: Additional parameters for the completion
            
        Returns:
            Completion message
        """
        # Get request timeout - allow override via kwargs or use the instance default
        request_timeout = kwargs.pop("timeout", self._timeout)
        
        # Check for vision model or images
        has_images = False
        for msg in messages:
            if hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata:
                has_images = True
                break
        
        # For vision models or images, use a longer timeout
        if "vision" in self.model_name.lower() or has_images:
            vision_timeout = max(request_timeout, 120.0)
            logger.debug(f"Using extended timeout ({vision_timeout}s) for async vision model request")
            request_timeout = vision_timeout
        
        # Initialize async client if needed
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=request_timeout)
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": [self._format_message(msg) for msg in messages],
            "stream": False,
            "temperature": kwargs.get("temperature", self.config.get("temperature", DEFAULT_TEMPERATURE)),
            "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens", DEFAULT_MAX_TOKENS)),
            "top_p": kwargs.get("top_p", self.config.get("top_p", DEFAULT_TOP_P)),
        }
        
        # Add any extra parameters
        for key, value in kwargs.items():
            if key not in payload and key not in ("stream", "timeout"):
                payload[key] = value
        
        # Make the API request
        logger.debug(f"Sending async request to Ollama API: {self.model_name} with timeout {request_timeout}s")
        try:
            response = await self._async_client.post(
                self._get_api_url("chat"),
                json=payload,
                timeout=request_timeout  # Use the determined timeout
            )
            
            # Handle HTTP errors
            if response.status_code != 200:
                self.track_request(False)
                if response.status_code == 404:
                    raise ModelNotFoundError(self.model_name)
                raise APIError(
                    response.status_code,
                    f"Ollama API error: {response.text}"
                )
                
            # Parse the response
            result = response.json()
            self.track_request(True)
            
            # Create and return the assistant message
            content = result.get("message", {}).get("content", "")
            return Message(
                role="assistant",
                content=content,
                metadata={
                    "provider": "ollama",
                    "model": self.model_name,
                    "response_metadata": {
                        key: value for key, value in result.items()
                        if key != "message"
                    }
                }
            )
            
        except httpx.ReadTimeout as e:
            self.track_request(False)
            logger.error(f"Async request to Ollama API timed out after {request_timeout}s: {e}")
            raise APIError(message=f"Async request to Ollama API timed out after {request_timeout}s. Try increasing the timeout value.")
        
        except httpx.RequestError as e:
            self.track_request(False)
            logger.error(f"Async request to Ollama API failed: {e}")
            raise APIError(message=f"Failed to connect to Ollama API: {e}")
    
    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncIterator[MessageProtocol]:
        """
        Generate a streaming completion asynchronously.
        
        Args:
            messages: List of messages to generate a completion for
            **kwargs: Additional parameters for the completion
            
        Returns:
            Async iterator of partial completion messages
        """
        # Get request timeout - allow override via kwargs or use the instance default
        request_timeout = kwargs.pop("timeout", self._timeout)
        
        # Check for vision model or images
        has_images = False
        for msg in messages:
            if hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata:
                has_images = True
                break
        
        # For vision models or images, use a longer timeout
        if "vision" in self.model_name.lower() or has_images:
            vision_timeout = max(request_timeout, 120.0)
            logger.debug(f"Using extended timeout ({vision_timeout}s) for async streaming vision model request")
            request_timeout = vision_timeout
        
        # Initialize async client if needed
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=request_timeout)
        
        # Prepare request payload
        payload = {
            "model": self.model_name,
            "messages": [self._format_message(msg) for msg in messages],
            "stream": True,
            "temperature": kwargs.get("temperature", self.config.get("temperature", DEFAULT_TEMPERATURE)),
            "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens", DEFAULT_MAX_TOKENS)),
            "top_p": kwargs.get("top_p", self.config.get("top_p", DEFAULT_TOP_P)),
        }
        
        # Make the API request
        logger.debug(f"Sending async streaming request to Ollama API: {self.model_name} with timeout {request_timeout}s")
        try:
            async with self._async_client.stream(
                "POST",
                self._get_api_url("chat"),
                json=payload,
                timeout=request_timeout  # Use the determined timeout
            ) as response:
                # Handle HTTP errors
                if response.status_code != 200:
                    self.track_request(False)
                    if response.status_code == 404:
                        raise ModelNotFoundError(self.model_name)
                    raise APIError(
                        response.status_code,
                        f"Ollama API error: {response.text}"
                    )
                
                # Track the request as successful
                self.track_request(True)
                
                # Process the streaming response
                content_buffer = ""
                
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    
                    try:
                        chunk_data = json.loads(line)
                        if "message" in chunk_data:
                            # Extract the content from the chunk
                            chunk_content = chunk_data["message"].get("content", "")
                            content_buffer += chunk_content
                            
                            # Create a partial message for this chunk
                            yield Message(
                                role="assistant",
                                content=content_buffer,
                                metadata={
                                    "provider": "ollama",
                                    "model": self.model_name,
                                    "is_partial": True,
                                }
                            )
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse streaming chunk: {e}")
                        continue
                
                # Final message with complete content
                yield Message(
                    role="assistant",
                    content=content_buffer,
                    metadata={
                        "provider": "ollama",
                        "model": self.model_name,
                        "is_partial": False,
                    }
                )
        
        except httpx.ReadTimeout as e:
            self.track_request(False)
            logger.error(f"Async streaming request to Ollama API timed out after {request_timeout}s: {e}")
            raise APIError(message=f"Async streaming request to Ollama API timed out after {request_timeout}s. Try increasing the timeout value.")
        
        except httpx.RequestError as e:
            self.track_request(False)
            logger.error(f"Streaming request to Ollama API failed: {e}")
            raise APIError(message=f"Failed to connect to Ollama API: {e}")
    
    def get_model_info(self) -> ModelInfo:
        """
        Get information about the current model.
        
        Returns:
            ModelInfo object with detected capabilities
        """
        # Use cached info if available
        if self._model_info is not None:
            return self._model_info
        
        try:
            # Get model details
            response = self._client.post(
                self._get_api_url("show"),
                json={"name": self.model_name},
                timeout=30.0  # Use a separate timeout for metadata requests
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to get model info for {self.model_name}: {response.status_code}")
                # Return basic model info with defaults
                self._model_info = ModelInfo(
                    id=self.model_name,
                    provider="ollama",
                    max_tokens=DEFAULT_MAX_TOKENS,
                    features=set(),
                    context_window=4096,  # Default conservative estimate
                    description=f"Ollama model: {self.model_name}"
                )
                return self._model_info
            
            model_data = response.json()
            
            # Detect model features
            features = set()
            
            # Detect vision capability
            vision_capable = False
            if "vision" in self.model_name.lower():
                vision_capable = True
            elif "projector_info" in model_data:
                vision_capable = True
            elif "details" in model_data and "families" in model_data["details"]:
                families = model_data["details"]["families"]
                if isinstance(families, list) and any("clip" in str(f).lower() for f in families):
                    vision_capable = True
            
            if vision_capable:
                features.add(ModelFeature.VISION)
                features.add(ModelFeature.MULTI_MODAL)
            
            # Detect tool/function calling capability
            tools_capable = False
            if "template" in model_data:
                template = model_data["template"]
                # Check for common tool/function calling template patterns
                tool_patterns = [
                    "tools", 
                    "tool_call", 
                    "ToolCalls",
                    "function", 
                    "\"name\": \"",  # JSON pattern for function calling
                    "parameters",
                    "available_tools",
                    "tool_response"
                ]
                if any(pattern in template for pattern in tool_patterns):
                    tools_capable = True
            
            if tools_capable:
                features.add(ModelFeature.FUNCTION_CALLING)
            
            # All Ollama models support streaming
            features.add(ModelFeature.STREAMING)
            
            # Add code capability for code-focused models
            if any(code_model in self.model_name.lower() for code_model in 
                  ["coder", "code", "starcoder", "wizard-coder", "phind-codellama"]):
                features.add(ModelFeature.CODE)
            
            # Extract context length based on model family
            context_window = 4096  # Default conservative estimate
            if "model_info" in model_data and "details" in model_data:
                family = model_data["details"].get("family", "")
                if family:
                    context_length_key = f"{family}.context_length"
                    if context_length_key in model_data.get("model_info", {}):
                        context_window = model_data["model_info"][context_length_key]
            
            # Get parameter size
            parameter_size = model_data.get("details", {}).get("parameter_size", "Unknown")
            description = f"Ollama model: {self.model_name} ({parameter_size})"
            
            # Create and cache model info
            self._model_info = ModelInfo(
                id=self.model_name,
                provider="ollama",
                max_tokens=min(DEFAULT_MAX_TOKENS, context_window // 2),  # Conservative estimate
                features=features,
                context_window=context_window,
                description=description
            )
            
            return self._model_info
            
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            # Return basic model info with defaults
            self._model_info = ModelInfo(
                id=self.model_name,
                provider="ollama",
                max_tokens=DEFAULT_MAX_TOKENS,
                features={ModelFeature.STREAMING},  # Assume at least streaming is supported
                context_window=4096,  # Default conservative estimate
                description=f"Ollama model: {self.model_name}"
            )
            return self._model_info
    
    def _format_message(self, message: MessageProtocol) -> Dict[str, Any]:
        """
        Format a message for Ollama API.
        
        Args:
            message: Message to format
            
        Returns:
            Formatted message dictionary
        """
        result = {"role": message.role}
        
        if message.content is not None:
            result["content"] = message.content
            
        if message.name is not None:
            result["name"] = message.name
            
        # Handle images in metadata
        if hasattr(message, "metadata") and message.metadata:
            if "images" in message.metadata and message.metadata["images"]:
                # Add the first image to the message
                # In a more complete implementation, we'd handle multiple images properly
                result["images"] = message.metadata["images"]
        
        return result