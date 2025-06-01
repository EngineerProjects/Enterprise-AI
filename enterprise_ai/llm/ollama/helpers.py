"""
Optimized helper functions maximizing schema class usage.
"""

import json
import os
import time
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

import httpx

from enterprise_ai.exceptions import APIError, ModelNotFoundError
from enterprise_ai.llm.ollama.tools import OllamaToolExtractor
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import LLMResponse, Message, ToolCall
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.ollama.helpers")


class OllamaMessageFormatter:
    """Optimized message formatting using schema classes."""

    @staticmethod
    def format_for_chat(message: MessageProtocol) -> Dict[str, Any]:
        """Format message for chat endpoint using schema methods."""
        # Use schema's to_dict and filter for chat format
        base_dict = message.to_dict() if hasattr(message, 'to_dict') else {
            "role": message.role,
            "content": message.content
        }
        
        # Keep only fields needed for chat API
        chat_format = {"role": base_dict["role"]}
        
        if base_dict.get("content") is not None:
            chat_format["content"] = base_dict["content"]
        
        if base_dict.get("name") is not None:
            chat_format["name"] = base_dict["name"]
        
        # Extract images from metadata
        if "metadata" in base_dict and base_dict["metadata"]:
            images = base_dict["metadata"].get("images")
            if images:
                chat_format["images"] = images
        
        return chat_format

    @staticmethod
    def format_for_generate(messages: List[MessageProtocol]) -> str:
        """Optimized prompt formatting using schema."""
        if not messages:
            return ""
        
        # Efficient formatting using schema methods
        formatted_parts = []
        
        for msg in messages:
            role_prefix = OllamaMessageFormatter._get_role_prefix(msg)
            content = msg.content or ""
            formatted_parts.append(f"{role_prefix}{content}")
        
        return "\n\n".join(formatted_parts)

    @staticmethod
    def _get_role_prefix(message: MessageProtocol) -> str:
        """Get appropriate role prefix for message."""
        role_prefixes = {
            "system": "System: ",
            "user": "User: ", 
            "assistant": "Assistant: ",
        }
        
        if message.role == "tool" and hasattr(message, "name") and message.name:
            return f"Tool ({message.name}): "
        
        return role_prefixes.get(message.role, f"{message.role.title()}: ")

    @staticmethod
    def extract_images_from_messages(messages: List[MessageProtocol]) -> List[str]:
        """Extract images using schema metadata access."""
        all_images = []
        
        for msg in messages:
            if hasattr(msg, "metadata") and msg.metadata:
                images = msg.metadata.get("images", [])
                all_images.extend(images)
            elif hasattr(msg, "get_images"):
                # Use schema method if available
                all_images.extend(msg.get_images())
        
        return all_images


class OllamaConfigHelper:
    """Centralized config helper optimized for schema usage."""
    
    TIMEOUT_MULTIPLIERS = {
        "vision": 2.0, "tools": 1.5, "large_model": 1.8, "streaming": 0.8
    }

    @staticmethod
    def build_chat_payload(
        model_name: str,
        messages: List[MessageProtocol], 
        formatter: OllamaMessageFormatter,
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build optimized chat payload using schema methods."""
        payload = {
            "model": model_name,
            "messages": [formatter.format_for_chat(msg) for msg in messages],
            "stream": stream,
        }
        
        # Add options efficiently
        options = OllamaConfigHelper._build_options(**kwargs)
        if options:
            payload["options"] = options
        
        # Add tools directly from kwargs (already normalized by tools module)
        if kwargs.get("tools"):
            payload["tools"] = kwargs["tools"]
            
        return payload

    @staticmethod
    def build_generate_payload(
        model_name: str,
        messages: List[MessageProtocol],
        formatter: OllamaMessageFormatter, 
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build optimized generate payload using schema methods."""
        prompt = formatter.format_for_generate(messages)
        images = formatter.extract_images_from_messages(messages)
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": stream,
        }
        
        # Add options directly for generate endpoint
        options = OllamaConfigHelper._build_options(**kwargs)
        payload.update(options)
        
        if images:
            payload["images"] = images
            
        return payload

    @staticmethod
    def _build_options(**kwargs: Any) -> Dict[str, Any]:
        """Build options dict with parameter mapping."""
        options = {}
        param_mapping = {
            "temperature": "temperature",
            "max_tokens": "num_predict", 
            "top_p": "top_p",
            "presence_penalty": "presence_penalty",
            "frequency_penalty": "frequency_penalty"
        }
        
        for key, ollama_key in param_mapping.items():
            if key in kwargs and kwargs[key] is not None:
                options[ollama_key] = kwargs[key]
        
        return options

    @staticmethod
    def determine_timeout_for_request(
        base_timeout: float,
        model_name: str,
        has_images: bool = False,
        has_tools: bool = False
    ) -> float:
        """Smart timeout calculation."""
        timeout = base_timeout
        
        if has_images or "vision" in model_name.lower():
            timeout *= OllamaConfigHelper.TIMEOUT_MULTIPLIERS["vision"]
        
        if has_tools:
            timeout *= OllamaConfigHelper.TIMEOUT_MULTIPLIERS["tools"]
        
        # Check for large models
        if any(indicator in model_name.lower() for indicator in ["70b", "65b", "180b", "mixtral"]):
            timeout *= OllamaConfigHelper.TIMEOUT_MULTIPLIERS["large_model"]
        
        return max(timeout, 10.0)

    @staticmethod
    def get_base_url_from_env(default: str) -> str:
        """Get base URL with environment fallbacks."""
        for env_var in ["OLLAMA_HOST", "ENTERPRISE_AI_OLLAMA_URL"]:
            url = os.environ.get(env_var)
            if url:
                return url
        return default

    @staticmethod
    def get_timeout_from_env(default: float) -> float:
        """Get timeout from environment with validation."""
        env_timeout = os.environ.get("ENTERPRISE_AI_OLLAMA_TIMEOUT")
        if env_timeout:
            try:
                timeout = float(env_timeout)
                return timeout if timeout > 0 else default
            except ValueError:
                logger.warning(f"Invalid timeout {env_timeout}, using default")
        return default


