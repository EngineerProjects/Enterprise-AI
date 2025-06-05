"""
Tool execution handler for MCP requests.

This module handles tool execution requests, routing them through
the existing Enterprise AI tool framework.
"""

from typing import Any, Dict, List, Optional

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.tool.core.registry import ToolRegistry

from ..executor import ToolExecutor
from ..session_manager import SessionManager

logger = get_logger("mcp.handlers.tool")


class ToolHandler:
    """Handles tool execution requests for the MCP server."""
    
    def __init__(
        self,
        executor: ToolExecutor,
        session_manager: SessionManager,
        tool_registry: Optional[ToolRegistry] = None
    ):
        """Initialize the tool handler."""
        self.executor = executor
        self.session_manager = session_manager
        self.tool_registry = tool_registry or ToolRegistry()
        
        # Auto-register tools from registry
        self._register_tools_from_registry()
    
    def _register_tools_from_registry(self) -> None:
        """Register all tools from the tool registry."""
        try:
            tools = self.tool_registry.get_all_tools()
            tool_functions = {}
            
            for tool_name, tool_instance in tools.items():
                # Create a wrapper function that calls the tool's execute method
                async def tool_wrapper(tool=tool_instance, **kwargs):
                    return await tool.execute(**kwargs)
                
                tool_functions[tool_name] = tool_wrapper
            
            self.executor.register_tools(tool_functions)
            logger.info("Registered %d tools from registry", len(tool_functions))
            
        except Exception as e:
            logger.error("Failed to register tools from registry: %s", e)
    
    async def handle_tool_execution(
        self,
        tool_calls: List[ToolCall],
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Handle tool execution requests.
        
        Args:
            tool_calls: List of tool calls to execute
            session_id: Optional session ID
            context: Optional execution context
            
        Returns:
            List of tool execution results
        """
        try:
            # Create session if not provided
            if session_id is None:
                session_id = self.session_manager.create_session()
            
            # Execute tools
            results = await self.executor.execute_tool_calls(
                tool_calls=tool_calls,
                session_id=session_id,
                context=context
            )
            
            return results
            
        except Exception as e:
            logger.error("Tool execution failed: %s", e)
            # Return error results for all tool calls
            error_results = []
            for tool_call in tool_calls:
                error_result = ToolResult(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    result="",
                    success=False,
                    error=f"Execution failed: {str(e)}",
                    metadata={}
                )
                error_results.append(error_result)
            
            return error_results
    
    async def handle_tool_list_request(self) -> List[Dict[str, Any]]:
        """Handle request to list available tools."""
        try:
            tools = self.tool_registry.get_all_tools()
            tool_definitions = []
            
            for tool_name, tool_instance in tools.items():
                tool_def = {
                    "name": tool_name,
                    "description": getattr(tool_instance, "description", ""),
                    "parameters": getattr(tool_instance, "parameters", {}),
                    "capabilities": list(getattr(tool_instance, "capabilities", [])),
                    "metadata": getattr(tool_instance, "metadata", {})
                }
                tool_definitions.append(tool_def)
            
            return tool_definitions
            
        except Exception as e:
            logger.error("Failed to list tools: %s", e)
            return []
    
    async def handle_tool_info_request(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Handle request for specific tool information."""
        try:
            tool_instance = self.tool_registry.get_tool(tool_name)
            if not tool_instance:
                return None
            
            return {
                "name": tool_name,
                "description": getattr(tool_instance, "description", ""),
                "parameters": getattr(tool_instance, "parameters", {}),
                "capabilities": list(getattr(tool_instance, "capabilities", [])),
                "config": getattr(tool_instance, "config", {}).dict() if hasattr(getattr(tool_instance, "config", {}), "dict") else {},
                "metadata": getattr(tool_instance, "metadata", {}),
                "execution_stats": self.executor.get_execution_stats()
            }
            
        except Exception as e:
            logger.error("Failed to get tool info for %s: %s", tool_name, e)
            return None