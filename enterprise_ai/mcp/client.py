"""
Client for connecting to the Model Context Protocol (MCP) server.

This module provides a client interface for agents to connect to and interact
with the MCP server, enabling tool discovery and execution.
"""

import asyncio
import uuid
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.logger import get_logger

logger = get_logger("mcp.client")

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from enterprise_ai.mcp.server import MCPSession, MCPServer


class MCPClient:
    """Client for interacting with the MCP server."""

    def __init__(self, session_id: str, create_if_not_exists: bool = True):
        """Initialize an MCP client.

        Args:
            session_id: ID of the session to connect to
            create_if_not_exists: Whether to create the session if it doesn't exist
        """
        self.session_id = session_id

        # Import here to avoid circular imports
        from enterprise_ai.mcp.server import get_mcp_server

        self._server = get_mcp_server()

        # Get or create the session
        self._session = self._server.get_session(session_id)
        if self._session is None and create_if_not_exists:
            self._session = self._server.create_session(session_id)
        elif self._session is None:
            raise ValueError(f"Session not found: {session_id}")

    @property
    def session(self) -> "MCPSession":
        """Get the MCP session.

        Returns:
            The MCP session

        Raises:
            RuntimeError: If not connected to a session
        """
        if self._session is None:
            raise RuntimeError("Not connected to an MCP session")
        return self._session

    def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools in this session.

        Returns:
            List of tool definitions
        """
        return list(self.session.get_available_tools())

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters to pass to the tool

        Returns:
            Tool execution result
        """
        result = await self.session.execute_tool(tool_name, **kwargs)
        return result

    async def close(self) -> None:
        """Close the MCP client and session."""
        if self._session is not None:
            await self._server.close_session(self.session_id)
            self._session = None

    def __del__(self) -> None:
        """Clean up resources when object is destroyed."""
        if hasattr(self, "_session") and self._session is not None:
            try:
                # Try using existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._server.close_session(self.session_id))
                else:
                    loop.run_until_complete(self._server.close_session(self.session_id))
            except RuntimeError:
                logger.warning(f"Could not close MCP session {self.session_id} during cleanup")


class AgentMCPClient(MCPClient):
    """An MCP client specifically for agent use."""

    def __init__(
        self,
        agent_id: str,
        tool_categories: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
    ):
        """Initialize an agent MCP client.

        Args:
            agent_id: ID of the agent
            tool_categories: Optional categories of tools to include
            tool_names: Optional specific tool names to include
        """
        session_id = f"agent-{agent_id}"
        self.agent_id = agent_id

        # Import here to avoid circular imports
        from enterprise_ai.mcp.server import get_mcp_server

        self._server = get_mcp_server()

        # Check if session exists
        self._session = self._server.get_session(session_id)

        if self._session is None:
            # Create a new session with specified tools
            self._session = self._server.create_session(
                session_id, tool_categories=tool_categories, tool_names=tool_names
            )

        # Session ID is agent-specific
        self.session_id = session_id

    async def update_tools(
        self,
        add_categories: Optional[List[str]] = None,
        add_tools: Optional[List[str]] = None,
        remove_tools: Optional[List[str]] = None,
    ) -> None:
        """Update the tools available to this agent.

        Args:
            add_categories: Categories of tools to add
            add_tools: Specific tool names to add
            remove_tools: Tools to remove
        """
        # Add tools from categories
        if add_categories:
            registry = self._server._registry
            for category in add_categories:
                tool_classes = registry.get_tools_by_category(category)
                for tool_cls in tool_classes:
                    try:
                        # Get tool parameters from class
                        name = getattr(tool_cls, "name", tool_cls.__name__)
                        description = getattr(tool_cls, "description", "No description available")
                        parameters = getattr(tool_cls, "parameters", None)

                        # Instantiate with required parameters
                        tool = tool_cls(name=name, description=description, parameters=parameters)
                        self.session.register_tool(tool)
                    except Exception as e:
                        logger.warning(f"Failed to add tool {tool_cls.__name__}: {e}")

        # Add specific tools
        if add_tools:
            registry = self._server._registry
            for name in add_tools:
                maybe_tool_cls = registry.get_tool_class(name)
                if maybe_tool_cls is not None:
                    try:
                        tool_cls = maybe_tool_cls
                        tool_name = getattr(tool_cls, "name", name)
                        description = getattr(tool_cls, "description", "No description available")
                        parameters = getattr(tool_cls, "parameters", None)

                        tool = tool_cls(
                            name=tool_name, description=description, parameters=parameters
                        )
                        self.session.register_tool(tool)
                    except Exception as e:
                        logger.warning(f"Failed to add tool {name}: {e}")

        # Remove tools
        if remove_tools:
            for tool_name in remove_tools:
                self.session.unregister_tool(tool_name)
