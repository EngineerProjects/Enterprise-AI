"""
Smart Tool Logging Module for Enterprise AI.

This module provides intelligent, source-focused logging that tracks:
- Actual sources used (not all attempted)
- Tool execution outcomes and performance  
- MCP usage patterns and statistics
- Research provenance and audit trails
"""

from enterprise_ai.tool.logging.smart_logger import (
    SmartToolLogger,
    ToolExecutionContext,
    SourceEvidence,
    ToolOutcome,
    MCPSession,
    LogLevel,
    get_smart_logger,
    log_source_used,
    log_tool_outcome
)

__all__ = [
    "SmartToolLogger",
    "ToolExecutionContext", 
    "SourceEvidence",
    "ToolOutcome",
    "MCPSession",
    "LogLevel",
    "get_smart_logger",
    "log_source_used", 
    "log_tool_outcome"
]
