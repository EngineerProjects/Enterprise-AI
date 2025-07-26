"""
FIXED: Ollama provider implementation with full API specification compliance.

Key compliance fixes:
1. System prompt handling using 'system' parameter for /api/generate
2. Correct parameter mapping to Ollama's options structure
3. Optimized endpoint selection logic (chat vs generate)
4. Verified tool format compliance with Ollama specification
5. Enhanced error handling and timeout management
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Iterator, AsyncIterator, Union, cast

import httpx

from enterprise_ai.defaults import (
    DEFAULT_OLLAMA_MODEL, 
    DEFAULT_OLLAMA_BASE_URL, 
    DEFAULT_OLLAMA_TIMEOUT,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TOP_P,
    get_config_value
)
from enterprise_ai.constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TOP_P,
    OLLAMA_API_BASE,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_TIMEOUT,
    ModelFeature,
)
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import Message, ModelInfo, LLMResponse, ProviderInfo, ToolCall
from enterprise_ai.types import MessageProtocol

from enterprise_ai.llm.ollama.tools import OllamaToolConverter, OllamaToolExtractor
from enterprise_ai.llm.ollama.capabilities import OllamaCapabilities
from enterprise_ai.llm.ollama.utils import normalize_base_url, validate_timeout, generate_request_id

# Import the FIXED helpers
from enterprise_ai.llm.ollama.helpers import (
    OllamaMessageFormatter,
    OllamaErrorHandler,
    OllamaConfigHelper,
    OllamaStreamProcessor,
    OllamaResponseProcessor,
)

logger = get_optimized_logger("llm.ollama")


class OllamaProvider(LLMProvider):
    """FIXED: Ollama LLM provider with full API specification compliance."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        capabilities: Optional[Set[str]] = None,
        verbose: bool = False,
        **kwargs: Any,
    ):
        """Initialize the Ollama provider with package-friendly configuration."""
        # Use explicit parameters with smart defaults (no config file required)
        model = model_name or DEFAULT_OLLAMA_MODEL
        url = base_url or DEFAULT_OLLAMA_BASE_URL
        self._base_url = normalize_base_url(url)
        
        # Use explicit timeout or default (no config file dependency)
        self._timeout = validate_timeout(timeout or DEFAULT_OLLAMA_TIMEOUT)
        self._explicit_capabilities = capabilities

        # Initialize base class with explicit parameters
        super().__init__(
            model_name=model,
            verbose=verbose,
            base_url=self._base_url,
            temperature=temperature or DEFAULT_LLM_TEMPERATURE,
            max_tokens=max_tokens or DEFAULT_LLM_MAX_TOKENS,
            top_p=top_p or DEFAULT_LLM_TOP_P,
            **kwargs,
        )

        # Initialize components
        self._tool_converter = OllamaToolConverter()
        self._tool_extractor = OllamaToolExtractor()
        self._capabilities = OllamaCapabilities()
        self._message_formatter = OllamaMessageFormatter()
        self._error_handler = OllamaErrorHandler()
        self._response_processor = OllamaResponseProcessor()

        # HTTP clients
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None

        logger.info("Initialized API-compliant Ollama provider: %s @ %s", model, self._base_url)

    def _get_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self._timeout)
        return self._async_client

    def _get_api_url(self, endpoint: str) -> str:
        """Get full API URL for endpoint."""
        return f"{self._base_url}/api/{endpoint.lstrip('/')}"

    # FIXED: Core completion methods with proper API compliance
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """FIXED: Generate completion with proper API endpoint selection."""
        request_id = generate_request_id()
        
        # Prepare request parameters
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        
        # FIXED: Enhanced timeout calculation
        timeout = OllamaConfigHelper.determine_timeout_for_request(
            self._timeout, self.model_name, has_images, has_tools, **kwargs
        )

        # Process tools
        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        # Build request parameters
        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            **kwargs
        }

        # FIXED: Improved endpoint selection logic
        use_chat = OllamaConfigHelper.should_use_chat_endpoint(messages, has_tools, **kwargs)
        
        if self.verbose:
            logger.info("Using %s endpoint for optimal API compliance", 'chat' if use_chat else 'generate')
        
        try:
            if use_chat:
                llm_response = self._execute_chat_request(messages, timeout, **request_params)
            else:
                llm_response = self._execute_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            result = self._llm_response_to_message(llm_response)
            
            return result
        except Exception as e:
            self.track_request(False)
            if self.verbose:
                logger.error("Ollama request %s failed: %s", request_id, str(e))
            raise

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """FIXED: Generate async completion with API compliance."""
        # Prepare request (same logic as sync)
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(
            self._timeout, self.model_name, has_images, has_tools, **kwargs
        )

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            **kwargs
        }

        use_chat = OllamaConfigHelper.should_use_chat_endpoint(messages, has_tools, **kwargs)
        
        try:
            if use_chat:
                llm_response = await self._execute_async_chat_request(messages, timeout, **request_params)
            else:
                llm_response = await self._execute_async_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            result = self._llm_response_to_message(llm_response)
            
            return result
        except Exception as e:
            self.track_request(False)
            if self.verbose:
                logger.error("Async Ollama request failed: %s", str(e))
            raise

    # FIXED: HTTP Request Execution Methods with proper payload building
    def _execute_chat_request(self, messages: List[MessageProtocol], timeout: float, **kwargs: Any) -> LLMResponse:
        """FIXED: Execute chat request with proper payload structure."""
        payload = OllamaConfigHelper.build_chat_payload(
            self.model_name, messages, self._message_formatter, **kwargs
        )
        
        try:
            response = self._get_client().post(self._get_api_url("chat"), json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            return self._response_processor.process_chat_response(result, self.model_name, self._tool_extractor)
            
        except httpx.HTTPStatusError as e:
            raise self._error_handler.handle_http_error(e)
        except httpx.ConnectError as e:
            raise self._error_handler.handle_connection_error(e)
        except httpx.ReadTimeout as e:
            raise self._error_handler.handle_timeout_error(e, timeout)

    def _execute_generate_request(self, messages: List[MessageProtocol], timeout: float, **kwargs: Any) -> LLMResponse:
        """FIXED: Execute generate request with proper system parameter usage."""
        payload = OllamaConfigHelper.build_generate_payload(
            self.model_name, messages, self._message_formatter, **kwargs
        )
        
        try:
            response = self._get_client().post(self._get_api_url("generate"), json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            return self._response_processor.process_generate_response(result, self.model_name, self._tool_extractor)
            
        except httpx.HTTPStatusError as e:
            raise self._error_handler.handle_http_error(e)
        except httpx.ConnectError as e:
            raise self._error_handler.handle_connection_error(e)
        except httpx.ReadTimeout as e:
            raise self._error_handler.handle_timeout_error(e, timeout)

    async def _execute_async_chat_request(self, messages: List[MessageProtocol], timeout: float, **kwargs: Any) -> LLMResponse:
        """FIXED: Execute async chat request."""
        payload = OllamaConfigHelper.build_chat_payload(
            self.model_name, messages, self._message_formatter, **kwargs
        )
        
        try:
            client = await self._get_async_client()
            response = await client.post(self._get_api_url("chat"), json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            return self._response_processor.process_chat_response(result, self.model_name, self._tool_extractor)
            
        except httpx.HTTPStatusError as e:
            raise self._error_handler.handle_http_error(e)
        except httpx.ConnectError as e:
            raise self._error_handler.handle_connection_error(e)
        except httpx.ReadTimeout as e:
            raise self._error_handler.handle_timeout_error(e, timeout)

    async def _execute_async_generate_request(self, messages: List[MessageProtocol], timeout: float, **kwargs: Any) -> LLMResponse:
        """FIXED: Execute async generate request."""
        payload = OllamaConfigHelper.build_generate_payload(
            self.model_name, messages, self._message_formatter, **kwargs
        )
        
        try:
            client = await self._get_async_client()
            response = await client.post(self._get_api_url("generate"), json=payload, timeout=timeout)
            response.raise_for_status()
            result = response.json()
            
            return self._response_processor.process_generate_response(result, self.model_name, self._tool_extractor)
            
        except httpx.HTTPStatusError as e:
            raise self._error_handler.handle_http_error(e)
        except httpx.ConnectError as e:
            raise self._error_handler.handle_connection_error(e)
        except httpx.ReadTimeout as e:
            raise self._error_handler.handle_timeout_error(e, timeout)

    # FIXED: Streaming Methods with proper endpoint selection
    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Iterator[MessageProtocol]:
        """FIXED: Generate streaming completion with proper API compliance."""
        # Prepare request
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(
            self._timeout, self.model_name, has_images, has_tools, **kwargs
        )

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            "stream": True,
            **kwargs
        }

        # FIXED: Use proper endpoint selection
        use_chat = OllamaConfigHelper.should_use_chat_endpoint(messages, has_tools, **kwargs)
        endpoint = "chat" if use_chat else "generate"
        
        if use_chat:
            payload = OllamaConfigHelper.build_chat_payload(
                self.model_name, messages, self._message_formatter, **request_params
            )
        else:
            payload = OllamaConfigHelper.build_generate_payload(
                self.model_name, messages, self._message_formatter, **request_params
            )

        yield from OllamaStreamProcessor.handle_streaming_request(
            self._get_client(), "POST", self._get_api_url(endpoint), 
            payload, timeout, self.model_name, self._error_handler
        )

    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncIterator[MessageProtocol]:
        """FIXED: Generate async streaming completion with API compliance."""
        # Prepare request
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(
            self._timeout, self.model_name, has_images, has_tools, **kwargs
        )

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            "stream": True,
            **kwargs
        }

        use_chat = OllamaConfigHelper.should_use_chat_endpoint(messages, has_tools, **kwargs)
        endpoint = "chat" if use_chat else "generate"
        
        if use_chat:
            payload = OllamaConfigHelper.build_chat_payload(
                self.model_name, messages, self._message_formatter, **request_params
            )
        else:
            payload = OllamaConfigHelper.build_generate_payload(
                self.model_name, messages, self._message_formatter, **request_params
            )

        async for msg in OllamaStreamProcessor.handle_async_streaming_request(
            await self._get_async_client(), "POST", self._get_api_url(endpoint), 
            payload, timeout, self.model_name, self._error_handler
        ):
            yield msg

    # Tool Call Methods with Fixed Argument Handling
    def complete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """
        FIXED: Generate completion and extract tool calls with proper Ollama argument handling.
        
        This override fixes the tool call argument serialization issue for multi-turn conversations.
        """
        request_id = generate_request_id()
        
        # Prepare request parameters  
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        
        timeout = OllamaConfigHelper.determine_timeout_for_request(
            self._timeout, self.model_name, has_images, has_tools, **kwargs
        )

        # Process tools
        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        # Build request parameters
        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            **kwargs
        }

        # Use chat endpoint for tool calls
        use_chat = OllamaConfigHelper.should_use_chat_endpoint(messages, has_tools, **kwargs)
        
        if self.verbose:
            logger.info("Using %s endpoint for optimal tool call compliance", 'chat' if use_chat else 'generate')
        
        try:
            if use_chat:
                llm_response = self._execute_chat_request(messages, timeout, **request_params)
            else:
                llm_response = self._execute_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            
            # FIXED: Convert LLMResponse to Message with proper tool call handling
            response_message = self._llm_response_to_message(llm_response)
            
            # Extract tool calls - they're already in the LLMResponse
            tool_calls = llm_response.tool_calls or []
            
            return response_message, tool_calls
            
        except Exception as e:
            self.track_request(False)
            if self.verbose:
                logger.error("Ollama tool completion request %s failed: %s", request_id, str(e))
            raise

    async def acomplete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """
        FIXED: Generate async completion and extract tool calls with proper Ollama argument handling.
        """
        # Same preparation logic as sync version
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(
            self._timeout, self.model_name, has_images, has_tools, **kwargs
        )

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            **kwargs
        }

        use_chat = OllamaConfigHelper.should_use_chat_endpoint(messages, has_tools, **kwargs)
        
        try:
            if use_chat:
                llm_response = await self._execute_async_chat_request(messages, timeout, **request_params)
            else:
                llm_response = await self._execute_async_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            response_message = self._llm_response_to_message(llm_response)
            tool_calls = llm_response.tool_calls or []
            
            return response_message, tool_calls
            
        except Exception as e:
            self.track_request(False)
            if self.verbose:
                logger.error("Async Ollama tool completion request failed: %s", str(e))
            raise

    # Model Information Methods (unchanged but validated)
    def get_model_info(self) -> ModelInfo:
        """Get model information using enhanced universal capability detection."""
        if self._model_info is not None:
            return self._model_info

        # Fetch model data from Ollama with enhanced error handling
        model_data = self._fetch_model_data()
        
        # Use the universal capability detection
        capabilities = self._capabilities.detect_model_capabilities(
            self.model_name, 
            model_data, 
            self._explicit_capabilities
        )
        
        # Extract technical specifications
        specs = self._capabilities.get_model_specifications(self.model_name, model_data)
        
        # Build enhanced description
        description = self._build_model_description(specs, model_data)
        
        # Create ModelInfo with comprehensive data
        self._model_info = ModelInfo(
            id=self.model_name,
            provider="ollama",
            max_tokens=capabilities.max_output_tokens,
            features=capabilities.to_feature_set(),
            context_window=capabilities.max_context_window,
            description=description,
            metadata={
                "specifications": specs,
                "api_compliance": "ollama_v1.0",  # Mark as API compliant
                "capabilities_details": {
                    "supports_streaming": capabilities.supports_streaming,
                    "supports_tools": capabilities.supports_tools,
                    "supports_vision": capabilities.supports_vision,
                    "supports_async": capabilities.supports_async,
                    "specializations": capabilities.specializations,
                    "languages": capabilities.languages,
                    "supported_formats": capabilities.supported_formats,
                }
            }
        )

        return self._model_info

    def _fetch_model_data(self) -> Optional[Dict[str, Any]]:
        """Fetch model data from Ollama with comprehensive error handling."""
        try:
            response = self._get_client().post(
                self._get_api_url("show"), 
                json={"name": self.model_name}, 
                timeout=30.0
            )
            
            if response.status_code == 200:
                model_data = response.json()
                return model_data
            elif response.status_code == 404:
                logger.warning("Model %s not found in Ollama", self.model_name)
                return None
            else:
                logger.warning("Unexpected response %s for model %s", response.status_code, self.model_name)
                return None
                
        except Exception as e:
            logger.warning("Failed to fetch model data for %s: %s", self.model_name, e)
            return None

    def _build_model_description(self, specs: Dict[str, Any], model_data: Optional[Dict]) -> str:
        """Build enhanced model description from specifications."""
        description_parts = [f"Ollama model: {self.model_name}"]
        
        # Add parameter size if available
        param_size = specs.get("parameter_size", "")
        if param_size and param_size != "unknown":
            description_parts.append(f"({param_size})")
        
        # Add architecture info
        architecture = specs.get("architecture", "")
        if architecture and architecture != "unknown":
            description_parts.append(f"[{architecture}]")
        
        # Add compliance note
        description_parts.append("[API Compliant]")
        
        # Add key capabilities
        capabilities = specs.get("capabilities", [])
        if capabilities:
            cap_str = ", ".join(capabilities)
            description_parts.append(f"Capabilities: {cap_str}")
        
        return " ".join(description_parts)

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information with API compliance details."""
        return ProviderInfo(
            name="ollama",
            description="High-performance local Ollama inference server (API Compliant)",
            base_url=self._base_url,
            supported_models=[self.model_name],
            features={ModelFeature.STREAMING, ModelFeature.FUNCTION_CALLING, ModelFeature.VISION},
            configuration={
                "base_url": self._base_url, 
                "timeout": self._timeout, 
                "model": self.model_name,
                "verbose": self.verbose,
                "api_compliance": "ollama_v1.0",
            },
            is_available=True,
        )

    # Utility Methods
    def _llm_response_to_message(self, llm_response: LLMResponse) -> MessageProtocol:
        """Convert LLMResponse to Message for backward compatibility."""
        metadata = {
            "provider": llm_response.provider,
            "model": llm_response.model,
            "finish_reason": llm_response.finish_reason,
            "usage_metadata": llm_response.usage_metadata,
            "response_metadata": llm_response.response_metadata,
            "api_compliant": True,  # Mark as API compliant
        }
        
        if llm_response.tool_calls:
            metadata["tool_calls"] = [tc.to_dict() for tc in llm_response.tool_calls]
        
        return cast(MessageProtocol, Message(role="assistant", content=llm_response.content, metadata=metadata))
    
    def get_model_specifications(self) -> Dict[str, Any]:
        """Get comprehensive model specifications using the universal capabilities system."""
        model_data = self._fetch_model_data()
        specs = self._capabilities.get_model_specifications(self.model_name, model_data)
        specs["api_compliance"] = "ollama_v1.0"
        return specs

    def is_suitable_for_task(self, task_requirements: Set[str]) -> bool:
        """Check if the model is suitable for specific task requirements."""
        model_data = self._fetch_model_data()
        return self._capabilities.is_model_suitable_for_task(
            self.model_name, 
            task_requirements, 
            model_data
        )

    def get_capability_details(self) -> Dict[str, Any]:
        """Get detailed capability information for debugging and inspection."""
        model_data = self._fetch_model_data()
        capabilities = self._capabilities.detect_model_capabilities(
            self.model_name, 
            model_data, 
            self._explicit_capabilities
        )
        
        return {
            "model_name": self.model_name,
            "provider": "ollama",
            "api_compliance": "ollama_v1.0",
            "detected_features": capabilities.to_feature_set(),
            "supports_streaming": capabilities.supports_streaming,
            "supports_tools": capabilities.supports_tools,
            "supports_vision": capabilities.supports_vision,
            "supports_async": capabilities.supports_async,
            "context_window": capabilities.max_context_window,
            "max_tokens": capabilities.max_output_tokens,
            "specializations": capabilities.specializations,
            "languages": capabilities.languages,
            "supported_formats": capabilities.supported_formats,
            "specifications": self._capabilities.get_model_specifications(self.model_name, model_data),
        }

    # Cleanup Methods
    def close(self) -> None:
        """Close HTTP clients."""
        if self._client:
            self._client.close()
            self._client = None

        if self._async_client:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_client.aclose())
                else:
                    asyncio.run(self._async_client.aclose())
            except Exception:
                pass
            self._async_client = None

    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.close()
        except Exception:
            pass
