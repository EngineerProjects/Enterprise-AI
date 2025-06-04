"""
Core tool components for Enterprise AI.

This module provides the unified base classes, utilities, and configuration
management for the tool system, eliminating redundancy with the schema system.
"""

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolState, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult, ToolFailure, ToolResultMetadata
from enterprise_ai.tool.core.collection import ToolCollection
from enterprise_ai.tool.core.registry import (
    register_tool,
    get_registry,
    ToolRegistry,
    search_tools,
    create_tool,
)

# Import new configuration management system
from enterprise_ai.tool.core.config_manager import (
    ConfigManager,
    ConfigValidationRule,
    get_config_manager,
    get_config,
    get_config_value,
    set_config_value,
    validate_path_config,
    is_command_blocked_config,
)
from enterprise_ai.tool.core.config_tool import ConfigurationTool

# Import schema components for consistency
from enterprise_ai.schema.tool import ToolCall, ToolDefinition, Function

__all__ = [
    # Base classes
    "BaseTool",
    "ToolError",
    "ToolState", 
    "ToolConfig",
    "ToolCapability",
    
    # Unified result classes
    "ToolResult",
    "CLIResult",
    "ToolFailure",
    "ToolResultMetadata",
    
    # Collection classes
    "ToolCollection",
    
    # Registry classes and functions
    "register_tool",
    "get_registry", 
    "ToolRegistry",
    "search_tools",
    "create_tool",
    
    # Configuration management system
    "ConfigManager",
    "ConfigValidationRule",
    "ConfigurationTool",
    "get_config_manager",
    "get_config",
    "get_config_value", 
    "set_config_value",
    "validate_path_config",
    "is_command_blocked_config",
    
    # Schema components (for consistency)
    "ToolCall",
    "ToolDefinition", 
    "Function",
]