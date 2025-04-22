"""
Tool integration for agents in Enterprise AI.

This module provides the foundation for agents to discover, select, 
and execute tools based on their roles and capabilities.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from enterprise_ai.agent.types import AgentProtocol
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.logger import get_logger

logger = get_logger("agent.tooling")


class AgentToolManager:
    """Manages tool access and execution for an agent."""
    
    def __init__(self, agent_id: str):
        """Initialize the tool manager for an agent.
        
        Args:
            agent_id: The ID of the agent this manager belongs to
        """
        self.agent_id = agent_id
        self._tools: Dict[str, BaseTool] = {}
        self._tool_usage_history: List[Dict[str, Any]] = []
        
    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the agent's available tools.
        
        Args:
            tool: The tool to add
        """
        self._tools[tool.name] = tool
        logger.debug(f"Added tool '{tool.name}' to agent {self.agent_id}")
        
    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent's available tools.
        
        Args:
            tool_name: Name of the tool to remove
            
        Returns:
            True if tool was removed, False if not found
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.debug(f"Removed tool '{tool_name}' from agent {self.agent_id}")
            return True
        return False
        
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name.
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            The tool if found, None otherwise
        """
        return self._tools.get(tool_name)
        
    def list_tools(self) -> List[str]:
        """List all available tool names.
        
        Returns:
            List of tool names available to this agent
        """
        return list(self._tools.keys())
    
    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all available tools.
        
        Returns:
            Dictionary mapping tool names to descriptions
        """
        return {name: tool.description for name, tool in self._tools.items()}
        
    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        tool = self.get_tool(tool_name)
        
        if not tool:
            logger.warning(f"Tool '{tool_name}' not found for agent {self.agent_id}")
            return ToolResult(error=f"Tool not found: {tool_name}")
            
        try:
            logger.info(f"Agent {self.agent_id} executing tool '{tool_name}'")
            result = await tool.execute(**kwargs)
            
            # Record tool usage
            self._tool_usage_history.append({
                "tool_name": tool_name,
                "timestamp": start_time,
                "duration": (datetime.now() - start_time).total_seconds(),
                "parameters": kwargs,
                "success": result.error is None,
                "error": result.error
            })
            
            # Ensure result is a ToolResult
            if isinstance(result, ToolResult):
                return result
            else:
                # If result is not a ToolResult (unlikely but possible), convert it
                return ToolResult(output=str(result))
            
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {str(e)}")
            
            # Record failed usage
            self._tool_usage_history.append({
                "tool_name": tool_name,
                "timestamp": start_time,
                "duration": (datetime.now() - start_time).total_seconds(),
                "parameters": kwargs,
                "success": False,
                "error": str(e)
            })
            
            return ToolResult(error=f"Tool execution error: {str(e)}")
    
    def get_usage_history(self) -> List[Dict[str, Any]]:
        """Get the tool usage history for this agent.
        
        Returns:
            List of tool usage records
        """
        return self._tool_usage_history.copy()