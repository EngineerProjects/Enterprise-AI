"""
Enterprise AI Model Context Protocol (MCP) Module.

This module provides a comprehensive tool execution engine that handles:
- Tool registration and management
- Authorization and approval workflows  
- Session management
- Agent communication
- Sandbox integration
- MCP protocol compliance

The MCP module serves as the execution layer that complements the LLM module's
text generation capabilities, enabling clean separation of concerns.
"""

from enterprise_ai.mcp.server import EnterpriseMCPServer
from enterprise_ai.mcp.executor import ToolExecutor
from enterprise_ai.mcp.session_manager import SessionManager
from enterprise_ai.mcp.config import MCPConfig

__all__ = [
    "EnterpriseMCPServer",
    "ToolExecutor", 
    "SessionManager",
    "MCPConfig",
]