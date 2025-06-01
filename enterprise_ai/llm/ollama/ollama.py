"""
Fast and reliable Ollama provider implementation with auto tool execution.

This implementation combines the speed of the old HTTP-based approach with
the reliability of enhanced tool handling, using schema classes for consistency.
Enhanced with autonomous tool execution capabilities for agent reasoning.
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Iterator, AsyncIterator, Union, cast, Callable

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
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, ModelInfo, LLMResponse, ProviderInfo, ToolCall
from enterprise_ai.types import MessageProtocol

from enterprise_ai.llm.ollama.tools import OllamaToolConverter, OllamaToolExtractor
from enterprise_ai.llm.ollama.capabilities import OllamaCapabilities
from enterprise_ai.llm.ollama.utils import normalize_base_url, validate_timeout, generate_request_id
from enterprise_ai.llm.ollama.helpers import (
    OllamaMessageFormatter,
    OllamaErrorHandler,
    OllamaConfigHelper,
    OllamaStreamProcessor,
    OllamaResponseProcessor,
)
from enterprise_ai.llm.tool_executor import ToolExecutor

logger = get_logger("llm.ollama")


class OllamaProvider(LLMProvider):
    """Fast and reliable Ollama LLM provider with autonomous tool execution capabilities."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        capabilities: Optional[Set[str]] = None,
        # Auto tool execution parameters
        tool_execute: str = "manual",  # "auto", "manual", "disabled"
        tool_executor: Optional[ToolExecutor] = None,
        max_tool_iterations: int = 5,
        tool_execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None,
        **kwargs: Any,
    ):
        """Initialize the Ollama provider with enhanced capabilities detection and auto tool execution."""
        # Configuration
        model = model_name or get_config("llm.ollama.model", DEFAULT_OLLAMA_MODEL)
        url = base_url or OllamaConfigHelper.get_base_url_from_env(OLLAMA_API_BASE)
        self._base_url = normalize_base_url(url)
        
        env_timeout = OllamaConfigHelper.get_timeout_from_env(DEFAULT_TIMEOUT)
        self._timeout = validate_timeout(timeout or env_timeout)
        self._explicit_capabilities = capabilities

        # Initialize base class
        super().__init__(
            model_name=model,
            base_url=self._base_url,
            temperature=temperature or get_config("llm.ollama.temperature", DEFAULT_TEMPERATURE),
            max_tokens=max_tokens or get_config("llm.ollama.max_tokens", DEFAULT_MAX_TOKENS),
            top_p=top_p or get_config("llm.ollama.top_p", DEFAULT_TOP_P),
            **kwargs,
        )

        # Initialize components with enhanced capabilities
        self._tool_converter = OllamaToolConverter()
        self._tool_extractor = OllamaToolExtractor()
        self._capabilities = OllamaCapabilities()  # Uses the new universal system
        self._message_formatter = OllamaMessageFormatter()
        self._error_handler = OllamaErrorHandler()
        self._response_processor = OllamaResponseProcessor()

        # Auto tool execution setup
        self.tool_execute = tool_execute
        self.max_tool_iterations = max_tool_iterations
        
        if tool_execute == "auto":
            self._tool_executor = tool_executor or ToolExecutor(
                max_iterations=max_tool_iterations,
                execution_timeout=tool_execution_timeout,
                allowed_tools=allowed_tools,
                forbidden_tools=forbidden_tools
            )
        else:
            self._tool_executor = None

        # HTTP clients
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None

        logger.info(f"Initialized Ollama provider: {model} @ {self._base_url} | Tool execution: {tool_execute}")

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

    # Tool Registration Methods
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool for auto execution."""
        if self._tool_executor:
            self._tool_executor.register_tool(name, func)
            logger.debug(f"Registered tool: {name}")
        else:
            logger.warning("Tool executor not initialized. Set tool_execute='auto' to enable.")

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools for auto execution."""
        if self._tool_executor:
            self._tool_executor.register_tools(tools)
            logger.debug(f"Registered {len(tools)} tools")
        else:
            logger.warning("Tool executor not initialized. Set tool_execute='auto' to enable.")

    # Main Completion Methods
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate completion with optional auto tool execution."""
        # Check if auto tool execution is enabled
        if self.tool_execute == "auto" and self._tool_executor:
            return self._complete_with_auto_tools(messages, **kwargs)
        else:
            return self._complete_standard(messages, **kwargs)

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate async completion with optional auto tool execution."""
        if self.tool_execute == "auto" and self._tool_executor:
            return await self._acomplete_with_auto_tools(messages, **kwargs)
        else:
            return await self._acomplete_standard(messages, **kwargs)

    # Standard Completion Methods (without auto tool execution)
    def _complete_standard(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Standard completion without auto tool execution."""
        request_id = generate_request_id()
        
        # Prepare request
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(self._timeout, self.model_name, has_images, has_tools)

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

        # Choose endpoint and execute
        use_chat = has_tools or any(msg.role != "user" for msg in messages[1:] if messages)
        
        try:
            if use_chat:
                llm_response = self._execute_chat_request(messages, timeout, **request_params)
            else:
                llm_response = self._execute_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            return self._llm_response_to_message(llm_response)
        except Exception as e:
            self.track_request(False)
            raise

    async def _acomplete_standard(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Standard async completion without auto tool execution."""
        # Prepare request (same logic as sync)
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(self._timeout, self.model_name, has_images, has_tools)

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            **kwargs
        }

        use_chat = has_tools or any(msg.role != "user" for msg in messages[1:] if messages)
        
        try:
            if use_chat:
                llm_response = await self._execute_async_chat_request(messages, timeout, **request_params)
            else:
                llm_response = await self._execute_async_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            return self._llm_response_to_message(llm_response)
        except Exception as e:
            self.track_request(False)
            raise

    # Auto Tool Execution Methods
    def _complete_with_auto_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Complete with automatic tool execution loop."""
        conversation = list(messages)  # Copy to avoid modifying original
        iteration = 0
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = self._complete_standard(conversation, **kwargs)
            
            # Check if model made tool calls
            if not self._has_tool_calls(response):
                # No tool calls, return final response
                logger.debug(f"No tool calls found, returning response (iteration {iteration + 1})")
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            logger.info(f"Auto-executing {len(tool_calls)} tool calls (iteration {iteration + 1})")
            
            # Execute tools
            tool_results = self._tool_executor.execute_tool_calls(tool_calls)
            
            # Add assistant message with tool calls to conversation
            conversation.append(response)
            
            # Add tool result messages to conversation
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning(f"Reached maximum tool iterations ({self.max_tool_iterations})")
        return response

    async def _acomplete_with_auto_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Async complete with automatic tool execution loop."""
        conversation = list(messages)
        iteration = 0
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = await self._acomplete_standard(conversation, **kwargs)
            
            # Check for tool calls
            if not self._has_tool_calls(response):
                logger.debug(f"No tool calls found, returning response (async iteration {iteration + 1})")
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            logger.info(f"Auto-executing {len(tool_calls)} tool calls async (iteration {iteration + 1})")
            
            # Execute tools asynchronously
            tool_results = await self._tool_executor.aexecute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning(f"Reached maximum async tool iterations ({self.max_tool_iterations})")
        return response

    def _has_tool_calls(self, response: MessageProtocol) -> bool:
        """Check if response contains tool calls."""
        return (
            hasattr(response, "metadata") and 
            response.metadata and 
            "tool_calls" in response.metadata and 
            response.metadata["tool_calls"]
        )

    # HTTP Request Execution Methods
    def _execute_chat_request(self, messages: List[MessageProtocol], timeout: float, **kwargs: Any) -> LLMResponse:
        """Execute chat request using helpers."""
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
        """Execute generate request using helpers."""
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
        """Execute async chat request."""
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
        """Execute async generate request."""
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

    # Streaming Methods
    def complete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> Iterator[MessageProtocol]:
        """Generate a streaming completion."""
        # Prepare request
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(self._timeout, self.model_name, has_images, has_tools)

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            "stream": True,
            **kwargs
        }

        use_chat = has_tools or any(msg.role != "user" for msg in messages[1:] if messages)
        endpoint = "chat" if use_chat else "generate"
        
        if use_chat:
            payload = OllamaConfigHelper.build_chat_payload(self.model_name, messages, self._message_formatter, **request_params)
        else:
            payload = OllamaConfigHelper.build_generate_payload(self.model_name, messages, self._message_formatter, **request_params)

        yield from OllamaStreamProcessor.handle_streaming_request(
            self._get_client(), "POST", self._get_api_url(endpoint), payload, timeout, self.model_name, self._error_handler
        )

    async def acomplete_stream(self, messages: List[MessageProtocol], **kwargs: Any) -> AsyncIterator[MessageProtocol]:
        """Generate an async streaming completion."""
        # Prepare request
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(self._timeout, self.model_name, has_images, has_tools)

        if has_tools:
            kwargs["tools"] = self._tool_converter.normalize_tools(kwargs.pop("tools"))

        request_params = {
            "temperature": kwargs.get("temperature", self.config.get("temperature")),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens")),
            "top_p": kwargs.get("top_p", self.config.get("top_p")),
            "stream": True,
            **kwargs
        }

        use_chat = has_tools or any(msg.role != "user" for msg in messages[1:] if messages)
        endpoint = "chat" if use_chat else "generate"
        
        if use_chat:
            payload = OllamaConfigHelper.build_chat_payload(self.model_name, messages, self._message_formatter, **request_params)
        else:
            payload = OllamaConfigHelper.build_generate_payload(self.model_name, messages, self._message_formatter, **request_params)

        async for msg in OllamaStreamProcessor.handle_async_streaming_request(
            await self._get_async_client(), "POST", self._get_api_url(endpoint), payload, timeout, self.model_name, self._error_handler
        ):
            yield msg

    # Model Information Methods
    def get_model_info(self) -> ModelInfo:
        """Get model information using enhanced universal capability detection."""
        if self._model_info is not None:
            return self._model_info

        # Fetch model data from Ollama with enhanced error handling
        model_data = self._fetch_model_data()
        
        # Use the new universal capability detection
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
                logger.debug(f"Retrieved model data for {self.model_name}")
                return model_data
            elif response.status_code == 404:
                logger.warning(f"Model {self.model_name} not found in Ollama")
                return None
            else:
                logger.warning(f"Unexpected response {response.status_code} for model {self.model_name}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to fetch model data for {self.model_name}: {e}")
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
        
        # Add key capabilities
        capabilities = specs.get("capabilities", [])
        if capabilities:
            cap_str = ", ".join(capabilities)
            description_parts.append(f"Capabilities: {cap_str}")
        
        return " ".join(description_parts)

    def get_provider_info(self) -> ProviderInfo:
        """Get provider information using schema class."""
        return ProviderInfo(
            name="ollama",
            description="High-performance local Ollama inference server with auto tool execution",
            base_url=self._base_url,
            supported_models=[self.model_name],
            features={ModelFeature.STREAMING, ModelFeature.FUNCTION_CALLING, ModelFeature.VISION},
            configuration={
                "base_url": self._base_url, 
                "timeout": self._timeout, 
                "model": self.model_name,
                "tool_execute": self.tool_execute,
                "max_tool_iterations": self.max_tool_iterations
            },
            is_available=True,
        )

    # Tool Execution Control Methods
    def enable_auto_tool_execution(self, tools: Optional[Dict[str, Callable]] = None) -> None:
        """Enable auto tool execution with optional tools."""
        self.tool_execute = "auto"
        if not self._tool_executor:
            self._tool_executor = ToolExecutor()
        if tools:
            self._tool_executor.register_tools(tools)
        logger.info("Auto tool execution enabled")

    def disable_auto_tool_execution(self) -> None:
        """Disable auto tool execution."""
        self.tool_execute = "manual"
        logger.info("Auto tool execution disabled")

    def get_tool_execution_stats(self) -> Optional[Dict[str, Any]]:
        """Get tool execution statistics."""
        if self._tool_executor:
            return self._tool_executor.get_execution_stats()
        return None

    # Utility Methods
    def _llm_response_to_message(self, llm_response: LLMResponse) -> MessageProtocol:
        """Convert LLMResponse to Message for backward compatibility."""
        metadata = {
            "provider": llm_response.provider,
            "model": llm_response.model,
            "finish_reason": llm_response.finish_reason,
            "usage_metadata": llm_response.usage_metadata,
            "response_metadata": llm_response.response_metadata,
        }
        
        if llm_response.tool_calls:
            metadata["tool_calls"] = [tc.to_dict() for tc in llm_response.tool_calls]
        
        return cast(MessageProtocol, Message(role="assistant", content=llm_response.content, metadata=metadata))
    
    def get_model_specifications(self) -> Dict[str, Any]:
        """Get comprehensive model specifications using the universal capabilities system."""
        model_data = self._fetch_model_data()
        return self._capabilities.get_model_specifications(self.model_name, model_data)

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
            "detected_features": capabilities.to_feature_set(),
            "supports_streaming": capabilities.supports_streaming,
            "supports_tools": capabilities.supports_tools,
            "supports_vision": capabilities.supports_vision,
            "supports_async": capabilities.supports_async,
            "context_window": capabilities.max_context_window,
            "max_output_tokens": capabilities.max_output_tokens,
            "specializations": capabilities.specializations,
            "languages": capabilities.languages,
            "supported_formats": capabilities.supported_formats,
            "specifications": self._capabilities.get_model_specifications(self.model_name, model_data),
            "tool_execution_enabled": self.tool_execute == "auto",
            "tool_execution_stats": self.get_tool_execution_stats()
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