class OllamaResponseProcessor:
    """Unified response processor maximizing schema usage."""
    
    @staticmethod
    def process_chat_response(
        result: Dict[str, Any], 
        model_name: str,
        tool_extractor: 'OllamaToolExtractor'
    ) -> LLMResponse:
        """Process chat response using LLMResponse schema."""
        message = result.get("message", {})
        content = message.get("content", "")
        
        # Process tool calls using schema
        tool_calls = OllamaResponseProcessor._extract_tool_calls(
            message, content, tool_extractor
        )
        
        # Use schema class for response
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=result.get("done_reason", "completed"),
            usage_metadata=OllamaResponseProcessor._extract_usage_metadata(result),
            response_metadata=OllamaResponseProcessor._extract_response_metadata(result),
            provider="ollama",
            model=model_name,
        )

    @staticmethod
    def process_generate_response(
        result: Dict[str, Any], 
        model_name: str,
        tool_extractor: 'OllamaToolExtractor'
    ) -> LLMResponse:
        """Process generate response using LLMResponse schema."""
        content = result.get("response", "")
        
        # Extract tool calls using schema extractor
        tool_calls = tool_extractor.extract_tool_calls_to_schema(content)
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=result.get("done_reason", "completed"),
            usage_metadata=OllamaResponseProcessor._extract_usage_metadata(result),
            response_metadata=OllamaResponseProcessor._extract_response_metadata(result),
            provider="ollama",
            model=model_name,
        )

    @staticmethod
    def _extract_tool_calls(
        message: Dict[str, Any], 
        content: str, 
        tool_extractor: 'OllamaToolExtractor'
    ) -> List[ToolCall]:
        """Extract tool calls using both native and content extraction."""
        tool_calls = []
        
        # First: try native tool calls from response
        if "tool_calls" in message:
            for raw_tc in message["tool_calls"]:
                try:
                    tool_call = ToolCall.from_dict(raw_tc)
                    tool_calls.append(tool_call)
                except Exception as e:
                    logger.debug(f"Failed to parse native tool call: {e}")
        
        # Fallback: extract from content if no native tool calls
        if not tool_calls and content:
            tool_calls = tool_extractor.extract_tool_calls_to_schema(content)
        
        return tool_calls

    @staticmethod
    def _extract_usage_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive usage metadata."""
        usage = {}
        
        # Token counts
        if "eval_count" in result:
            usage["completion_tokens"] = result["eval_count"]
        if "prompt_eval_count" in result:
            usage["prompt_tokens"] = result["prompt_eval_count"]
        
        if usage:
            usage["total_tokens"] = usage.get("completion_tokens", 0) + usage.get("prompt_tokens", 0)
        
        # Timing information (convert nanoseconds to milliseconds)
        if "eval_duration" in result:
            usage["completion_time_ms"] = result["eval_duration"] // 1_000_000
        if "prompt_eval_duration" in result:
            usage["prompt_time_ms"] = result["prompt_eval_duration"] // 1_000_000
        
        return usage

    @staticmethod
    def _extract_response_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract response metadata efficiently."""
        excluded_keys = {"message", "response", "done", "done_reason"}
        return {k: v for k, v in result.items() if k not in excluded_keys}


