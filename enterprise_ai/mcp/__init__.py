"""
Model Context Protocol (MCP) for Enterprise AI.

This module provides a protocol for AI agents to discover and use tools in a
standardized way. MCP enables dynamic tool discovery, manages tool lifecycle,
and provides a consistent interface for tool execution.

The main components are:
- MCPServer: Central server that manages tool sessions
- MCPClient: Client for connecting to the MCP server
- AgentMCPClient: Specialized client for AI agent use

MCP follows these key principles:
1. Dynamic tool discovery based on agent capabilities
2. Standardized tool execution and error handling
3. Clean separation between agents and tool implementations
4. Centralized tool management and monitoring
"""

from enterprise_ai.mcp.server import MCPServer, MCPSession, get_mcp_server
from enterprise_ai.mcp.client import MCPClient, AgentMCPClient, ToolFilterStrategy
from enterprise_ai.mcp.utils import (
    format_tool_descriptions,
    format_tool_result,
    get_all_sessions_info,
    execute_tool_by_name,
    get_tool_schema,
    batch_execute_tools,
    get_tool_capabilities,
    get_compatible_tools,
    create_tool_usage_guide,
)

__all__ = [
    # Server components
    "MCPServer",
    "MCPSession",
    "get_mcp_server",
    # Client components
    "MCPClient",
    "AgentMCPClient",
    "ToolFilterStrategy",
    # Utility functions
    "format_tool_descriptions",
    "format_tool_result",
    "get_all_sessions_info",
    "execute_tool_by_name",
    "get_tool_schema",
    "batch_execute_tools",
    "get_tool_capabilities",
    "get_compatible_tools",
    "create_tool_usage_guide",
]
