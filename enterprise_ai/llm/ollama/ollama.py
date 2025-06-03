"""
Enhanced Ollama provider implementation with comprehensive execution control.

This implementation combines the speed of the HTTP-based approach with
enhanced tool execution control, approval workflows, and verbose logging.
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
from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import Message, ModelInfo, LLMResponse, ProviderInfo, ToolCall, ToolResult
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.base import ExecutionMode

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

logger = get_optimized_logger("llm.ollama")


class OllamaProvider(LLMProvider):
    """Enhanced Ollama LLM provider with comprehensive execution control."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        timeout: Optional[float] = None,
        capabilities: Optional[Set[str]] = None,
        # Enhanced execution parameters (inherited from base)
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        approval_callback: Optional[Callable] = None,
        verbose: bool = False,
        max_tool_iterations: int = 5,
        tool_execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None,
        hybrid_danger_threshold: int = 2,
        **kwargs: Any,
    ):
        """Initialize the Ollama provider with enhanced execution control."""
        # Configuration
        model = model_name or get_config("llm.ollama.model", DEFAULT_OLLAMA_MODEL)
        url = base_url or OllamaConfigHelper.get_base_url_from_env(OLLAMA_API_BASE)
        self._base_url = normalize_base_url(url)
        
        env_timeout = OllamaConfigHelper.get_timeout_from_env(DEFAULT_TIMEOUT)
        self._timeout = validate_timeout(timeout or env_timeout)
        self._explicit_capabilities = capabilities

        # Initialize base class with enhanced parameters
        super().__init__(
            model_name=model,
            execution_mode=execution_mode,
            approval_callback=approval_callback,
            verbose=verbose,
            max_tool_iterations=max_tool_iterations,
            tool_execution_timeout=tool_execution_timeout,
            allowed_tools=allowed_tools,
            forbidden_tools=forbidden_tools,
            hybrid_danger_threshold=hybrid_danger_threshold,
            base_url=self._base_url,
            temperature=temperature or get_config("llm.ollama.temperature", DEFAULT_TEMPERATURE),
            max_tokens=max_tokens or get_config("llm.ollama.max_tokens", DEFAULT_MAX_TOKENS),
            top_p=top_p or get_config("llm.ollama.top_p", DEFAULT_TOP_P),
            **kwargs,
        )

        # Initialize components with enhanced capabilities
        self._tool_converter = OllamaToolConverter()
        self._tool_extractor = OllamaToolExtractor()
        self._capabilities = OllamaCapabilities()
        self._message_formatter = OllamaMessageFormatter()
        self._error_handler = OllamaErrorHandler()
        self._response_processor = OllamaResponseProcessor()

        # Enhanced tool execution setup
        self._tool_executor = ToolExecutor(
            max_iterations=max_tool_iterations,
            execution_timeout=tool_execution_timeout,
            allowed_tools=allowed_tools,
            forbidden_tools=forbidden_tools,
            execution_mode=execution_mode,
            approval_callback=approval_callback,
            verbose=verbose,
            hybrid_danger_threshold=hybrid_danger_threshold,
        )

        # HTTP clients
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None

        logger.info("Initialized Ollama provider: %s @ %s | Execution mode: %s", model, self._base_url, execution_mode)

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

    # Enhanced Tool Registration Methods
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool for execution."""
        self._tool_executor.register_tool(name, func)
        if self.verbose:
            logger.info("Registered tool: %s", name)

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools for execution."""
        self._tool_executor.register_tools(tools)
        if self.verbose:
            logger.info("Registered %s tools", len(tools))

    # Enhanced completion methods
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate completion with execution mode support."""
        if self.execution_mode == ExecutionMode.AUTO:
            return self._complete_with_auto_tools(messages, **kwargs)
        elif self.execution_mode == ExecutionMode.DISABLED:
            return self._complete_standard(messages, **kwargs)
        else:  # MANUAL or HYBRID
            if self.approval_callback:
                return self._complete_with_controlled_tools(messages, **kwargs)
            else:
                return self._complete_with_auto_tools(messages, **kwargs)

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate async completion with execution mode support."""
        if self.execution_mode == ExecutionMode.AUTO:
            return await self._acomplete_with_auto_tools(messages, **kwargs)
        elif self.execution_mode == ExecutionMode.DISABLED:
            return await self._acomplete_standard(messages, **kwargs)
        else:  # MANUAL or HYBRID
            if self.approval_callback:
                return await self._acomplete_with_controlled_tools(messages, **kwargs)
            else:
                return await self._acomplete_with_auto_tools(messages, **kwargs)

    # Enhanced tool execution methods
    def complete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """Generate completion and extract tool calls without executing them."""
        response = self._complete_standard(messages, **kwargs)
        tool_calls = self._extract_tool_calls_from_response(response)
        return response, tool_calls

    async def acomplete_with_tool_calls(
        self, 
        messages: List[MessageProtocol],
        **kwargs: Any
    ) -> tuple[MessageProtocol, List[ToolCall]]:
        """Generate completion and extract tool calls without executing them (async)."""
        response = await self._acomplete_standard(messages, **kwargs)
        tool_calls = self._extract_tool_calls_from_response(response)
        return response, tool_calls

    def execute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Execute tool calls manually with current execution settings."""
        return self._tool_executor.execute_tool_calls(tool_calls, context)

    async def aexecute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Execute tool calls manually with current execution settings (async)."""
        return await self._tool_executor.aexecute_tool_calls(tool_calls, context)

    # Standard Completion Methods (no auto tool execution)
    def _complete_standard(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Standard completion without auto tool execution."""
        request_id = generate_request_id()
        
        if self.verbose:
            logger.info("Making Ollama completion request %s with %s messages", request_id, len(messages))
        
        # Prepare request
        has_images = any(hasattr(msg, "metadata") and msg.metadata and "images" in msg.metadata for msg in messages)
        has_tools = "tools" in kwargs and kwargs["tools"]
        timeout = OllamaConfigHelper.determine_timeout_for_request(self._timeout, self.model_name, has_images, has_tools)

        if self.verbose:
            logger.info("Request config: has_images=%s, has_tools=%s, timeout=%ss", has_images, has_tools, timeout)

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
        
        if self.verbose:
            logger.info("Using %s endpoint", 'chat' if use_chat else 'generate')
        
        try:
            if use_chat:
                llm_response = self._execute_chat_request(messages, timeout, **request_params)
            else:
                llm_response = self._execute_generate_request(messages, timeout, **request_params)
            
            self.track_request(True)
            result = self._llm_response_to_message(llm_response)
            
            if self.verbose:
                logger.info("Ollama request %s completed successfully", request_id)
            
            return result
        except Exception as e:
            self.track_request(False)
            if self.verbose:
                logger.error("Ollama request %s failed: %s", request_id, str(e))
            raise

    async def _acomplete_standard(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Standard async completion without auto tool execution."""
        if self.verbose:
            logger.info("Making async Ollama completion request with %s messages", len(messages))
        
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
            result = self._llm_response_to_message(llm_response)
            
            if self.verbose:
                logger.info("Async Ollama request completed successfully")
            
            return result
        except Exception as e:
            self.track_request(False)
            if self.verbose:
                logger.error("Async Ollama request failed: %s", str(e))
            raise

    # Auto Tool Execution Methods
    def _complete_with_auto_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Complete with automatic tool execution loop."""
        conversation = list(messages)
        iteration = 0
        
        if self.verbose:
            logger.info("Starting auto tool execution loop with %s initial messages", len(messages))
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = self._complete_standard(conversation, **kwargs)
            
            # Check if model made tool calls
            if not self._has_tool_calls(response):
                if self.verbose:
                    logger.info("No tool calls found, returning response (iteration %s)", iteration + 1)
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            if self.verbose:
                logger.info("Auto-executing %s tool calls (iteration %s)", len(tool_calls), iteration + 1)
            
            # Execute tools with current executor settings
            tool_results = self._tool_executor.execute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning("Reached maximum tool iterations (%s)", self.max_tool_iterations)
        return response

    async def _acomplete_with_auto_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Async complete with automatic tool execution loop."""
        conversation = list(messages)
        iteration = 0
        
        if self.verbose:
            logger.info("Starting async auto tool execution loop with %s initial messages", len(messages))
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = await self._acomplete_standard(conversation, **kwargs)
            
            # Check for tool calls
            if not self._has_tool_calls(response):
                if self.verbose:
                    logger.info("No tool calls found, returning response (async iteration %s)", iteration + 1)
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            if self.verbose:
                logger.info("Auto-executing %s tool calls async (iteration %s)", len(tool_calls), iteration + 1)
            
            # Execute tools asynchronously
            tool_results = await self._tool_executor.aexecute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning("Reached maximum async tool iterations (%s)", self.max_tool_iterations)
        return response

    # Controlled tool execution (manual/hybrid with approval)
    def _complete_with_controlled_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Complete with controlled tool execution based on execution mode."""
        conversation = list(messages)
        iteration = 0
        
        if self.verbose:
            logger.info("Starting controlled tool execution with %s mode", self.execution_mode)
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = self._complete_standard(conversation, **kwargs)
            
            # Check if model made tool calls
            if not self._has_tool_calls(response):
                if self.verbose:
                    logger.info("No tool calls found, returning response (iteration %s)", iteration + 1)
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            if self.verbose:
                logger.info("Processing %s tool calls with %s mode (iteration %s)", len(tool_calls), self.execution_mode, iteration + 1)
            
            # Execute tools with approval control
            tool_results = self._tool_executor.execute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning("Reached maximum tool iterations (%s)", self.max_tool_iterations)
        return response

    async def _acomplete_with_controlled_tools(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Async complete with controlled tool execution based on execution mode."""
        conversation = list(messages)
        iteration = 0
        
        if self.verbose:
            logger.info("Starting async controlled tool execution with %s mode", self.execution_mode)
        
        while iteration < self.max_tool_iterations:
            # Get response from model
            response = await self._acomplete_standard(conversation, **kwargs)
            
            # Check if model made tool calls
            if not self._has_tool_calls(response):
                if self.verbose:
                    logger.info("No tool calls found, returning response (async iteration %s)", iteration + 1)
                return response
            
            tool_calls_data = response.metadata["tool_calls"]
            tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
            
            if self.verbose:
                logger.info("Processing %s tool calls with %s mode (async iteration %s)", len(tool_calls), self.execution_mode, iteration + 1)
            
            # Execute tools with approval control
            tool_results = await self._tool_executor.aexecute_tool_calls(tool_calls)
            
            # Update conversation
            conversation.append(response)
            tool_messages = self._tool_executor.create_tool_messages(tool_results)
            conversation.extend(tool_messages)
            
            iteration += 1
        
        logger.warning("Reached maximum async tool iterations (%s)", self.max_tool_iterations)
        return response

    def _has_tool_calls(self, response: MessageProtocol) -> bool:
        """Check if response contains tool calls."""
        return (
            hasattr(response, "metadata") and 
            response.metadata and 
            "tool_calls" in response.metadata and 
            response.metadata["tool_calls"]
        )

    # HTTP Request Execution Methods (unchanged)
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

    # Streaming Methods (unchanged)
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

    # Model Information Methods (unchanged)
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
                "execution_mode": self.execution_mode,
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
                if self.verbose:
                    logger.info("Retrieved model data for %s", self.model_name)
                else:
                    logger.debug("Retrieved model data for %s", self.model_name)
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
            description="High-performance local Ollama inference server with enhanced execution control",
            base_url=self._base_url,
            supported_models=[self.model_name],
            features={ModelFeature.STREAMING, ModelFeature.FUNCTION_CALLING, ModelFeature.VISION},
            configuration={
                "base_url": self._base_url, 
                "timeout": self._timeout, 
                "model": self.model_name,
                "execution_mode": self.execution_mode,
                "max_tool_iterations": self.max_tool_iterations,
                "verbose": self.verbose,
            },
            is_available=True,
        )

    # Enhanced execution control methods
    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Change the execution mode."""
        super().set_execution_mode(mode)
        self._tool_executor.set_execution_mode(mode)

    def set_approval_callback(self, callback: Optional[Callable]) -> None:
        """Set or update the approval callback."""
        super().set_approval_callback(callback)
        self._tool_executor.set_approval_callback(callback)

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose logging."""
        super().set_verbose(verbose)
        self._tool_executor.set_verbose(verbose)

    def get_tool_execution_stats(self) -> Optional[Dict[str, Any]]:
        """Get tool execution statistics."""
        return self._tool_executor.get_execution_stats()

    # Utility Methods (unchanged)
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
            "provider": "ollama",
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
            "execution_mode": self.execution_mode,
            "tool_execution_stats": self.get_tool_execution_stats()
        }

    # Cleanup Methods (unchanged)
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