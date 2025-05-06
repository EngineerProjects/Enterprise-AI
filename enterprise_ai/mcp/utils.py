"""
Utility functions for the Model Context Protocol (MCP).

This module provides helper functions for working with the MCP server,
formatting tool descriptions, and managing tool execution.
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Type, cast

from enterprise_ai.tool.core.base import BaseTool, ToolCapability, ToolConfig
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


def get_tool_capabilities(tool: Union[BaseTool, Type[BaseTool], str]) -> Set[str]:
    """Get the capabilities of a tool.

    Args:
        tool: Tool instance, class, or name

    Returns:
        Set of capability strings
    """
    # For tool instances
    if isinstance(tool, BaseTool):
        capabilities = getattr(tool, "capabilities", set())
        return {cap.value if hasattr(cap, "value") else str(cap) for cap in capabilities}

    # For tool classes
    if isinstance(tool, type) and issubclass(tool, BaseTool):
        capabilities = getattr(tool, "capabilities", set())
        return {cap.value if hasattr(cap, "value") else str(cap) for cap in capabilities}

    # For tool names
    if isinstance(tool, str):
        from enterprise_ai.tool.core.registry import get_registry

        registry = get_registry()
        tool_cls = registry.get_tool_class(tool)
        if tool_cls:
            return get_tool_capabilities(tool_cls)

    return set()


def get_all_sessions_info() -> Dict[str, Dict[str, Any]]:
    """Get information about all active MCP sessions.

    Returns:
        Dictionary of session information
    """
    from enterprise_ai.mcp.server import get_mcp_server

    server = get_mcp_server()
    sessions = {}

    for session_id in server.get_all_sessions():
        session_info = server.get_session_info(session_id)
        if session_info:
            sessions[session_id] = session_info

    return sessions


async def execute_tool_by_name(
    tool_name: str, session_id: Optional[str] = None, timeout: Optional[float] = None, **kwargs: Any
) -> ToolResult:
    """Execute a tool by name in a specific session or create a temporary session.

    Args:
        tool_name: Name of the tool to execute
        session_id: Optional session ID to use
        timeout: Optional timeout override
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
        result = await session.execute_tool(tool_name, timeout=timeout, **kwargs)
        return result
    finally:
        # Clean up temporary session if created
        if not session_id:
            await server.close_session(session.session_id)


async def batch_execute_tools(
    executions: List[Dict[str, Any]], session_id: Optional[str] = None, parallel: bool = True
) -> Dict[str, ToolResult]:
    """Execute multiple tools in batch mode.

    Args:
        executions: List of tool execution specifications:
                   [{"tool_name": "name", "parameters": {...}, "timeout": optional_timeout}, ...]
        session_id: Optional session ID to use
        parallel: Whether to execute tools in parallel (True) or sequentially (False)

    Returns:
        Dictionary mapping execution IDs to results
    """
    from enterprise_ai.mcp.server import get_mcp_server
    from enterprise_ai.mcp.client import MCPClient

    # Create client with session
    if session_id:
        client = MCPClient(session_id)
    else:
        # Create temporary session
        temp_id = f"temp-batch-{uuid.uuid4()}"
        server = get_mcp_server()

        # Get all tool names
        tool_names = [
            execution.get("tool_name") for execution in executions if execution.get("tool_name")
        ]

        # Create session with all needed tools
        server.create_session(temp_id, tool_names=tool_names)
        client = MCPClient(temp_id)

    try:
        # Execute tools
        if parallel:
            results = await client.execute_tools_parallel(executions)
        else:
            results = await client.execute_tools_sequential(executions)

        # Convert to dictionary with execution IDs
        return {f"exec-{i}": result for i, (_, result) in enumerate(results)}
    finally:
        # Clean up temporary session if created
        if not session_id:
            await client.close()


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
        version = getattr(tool_cls, "version", "1.0.0")
        capabilities = getattr(tool_cls, "capabilities", set())

        # Convert capabilities to a list of strings
        capability_list = [cap.value if hasattr(cap, "value") else str(cap) for cap in capabilities]

        return {
            "name": name,
            "description": description,
            "parameters": parameters,
            "version": version,
            "capabilities": capability_list,
        }
    except Exception as e:
        logger.error(f"Error getting tool schema for {tool_name}: {e}")
        return None


