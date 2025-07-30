"""
Simplified MCP Module for Enterprise AI.

Focused on tool execution only - leverages existing tool infrastructure.
Enhanced with user-friendly sandbox configuration system.
"""

from enterprise_ai.mcp.executor import (
    ToolMCP, 
    create_simple_mcp,
    create_local_mcp,
    create_execution_sandbox_mcp,
    create_file_sandbox_mcp,
    create_full_sandbox_mcp,
)
from enterprise_ai.mcp.enhanced_sandbox import (
    EnhancedSandboxConfig,
    create_local_config,
    create_execution_sandbox,
    create_file_sandbox,
    create_full_sandbox,
    create_custom_sandbox,
    get_config_by_name,
    TOOL_GROUPS,
)
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
    # Core MCP functionality
    "ToolMCP", 
    "create_simple_mcp",
    
    # Enhanced MCP factory functions
    "create_local_mcp",
    "create_execution_sandbox_mcp",
    "create_file_sandbox_mcp", 
    "create_full_sandbox_mcp",
    
    # Enhanced Sandbox Configuration
    "EnhancedSandboxConfig",
    "create_local_config",
    "create_execution_sandbox",
    "create_file_sandbox",
    "create_full_sandbox",
    "create_custom_sandbox",
    "get_config_by_name",
    "TOOL_GROUPS",

    # Legacy Sandbox Configuration (backward compatibility)
    "SandboxConfig",
    "create_sandbox_config", 
    "DEFAULT_SANDBOX_CONFIG",
    "SAFE_SANDBOX_CONFIG", 
    "STRICT_SANDBOX_CONFIG",

    # Sandbox Executors
    "SimpleMCPExecutor",
    "SandboxToolExecutor"
]
