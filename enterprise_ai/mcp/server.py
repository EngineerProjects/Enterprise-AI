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
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Type, Union, cast, Tuple
import uuid
import json

from pydantic import BaseModel, Field, model_validator, root_validator

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolState, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata
from enterprise_ai.tool.core.registry import get_registry, search_tools
from enterprise_ai.tool.core.collection import ToolCollection
from enterprise_ai.logger import get_logger

logger = get_logger("mcp.server")


class ToolRequest(BaseModel):
    """A request to execute a tool."""

    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timeout: Optional[float] = Field(default=None, description="Timeout for this specific request")
    cache_key: Optional[str] = Field(
        default=None, description="Optional cache key for this request"
    )


class ToolResponse(BaseModel):
    """A response from a tool execution."""

    request_id: str
    tool_name: str
    success: bool
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    execution_time: float = 0.0

    @model_validator(mode="after")
    def validate_result_error(self) -> "ToolResponse":
        """Validate that either result or error is present."""
        if self.success and not self.result:
            raise ValueError("Success=True requires a result")
        if not self.success and not self.error:
            raise ValueError("Success=False requires an error")
        return self


class MCPToolConfig(BaseModel):
    """Configuration for a tool in MCP."""

    timeout: float = Field(default=60.0, description="Default timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    cache_enabled: bool = Field(default=False, description="Whether to cache results")
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    result_log_enabled: bool = Field(default=True, description="Whether to log results")
    usage_metrics_enabled: bool = Field(default=True, description="Whether to track usage metrics")
    custom_config: Dict[str, Any] = Field(default_factory=dict, description="Custom configuration")


class MCPCache:
    """Simple cache for MCP tool results."""

    def __init__(self, default_ttl: int = 300):
        """Initialize the cache with default TTL."""
        self._cache: Dict[str, Tuple[ToolResult, datetime]] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[ToolResult]:
        """Get a result from the cache if present and not expired."""
        if key not in self._cache:
            return None

        result, expiry = self._cache[key]
        if datetime.now() > expiry:
            # Expired
            del self._cache[key]
            return None

        # Mark as cache hit
        if result.metadata:
            result.metadata.cache_hit = True

        return result

    def put(self, key: str, result: ToolResult, ttl: Optional[int] = None) -> None:
        """Store a result in the cache with expiry time."""
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        expiry = datetime.now() + timedelta(seconds=ttl_seconds)

        # Store a copy to avoid mutation issues
        result_dict = result.dict()
        result_copy = ToolResult(**result_dict)

        self._cache[key] = (result_copy, expiry)

    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()

    def cleanup(self) -> int:
        """Remove expired entries and return count of removed entries."""
        now = datetime.now()
        expired_keys = [k for k, (_, expiry) in self._cache.items() if now > expiry]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)


class MCPUsageMetrics:
    """Usage metrics tracker for MCP."""

    def __init__(self) -> None:
        """Initialize the metrics tracker."""
        self._tool_executions: Dict[str, int] = {}
        self._tool_errors: Dict[str, int] = {}
        self._tool_execution_times: Dict[str, List[float]] = {}
        self._session_executions: Dict[str, int] = {}
        self._last_execution_time: Dict[str, datetime] = {}

    def record_execution(
        self, tool_name: str, session_id: str, success: bool, execution_time: float
    ) -> None:
        """Record a tool execution."""
        # Update tool execution count
        self._tool_executions[tool_name] = self._tool_executions.get(tool_name, 0) + 1

        # Update error count if failed
        if not success:
            self._tool_errors[tool_name] = self._tool_errors.get(tool_name, 0) + 1

        # Update execution times
        if tool_name not in self._tool_execution_times:
            self._tool_execution_times[tool_name] = []
        self._tool_execution_times[tool_name].append(execution_time)

        # Update session execution count
        self._session_executions[session_id] = self._session_executions.get(session_id, 0) + 1

        # Update last execution time
        self._last_execution_time[tool_name] = datetime.now()

    def get_tool_metrics(self, tool_name: str) -> Dict[str, Any]:
        """Get metrics for a specific tool."""
        execution_times = self._tool_execution_times.get(tool_name, [])
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0

        return {
            "executions": self._tool_executions.get(tool_name, 0),
            "errors": self._tool_errors.get(tool_name, 0),
            "avg_execution_time": avg_time,
            "last_execution": self._last_execution_time.get(tool_name),
        }

    def get_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Get metrics for a specific session."""
        return {
            "executions": self._session_executions.get(session_id, 0),
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics."""
        return {
            "total_executions": sum(self._tool_executions.values()),
            "total_errors": sum(self._tool_errors.values()),
            "tools": {tool: self.get_tool_metrics(tool) for tool in self._tool_executions.keys()},
            "sessions": {
                session: {"executions": count}
                for session, count in self._session_executions.items()
            },
        }


