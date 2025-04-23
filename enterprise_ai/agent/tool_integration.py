"""
Tool integration layer for Enterprise AI agents.

This module provides the core functionality for integrating tools with agents,
serving as a bridge between the agent system and the Model Context Protocol (MCP).
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.prompt import get_prompt, format_prompt, combine_prompts

logger = get_logger("agent.tool_integration")


class ToolIntegrationError(Exception):
    """Error raised during tool integration."""

    def __init__(self, message: str):
        self.message = message
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

                tool_calls.append({"name": name, "parameters": params})

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
                        {"name": name, "parameters": params, "id": tool_call.get("id")}
                    )

        # Check for metadata with tool_calls (Anthropic format)
        elif "metadata" in message and "tool_calls" in message["metadata"]:
            for tool_call in message["metadata"]["tool_calls"]:
                name = tool_call.get("name", "")
                params = tool_call.get("parameters", {})

                tool_calls.append({"name": name, "parameters": params, "id": tool_call.get("id")})

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

                    tool_calls.append({"name": name, "parameters": params})
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
                                # If can't parse params as JSON, use empty dict
                                pass

                        tool_calls.append({"name": name, "parameters": params})

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

                tool_calls.append({"name": tool_name, "parameters": params})

        return tool_calls

    @staticmethod
    def format_tool_response(
        tool_name: str, tool_result: ToolResult, tool_call_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format a tool execution result for LLM function calling.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            tool_call_id: Optional ID of the tool call

        Returns:
            Formatted tool response
        """
        # Format response based on whether it was successful
        if tool_result.error:
            content = f"Error: {tool_result.error}"
            status = "error"
        else:
            content = str(tool_result.output) if tool_result.output is not None else ""
            status = "success"

        result = {"tool": tool_name, "status": status, "output": content}

        # Add tool_call_id if provided
        if tool_call_id:
            result["tool_call_id"] = tool_call_id

        return result

    @staticmethod
    def format_tool_response_as_message(
        tool_name: str, tool_result: ToolResult, tool_call_id: Optional[str] = None
    ) -> str:
        """
        Format a tool execution result as a text message.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            tool_call_id: Optional ID of the tool call

        Returns:
            Formatted tool response as text
        """
        response = FunctionCallingFormatter.format_tool_response(
            tool_name, tool_result, tool_call_id
        )

        return f"""<tool_result>
{json.dumps(response, indent=2)}
</tool_result>"""


def parse_message_for_tool_calls(message: MessageProtocol) -> List[Dict[str, Any]]:
    """
    Parse a message for tool calls.

    Args:
        message: Message to parse

    Returns:
        List of tool calls with name and parameters
    """
    message_dict: Dict[str, Any] = {"content": message.content}

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


def format_tool_response_message(
    tool_name: str, tool_result: ToolResult, tool_call_id: Optional[str] = None
) -> MessageProtocol:
    """
    Format a tool execution result as a user message.

    Args:
        tool_name: Name of the executed tool
        tool_result: Result of tool execution
        tool_call_id: Optional ID of the tool call

    Returns:
        Formatted message
    """
    response_text = FunctionCallingFormatter.format_tool_response_as_message(
        tool_name, tool_result, tool_call_id
    )

    return cast(MessageProtocol, Message.user_message(response_text))


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
        prompt_id = "system.cot"
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