async def get_compatible_tools(tool_names: List[str]) -> Dict[str, List[str]]:
    """Find compatible tools that can work together.

    Args:
        tool_names: List of tool names to check compatibility

    Returns:
        Dictionary mapping each tool to a list of compatible tools
    """
    from enterprise_ai.tool.core.registry import get_registry

    registry = get_registry()
    result = {}

    # Get tool classes for all names
    tools_info = {}
    for name in tool_names:
        tool_cls = registry.get_tool_class(name)
        if not tool_cls:
            continue

        # Get dependencies and capabilities
        dependencies = getattr(tool_cls, "dependencies", [])
        capabilities = getattr(tool_cls, "capabilities", set())
        capabilities = {cap.value if hasattr(cap, "value") else str(cap) for cap in capabilities}

        tools_info[name] = {"dependencies": dependencies, "capabilities": capabilities}

    # Check compatibility for each tool
    for name, info in tools_info.items():
        compatible = []
        dependencies = info["dependencies"]

        for other_name, other_info in tools_info.items():
            if name == other_name:
                continue

            # Check if the other tool is a dependency
            if other_name in dependencies:
                compatible.append(other_name)
                continue

            # Check if tools share capabilities (which can be a sign of compatibility)
            other_capabilities = other_info["capabilities"]
            if other_capabilities and info["capabilities"]:
                if other_capabilities.intersection(info["capabilities"]):
                    compatible.append(other_name)
                    continue

            # Tools without shared capabilities or dependencies are not guaranteed
            # to be compatible, but we don't have proof they are incompatible

        result[name] = compatible

    return result


def generate_tool_usage_example(tool_name: str) -> Optional[Dict[str, Any]]:
    """Generate a usage example for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Dictionary with example parameters or None if not possible
    """
    schema = get_tool_schema(tool_name)
    if not schema or not schema.get("parameters"):
        return None

    parameters = schema["parameters"]
    example = {}

    # Create example parameters based on JSON schema
    props = parameters.get("properties", {})
    for name, prop in props.items():
        prop_type = prop.get("type")

        # Generate reasonable defaults based on type
        if prop_type == "string":
            # Use enum value if available
            if "enum" in prop:
                example[name] = prop["enum"][0]
            # Use a sample value based on description
            elif "description" in prop:
                desc = prop["description"].lower()
                if "url" in desc:
                    example[name] = "https://example.com"
                elif "file" in desc or "path" in desc:
                    example[name] = "/home/user/example.txt"
                elif "email" in desc:
                    example[name] = "user@example.com"
                elif "name" in desc:
                    example[name] = "example_name"
                else:
                    example[name] = "example_string"
        elif prop_type == "number" or prop_type == "integer":
            example[name] = 42
        elif prop_type == "boolean":
            example[name] = True
        elif prop_type == "array":
            example[name] = []
        elif prop_type == "object":
            example[name] = {}

    return {"tool_name": tool_name, "parameters": example}


def create_tool_usage_guide(tool_name: str) -> str:
    """Create a detailed usage guide for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Formatted usage guide as a string
    """
    schema = get_tool_schema(tool_name)
    if not schema:
        return f"No information available for tool: {tool_name}"

    name = schema.get("name", tool_name)
    description = schema.get("description", "No description available")
    parameters = schema.get("parameters", {})
    version = schema.get("version", "1.0.0")
    capabilities = schema.get("capabilities", [])

    # Generate example usage
    example = generate_tool_usage_example(tool_name)

    # Format the guide
    lines = [
        f"# {name} (v{version})",
        "",
        f"{description}",
        "",
        "## Capabilities",
    ]

    if capabilities:
        for cap in capabilities:
            lines.append(f"- {cap}")
    else:
        lines.append("- No specific capabilities listed")

    lines.extend(
        [
            "",
            "## Parameters",
        ]
    )

    required = parameters.get("required", [])
    props = parameters.get("properties", {})

    if props:
        for prop_name, prop_info in props.items():
            req_str = " (required)" if prop_name in required else " (optional)"
            prop_type = prop_info.get("type", "any")
            prop_desc = prop_info.get("description", "No description")

            lines.append(f"### {prop_name}: {prop_type}{req_str}")
            lines.append(f"{prop_desc}")

            # Add enum values if available
            if "enum" in prop_info:
                lines.append("")
                lines.append("Allowed values:")
                for val in prop_info["enum"]:
                    lines.append(f"- `{val}`")

            lines.append("")
    else:
        lines.append("No parameters specified")

    # Add example usage
    lines.extend(
        [
            "## Example Usage",
            "",
            "```python",
            "await client.execute_tool(",
            f'    "{name}",',
        ]
    )

    if example and example.get("parameters"):
        for param_name, param_value in example["parameters"].items():
            if isinstance(param_value, str):
                lines.append(f'    {param_name}="{param_value}",')
            else:
                lines.append(f"    {param_name}={param_value},")

    lines.extend(
        [
            ")",
            "```",
        ]
    )

    return "\n".join(lines)
