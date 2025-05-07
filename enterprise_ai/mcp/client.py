"""
Client for connecting to the Model Context Protocol (MCP) server.

This module provides a client interface for agents to connect to and interact
with the MCP server, enabling tool discovery and execution.
"""

import asyncio
import uuid
import time
from typing import Any, Dict, List, Optional, Set, Union, Type, TypeVar, Tuple, cast
from enum import Enum

from enterprise_ai.tool.core.base import BaseTool, ToolState, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.logger import get_logger

from typing import TYPE_CHECKING

logger = get_logger("mcp.client")


if TYPE_CHECKING:
    from enterprise_ai.mcp.server import MCPSession, MCPServer


class ToolFilterStrategy(str, Enum):
    """Strategy for filtering tools."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


class MCPClient:
    """Client for interacting with the MCP server."""

    def __init__(
        self,
        session_id: str,
        create_if_not_exists: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize an MCP client.

        Args:
            session_id: ID of the session to connect to
            create_if_not_exists: Whether to create the session if it doesn't exist
            config: Optional configuration for the session if created
        """
        self.session_id = session_id
        self._config = config or {}

        # Import here to avoid circular imports
        from enterprise_ai.mcp.server import get_mcp_server

        self._server = get_mcp_server()

        # Get or create the session
        self._session = self._server.get_session(session_id)
        if self._session is None and create_if_not_exists:
            self._session = self._server.create_session(session_id, config=self._config)
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

    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:
        """Get detailed information about a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with tool information
        """
        # First check if the tool is available in the session
        tool = self.session.get_tool(tool_name)
        if not tool:
            return {}

        # Get tool metrics from the session
        metrics = self.session.get_tool_metrics(tool_name)

        # Basic tool info
        info = {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "version": getattr(tool, "version", "1.0.0"),
            "requires_initialization": getattr(tool, "requires_initialization", False),
            "authorization_required": getattr(tool, "authorization_required", False),
            "state": str(getattr(tool, "state", ToolState.IDLE)),
            "metrics": metrics,
        }

        # Add capabilities if available
        capabilities = getattr(tool, "capabilities", None)
        if capabilities:
            info["capabilities"] = [str(cap) for cap in capabilities]

        # Add usage examples if available
        examples = getattr(tool, "usage_examples", None)
        if examples:
            info["usage_examples"] = examples

        return info

    async def execute_tool(
        self,
        tool_name: str,
        timeout: Optional[float] = None,
        cache_key: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            timeout: Optional timeout override
            cache_key: Optional cache key for this execution
            **kwargs: Parameters to pass to the tool

        Returns:
            Tool execution result
        """
        result = await self.session.execute_tool(
            tool_name, timeout=timeout, cache_key=cache_key, **kwargs
        )
        return result

    async def execute_tools_sequential(
        self, executions: List[Dict[str, Any]]
    ) -> List[Tuple[str, ToolResult]]:
        """Execute multiple tools sequentially.

        Args:
            executions: List of execution specifications. Each one should have:
                        - tool_name: Name of the tool to execute
                        - parameters: Dictionary of parameters
                        - Optional timeout, cache_key

        Returns:
            List of (tool_name, result) tuples
        """
        results = []
        for execution in executions:
            tool_name = execution.get("tool_name")
            if not tool_name:
                logger.error("Missing tool_name in execution specification")
                continue

            # Extract parameters and options
            parameters = execution.get("parameters", {})
            timeout = execution.get("timeout")
            cache_key = execution.get("cache_key")

            # Execute the tool
            result = await self.execute_tool(
                tool_name, timeout=timeout, cache_key=cache_key, **parameters
            )

            results.append((tool_name, result))

        return results

    async def execute_tools_parallel(
        self, executions: List[Dict[str, Any]]
    ) -> List[Tuple[str, ToolResult]]:
        """Execute multiple tools in parallel.

        Args:
            executions: List of execution specifications. Each one should have:
                        - tool_name: Name of the tool to execute
                        - parameters: Dictionary of parameters
                        - Optional timeout, cache_key

        Returns:
            List of (tool_name, result) tuples in the same order as executions
        """
        # Create tasks for each execution
        tasks = []
        tool_names = []

        for execution in executions:
            tool_name = execution.get("tool_name")
            if not tool_name:
                logger.error("Missing tool_name in execution specification")
                continue

            # Extract parameters and options
            parameters = execution.get("parameters", {})
            timeout = execution.get("timeout")
            cache_key = execution.get("cache_key")

            # Create task
            task = self.execute_tool(tool_name, timeout=timeout, cache_key=cache_key, **parameters)

            tasks.append(task)
            tool_names.append(tool_name)

        # Execute all tasks in parallel
        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, converting exceptions to error results
        final_results: List[Tuple[str, ToolResult]] = []
        for i, (tool_name, result) in enumerate(zip(tool_names, results)):
            if isinstance(result, Exception):
                # Convert exception to error result
                from enterprise_ai.tool.core.result import ToolFailure, ToolResultMetadata

                error_result = ToolFailure(
                    error=f"Execution error: {str(result)}",
                    metadata=ToolResultMetadata(tool_name=tool_name, session_id=self.session_id),
                )
                final_results.append((tool_name, error_result))
            else:
                final_results.append((tool_name, cast(ToolResult, result)))

        return final_results

    def search_tools(
        self,
        query: Optional[str] = None,
        categories: Optional[List[str]] = None,
        capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        match_all_capabilities: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search for tools matching criteria within this session.

        Args:
            query: Optional text to search in names and descriptions
            categories: Optional categories to filter by
            capabilities: Optional capabilities to filter by
            match_all_capabilities: Whether all capabilities must match

        Returns:
            List of tool definitions matching criteria
        """
        # Get all available tools
        all_tools = self.discover_tools()

        # No filters, return all
        if not query and not categories and not capabilities:
            return all_tools

        # Filter tools based on criteria
        results = []

        for tool_def in all_tools:
            # Skip non-standard formats
            if not isinstance(tool_def, dict) or "function" not in tool_def:
                continue

            function_data = tool_def.get("function", {})
            tool_name = function_data.get("name", "")
            description = function_data.get("description", "")

            # Get full tool information for additional filtering
            tool_info = self.get_tool_info(tool_name)

            # Filter by query
            if query and not (
                query.lower() in tool_name.lower() or query.lower() in description.lower()
            ):
                continue

            # Filter by categories (get from underlying tool)
            if categories:
                tool_categories = tool_info.get("categories", [])
                if not any(cat in tool_categories for cat in categories):
                    continue

            # Filter by capabilities
            if capabilities:
                tool_capabilities = tool_info.get("capabilities", [])

                # Convert ToolCapability enums to strings if needed
                cap_values = [
                    cap.value if isinstance(cap, ToolCapability) else cap for cap in capabilities
                ]

                if match_all_capabilities:
                    # All specified capabilities must be present
                    if not all(cap in tool_capabilities for cap in cap_values):
                        continue
                else:
                    # At least one capability must be present
                    if not any(cap in tool_capabilities for cap in cap_values):
                        continue

            # All filters passed, add to results
            results.append(tool_def)

        return results

    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current session.

        Returns:
            Dictionary with session information
        """
        return self._server.get_session_info(self.session_id)

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value in the session.

        Args:
            key: Context key
            value: Context value
        """
        self.session.set_context(key, value)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value from the session.

        Args:
            key: Context key
            default: Default value if not found

        Returns:
            Context value or default
        """
        return self.session.get_context(key, default)

    def clear_context(self) -> None:
        """Clear all context values in the session."""
        self.session.clear_context()

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
        tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        filter_strategy: ToolFilterStrategy = ToolFilterStrategy.INCLUDE,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize an agent MCP client.

        Args:
            agent_id: ID of the agent
            tool_categories: Optional categories of tools to include/exclude
            tool_names: Optional specific tool names to include/exclude
            tool_capabilities: Optional capabilities to include/exclude
            filter_strategy: Whether to include or exclude the specified tools
            config: Optional configuration for the session
        """
        session_id = f"agent-{agent_id}"
        self.agent_id = agent_id
        self.filter_strategy = filter_strategy

        # Import here to avoid circular imports
        from enterprise_ai.mcp.server import get_mcp_server

        self._server = get_mcp_server()

        # Check if session exists
        self._session = self._server.get_session(session_id)

        if self._session is None:
            # Create a new session with specified tools
            self._session = self._server.create_session(
                session_id,
                tool_categories=tool_categories
                if filter_strategy == ToolFilterStrategy.INCLUDE
                else None,
                tool_names=tool_names if filter_strategy == ToolFilterStrategy.INCLUDE else None,
                tool_capabilities=tool_capabilities
                if filter_strategy == ToolFilterStrategy.INCLUDE
                else None,
                config=config,
            )

            # If using EXCLUDE strategy, remove specified tools
            if filter_strategy == ToolFilterStrategy.EXCLUDE:
                # Handle excluded categories
                if tool_categories:
                    # Get all tools from excluded categories
                    for category in tool_categories:
                        tools = self._server._registry.get_tools_by_category(category)
                        for tool_cls in tools:
                            name = getattr(tool_cls, "name", tool_cls.__name__)
                            # Remove from session if present
                            self._session.unregister_tool(name)

                # Handle excluded specific tools
                if tool_names:
                    for name in tool_names:
                        self._session.unregister_tool(name)

                # Handle excluded capabilities
                if tool_capabilities:
                    # Convert ToolCapability enums to strings if needed
                    cap_values = [
                        cap.value if isinstance(cap, ToolCapability) else cap
                        for cap in tool_capabilities
                    ]

                    # Get tools with these capabilities
                    from enterprise_ai.tool.core.registry import search_tools

                    capability_tools = search_tools(
                        capabilities=cap_values,
                        match_all_capabilities=False,  # Match any capability
                    )

                    # Remove matching tools
                    for tool_cls in capability_tools:
                        name = getattr(tool_cls, "name", tool_cls.__name__)
                        self._session.unregister_tool(name)

        # Session ID is agent-specific
        self.session_id = session_id

    async def update_tools(
        self,
        add_categories: Optional[List[str]] = None,
        add_tools: Optional[List[str]] = None,
        add_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        remove_tools: Optional[List[str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the tools available to this agent.

        Args:
            add_categories: Categories of tools to add
            add_tools: Specific tool names to add
            add_capabilities: Capabilities to add
            remove_tools: Tools to remove
            config: Optional configuration for added tools
        """
        # Add tools from categories
        if add_categories:
            registry = self._server._registry
            for category in add_categories:
                tool_classes = registry.get_tools_by_category(category)
                for tool_cls in tool_classes:
                    name = getattr(tool_cls, "name", tool_cls.__name__)
                    await self._server.add_tool_to_session(self.session_id, name, config)

        # Add tools with capabilities
        if add_capabilities:
            # Convert ToolCapability enums to strings if needed
            cap_values = [
                cap.value if isinstance(cap, ToolCapability) else cap for cap in add_capabilities
            ]

            # Get tools with these capabilities
            from enterprise_ai.tool.core.registry import search_tools

            capability_tools = search_tools(
                capabilities=cap_values,
                match_all_capabilities=False,  # Match any capability
            )

            # Add each tool
            for tool_cls in capability_tools:
                name = getattr(tool_cls, "name", tool_cls.__name__)
                await self._server.add_tool_to_session(self.session_id, name, config)

        # Add specific tools
        if add_tools:
            for name in add_tools:
                await self._server.add_tool_to_session(self.session_id, name, config)

        # Remove tools
        if remove_tools:
            for tool_name in remove_tools:
                self.session.unregister_tool(tool_name)

    async def register_custom_tool(self, tool: BaseTool) -> bool:
        """Register a custom tool instance with this agent's session.

        Args:
            tool: The tool instance to register

        Returns:
            True if registration succeeded, False otherwise
        """
        try:
            # Register with session
            self.session.register_tool(tool)
            return True
        except Exception as e:
            logger.error(f"Failed to register custom tool: {e}")
            return False

    def get_filter_status(self) -> Dict[str, Any]:
        """Get the current tool filtering status.

        Returns:
            Dictionary with filter information
        """
        return {
            "strategy": self.filter_strategy,
            "tool_count": len(self.discover_tools()),
        }
