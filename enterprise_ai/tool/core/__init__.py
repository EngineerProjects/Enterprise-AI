"""
Core tool components for Enterprise AI.

This module provides the base classes and utilities for the tool system.
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

__all__ = [
    # Base classes
    "BaseTool",
    "ToolError",
    "ToolState",
    "ToolConfig",
    "ToolCapability",
    # Result classes
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
]
