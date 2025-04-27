"""
Utility functions for the Model Context Protocol (MCP).

This module provides helper functions for working with the MCP server,
formatting tool descriptions, and managing tool execution.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.logger import get_logger

logger = get_logger("mcp.utils")


def format_tool_descriptions(tools: List[Dict[str, Any]]) -> str:
    """Format tool descriptions for inclusion in prompts.

    Args:
        tools: List of tool definitions

    Returns:
        Formatted tool descriptions as a string
    """
    if not tools:
        return "No tools available."

    formatted = ""
    for tool in tools:
        try:
            # Handle different tool formats
            tool_name = None
            tool_description = "No description available"
            tool_params = {}

            # Extract tool name
            if isinstance(tool, dict):
                if "name" in tool:
                    tool_name = tool.get("name")
                elif "function" in tool and isinstance(tool.get("function"), dict):
                    function_data = tool.get("function", {})
                    tool_name = function_data.get("name")
                    tool_description = function_data.get("description", tool_description)
                    tool_params = function_data.get("parameters", {})

            # Skip tools without names
            if not tool_name:
                continue

            formatted += f"Tool: {tool_name}\n"
            formatted += f"Description: {tool_description}\n"

            # Format parameters if available and well-formed
            if tool_params and isinstance(tool_params, dict):
                formatted += "Parameters:\n"

                # Handle OpenAPI/JSON Schema style properties
                properties = tool_params.get("properties", {})
                required = tool_params.get("required", [])

                if properties and isinstance(properties, dict):
                    for param_name, param_info in properties.items():
                        if not isinstance(param_info, dict):
                            continue

                        param_type = param_info.get("type", "any")
                        description = param_info.get("description", "")
                        is_required = param_name in required

                        req_str = " (required)" if is_required else " (optional)"
                        formatted += f"  - {param_name}: {param_type}{req_str} - {description}\n"
                else:
                    # Simple parameter summary
                    formatted += f"  {str(tool_params)}\n"

            formatted += "\n"
        except Exception as e:
            logger.warning(f"Error formatting tool description: {e}")
            continue

    return formatted


def format_tool_result(result: ToolResult) -> str:
    """Format a tool result for display.

    Args:
        result: Tool execution result

    Returns:
        Formatted result string
    """
    if result.error:
        return f"Error: {result.error}"

    if result.output is None:
        return "No output from tool."

    # Handle different output types
    if isinstance(result.output, (dict, list)):
        try:
            return json.dumps(result.output, indent=2)
        except (TypeError, ValueError):
            return str(result.output)

    return str(result.output)


def get_all_sessions_info() -> Dict[str, Dict[str, Any]]:
    """Get information about all active MCP sessions.

    Returns:
        Dictionary of session information
    """
    from enterprise_ai.mcp.server import get_mcp_server

    server = get_mcp_server()
    sessions = {}

    for session_id in server.get_all_sessions():
        session = server.get_session(session_id)
        if session:
            tool_count = len(session.get_available_tools())
            history_count = len(session.get_history())

            sessions[session_id] = {
                "tool_count": tool_count,
                "history_count": history_count,
                "is_agent_session": session_id.startswith("agent-"),
            }

    return sessions


async def execute_tool_by_name(
    tool_name: str, session_id: Optional[str] = None, **kwargs: Any
) -> ToolResult:
    """Execute a tool by name in a specific session or create a temporary session.

    Args:
        tool_name: Name of the tool to execute
        session_id: Optional session ID to use
        **kwargs: Parameters for the tool

    Returns:
        Tool execution result
    """
    from enterprise_ai.mcp.server import get_mcp_server

    server = get_mcp_server()

    # Use provided session or create a temporary one
    if session_id:
        session = server.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
    else:
        # Create a temporary session with just this tool
        temp_id = f"temp-{uuid.uuid4()}"
        session = server.create_session(temp_id, tool_names=[tool_name])

    try:
        # Execute the tool
        result = await session.execute_tool(tool_name, **kwargs)
        return result
    finally:
        # Clean up temporary session if created
        if not session_id:
            await server.close_session(session.session_id)


def get_tool_schema(tool_name: str) -> Optional[Dict[str, Any]]:
    """Get the JSON schema for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool schema or None if not found
    """
    from enterprise_ai.tool.core.registry import get_registry

    registry = get_registry()

    tool_cls = registry.get_tool_class(tool_name)
    if not tool_cls:
        return None

    # Create a temporary instance to get the parameters
    try:
        name = getattr(tool_cls, "name", tool_name)
        description = getattr(tool_cls, "description", "")
        parameters = getattr(tool_cls, "parameters", {})

        return {"name": name, "description": description, "parameters": parameters}
    except Exception as e:
        logger.error(f"Error getting tool schema for {tool_name}: {e}")
        return None
