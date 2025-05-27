"""
Tool adapters for LLM providers.

This module provides adapter classes to handle tool calling formats
across different LLM providers, ensuring consistent behavior.
"""


from datetime import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.refactored.adapters")


class ToolFormat(Enum):
    """Enum for different tool calling formats."""

    OPENAI = "openai"  # OpenAI format with function objects
    ANTHROPIC = "anthropic"  # Anthropic Claude format
    OLLAMA = "ollama"  # Ollama format
    TOGETHER = "together"  # Together.ai format
    GENERIC = "generic"  # Generic format for other providers


class ToolAdapter:
    """
    Base tool adapter class.

    This class provides methods for converting between different tool formats
    and standardizing tool call extraction from LLM responses.
    """

    def __init__(self, default_format: ToolFormat = ToolFormat.GENERIC):
        """
        Initialize the tool adapter.

        Args:
            default_format: Default tool format to use
        """
        self.default_format = default_format

    def format_for_provider(
        self, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Format tools for a specific provider.

        Args:
            tools: List of tools in standard format
            **kwargs: Additional formatting options

        Returns:
            Tuple of (formatted_tools, updated_kwargs)
        """
        # Default implementation just passes through the tools
        return tools, kwargs

    def extract_tool_calls(self, response: MessageProtocol) -> List[Dict[str, Any]]:
        """
        Extract tool calls from an LLM response.

        Args:
            response: LLM response message

        Returns:
            List of standardized tool calls
        """
        # Default implementation checks metadata for tool_calls
        if hasattr(response, "metadata") and response.metadata:
            if "tool_calls" in response.metadata:
                return response.metadata["tool_calls"]

        # Try to parse from content
        return self._extract_from_content(response.content or "")

    def _extract_from_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from message content.

        Args:
            content: Message content

        Returns:
            List of tool calls
        """
        # Default implementation returns empty list
        # Subclasses should implement specific parsing logic
        return []

    def standardize_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardize a tool call to the common format.

        Args:
            tool_call: Provider-specific tool call

        Returns:
            Standardized tool call
        """
        # Ensure the tool call has the required fields
        if "name" not in tool_call:
            if "function" in tool_call and "name" in tool_call["function"]:
                tool_call["name"] = tool_call["function"]["name"]
            else:
                logger.warning(f"Tool call missing name: {tool_call}")
                tool_call["name"] = "unknown_tool"

        if "parameters" not in tool_call:
            if "function" in tool_call and "arguments" in tool_call["function"]:
                import json
                try:
                    tool_call["parameters"] = json.loads(tool_call["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    tool_call["parameters"] = {}
            else:
                tool_call["parameters"] = {}

        # Ensure ID is present
        if "id" not in tool_call:
            import time
            tool_call["id"] = f"gen-{time.time()}"

        return tool_call


class OpenAIToolAdapter(ToolAdapter):
    """
    Tool adapter for OpenAI-compatible providers.

    This adapter handles the OpenAI function calling format.
    """

    def __init__(self):
        """Initialize the OpenAI tool adapter."""
        super().__init__(default_format=ToolFormat.OPENAI)

    def format_for_provider(
        self, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Format tools for OpenAI format.

        Args:
            tools: List of tools in standard format
            **kwargs: Additional formatting options

        Returns:
            Tuple of (formatted_tools, updated_kwargs)
        """
        # OpenAI expects tools in a specific format
        formatted_tools = []
        for tool in tools:
            if "function" in tool:
                # Already in OpenAI format
                formatted_tools.append(tool)
            else:
                # Convert to OpenAI format
                formatted_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    },
                }
                formatted_tools.append(formatted_tool)

        # Update kwargs with the formatted tools
        updated_kwargs = kwargs.copy()
        updated_kwargs["tools"] = formatted_tools
        return formatted_tools, updated_kwargs

    def extract_tool_calls(self, response: MessageProtocol) -> List[Dict[str, Any]]:
        """
        Extract tool calls from an OpenAI response.

        Args:
            response: OpenAI response message

        Returns:
            List of standardized tool calls
        """
        tool_calls = []

        # Check metadata for tool_calls
        if hasattr(response, "metadata") and response.metadata:
            # Modern OpenAI format with tool_calls in metadata
            if "tool_calls" in response.metadata:
                for tool_call in response.metadata["tool_calls"]:
                    standardized = self.standardize_tool_call(tool_call)
                    tool_calls.append(standardized)
                return tool_calls

        # Check for function_call in metadata (older OpenAI format)
        if hasattr(response, "metadata") and response.metadata:
            if "function_call" in response.metadata:
                function_call = response.metadata["function_call"]
                if isinstance(function_call, dict):
                    import json
                    name = function_call.get("name", "")
                    arguments = function_call.get("arguments", "{}")

                    # Parse arguments
                    try:
                        params = json.loads(arguments)
                    except json.JSONDecodeError:
                        params = {}

                    tool_calls.append(
                        {
                            "name": name,
                            "parameters": params,
                            "type": "function_call",
                            "id": function_call.get("id", f"gen-{time.time()}"),
                        }
                    )
                    return tool_calls

        # If no tool calls found in metadata, try parsing from content
        if not tool_calls:
            content_tool_calls = self._extract_from_content(response.content or "")
            tool_calls.extend(content_tool_calls)

        return tool_calls

    def _extract_from_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from message content.

        Args:
            content: Message content

        Returns:
            List of tool calls
        """
        import re
        import json

        tool_calls = []

        # Look for function calls in markdown code blocks
        function_blocks = re.findall(r"```(?:json)?\s*({[\s\S]*?})```", content, re.DOTALL)
        for block in function_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict):
                    if "function" in data or "name" in data:
                        # Looks like a function call
                        standardized = self.standardize_tool_call(data)
                        tool_calls.append(standardized)
            except json.JSONDecodeError:
                continue

        # Look for tool request format
        tool_requests = re.findall(r"<tool_request>(.*?)</tool_request>", content, re.DOTALL)
        for request_text in tool_requests:
            try:
                request_data = json.loads(request_text)
                standardized = self.standardize_tool_call({
                    "name": request_data.get("tool", ""),
                    "parameters": request_data.get("parameters", {}),
                    "type": "text_tool",
                    "id": request_data.get("id", f"gen-{time.time()}"),
                })
                tool_calls.append(standardized)
            except json.JSONDecodeError:
                # Try to extract with regex if JSON parsing fails
                name_match = re.search(r'"tool":\s*"([^"]+)"', request_text)
                params_match = re.search(r'"parameters":\s*({.*})', request_text)

                if name_match:
                    tool_name = name_match.group(1)
                    params = {}

                    if params_match:
                        try:
                            params = json.loads(params_match.group(1))
                        except json.JSONDecodeError:
                            # Extract key-value pairs with regex
                            param_matches = re.findall(
                                r'"([^"]+)":\s*("[^"]*"|[\d.]+|\{.*?\}|\[.*?\]|true|false)',
                                params_match.group(1),
                            )
                            for param_name, param_value in param_matches:
                                # Convert to appropriate type
                                if param_value.startswith('"') and param_value.endswith('"'):
                                    params[param_name] = param_value[1:-1]
                                elif param_value.lower() in ["true", "false"]:
                                    params[param_name] = param_value.lower() == "true"
                                elif param_value.replace(".", "", 1).isdigit():
                                    if "." in param_value:
                                        params[param_name] = float(param_value)
                                    else:
                                        params[param_name] = int(param_value)
                                else:
                                    params[param_name] = param_value

                    tool_calls.append(
                        {
                            "name": tool_name,
                            "parameters": params,
                            "type": "text_tool",
                            "id": f"gen-{time.time()}",
                        }
                    )

        return tool_calls


class AnthropicToolAdapter(ToolAdapter):
    """
    Tool adapter for Anthropic Claude providers.

    This adapter handles the Anthropic Claude tool calling format.
    """

    def __init__(self):
        """Initialize the Anthropic tool adapter."""
        super().__init__(default_format=ToolFormat.ANTHROPIC)

    def format_for_provider(
        self, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Format tools for Anthropic Claude format.

        Args:
            tools: List of tools in standard format
            **kwargs: Additional formatting options

        Returns:
            Tuple of (formatted_tools, updated_kwargs)
        """
        # Claude expects tools in a specific format
        formatted_tools = []
        for tool in tools:
            if "function" in tool and "parameters" in tool["function"]:
                # Already in a compatible format, just needs slight adjustment
                formatted_tool = {
                    "name": tool["function"]["name"],
                    "description": tool["function"]["description"],
                    "parameters": tool["function"]["parameters"],
                }
                formatted_tools.append(formatted_tool)
            else:
                # Convert to Claude format
                formatted_tool = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                }
                formatted_tools.append(formatted_tool)

        # Update kwargs with the formatted tools
        updated_kwargs = kwargs.copy()
        updated_kwargs["tools"] = formatted_tools
        return formatted_tools, updated_kwargs

    def extract_tool_calls(self, response: MessageProtocol) -> List[Dict[str, Any]]:
        """
        Extract tool calls from an Anthropic Claude response.

        Args:
            response: Claude response message

        Returns:
            List of standardized tool calls
        """
        tool_calls = []

        # Check metadata for tool_calls (Claude format)
        if hasattr(response, "metadata") and response.metadata:
            if "tool_calls" in response.metadata:
                for tool_call in response.metadata["tool_calls"]:
                    standardized = self.standardize_tool_call(tool_call)
                    tool_calls.append(standardized)
                return tool_calls

        # If no tool calls found in metadata, try parsing from content
        if not tool_calls:
            content_tool_calls = self._extract_from_content(response.content or "")
            tool_calls.extend(content_tool_calls)

        return tool_calls

    def _extract_from_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from message content.

        Args:
            content: Message content

        Returns:
            List of tool calls
        """
        import re
        import json

        tool_calls = []

        # Look for Claude's XML tool call format
        tool_matches = re.findall(r"<tool_call>(.*?)</tool_call>", content, re.DOTALL)
        for tool_text in tool_matches:
            name_match = re.search(r"<name>(.*?)</name>", tool_text)
            params_match = re.search(r"<parameters>(.*?)</parameters>", tool_text)

            if name_match:
                tool_name = name_match.group(1)
                params = {}

                if params_match:
                    params_text = params_match.group(1)
                    try:
                        params = json.loads(params_text)
                    except json.JSONDecodeError:
                        # Try to parse as XML
                        param_matches = re.findall(r"<(\w+)>(.*?)</\1>", params_text, re.DOTALL)
                        for param_name, param_value in param_matches:
                            # Try to convert to appropriate type
                            if param_value.lower() in ["true", "false"]:
                                params[param_name] = param_value.lower() == "true"
                            elif param_value.isdigit():
                                params[param_name] = int(param_value)
                            elif param_value.replace(".", "", 1).isdigit():
                                params[param_name] = float(param_value)
                            else:
                                params[param_name] = param_value

                tool_calls.append(
                    {
                        "name": tool_name,
                        "parameters": params,
                        "type": "claude_tool",
                        "id": f"gen-{time.time()}",
                    }
                )

        # Also look for JSON format in code blocks
        function_blocks = re.findall(r"```(?:json)?\s*({[\s\S]*?})```", content, re.DOTALL)
        for block in function_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict) and ("name" in data or "tool" in data):
                    # Looks like a tool call
                    name = data.get("name") or data.get("tool", "")
                    params = data.get("parameters") or data.get("arguments", {})
                    
                    tool_calls.append(
                        {
                            "name": name,
                            "parameters": params,
                            "type": "json_tool",
                            "id": data.get("id", f"gen-{time.time()}"),
                        }
                    )
            except json.JSONDecodeError:
                continue

        return tool_calls


class OllamaToolAdapter(ToolAdapter):
    """
    Tool adapter for Ollama providers.

    This adapter handles the Ollama tool calling format.
    """

    def __init__(self):
        """Initialize the Ollama tool adapter."""
        super().__init__(default_format=ToolFormat.OLLAMA)

    def format_for_provider(
        self, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> Tuple[Any, Dict[str, Any]]:
        """
        Format tools for Ollama format.

        Args:
            tools: List of tools in standard format
            **kwargs: Additional formatting options

        Returns:
            Tuple of (formatted_tools, updated_kwargs)
        """
        # Ollama expects tools in a format similar to OpenAI
        formatted_tools = []
        for tool in tools:
            if "function" in tool:
                # Already in a compatible format
                formatted_tools.append(tool)
            else:
                # Convert to Ollama format
                formatted_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    },
                }
                formatted_tools.append(formatted_tool)

        # Update kwargs with the formatted tools
        updated_kwargs = kwargs.copy()
        updated_kwargs["tools"] = formatted_tools
        return formatted_tools, updated_kwargs

    def extract_tool_calls(self, response: MessageProtocol) -> List[Dict[str, Any]]:
        """
        Extract tool calls from an Ollama response.

        Args:
            response: Ollama response message

        Returns:
            List of standardized tool calls
        """
        tool_calls = []

        # Check metadata for tool_calls
        if hasattr(response, "metadata") and response.metadata:
            if "tool_calls" in response.metadata:
                for tool_call in response.metadata["tool_calls"]:
                    standardized = self.standardize_tool_call(tool_call)
                    tool_calls.append(standardized)
                return tool_calls

        # If no tool calls found in metadata, try parsing from content
        if not tool_calls:
            content_tool_calls = self._extract_from_content(response.content or "")
            tool_calls.extend(content_tool_calls)

        return tool_calls

    def _extract_from_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract tool calls from message content.

        Args:
            content: Message content

        Returns:
            List of tool calls
        """
        import re
        import json
        import time

        tool_calls = []

        # Look for ReAct format: Action: tool_name(param1=value1, param2=value2)
        action_matches = re.findall(r"Action:\s*(\w+)\s*\(([^)]*)\)", content)
        for tool_name, param_str in action_matches:
            # Parse parameters
            params = {}
            param_pairs = re.findall(r"(\w+)=([^,]+)(?:,|$)", param_str)
            for key, value in param_pairs:
                # Try to convert to appropriate types
                if value.lower() == "true":
                    params[key] = True
                elif value.lower() == "false":
                    params[key] = False
                elif value.isdigit():
                    params[key] = int(value)
                elif value.replace(".", "", 1).isdigit():
                    params[key] = float(value)
                else:
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    params[key] = value

            tool_calls.append(
                {
                    "name": tool_name,
                    "parameters": params,
                    "type": "react_action",
                    "id": f"gen-{time.time()}",
                }
            )

        # Look for tool request format
        tool_requests = re.findall(r"<tool_request>(.*?)</tool_request>", content, re.DOTALL)
        for request_text in tool_requests:
            try:
                request_data = json.loads(request_text)
                tool_name = request_data.get("tool", "")
                params = request_data.get("parameters", {})

                tool_calls.append(
                    {
                        "name": tool_name,
                        "parameters": params,
                        "type": "text_tool",
                        "id": request_data.get("id", f"gen-{time.time()}"),
                    }
                )
            except json.JSONDecodeError:
                # Try to extract with regex if JSON parsing fails
                name_match = re.search(r'"tool":\s*"([^"]+)"', request_text)
                params_match = re.search(r'"parameters":\s*({.*})', request_text)

                if name_match:
                    tool_name = name_match.group(1)
                    params = {}

                    if params_match:
                        try:
                            params = json.loads(params_match.group(1))
                        except json.JSONDecodeError:
                            # Extract key-value pairs with regex
                            param_matches = re.findall(
                                r'"([^"]+)":\s*("[^"]*"|[\d.]+|\{.*?\}|\[.*?\]|true|false)',
                                params_match.group(1),
                            )
                            for param_name, param_value in param_matches:
                                # Convert to appropriate type
                                if param_value.startswith('"') and param_value.endswith('"'):
                                    params[param_name] = param_value[1:-1]
                                elif param_value.lower() in ["true", "false"]:
                                    params[param_name] = param_value.lower() == "true"
                                elif param_value.replace(".", "", 1).isdigit():
                                    if "." in param_value:
                                        params[param_name] = float(param_value)
                                    else:
                                        params[param_name] = int(param_value)
                                else:
                                    params[param_name] = param_value

                    tool_calls.append(
                        {
                            "name": tool_name,
                            "parameters": params,
                            "type": "text_tool",
                            "id": f"gen-{time.time()}",
                        }
                    )

        # Look for JSON code blocks
        json_matches = re.findall(r"```(?:json)?\s*({[\s\S]*?})```", content, re.DOTALL)
        for json_str in json_matches:
            try:
                json_data = json.loads(json_str)
                if isinstance(json_data, dict) and ("tool" in json_data or "name" in json_data):
                    tool_name = json_data.get("tool") or json_data.get("name", "")
                    params = json_data.get("parameters", {})

                    # Only add if not already captured above
                    if tool_name and not any(
                        call["name"] == tool_name and call["parameters"] == params
                        for call in tool_calls
                    ):
                        tool_calls.append(
                            {
                                "name": tool_name,
                                "parameters": params,
                                "type": "json_tool",
                                "id": json_data.get("id", f"gen-{time.time()}"),
                            }
                        )
            except json.JSONDecodeError:
                pass

        return tool_calls


# Factory function to create appropriate adapter
def create_adapter_for_provider(provider_name: str) -> ToolAdapter:
    """
    Create an appropriate tool adapter for a provider.

    Args:
        provider_name: Name of the provider

    Returns:
        ToolAdapter instance for the provider
    """
    provider_lower = provider_name.lower()
    
    if provider_lower == "openai" or provider_lower == "azure":
        return OpenAIToolAdapter()
    elif provider_lower == "anthropic" or provider_lower.startswith("claude"):
        return AnthropicToolAdapter()
    elif provider_lower == "ollama":
        return OllamaToolAdapter()
    else:
        # Default to generic adapter
        return ToolAdapter()
