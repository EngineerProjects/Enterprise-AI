"""
Core tool components for Enterprise AI.

This module provides the base classes and utilities for the tool system.
"""

from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import ToolResult, CLIResult, ToolFailure
from enterprise_ai.tool.core.collection import ToolCollection
from enterprise_ai.tool.core.registry import register_tool, get_registry, ToolRegistry

__all__ = [
    # Base classes
    "BaseTool",
    "ToolError",
    # Result classes
    "ToolResult",
    "CLIResult",
    "ToolFailure",
    # Collection classes
    "ToolCollection",
    # Registry classes and functions
    "register_tool",
    "get_registry",
    "ToolRegistry",
]
