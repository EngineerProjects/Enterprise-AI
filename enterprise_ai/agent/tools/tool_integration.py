"""
Tool integration layer for Enterprise AI agents.

This module provides the core functionality for integrating tools with agents,
serving as a bridge between the agent system and the Model Context Protocol (MCP).
"""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.prompt import get_prompt, format_prompt, combine_prompts
from enterprise_ai.mcp.utils import format_tool_result

logger = get_logger("agent.tool_integration")


class ToolIntegrationError(Exception):
    """Error raised during tool integration."""

    def __init__(
        self, message: str, error_code: Optional[str] = None, tool_name: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.tool_name = tool_name
        super().__init__(self.message)


class FunctionCallingFormatter:
    """
    Utility for formatting function calling requests and responses.

    This class provides methods for parsing function calls from LLM responses
    and formatting function results for subsequent LLM prompts.
    """

    @staticmethod
    def parse_tool_calls(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse tool calls from a message with function calls.

        Args:
            message: Message to parse

        Returns:
            List of tool calls with name and parameters
        """
        tool_calls = []

        # Check for function_call in the message (OpenAI format)
        if "function_call" in message:
            function_call = message["function_call"]
            if isinstance(function_call, dict):
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
                        "id": function_call.get("id", str(time.time())),
                    }
                )

        # Check for tool_calls in the message (newer OpenAI format)
        elif "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                if tool_call.get("type") == "function":
                    function = tool_call.get("function", {})
                    name = function.get("name", "")
                    arguments = function.get("arguments", "{}")

                    # Parse arguments
                    try:
                        params = json.loads(arguments)
                    except json.JSONDecodeError:
                        params = {}

                    tool_calls.append(
                        {
                            "name": name,
                            "parameters": params,
                            "type": "tool_call",
                            "id": tool_call.get("id", str(time.time())),
                        }
                    )

        # Check for metadata with tool_calls (Anthropic format)
        elif "metadata" in message and "tool_calls" in message["metadata"]:
            for tool_call in message["metadata"]["tool_calls"]:
                name = tool_call.get("name", "")
                params = tool_call.get("parameters", {})

                tool_calls.append(
                    {
                        "name": name,
                        "parameters": params,
                        "type": "anthropic_tool",
                        "id": tool_call.get("id", str(time.time())),
                    }
                )

        # Check content for specific format (fallback for text-based tools)
        elif "content" in message and message["content"]:
            content = message["content"]

            # Look for tool request format like:
            # <tool_request>
            # "tool": "tool_name",
            # "parameters": { ... }
            # </tool_request>
            tool_requests = re.findall(r"<tool_request>(.*?)</tool_request>", content, re.DOTALL)

            for request_text in tool_requests:
                # Try to parse as JSON first
                try:
                    request_data = json.loads(request_text)
                    name = request_data.get("tool", "")
                    params = request_data.get("parameters", {})

                    tool_calls.append(
                        {
                            "name": name,
                            "parameters": params,
                            "type": "text_tool",
                            "id": request_data.get("id", str(time.time())),
                        }
                    )
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract key-value pairs
                    name_match = re.search(r'"tool":\s*"([^"]+)"', request_text)
                    params_match = re.search(r'"parameters":\s*({.*})', request_text)

                    if name_match:
                        name = name_match.group(1)
                        params = {}

                        if params_match:
                            try:
                                params = json.loads(params_match.group(1))
                            except json.JSONDecodeError:
                                # If can't parse params as JSON, extract key-value pairs
                                param_matches = re.findall(
                                    r'"([^"]+)":\s*("[^"]*"|[\d.]+|\{.*?\}|\[.*?\]|true|false)',
                                    params_match.group(1),
                                )
                                for param_name, param_value in param_matches:
                                    # Convert value to appropriate type
                                    if param_value.startswith('"') and param_value.endswith('"'):
                                        # String value
                                        params[param_name] = param_value[1:-1]
                                    elif param_value.lower() in ["true", "false"]:
                                        # Boolean value
                                        params[param_name] = param_value.lower() == "true"
                                    elif param_value.replace(".", "", 1).isdigit():
                                        # Numeric value
                                        if "." in param_value:
                                            params[param_name] = float(param_value)
                                        else:
                                            params[param_name] = int(param_value)
                                    else:
                                        # Default to string
                                        params[param_name] = param_value

                        tool_calls.append(
                            {
                                "name": name,
                                "parameters": params,
                                "type": "text_tool",
                                "id": str(time.time()),
                            }
                        )

            # Also check for ReAct format: Action: tool_name(param1=value1, param2=value2)
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
                        "id": str(time.time()),
                    }
                )

        # Look for JSON-formatted tool calls inline in the content
        if "content" in message and message["content"]:
            content = message["content"]

            # Match JSON objects that have a "tool" field
            json_tool_matches = re.findall(r"```(?:json)?\s*({[\s\S]*?})```", content)
            for json_str in json_tool_matches:
                try:
                    json_data = json.loads(json_str)
                    if isinstance(json_data, dict) and "tool" in json_data:
                        name = json_data.get("tool", "")
                        params = json_data.get("parameters", {})

                        # Only add if not already captured above
                        if name and not any(
                            call["name"] == name and call["parameters"] == params
                            for call in tool_calls
                        ):
                            tool_calls.append(
                                {
                                    "name": name,
                                    "parameters": params,
                                    "type": "json_tool",
                                    "id": json_data.get("id", str(time.time())),
                                }
                            )
                except json.JSONDecodeError:
                    pass

        return tool_calls

    @staticmethod
    def format_tool_response(
        tool_name: str,
        tool_result: ToolResult,
        tool_call_id: Optional[str] = None,
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        """
        Format a tool execution result for LLM function calling.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            tool_call_id: Optional ID of the tool call
            include_metadata: Whether to include result metadata

        Returns:
            Formatted tool response
        """
        # Format response based on whether it was successful
        if tool_result.error:
            content = f"Error: {tool_result.error}"
            status = "error"
        else:
            content = format_tool_result(tool_result)
            status = "success"

        # Create the base response
        result = {"tool": tool_name, "status": status, "output": content}

        # Add tool_call_id if provided
        if tool_call_id:
            result["tool_call_id"] = tool_call_id

        # Add execution time if available
        if tool_result.metadata and tool_result.metadata.execution_time_ms is not None:
            result["execution_time_ms"] = tool_result.metadata.execution_time_ms

        # Add metadata if requested
        if include_metadata and tool_result.metadata:
            meta_dict = {}

            # Add tool name
            if tool_result.metadata.tool_name:
                meta_dict["tool_name"] = tool_result.metadata.tool_name

            # Add tool version
            if tool_result.metadata.tool_version:
                meta_dict["tool_version"] = tool_result.metadata.tool_version

            # Add execution ID
            if tool_result.metadata.execution_id:
                meta_dict["execution_id"] = tool_result.metadata.execution_id

            # Add timestamps
            if tool_result.metadata.start_time:
                meta_dict["start_time"] = tool_result.metadata.start_time.isoformat()
            if tool_result.metadata.end_time:
                meta_dict["end_time"] = tool_result.metadata.end_time.isoformat()

            # Add cache info
            if tool_result.metadata.cache_hit:
                meta_dict["cache_hit"] = True

            # Add to result if we have metadata
            if meta_dict:
                result["metadata"] = meta_dict

        # Add error details for failures
        if tool_result.error and isinstance(tool_result, ToolFailure):
            if tool_result.error_code:
                result["error_code"] = tool_result.error_code

            if hasattr(tool_result, "retryable") and tool_result.retryable:
                result["retryable"] = True

            if hasattr(tool_result, "suggestions") and tool_result.suggestions:
                result["suggestions"] = tool_result.suggestions

        return result

    @staticmethod
    def format_tool_response_as_message(
        tool_name: str,
        tool_result: ToolResult,
        tool_call_id: Optional[str] = None,
        response_format: str = "json",
    ) -> str:
        """
        Format a tool execution result as a text message.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            tool_call_id: Optional ID of the tool call
            response_format: Format of the response ("json", "markdown", or "react")

        Returns:
            Formatted tool response as text
        """
        response = FunctionCallingFormatter.format_tool_response(
            tool_name, tool_result, tool_call_id
        )

        if response_format == "json":
            return f"""<tool_result>
{json.dumps(response, indent=2)}
</tool_result>"""
        elif response_format == "react":
            # Format as ReAct observation
            if tool_result.error:
                return f"Observation: Error executing {tool_name}: {tool_result.error}"
            else:
                # Handle different output types for better formatting
                if isinstance(tool_result.output, (dict, list)):
                    try:
                        formatted_output = json.dumps(tool_result.output, indent=2)
                        return f"Observation: {formatted_output}"
                    except (TypeError, ValueError):
                        return f"Observation: {tool_result.output}"
                else:
                    return f"Observation: {tool_result.output}"
        else:  # markdown format
            result_md = f"### Tool Result: {tool_name}\n\n"

            if tool_result.error:
                result_md += f"**Error:** {tool_result.error}\n\n"

                # Add suggestions if available
                if isinstance(tool_result, ToolFailure) and tool_result.suggestions:
                    result_md += "**Suggestions:**\n"
                    for suggestion in tool_result.suggestions:
                        result_md += f"- {suggestion}\n"
                    result_md += "\n"
            else:
                # Handle different output types for better formatting
                if isinstance(tool_result.output, (dict, list)):
                    try:
                        result_md += "```json\n"
                        result_md += json.dumps(tool_result.output, indent=2)
                        result_md += "\n```\n"
                    except (TypeError, ValueError):
                        result_md += f"{tool_result.output}\n"
                else:
                    result_md += f"{tool_result.output}\n"

            # Add metadata if available
            if tool_result.metadata and tool_result.metadata.execution_time_ms is not None:
                result_md += f"\n*Execution time: {tool_result.metadata.execution_time_ms:.2f}ms*"

            return result_md


def parse_message_for_tool_calls(message: MessageProtocol) -> List[Dict[str, Any]]:
    """
    Parse a message for tool calls.

    Args:
        message: Message to parse

    Returns:
        List of tool calls with name and parameters
    """
    if not message:
        logger.warning("Empty message received in parse_message_for_tool_calls")
        return []

    try:
        message_dict: Dict[str, Any] = {"content": getattr(message, "content", "")}

        # Add function_call if available
        if hasattr(message, "function_call") and message.function_call:
            message_dict["function_call"] = message.function_call

        # Add tool_calls if available
        if hasattr(message, "tool_calls") and message.tool_calls:
            message_dict["tool_calls"] = message.tool_calls

        # Add metadata if available
        if hasattr(message, "metadata") and message.metadata:
            # Explicitly annotate as Dict[str, Any] to fix type mismatch
            message_dict["metadata"] = dict(message.metadata)

        return FunctionCallingFormatter.parse_tool_calls(message_dict)
    except Exception as e:
        logger.error(f"Error parsing message for tool calls: {e}")
        return []


def format_tool_response_message(
    tool_name: str,
    tool_result: ToolResult,
    tool_call_id: Optional[str] = None,
    response_format: str = "json",
) -> MessageProtocol:
    """
    Format a tool execution result as a user message.

    Args:
        tool_name: Name of the executed tool
        tool_result: Result of tool execution
        tool_call_id: Optional ID of the tool call
        response_format: Format of the response ("json", "markdown", or "react")

    Returns:
        Formatted message
    """
    response_text = FunctionCallingFormatter.format_tool_response_as_message(
        tool_name, tool_result, tool_call_id, response_format
    )

    # Create metadata for the message
    metadata = {"tool_result": True, "tool_name": tool_name, "success": tool_result.error is None}

    # Add tool call ID if provided
    if tool_call_id:
        metadata["tool_call_id"] = tool_call_id

    # Add execution time if available
    if tool_result.metadata and tool_result.metadata.execution_time_ms is not None:
        metadata["execution_time_ms"] = tool_result.metadata.execution_time_ms

    # Add error info if applicable
    if tool_result.error:
        metadata["error"] = tool_result.error
        if isinstance(tool_result, ToolFailure) and tool_result.error_code:
            metadata["error_code"] = tool_result.error_code

    # Create the message
    if response_format == "react":
        # For ReAct format, use a standard user message
        return cast(MessageProtocol, Message.user_message(response_text, metadata=metadata))
    elif tool_call_id:
        # Use tool message if tool_call_id is provided
        return cast(
            MessageProtocol,
            Message.tool_message(response_text, tool_name, tool_call_id, metadata=metadata),
        )
    else:
        # Default to user message
        return cast(MessageProtocol, Message.user_message(response_text, metadata=metadata))


def get_tool_prompt_for_reasoning(reasoning_type: str, tools_description: str) -> str:
    """
    Get the appropriate tool prompt for a reasoning framework.

    Args:
        reasoning_type: Type of reasoning framework
        tools_description: Formatted description of available tools

    Returns:
        Formatted tool prompt
    """
    # Try to get the right prompt template
    if reasoning_type == "react":
        prompt_id = "system.react"
    elif reasoning_type == "cot":
        prompt_id = "system.tool_cot"
    elif reasoning_type == "swe":
        prompt_id = "system.swe"
    elif reasoning_type == "mcp":
        prompt_id = "system.mcp"
    else:
        # Default to basic tools prompt
        prompt_id = "system.with_tools"

    # Format the prompt with tool descriptions
    try:
        prompt = format_prompt(prompt_id, tools_description=tools_description)
        if prompt:
            return prompt
    except Exception as e:
        logger.warning(f"Error formatting tool prompt {prompt_id}: {e}")

    # Fallback to basic tools prompt if specific one isn't available
    try:
        prompt = format_prompt("system.with_tools", tools_description=tools_description)
        if prompt:
            return prompt
    except Exception as e:
        logger.warning(f"Error formatting fallback tool prompt: {e}")

    # Final fallback - a minimal tools description
    return f"""You have access to tools that extend your capabilities.

Available tools:
{tools_description}

When I respond with tool results, they will be in this format:
<tool_result>
  "tool": "tool_name",
  "status": "success|error",
  "output": "Result of the tool execution"
</tool_result>
"""


def get_tool_error_handling_prompt() -> str:
    """
    Get a prompt for handling tool errors.

    Returns:
        Formatted error handling prompt
    """
    try:
        prompt = format_prompt("system.tool_error")
        if prompt:
            return prompt
    except Exception as e:
        logger.warning(f"Error formatting tool error prompt: {e}")

    # Fallback to a default prompt
    return """When a tool execution returns an error, follow these steps:

1. Check if you provided the correct parameters in the proper format
2. Consider if the tool's preconditions were met
3. Try alternative approaches or different tools if necessary
4. For temporary errors, retry the operation
5. For permanent errors, report the issue and try a different approach

Common error types:
- Parameter errors: Correct the parameter format or values
- Access errors: Verify permissions or resource availability
- Execution errors: Check for invalid operations
- Timeout errors: Consider breaking the task into smaller parts
"""


def get_tool_capabilities_description(
    capabilities: List[Union[str, ToolCapability]], detailed: bool = True
) -> str:
    """
    Get a description of tool capabilities.

    Args:
        capabilities: List of capabilities
        detailed: Whether to include detailed descriptions

    Returns:
        Formatted capabilities description
    """
    cap_names = [cap.value if isinstance(cap, ToolCapability) else str(cap) for cap in capabilities]

    if not detailed:
        # Simple list
        return ", ".join(cap_names)

    # Detailed descriptions
    capability_descriptions = {
        "file_access": "Access to file system for reading and writing files",
        "network_access": "Access to perform network requests",
        "code_execution": "Ability to execute code in various languages",
        "api_access": "Access to external APIs",
        "data_processing": "Processing and analysis of data",
        "image_processing": "Generation and manipulation of images",
        "text_generation": "Creation and manipulation of text content",
        "vector_db": "Access to vector databases for semantic search",
        "agent_interaction": "Communication with other agents",
        "browser_control": "Control of browser for web automation",
        "terminal_access": "Access to terminal commands",
        "planning": "Creation and management of plans",
        "search": "Ability to search for information",
        "utility": "Miscellaneous utility functions",
    }

    descriptions = []
    for cap in cap_names:
        if cap in capability_descriptions:
            descriptions.append(f"- {cap}: {capability_descriptions[cap]}")
        else:
            descriptions.append(f"- {cap}")

    return "\n".join(descriptions)


def validate_tool_parameters(
    tool_name: str, params: Dict[str, Any], schema: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Validate tool parameters against a schema.

    Args:
        tool_name: Name of the tool
        params: Parameters to validate
        schema: JSON Schema for validation

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required parameters
    required = schema.get("required", [])
    for req in required:
        if req not in params:
            return False, f"Missing required parameter: {req}"

    # Check parameter types
    properties = schema.get("properties", {})
    for name, value in params.items():
        if name in properties:
            prop = properties[name]
            prop_type = prop.get("type")

            # Type validation
            if prop_type == "string" and not isinstance(value, str):
                return False, f"Parameter '{name}' must be a string"
            elif prop_type == "number" and not isinstance(value, (int, float)):
                return False, f"Parameter '{name}' must be a number"
            elif prop_type == "integer" and not isinstance(value, int):
                return False, f"Parameter '{name}' must be an integer"
            elif prop_type == "boolean" and not isinstance(value, bool):
                return False, f"Parameter '{name}' must be a boolean"
            elif prop_type == "array" and not isinstance(value, list):
                return False, f"Parameter '{name}' must be an array"
            elif prop_type == "object" and not isinstance(value, dict):
                return False, f"Parameter '{name}' must be an object"

            # Enum validation
            if "enum" in prop and value not in prop["enum"]:
                return (
                    False,
                    f"Parameter '{name}' must be one of: {', '.join(map(str, prop['enum']))}",
                )

    return True, None


def merge_tool_schemas(schemas: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Merge multiple tool schemas into a single dictionary.

    Args:
        schemas: List of tool schemas

    Returns:
        Dictionary mapping tool names to schema objects
    """
    merged = {}
    for schema in schemas:
        if "function" in schema:
            func = schema["function"]
            name = func.get("name")
            if name:
                merged[name] = func
    return merged


async def execute_tool_with_retry(
    agent: AgentProtocol,
    tool_name: str,
    parameters: Dict[str, Any],
    max_retries: int = 2,
    backoff_base: float = 1.0,
    timeout: Optional[float] = None,
) -> ToolResult:
    """
    Execute a tool with retry logic.

    Args:
        agent: Agent to execute the tool
        tool_name: Name of the tool to execute
        parameters: Tool parameters
        max_retries: Maximum number of retry attempts
        backoff_base: Base time for exponential backoff
        timeout: Optional timeout for tool execution

    Returns:
        Tool execution result
    """
    if not hasattr(agent, "_tool_manager"):
        return ToolFailure(error="Agent does not have a tool manager", error_code="NO_TOOL_MANAGER")

    tool_manager = getattr(agent, "_tool_manager")

    # Validate tool exists
    if tool_name not in tool_manager.list_tools():
        return ToolFailure(error=f"Tool not found: {tool_name}", error_code="TOOL_NOT_FOUND")

    # Execute with retry logic
    try:
        result = await tool_manager.execute_tool(
            tool_name=tool_name,
            timeout=timeout,
            retry_count=max_retries,
            retry_delay=backoff_base,
            **parameters,
        )
        return result
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return ToolFailure(error=f"Tool execution error: {str(e)}", error_code="EXECUTION_ERROR")
