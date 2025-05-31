"""
Ollama provider implementation.

Simple, clean tool calling without manual parsing or complex adapters.
"""

import json
import os
import asyncio
import threading
from typing import Any, Dict, List, Optional, Set, Union, cast, AsyncGenerator, Generator

import httpx

from enterprise_ai.config import get_config
from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    OLLAMA_API_BASE,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TIMEOUT,
    ModelFeature,
)
from enterprise_ai.exceptions import APIError, ModelNotFoundError
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.providers.registry import register_provider
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo
from enterprise_ai.schema.tool import TOOL_CHOICE_VALUES, TOOL_CHOICE_TYPE, ToolChoice
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.providers.ollama")


@register_provider("ollama")
class OllamaProvider(LLMProvider):
    """
    Ollama LLM provider with proper async/sync handling.
    
    Simplified tool calling and improved resource management.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ):
        """Initialize the Ollama provider."""
        # Get config values or use defaults
        model = model_name or get_config("llm.ollama.model", DEFAULT_OLLAMA_MODEL)
        url = base_url or get_config("llm.ollama.base_url", OLLAMA_API_BASE)

        # Normalize URL
        if url.endswith("/api"):
            url = url[:-4]
        if url.endswith("/"):
            url = url[:-1]

        # Set timeout
        env_timeout = os.environ.get("ENTERPRISE_AI_OLLAMA_TIMEOUT")
        if env_timeout:
            try:
                self._timeout = float(env_timeout)
            except ValueError:
                self._timeout = timeout or get_config("llm.ollama.timeout", DEFAULT_TIMEOUT)
        else:
            self._timeout = timeout or get_config("llm.ollama.timeout", DEFAULT_TIMEOUT)

        # Initialize base class
        super().__init__(
            model_name=model,
            base_url=url,
            temperature=temperature or get_config("llm.ollama.temperature", DEFAULT_TEMPERATURE),
            max_tokens=max_tokens or get_config("llm.ollama.max_tokens", DEFAULT_MAX_TOKENS),
            top_p=top_p or get_config("llm.ollama.top_p", DEFAULT_TOP_P),
            **kwargs,
        )

        # Initialize clients
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._client_lock = threading.Lock()
        self._async_client_lock = asyncio.Lock()
        self._closed = False

        logger.info(f"Initialized Ollama provider with model {model}")

    def _get_client(self) -> httpx.Client:
        """Get or create sync client safely."""
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(timeout=self._timeout)
        return self._client

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async client safely."""
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        if self._async_client is None:
            async with self._async_client_lock:
                if self._async_client is None:
                    self._async_client = httpx.AsyncClient(timeout=self._timeout)
        return self._async_client

    def _get_api_url(self, endpoint: str) -> str:
        """Get the full API URL for a given endpoint."""
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]
        return f"{self.config['base_url']}/api/{endpoint}"

    @staticmethod
    def format_messages(messages: List[Union[dict, MessageProtocol]]) -> List[dict]:
        """
        Format messages for Ollama API.
        
        Args:
            messages: List of messages
            
        Returns:
            List of formatted messages in Ollama format
        """
        formatted_messages = []

        for message in messages:
            # Convert Message objects to dictionaries
            if hasattr(message, 'to_dict'):
                message_dict = message.to_dict()
            elif isinstance(message, dict):
                message_dict = message
            else:
                raise TypeError(f"Unsupported message type: {type(message)}")

            # Basic message structure
            formatted_msg = {"role": message_dict["role"]}
            
            # Add content if present
            if "content" in message_dict and message_dict["content"] is not None:
                formatted_msg["content"] = message_dict["content"]

            # Add tool-specific fields
            if "tool_call_id" in message_dict and message_dict["tool_call_id"]:
                formatted_msg["tool_call_id"] = message_dict["tool_call_id"]
                
            if "name" in message_dict and message_dict["name"]:
                formatted_msg["name"] = message_dict["name"]

            # Add tool calls from metadata if present
            metadata = message_dict.get("metadata", {})
            if metadata and "tool_calls" in metadata:
                formatted_msg["tool_calls"] = metadata["tool_calls"]

            # Handle images in metadata
            if metadata and "images" in metadata and metadata["images"]:
                formatted_msg["images"] = metadata["images"]

            formatted_messages.append(formatted_msg)

        return formatted_messages

    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion using Ollama API (synchronous)."""
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        try:
            # Use sync client for sync completion
            formatted_messages = self.format_messages(messages)
            prompt = self._messages_to_prompt(formatted_messages)
            
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "temperature": kwargs.get("temperature", self.config.get("temperature")),
                "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens")),
                "top_p": kwargs.get("top_p", self.config.get("top_p")),
            }

            # Add images if present
            images = self._extract_images_from_messages(formatted_messages)
            if images:
                payload["images"] = images

            # Use sync client
            client = self._get_client()
            response = client.post(
                self._get_api_url("generate"),
                json=payload,
                timeout=kwargs.get("timeout", self._timeout)
            )

            if response.status_code != 200:
                self.track_request(False)
                if response.status_code == 404:
                    raise ModelNotFoundError(self.model_name)
                raise APIError(response.status_code, f"Ollama API error: {response.text}")

            result = response.json()
            self.track_request(True)

            content = result.get("response", "")
            return cast(MessageProtocol, Message(
                role="assistant",
                content=content,
                metadata={
                    "provider": "ollama",
                    "model": self.model_name,
                    "response_metadata": {k: v for k, v in result.items() if k not in ("response", "model")},
                },
            ))

        except httpx.ReadTimeout as e:
            self.track_request(False)
            logger.error(f"Request timed out: {e}")
            raise APIError(message=f"Request timed out after {kwargs.get('timeout', self._timeout)}s")
        except httpx.RequestError as e:
            self.track_request(False)
            logger.error(f"Request failed: {e}")
            raise APIError(message=f"Failed to connect to Ollama API: {e}")
        except Exception as e:
            self.track_request(False)
            logger.error(f"Completion failed: {e}")
            raise

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion asynchronously."""
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        # Check if tools are specified
        if "tools" in kwargs and kwargs["tools"]:
            # Use ask_tool for tool-enabled requests
            return await self.ask_tool(messages, **kwargs)
        
        # Regular completion without tools
        formatted_messages = self.format_messages(messages)
        prompt = self._messages_to_prompt(formatted_messages)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
        }

        # Add images if present
        images = self._extract_images_from_messages(formatted_messages)
        if images:
            payload["images"] = images

        # Get async client
        client = await self._get_async_client()

        try:
            response = await client.post(
                self._get_api_url("generate"),
                json=payload,
                timeout=kwargs.get("timeout", self._timeout)
            )

            if response.status_code != 200:
                self.track_request(False)
                if response.status_code == 404:
                    raise ModelNotFoundError(self.model_name)
                raise APIError(response.status_code, f"Ollama API error: {response.text}")

            result = response.json()
            self.track_request(True)

            content = result.get("response", "")
            return cast(MessageProtocol, Message(
                role="assistant",
                content=content,
                metadata={
                    "provider": "ollama",
                    "model": self.model_name,
                    "response_metadata": {k: v for k, v in result.items() if k not in ("response", "model")},
                },
            ))

        except httpx.ReadTimeout as e:
            self.track_request(False)
            logger.error(f"Request timed out: {e}")
            raise APIError(message=f"Request timed out after {kwargs.get('timeout', self._timeout)}s")
        except httpx.RequestError as e:
            self.track_request(False)
            logger.error(f"Request failed: {e}")
            raise APIError(message=f"Failed to connect to Ollama API: {e}")

    async def ask_tool(
        self,
        messages: List[MessageProtocol],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: TOOL_CHOICE_TYPE = ToolChoice.AUTO,
        timeout: int = 300,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Optional[MessageProtocol]:
        """
        Ask Ollama LLM using functions/tools.

        Args:
            messages: List of conversation messages
            tools: List of tools/functions available to the model
            tool_choice: Tool choice strategy
            timeout: Request timeout in seconds
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional completion arguments

        Returns:
            Assistant message with tool_calls in metadata, or None if failed
        """
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        try:
            # Validate tool_choice
            if tool_choice not in TOOL_CHOICE_VALUES and not isinstance(tool_choice, dict):
                raise ValueError(f"Invalid tool_choice: {tool_choice}")

            # Validate tools if provided
            if tools:
                for tool in tools:
                    if not isinstance(tool, dict) or "type" not in tool:
                        raise ValueError("Each tool must be a dict with 'type' field")

            # Format messages for Ollama
            formatted_messages = self.format_messages(messages)

            # Prepare request payload
            payload = {
                "model": self.model_name,
                "messages": formatted_messages,
                "stream": False,
                "options": {
                    "temperature": temperature or self.config.get("temperature"),
                    "num_predict": max_tokens or self.config.get("max_tokens"),
                    "top_p": self.config.get("top_p"),
                },
            }

            # Add tools if provided
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = tool_choice

            # Get async client
            client = await self._get_async_client()

            # Make API request to chat endpoint (for tool support)
            response = await client.post(
                self._get_api_url("chat"),
                json=payload,
                timeout=timeout
            )

            # Handle HTTP errors
            if response.status_code != 200:
                self.track_request(False)
                if response.status_code == 404:
                    raise ModelNotFoundError(self.model_name)
                raise APIError(response.status_code, f"Ollama API error: {response.text}")

            # Parse response
            result = response.json()
            self.track_request(True)

            # Extract message from response
            message_data = result.get("message", {})
            content = message_data.get("content", "")
            tool_calls = message_data.get("tool_calls", [])

            # Create metadata
            metadata = {
                "provider": "ollama",
                "model": self.model_name,
                "response_metadata": {k: v for k, v in result.items() if k not in ("message", "model")},
            }

            # Add tool calls to metadata if present
            if tool_calls:
                metadata["tool_calls"] = tool_calls

            # Return assistant message
            return cast(MessageProtocol, Message(
                role="assistant",
                content=content,
                metadata=metadata
            ))

        except Exception as e:
            self.track_request(False)
            logger.error(f"Error in ask_tool: {e}")
            raise

    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Generator[Any, None, None]:
        """Generate a streaming completion (synchronous)."""
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        # For streaming, we need to run the async version in a new thread with a new event loop
        def _run_async_stream():
            """Run async streaming in a separate thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Collect all chunks from async generator
                chunks = []
                async def collect_chunks():
                    async for chunk in self.acomplete_stream(messages, **kwargs):
                        chunks.append(chunk)
                
                loop.run_until_complete(collect_chunks())
                return chunks
            finally:
                # Clean up the loop
                try:
                    loop.close()
                except Exception:
                    pass

        # Run in thread and yield results
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(_run_async_stream)
            chunks = future.result()
            for chunk in chunks:
                yield chunk

    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncGenerator[Any, None]:
        """Generate an async streaming completion."""
        if self._closed:
            raise RuntimeError("Provider has been closed")
            
        formatted_messages = self.format_messages(messages)
        prompt = self._messages_to_prompt(formatted_messages)
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
        }

        # Add images if present
        images = self._extract_images_from_messages(formatted_messages)
        if images:
            payload["images"] = images

        # Get async client
        client = await self._get_async_client()

        try:
            async with client.stream(
                "POST",
                self._get_api_url("generate"),
                json=payload,
                timeout=kwargs.get("timeout", self._timeout)
            ) as response:
                if response.status_code != 200:
                    self.track_request(False)
                    if response.status_code == 404:
                        raise ModelNotFoundError(self.model_name)
                    raise APIError(response.status_code, f"Ollama API error: {await response.aread()}")

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            chunk_data = json.loads(line)
                            content = chunk_data.get("response", "")
                            if content:
                                # Create a message-like chunk
                                chunk = Message(
                                    role="assistant",
                                    content=content,
                                    metadata={
                                        "provider": "ollama",
                                        "model": self.model_name,
                                        "chunk": True,
                                        "done": chunk_data.get("done", False)
                                    }
                                )
                                yield chunk
                            
                            if chunk_data.get("done", False):
                                self.track_request(True)
                                break
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            self.track_request(False)
            logger.error(f"Streaming failed: {e}")
            raise

    def _messages_to_prompt(self, messages: List[dict]) -> str:
        """Convert messages to a single prompt string."""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            if role == "system":
                prompt += f"System: {content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"
            elif role == "tool":
                name = msg.get("name", "unknown")
                prompt += f"Tool ({name}): {content}\n\n"

        return prompt.rstrip()

    def _extract_images_from_messages(self, messages: List[dict]) -> List[str]:
        """Extract images from messages."""
        images = []
        for msg in messages:
            if "images" in msg and msg["images"]:
                images.extend(msg["images"])
        return images

    def get_model_info(self) -> ModelInfo:
        """Get information about the current model."""
        if self._model_info is not None:
            return self._model_info

        try:
            client = self._get_client()
            response = client.post(
                self._get_api_url("show"),
                json={"name": self.model_name},
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.warning(f"Failed to get model info for {self.model_name}")
                model_info = ModelInfo(
                    id=self.model_name,
                    provider="ollama",
                    max_tokens=DEFAULT_MAX_TOKENS,
                    features=set(),
                    context_window=4096,
                    description=f"Ollama model: {self.model_name}",
                )
                self._model_info = model_info
                return model_info

            model_data = response.json()

            # Detect model features
            features = set()

            # Check for vision capability
            if "vision" in self.model_name.lower() or "projector_info" in model_data:
                features.add(ModelFeature.VISION)
                features.add(ModelFeature.MULTI_MODAL)

            # Check for tool calling capability
            if "template" in model_data:
                template = model_data["template"]
                tool_patterns = ["tools", "tool_call", "function", "parameters"]
                if any(pattern in template for pattern in tool_patterns):
                    features.add(ModelFeature.FUNCTION_CALLING)

            # All Ollama models support streaming
            features.add(ModelFeature.STREAMING)

            # Code capability for code models
            if any(code_model in self.model_name.lower() for code_model in ["coder", "code", "starcoder"]):
                features.add(ModelFeature.CODE)

            # Extract context window
            context_window = 4096
            if "model_info" in model_data and "details" in model_data:
                for key, value in model_data.get("model_info", {}).items():
                    if "context_length" in key.lower() and isinstance(value, (int, float)):
                        context_window = int(value)
                        break

            # Parameter size
            parameter_size = "Unknown"
            if "details" in model_data and "parameter_size" in model_data["details"]:
                parameter_size = model_data["details"]["parameter_size"]

            description = f"Ollama model: {self.model_name} ({parameter_size})"

            model_info = ModelInfo(
                id=self.model_name,
                provider="ollama",
                max_tokens=min(DEFAULT_MAX_TOKENS, context_window // 2),
                features=features,
                context_window=context_window,
                description=description,
            )

            self._model_info = model_info
            return model_info

        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            model_info = ModelInfo(
                id=self.model_name,
                provider="ollama",
                max_tokens=DEFAULT_MAX_TOKENS,
                features={ModelFeature.STREAMING},
                context_window=4096,
                description=f"Ollama model: {self.model_name}",
            )
            self._model_info = model_info
            return model_info

    def close(self) -> None:
        """Close and cleanup provider resources."""
        if self._closed:
            return
            
        self._closed = True
        
        # Close sync client
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing sync client: {e}")
            finally:
                self._client = None

    async def aclose(self) -> None:
        """Async close and cleanup provider resources."""
        if self._closed:
            return
            
        self._closed = True
        
        # Close async client
        if self._async_client:
            try:
                await self._async_client.aclose()
            except Exception as e:
                logger.warning(f"Error closing async client: {e}")
            finally:
                self._async_client = None

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if not self._closed:
            self.close()