class MCPSession:
    """A session for interacting with tools via the MCP protocol."""

    def __init__(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None,
        cache: Optional[MCPCache] = None,
        metrics: Optional[MCPUsageMetrics] = None,
    ):
        """Initialize an MCP session.

        Args:
            session_id: Unique identifier for this session
            config: Optional configuration for this session
            cache: Optional cache instance to use
            metrics: Optional metrics tracker to use
        """
        self.session_id = session_id
        self._tool_collection = ToolCollection()
        self._history: List[Dict[str, Any]] = []
        self._tool_configs: Dict[str, MCPToolConfig] = {}
        self._cache = cache
        self._metrics = metrics
        self._locks: Dict[str, asyncio.Lock] = {}
        self._custom_context: Dict[str, Any] = {}

        # Initialize basic configuration
        self._config = config or {}
        logger.info(f"Created MCP session: {session_id}")

    def register_tool(self, tool: BaseTool, config: Optional[MCPToolConfig] = None) -> None:
        """Register a tool with this session.

        Args:
            tool: Tool instance to register
            config: Optional tool-specific configuration
        """
        try:
            # Add tool to collection
            self._tool_collection.add_tool(tool)

            # Store tool configuration
            self._tool_configs[tool.name] = config or MCPToolConfig()

            # Create a lock for this tool
            self._locks[tool.name] = asyncio.Lock()

            # Register state change handler
            if hasattr(tool, "register_state_change_handler"):
                tool.register_state_change_handler(self._handle_tool_state_change)

            logger.debug(f"Registered tool '{tool.name}' with session {self.session_id}")
        except Exception as e:
            logger.error(f"Error registering tool {getattr(tool, 'name', 'unknown')}: {e}")

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

        # Unregister state change handler
        tool.unregister_state_change_handler(self._handle_tool_state_change)

        # Clean up tool locks
        if tool_name in self._locks:
            del self._locks[tool_name]

        # Remove tool configuration
        if tool_name in self._tool_configs:
            del self._tool_configs[tool_name]

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

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Args:
            tool_name: Name of the tool to get

        Returns:
            The tool if found, otherwise None
        """
        return self._tool_collection.get_tool(tool_name)

    def _handle_tool_state_change(self, state: ToolState) -> None:
        """Handle tool state changes."""
        # This is called by tools when their state changes
        # Currently just logging, but could be expanded
        pass

    def _generate_cache_key(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Generate a cache key for a tool execution.

        Args:
            tool_name: Name of the tool
            parameters: Parameters for the execution

        Returns:
            Cache key string
        """
        # Create a deterministic string representation of parameters
        params_str = json.dumps(parameters, sort_keys=True)
        # Combine tool name and parameters for cache key
        return f"{tool_name}:{params_str}"

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
            timeout: Optional timeout override for this execution
            cache_key: Optional cache key for this execution
            **kwargs: Parameters to pass to the tool

        Returns:
            Tool execution result
        """
        start_time = datetime.now()

        # Get tool configuration
        tool_config = self._tool_configs.get(tool_name, MCPToolConfig())

        # Try cache first if enabled and key provided
        if self._cache and tool_config.cache_enabled and cache_key:
            cache_result = self._cache.get(cache_key)
            if cache_result:
                logger.debug(f"Cache hit for tool '{tool_name}' in session {self.session_id}")

                # Record the execution in history
                request_record = {
                    "type": "request",
                    "tool": tool_name,
                    "parameters": kwargs,
                    "timestamp": start_time.isoformat(),
                    "cache_hit": True,
                }
                self._history.append(request_record)

                # Record cache hit in metrics
                if self._metrics and tool_config.usage_metrics_enabled:
                    self._metrics.record_execution(tool_name, self.session_id, True, 0.0)

                return cache_result

        # Generate automatic cache key if not provided
        if self._cache and tool_config.cache_enabled and not cache_key:
            cache_key = self._generate_cache_key(tool_name, kwargs)

        # Record the execution request
        request_record = {
            "type": "request",
            "tool": tool_name,
            "parameters": kwargs,
            "timestamp": start_time.isoformat(),
        }
        self._history.append(request_record)

        # Get the lock for this tool
        tool_lock = self._locks.get(tool_name)

        # Use the lock if available
        if tool_lock:
            async with tool_lock:
                result = await self._execute_tool_internal(
                    tool_name, kwargs, timeout or tool_config.timeout
                )
        else:
            # No lock found, execute directly
            result = await self._execute_tool_internal(
                tool_name, kwargs, timeout or tool_config.timeout
            )

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Record the result
        result_record = {
            "type": "result",
            "tool": tool_name,
            "success": result.error is None,
            "execution_time": execution_time,
            "timestamp": end_time.isoformat(),
        }
        self._history.append(result_record)

        # Add to cache if successful and caching is enabled
        if self._cache and tool_config.cache_enabled and cache_key and result.error is None:
            self._cache.put(cache_key, result, tool_config.cache_ttl)

        # Record metrics
        if self._metrics and tool_config.usage_metrics_enabled:
            self._metrics.record_execution(
                tool_name, self.session_id, result.error is None, execution_time
            )

        return result

    async def _execute_tool_internal(
        self, tool_name: str, tool_input: Dict[str, Any], timeout: float
    ) -> ToolResult:
        """Internal method to execute a tool with timeout."""
        try:
            # Create task with timeout
            task = asyncio.create_task(
                self._tool_collection.execute(name=tool_name, tool_input=tool_input)
            )

            # Wait for the task with timeout
            result = await asyncio.wait_for(task, timeout=timeout)

            # Set session_id in metadata if not already present
            if result.metadata and not result.metadata.session_id:
                result.metadata.session_id = self.session_id

            return result

        except asyncio.TimeoutError:
            return ToolFailure(
                error=f"Tool execution timed out after {timeout} seconds",
                system="Tool execution timed out",
                metadata=ToolResultMetadata(tool_name=tool_name, session_id=self.session_id),
            )
        except Exception as e:
            if isinstance(e, ToolError):
                error_msg = e.message
            else:
                error_msg = str(e)

            return ToolFailure(
                error=error_msg,
                system=f"Error executing tool: {type(e).__name__}",
                metadata=ToolResultMetadata(tool_name=tool_name, session_id=self.session_id),
            )

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the history of tool executions in this session.

        Returns:
            List of execution history records
        """
        return self._history.copy()

    def set_context(self, key: str, value: Any) -> None:
        """Set a value in the session context.

        Args:
            key: Context key
            value: Context value
        """
        self._custom_context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a value from the session context.

        Args:
            key: Context key
            default: Default value if key not found

        Returns:
            The value if found, otherwise default
        """
        return self._custom_context.get(key, default)

    def clear_context(self) -> None:
        """Clear the entire session context."""
        self._custom_context.clear()

    def get_tool_metrics(self, tool_name: str) -> Dict[str, Any]:
        """Get usage metrics for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary of tool metrics
        """
        if not self._metrics:
            return {}

        return self._metrics.get_tool_metrics(tool_name)

    def get_session_metrics(self) -> Dict[str, Any]:
        """Get metrics for this session.

        Returns:
            Dictionary of session metrics
        """
        if not self._metrics:
            return {}

        metrics = self._metrics.get_session_metrics(self.session_id)
        metrics["tool_count"] = len(self._tool_collection)
        metrics["history_count"] = len(self._history)
        return metrics

    async def cleanup(self) -> None:
        """Clean up resources used by this session."""
        # Perform any necessary cleanup for tools
        for tool in self._tool_collection:
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
        self._cache = MCPCache()
        self._metrics = MCPUsageMetrics()
        self._locks: Dict[str, asyncio.Lock] = {}
        self._default_config: Dict[str, Any] = {}

        logger.info("Initialized MCP server")

    def get_default_config(self) -> Dict[str, Any]:
        """Get the default server configuration."""
        return self._default_config.copy()

    def set_default_config(self, config: Dict[str, Any]) -> None:
        """Set the default server configuration.

        Args:
            config: New default configuration
        """
        self._default_config = config.copy()

    def create_session(
        self,
        session_id: str,
        config: Optional[Dict[str, Any]] = None,
        tool_categories: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
        tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    ) -> MCPSession:
        """Create a new MCP session with specific tools.

        Args:
            session_id: Unique identifier for the session
            config: Optional session configuration
            tool_categories: Optional list of tool categories to include
            tool_names: Optional list of specific tool names to include
            tool_capabilities: Optional list of capabilities to include

        Returns:
            New MCP session

        Raises:
            ValueError: If a session with this ID already exists
        """
        if session_id in self._sessions:
            raise ValueError(f"Session already exists: {session_id}")

        # Combine provided config with default config
        session_config = self.get_default_config()
        if config:
            session_config.update(config)

        # Create new session
        session = MCPSession(
            session_id=session_id, config=session_config, cache=self._cache, metrics=self._metrics
        )

        # Auto-discover and load all available tools if no specific filters are provided
        if not tool_categories and not tool_names and not tool_capabilities:
            # Load all registered tools
            all_tool_classes = self._registry.get_all_tool_classes()
            
            for tool_name, tool_cls in all_tool_classes.items():
                tool = self._safe_initialize_tool(tool_cls, tool_name, session_config)
                if tool:
                    # Create MCP tool config
                    mcp_tool_config = MCPToolConfig(
                        timeout=session_config.get("tool_timeout", 60.0),
                        max_retries=session_config.get("tool_retries", 3),
                        cache_enabled=session_config.get("cache_enabled", False),
                        cache_ttl=session_config.get("cache_ttl", 300),
                        result_log_enabled=session_config.get("result_logging", True),
                        usage_metrics_enabled=session_config.get("metrics_enabled", True),
                    )
                    # Register the tool
                    session.register_tool(tool, mcp_tool_config)
        else:
            # ... existing tool loading logic with filters
            pass

        self._sessions[session_id] = session
        return session
    
    def _safe_initialize_tool(self, tool_cls: Type["BaseTool"], name: str, session_config: Dict[str, Any]) -> Optional["BaseTool"]:
        """Safely initialize a tool with multiple fallback strategies."""
        try:
            # Get tool attributes
            tool_name = getattr(tool_cls, "name", name)
            description = getattr(tool_cls, "description", "No description available")
            parameters = getattr(tool_cls, "parameters", {})

            # Ensure parameters is a dictionary
            if parameters is None:
                parameters = {}

            # Configure tool
            tool_config = ToolConfig(
                timeout=session_config.get("tool_timeout", 60.0),
                max_retries=session_config.get("tool_retries", 3),
                cache_results=session_config.get("cache_enabled", False),
            )

            # Method 1: Try with full parameters
            try:
                tool = tool_cls(
                    name=tool_name,
                    description=description,
                    parameters=parameters,
                    config=tool_config,
                )
                return tool
            except (TypeError, ValueError, AttributeError):
                pass

            # Method 2: Try with config only
            try:
                tool = tool_cls(config=tool_config)
                return tool
            except (TypeError, ValueError, AttributeError):
                pass

            # Method 3: Try with no arguments
            try:
                tool = tool_cls()
                return tool
            except (TypeError, ValueError, AttributeError):
                pass

            logger.warning(f"Could not initialize tool {name} with any method")
            return None
            
        except Exception as e:
            logger.error(f"Error initializing tool {name}: {e}")
            return None    

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

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get detailed information about a session.

        Args:
            session_id: ID of the session

        Returns:
            Dictionary with session information or empty dict if not found
        """
        session = self.get_session(session_id)
        if not session:
            return {}

        tool_count = len(session.get_available_tools())
        history_count = len(session.get_history())
        metrics = session.get_session_metrics()

        return {
            "session_id": session_id,
            "tool_count": tool_count,
            "history_count": history_count,
            "is_agent_session": session_id.startswith("agent-"),
            **metrics,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get server-wide metrics.

        Returns:
            Dictionary of metrics
        """
        metrics = self._metrics.get_all_metrics()

        # Add server-specific metrics
        metrics["session_count"] = len(self._sessions)
        metrics["cache_size"] = len(self._cache._cache)

        return metrics

    async def add_tool_to_session(
        self, session_id: str, tool_name: str, config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a specific tool to an existing session.

        Args:
            session_id: ID of the session
            tool_name: Name of the tool to add
            config: Optional tool configuration

        Returns:
            True if the tool was added, False if not
        """
        session = self.get_session(session_id)
        if not session:
            return False

        # Check if tool is already in session
        if session.get_tool(tool_name):
            return True

        # Get tool class
        tool_cls = self._registry.get_tool_class(tool_name)
        if not tool_cls:
            return False

        try:
            # Extract basic tool info
            name = getattr(tool_cls, "name", tool_name)
            description = getattr(tool_cls, "description", "No description available")
            parameters = getattr(tool_cls, "parameters", None)

            # Create tool config
            tool_config = ToolConfig()
            if config:
                # Update from provided config
                for key, value in config.items():
                    if hasattr(tool_config, key):
                        setattr(tool_config, key, value)

            # Create and initialize the tool
            tool = tool_cls(
                name=name, description=description, parameters=parameters, config=tool_config
            )

            # Initialize if needed
            if getattr(tool, "requires_initialization", False):
                success = await tool.initialize()
                if not success:
                    logger.error(f"Failed to initialize tool {name}")
                    return False

            # Create MCP tool config
            mcp_tool_config = MCPToolConfig(
                timeout=tool_config.timeout if tool_config.timeout is not None else 60.0,
                max_retries=tool_config.max_retries if tool_config.max_retries is not None else 3,
                cache_enabled=tool_config.cache_results
                if tool_config.cache_results is not None
                else False,
                cache_ttl=config.get("cache_ttl", 300) if config else 300,
                result_log_enabled=config.get("result_logging", True) if config else True,
                usage_metrics_enabled=config.get("metrics_enabled", True) if config else True,
            )

            # Register with the session
            session.register_tool(tool, mcp_tool_config)
            return True

        except Exception as e:
            logger.error(f"Error adding tool {tool_name} to session {session_id}: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear the entire server cache."""
        self._cache.clear()

    async def cleanup(self) -> None:
        """Clean up all server resources."""
        # Close all sessions
        for session_id in list(self._sessions.keys()):
            await self.close_session(session_id)

        # Clear cache
        self._cache.clear()

        logger.info("MCP server resources cleaned up")


# Singleton accessor function
def get_mcp_server() -> MCPServer:
    """Get the global MCP server instance.

    Returns:
        Singleton MCP server instance
    """
    return MCPServer()
