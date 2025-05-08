"""
Tool integration for Enterprise AI agents.

This module provides utilities for discovering, managing, and
executing tools, enabling agents to interact with external systems.
"""

from enterprise_ai.agent.tools.tooling import (
    AgentToolManager,
    ToolUsageMetrics,
)

from enterprise_ai.agent.tools.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
    validate_tool_parameters,
    get_tool_error_handling_prompt,
    get_tool_capabilities_description,
    execute_tool_with_retry,
    ToolIntegrationError,
    FunctionCallingFormatter,
    merge_tool_schemas,
)

__all__ = [
    # Tool management
    "AgentToolManager",
    "ToolUsageMetrics",
    
    # Tool integration utilities
    "parse_message_for_tool_calls",
    "format_tool_response_message",
    "get_tool_prompt_for_reasoning",
    "validate_tool_parameters",
    "get_tool_error_handling_prompt",
    "get_tool_capabilities_description",
    "execute_tool_with_retry",
    "ToolIntegrationError", 
    "FunctionCallingFormatter",
    "merge_tool_schemas",
]