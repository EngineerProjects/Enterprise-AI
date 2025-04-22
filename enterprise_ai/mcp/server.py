"""
Model Context Protocol server for Enterprise AI.

This module provides a server implementation for the Model Context Protocol,
which enables dynamic tool discovery and execution for AI agents. The MCP server
manages tool sessions, handles tool lifecycle, and provides a standardized
interface for agents to interact with tools.

The key components are:
- MCPServer: Central manager for MCP sessions and tool registration
- MCPSession: Per-agent session for tool interaction and history tracking
- MCPToolProvider: Interface for dynamically providing tools to sessions
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Type, cast
import uuid

from pydantic import BaseModel, Field

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import ToolResult, ToolFailure
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.tool.core.collection import ToolCollection
from enterprise_ai.logger import get_logger

logger = get_logger("mcp.server")


class ToolRequest(BaseModel):
    """A request to execute a tool."""
    
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    

class ToolResponse(BaseModel):
    """A response from a tool execution."""
    
    request_id: str
    tool_name: str
    success: bool
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class MCPSession:
    """A session for interacting with tools via the MCP protocol."""
    
    def __init__(self, session_id: str):
        """Initialize an MCP session.
        
        Args:
            session_id: Unique identifier for this session
        """
        self.session_id = session_id
        self._tool_collection = ToolCollection()
        self._history: List[Dict[str, Any]] = []
        logger.info(f"Created MCP session: {session_id}")
        
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool with this session.
        
        Args:
            tool: Tool instance to register
        """
        self._tool_collection.add_tool(tool)
        logger.debug(f"Registered tool '{tool.name}' with session {self.session_id}")
        
    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool from this session.
        
        Args:
            tool_name: Name of the tool to unregister
            
        Returns:
            True if the tool was removed, False if not found
        """
        tool = self._tool_collection.get_tool(tool_name)
        if not tool:
            return False
            
        # Create a new collection without this tool
        tools = [t for t in self._tool_collection if t.name != tool_name]
        self._tool_collection = ToolCollection(*tools)
        logger.debug(f"Unregistered tool '{tool_name}' from session {self.session_id}")
        return True
        
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools with their descriptions.
        
        Returns:
            List of tool definitions
        """
        return self._tool_collection.to_params()
    
    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters to pass to the tool
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        
        # Record the execution request
        request_record = {
            "type": "request",
            "tool": tool_name,
            "parameters": kwargs,
            "timestamp": start_time.isoformat()
        }
        self._history.append(request_record)
        
        # Execute the tool
        result = await self._tool_collection.execute(
            name=tool_name, 
            tool_input=kwargs
        )
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # Record the result
        result_record = {
            "type": "result",
            "tool": tool_name,
            "success": result.error is None,
            "execution_time": execution_time,
            "timestamp": end_time.isoformat()
        }
        self._history.append(result_record)
        
        return result
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get the history of tool executions in this session.
        
        Returns:
            List of execution history records
        """
        return self._history.copy()
    
    async def cleanup(self) -> None:
        """Clean up resources used by this session."""
        # Perform any necessary cleanup for tools
        for tool in self._tool_collection:
            if hasattr(tool, "cleanup") and callable(getattr(tool, "cleanup")):
                try:
                    await tool.cleanup()
                except Exception as e:
                    logger.warning(f"Error during tool cleanup: {e}")
        
        logger.info(f"Cleaned up MCP session: {self.session_id}")


class MCPServer:
    """Model Context Protocol server that manages tool access."""
    
    _instance = None
    
    def __new__(cls) -> "MCPServer":
        """Create a singleton instance of the MCP server."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the MCP server."""
        # Skip initialization if already done
        if getattr(self, "_initialized", False):
            return
            
        self._sessions: Dict[str, MCPSession] = {}
        self._registry = get_registry()
        self._initialized = True
        
        logger.info("Initialized MCP server")
        
    def create_session(self, session_id: str, 
                    tool_categories: Optional[List[str]] = None,
                    tool_names: Optional[List[str]] = None) -> MCPSession:
        """Create a new MCP session with specific tools.
        
        Args:
            session_id: Unique identifier for the session
            tool_categories: Optional list of tool categories to include
            tool_names: Optional list of specific tool names to include
            
        Returns:
            New MCP session
            
        Raises:
            ValueError: If a session with this ID already exists
        """
        if session_id in self._sessions:
            raise ValueError(f"Session already exists: {session_id}")
            
        session = MCPSession(session_id)
        
        # Load tools from categories if specified
        if tool_categories:
            for category in tool_categories:
                tool_classes = self._registry.get_tools_by_category(category)
                for tool_cls in tool_classes:
                    try:
                        # Create an instance with the class's own name and description
                        # We can use getattr to safely get class attributes
                        name = getattr(tool_cls, "name", tool_cls.__name__)
                        description = getattr(tool_cls, "description", "No description available")
                        parameters = getattr(tool_cls, "parameters", None)
                        
                        # Instantiate the tool with required parameters
                        tool = tool_cls(
                            name=name,
                            description=description,
                            parameters=parameters
                        )
                        session.register_tool(tool)
                    except Exception as e:
                        logger.warning(f"Failed to initialize tool {tool_cls.__name__}: {e}")
        
        # Load specific tools if specified
        if tool_names:
            for name in tool_names:
                # Use type annotation to handle optional return type
                maybe_tool_cls = self._registry.get_tool_class(name)
                if maybe_tool_cls is not None:
                    try:
                        # Create an instance with the class's own parameters
                        tool_cls = maybe_tool_cls  # Now the type checker knows it's not None
                        tool_name = getattr(tool_cls, "name", name)
                        description = getattr(tool_cls, "description", "No description available")
                        parameters = getattr(tool_cls, "parameters", None)
                        
                        # Instantiate the tool with required parameters
                        tool = tool_cls(
                            name=tool_name,
                            description=description,
                            parameters=parameters
                        )
                        session.register_tool(tool)
                    except Exception as e:
                        logger.warning(f"Failed to initialize tool {name}: {e}")
        
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get an existing MCP session.
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            Session if found, None otherwise
        """
        return self._sessions.get(session_id)
    
    async def close_session(self, session_id: str) -> bool:
        """Close and cleanup an MCP session.
        
        Args:
            session_id: ID of the session to close
            
        Returns:
            True if the session was closed, False if not found
        """
        if session_id in self._sessions:
            session = self._sessions[session_id]
            await session.cleanup()
            del self._sessions[session_id]
            return True
        return False
    
    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs.
        
        Returns:
            List of session IDs
        """
        return list(self._sessions.keys())


# Singleton accessor function
def get_mcp_server() -> MCPServer:
    """Get the global MCP server instance.
    
    Returns:
        Singleton MCP server instance
    """
    return MCPServer()