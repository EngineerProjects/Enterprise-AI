"""
Logging system for Enterprise AI.

This module provides a centralized logging system for all components,
including the simplified tool call logging system (.log files only).
"""

from enterprise_ai.logger.base import setup_logger, get_logger
from enterprise_ai.logger.enhanced import (
    PerformantLogger, 
    get_optimized_logger, 
    setup_enterprise_logging,
    Colors,
    debug_log,
    conditional_debug
)

# Simplified tool call logging (log files only - no JSON)
from enterprise_ai.logger.simplified_logger import (
    SimplifiedToolLogger,
    ToolCallRecord,
    ToolOutputRecord,
    get_simplified_tool_logger,
    log_tool_execution
)

# Simplified MCP integration for log-only comprehensive logging
from enterprise_ai.logger.simplified_integration import (
    patch_mcp_simplified_logging,
    unpatch_mcp_simplified_logging
)

# Backward compatibility - minimal ToolExecutionContext
from enterprise_ai.logger.tool_context import ToolExecutionContext

__all__ = [
    # Original logger system
    "setup_logger", 
    "get_logger",
    "PerformantLogger", 
    "get_optimized_logger", 
    "setup_enterprise_logging",
    "Colors",
    "debug_log",
    "conditional_debug",
    
    # Simplified tool call logging (log files only)
    "SimplifiedToolLogger",
    "ToolCallRecord", 
    "ToolOutputRecord",
    "get_simplified_tool_logger",
    "log_tool_execution",
    
    # Simplified MCP integration
    "patch_mcp_simplified_logging",
    "unpatch_mcp_simplified_logging",
    
    # Backward compatibility
    "ToolExecutionContext"
]
