"""
Simplified MCP Module for Enterprise AI.

Focused on tool execution only - leverages existing tool infrastructure.
"""

from enterprise_ai.mcp.executor import ToolMCP, create_simple_mcp
from enterprise_ai.mcp.sandbox_config import (
    SandboxConfig, 
    create_sandbox_config,
    DEFAULT_SANDBOX_CONFIG,
    SAFE_SANDBOX_CONFIG,
    STRICT_SANDBOX_CONFIG
)
from enterprise_ai.mcp.sandbox_executor import (
    SimpleMCPExecutor,
    SandboxToolExecutor,
)

__all__ = [
    "ToolMCP", 
    "create_simple_mcp",

    # Sandbox Configuration
    "SandboxConfig",
    "create_sandbox_config", 
    "DEFAULT_SANDBOX_CONFIG",
    "SAFE_SANDBOX_CONFIG", 
    "STRICT_SANDBOX_CONFIG",

    # Sandbox Executor
    "SimpleMCPExecutor",
    "SandboxToolExecutor"
]