class OllamaErrorHandler:
    """Enhanced error handling with detailed context."""
    
    ERROR_MAPPING = {
        400: "Bad request - check parameters",
        401: "Unauthorized - check API key", 
        404: "Model not found - verify model name",
        429: "Rate limited - reduce request frequency",
        500: "Internal server error",
        503: "Service unavailable - Ollama may be overloaded"
    }

    @staticmethod
    def handle_http_error(error: httpx.HTTPStatusError) -> Exception:
        """Enhanced HTTP error handling with context."""
        status_code = error.response.status_code
        response_text = error.response.text
        
        base_message = OllamaErrorHandler.ERROR_MAPPING.get(
            status_code, f"HTTP {status_code} error"
        )
        
        if status_code == 404:
            return ModelNotFoundError(f"{base_message}. Response: {response_text[:200]}")
        
        full_message = f"{base_message}: {response_text[:500]}" if response_text else base_message
        return APIError(status_code, full_message)

    @staticmethod
    def handle_connection_error(error: httpx.ConnectError) -> Exception:
        """Enhanced connection error with troubleshooting."""
        return APIError(
            message="Failed to connect to Ollama server. "
                   "Troubleshooting: 1) Ensure Ollama is running: 'ollama serve' "
                   "2) Check port 11434 accessibility 3) Verify OLLAMA_HOST env var"
        )

    @staticmethod
    def handle_timeout_error(error: httpx.ReadTimeout, timeout: float) -> Exception:
        """Enhanced timeout error with suggestions."""
        return APIError(
            message=f"Request timed out after {timeout}s. "
                   f"Consider increasing timeout via ENTERPRISE_AI_OLLAMA_TIMEOUT. "
                   f"Vision models need 120s+, large models need 90s+, tool requests need 60s+"
        )


class OllamaStreamProcessor:
    """Optimized streaming processor using schema classes."""

    @staticmethod
    def handle_streaming_request(
        client, method: str, url: str, payload: Dict[str, Any],
        timeout: float, model_name: str, error_handler: OllamaErrorHandler
    ) -> Iterator[MessageProtocol]:
        """Optimized streaming using schema classes."""
        try:
            with client.stream(method, url, json=payload, timeout=timeout) as response:
                response.raise_for_status()
                
                content_buffer = ""
                chunk_index = 0
                
                for line in response.iter_lines():
                    if line:
                        chunk_data = OllamaStreamProcessor._process_chunk_line(line)
                        if chunk_data:
                            content_buffer += OllamaStreamProcessor._extract_chunk_content(chunk_data)
                            
                            # Use Message schema for streaming responses
                            yield Message(
                                role="assistant",
                                content=content_buffer,
                                metadata={
                                    "provider": "ollama",
                                    "model": model_name,
                                    "is_partial": not chunk_data.get("done", False),
                                    "chunk_index": chunk_index,
                                }
                            )
                            chunk_index += 1
                            
        except httpx.HTTPStatusError as e:
            raise error_handler.handle_http_error(e)
        except httpx.ConnectError as e:
            raise error_handler.handle_connection_error(e)
        except httpx.ReadTimeout as e:
            raise error_handler.handle_timeout_error(e, timeout)

    @staticmethod
    async def handle_async_streaming_request(
        client, method: str, url: str, payload: Dict[str, Any],
        timeout: float, model_name: str, error_handler: OllamaErrorHandler
    ) -> AsyncIterator[MessageProtocol]:
        """Async streaming using schema classes."""
        try:
            async with client.stream(method, url, json=payload, timeout=timeout) as response:
                response.raise_for_status()
                
                content_buffer = ""
                chunk_index = 0
                
                async for line in response.aiter_lines():
                    if line:
                        chunk_data = OllamaStreamProcessor._process_chunk_line(line)
                        if chunk_data:
                            content_buffer += OllamaStreamProcessor._extract_chunk_content(chunk_data)
                            
                            yield Message(
                                role="assistant",
                                content=content_buffer,
                                metadata={
                                    "provider": "ollama",
                                    "model": model_name,
                                    "is_partial": not chunk_data.get("done", False),
                                    "chunk_index": chunk_index,
                                }
                            )
                            chunk_index += 1
                            
        except httpx.HTTPStatusError as e:
            raise error_handler.handle_http_error(e)
        except httpx.ConnectError as e:
            raise error_handler.handle_connection_error(e)
        except httpx.ReadTimeout as e:
            raise error_handler.handle_timeout_error(e, timeout)

    @staticmethod
    def _process_chunk_line(line: str) -> Optional[Dict[str, Any]]:
        """Process individual chunk line."""
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_chunk_content(chunk_data: Dict[str, Any]) -> str:
        """Extract content from chunk based on endpoint type."""
        if "response" in chunk_data:  # Generate endpoint
            return chunk_data.get("response", "")
        elif "message" in chunk_data:  # Chat endpoint
            return chunk_data["message"].get("content", "")
        return ""