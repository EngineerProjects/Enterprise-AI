"""
Tool integration for agents in Enterprise AI.

This module provides the foundation for agents to discover, select,
and execute tools based on their roles and capabilities.
"""

from datetime import datetime
import asyncio
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.types import AgentProtocol
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.mcp.client import AgentMCPClient
from enterprise_ai.mcp.utils import format_tool_descriptions
from enterprise_ai.logger import get_logger
from enterprise_ai.prompt import get_prompt, format_prompt

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

        # MCP client for tool integration
        self._mcp_client: Optional[AgentMCPClient] = None
        self._mcp_initialized = False

        logger.info(f"Initialized tool manager for agent {agent_id}")

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
        # Local tools
        tool_names = list(self._tools.keys())

        # Add MCP tool names if initialized
        if self._mcp_client and self._mcp_initialized:
            mcp_tools = self._mcp_client.discover_tools()
            for tool in mcp_tools:
                if "function" in tool and "name" in tool["function"]:
                    tool_names.append(tool["function"]["name"])

        return tool_names

    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all available tools.

        Returns:
            Dictionary mapping tool names to descriptions
        """
        descriptions = {name: tool.description for name, tool in self._tools.items()}

        # Add MCP tool descriptions if initialized
        if self._mcp_client and self._mcp_initialized:
            mcp_tools = self._mcp_client.discover_tools()
            for tool in mcp_tools:
                if "function" in tool and "name" in tool["function"]:
                    name = tool["function"]["name"]
                    descriptions[name] = tool["function"]["description"]

        return descriptions

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        start_time = datetime.now()

        try:
            # Check if it's a local tool
            if tool_name in self._tools:
                logger.info(f"Agent {self.agent_id} executing tool '{tool_name}'")
                tool_result = await self._tools[tool_name].execute(**kwargs)

                self._record_tool_usage(tool_name, start_time, kwargs, tool_result)
                return cast(ToolResult, tool_result)

            # Check if we should try MCP
            if self._mcp_client:
                # Initialize MCP client if not already
                if not self._mcp_initialized:
                    await self._init_mcp_client()

                # Try to execute via MCP
                if self._mcp_initialized:
                    logger.info(f"Agent {self.agent_id} executing MCP tool '{tool_name}'")
                    tool_result = await self._mcp_client.execute_tool(tool_name, **kwargs)

                    self._record_tool_usage(tool_name, start_time, kwargs, tool_result)
                    return cast(ToolResult, tool_result)

            logger.error(f"Tool '{tool_name}' not found for agent {self.agent_id}")
            return ToolResult(error=f"Tool not found: {tool_name}")

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")

            # Record failed usage
            error_result = ToolResult(error=f"Tool execution error: {str(e)}")
            self._record_tool_usage(tool_name, start_time, kwargs, error_result)

            return error_result

    def _record_tool_usage(
        self, tool_name: str, start_time: datetime, parameters: Dict[str, Any], result: ToolResult
    ) -> None:
        """Record tool usage for history tracking."""
        self._tool_usage_history.append(
            {
                "tool_name": tool_name,
                "timestamp": start_time,
                "duration": (datetime.now() - start_time).total_seconds(),
                "parameters": parameters,
                "success": result.error is None,
                "error": result.error,
            }
        )

    def get_usage_history(self) -> List[Dict[str, Any]]:
        """Get the tool usage history for this agent.

        Returns:
            List of tool usage records
        """
        return self._tool_usage_history.copy()

    def get_formatted_tool_descriptions(self) -> str:
        """Get formatted tool descriptions for prompts.

        Returns:
            String with formatted tool descriptions
        """
        try:
            # If using MCP client, use its formatter
            if self._mcp_client and self._mcp_initialized:
                tools = self._mcp_client.discover_tools()
                return format_tool_descriptions(tools)

            # Format local tools
            tools_list = []
            for name, tool in self._tools.items():
                try:
                    if hasattr(tool, "to_param"):
                        tool_dict = tool.to_param()
                        tools_list.append(tool_dict)
                except Exception as e:
                    logger.warning(f"Error formatting tool {name}: {e}")
                    # Skip this tool and continue with others

            return format_tool_descriptions(tools_list)
        except Exception as e:
            logger.error(f"Error formatting tool descriptions: {e}")
            return ""

    async def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all available tools.

        Returns:
            List of tool schemas in function calling format
        """
        # Local tools
        schemas = [tool.to_param() for tool in self._tools.values()]

        # Add MCP tools if initialized
        if self._mcp_client:
            # Initialize MCP client if not already
            if not self._mcp_initialized:
                await self._init_mcp_client()

            if self._mcp_initialized:
                mcp_tools = self._mcp_client.discover_tools()
                schemas.extend(mcp_tools)

        return schemas

    async def enable_mcp(
        self, tool_categories: Optional[List[str]] = None, tool_names: Optional[List[str]] = None
    ) -> bool:
        """Enable Model Context Protocol for this agent.

        Args:
            tool_categories: Optional categories of tools to include
            tool_names: Optional specific tool names to include

        Returns:
            True if MCP was successfully enabled
        """
        try:
            # Create MCP client
            self._mcp_client = AgentMCPClient(
                agent_id=self.agent_id, tool_categories=tool_categories, tool_names=tool_names
            )

            # Initialize
            await self._init_mcp_client()
            return True
        except Exception as e:
            logger.error(f"Failed to enable MCP for agent {self.agent_id}: {e}")
            self._mcp_client = None
            self._mcp_initialized = False
            return False

    async def _init_mcp_client(self) -> None:
        """Initialize the MCP client if needed."""
        if not self._mcp_client or self._mcp_initialized:
            return

        try:
            # Discover available tools to cache them
            self._mcp_client.discover_tools()
            self._mcp_initialized = True
            logger.info(f"Initialized MCP for agent {self.agent_id}")
        except Exception as e:
            logger.error(f"Failed to initialize MCP for agent {self.agent_id}: {e}")
            self._mcp_initialized = False

    async def update_mcp_tools(
        self,
        add_categories: Optional[List[str]] = None,
        add_tools: Optional[List[str]] = None,
        remove_tools: Optional[List[str]] = None,
    ) -> bool:
        """Update the MCP tools available to this agent.

        Args:
            add_categories: Categories of tools to add
            add_tools: Specific tool names to add
            remove_tools: Tools to remove

        Returns:
            True if update was successful
        """
        if not self._mcp_client:
            logger.warning(f"MCP not enabled for agent {self.agent_id}")
            return False

        try:
            await self._mcp_client.update_tools(
                add_categories=add_categories, add_tools=add_tools, remove_tools=remove_tools
            )
            logger.info(f"Updated MCP tools for agent {self.agent_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update MCP tools for agent {self.agent_id}: {e}")
            return False

    async def cleanup(self) -> None:
        """Clean up resources used by the tool manager."""
        # Clean up MCP client
        if self._mcp_client:
            try:
                await self._mcp_client.close()
                logger.info(f"Closed MCP client for agent {self.agent_id}")
            except Exception as e:
                logger.warning(f"Error closing MCP client: {e}")

        # Clean up local tools if they have cleanup methods
        for tool in self._tools.values():
            if hasattr(tool, "cleanup") and callable(getattr(tool, "cleanup")):
                try:
                    await tool.cleanup()
                except Exception as e:
                    logger.warning(f"Error during tool cleanup for {tool.name}: {e}")

        logger.info(f"Cleaned up tool manager for agent {self.agent_id}")
