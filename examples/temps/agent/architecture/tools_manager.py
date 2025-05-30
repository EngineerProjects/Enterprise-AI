"""
Tool management for agents.

This module handles tool discovery, selection, and execution,
building on the enhanced AgentToolManager implementation.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union, cast

from enterprise_ai.agent.architecture.errors import (
    AgentError,
    AgentErrorCode,
    ErrorManager,
    ToolError,
)
from enterprise_ai.agent.architecture.errors import RetryOptions, retry_async
from enterprise_ai.agent.architecture.utils import ensure_event_loop, run_async, timer
from enterprise_ai.logger import get_logger
from enterprise_ai.mcp.client import AgentMCPClient, ToolFilterStrategy
from enterprise_ai.mcp.utils import format_tool_descriptions, get_tool_capabilities
from enterprise_ai.tool.core.base import BaseTool, ToolCapability, ToolState
from enterprise_ai.tool.core.registry import get_registry, search_tools
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata

logger = get_logger("agent.tools_manager")


class ToolUsageMetrics:
    """Tracks metrics for tool usage."""

    def __init__(self) -> None:
        """Initialize tool usage metrics."""
        self.total_executions: int = 0
        self.successful_executions: int = 0
        self.failed_executions: int = 0
        self.execution_times: Dict[str, List[float]] = {}
        self.error_counts: Dict[str, int] = {}
        self.last_execution_time: Dict[str, datetime] = {}

    def record_execution(
        self, tool_name: str, success: bool, execution_time: float, error: Optional[str] = None
    ) -> None:
        """Record a tool execution."""
        self.total_executions += 1

        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1

            # Track error counts by type
            if error:
                error_type = error.split(":", 1)[0] if ":" in error else error
                self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

        # Track execution times by tool
        if tool_name not in self.execution_times:
            self.execution_times[tool_name] = []
        self.execution_times[tool_name].append(execution_time)

        # Update last execution time
        self.last_execution_time[tool_name] = datetime.now()

    def get_avg_execution_time(self, tool_name: Optional[str] = None) -> float:
        """Get average execution time for a tool or all tools."""
        if tool_name:
            times = self.execution_times.get(tool_name, [])
            return sum(times) / len(times) if times else 0.0

        all_times = [t for times in self.execution_times.values() for t in times]
        return sum(all_times) / len(all_times) if all_times else 0.0

    def get_success_rate(self, tool_name: Optional[str] = None) -> float:
        """Get success rate for a tool or overall."""
        if self.total_executions == 0:
            return 0.0

        if tool_name:
            tool_executions = len(self.execution_times.get(tool_name, []))
            if tool_executions == 0:
                return 0.0

            # Calculate from overall stats since we don't track per-tool success
            tool_errors = sum(
                count for t, count in self.error_counts.items() if t.startswith(f"{tool_name}:")
            )
            return (tool_executions - tool_errors) / tool_executions

        return self.successful_executions / self.total_executions


class AgentToolsManager:
    """Manages tool access and execution for an agent."""

    def __init__(self, agent: Any) -> None:
        """Initialize the tool manager for an agent.

        Args:
            agent: The agent this manager belongs to
        """
        self.agent = agent
        self.agent_id = getattr(agent, "id", "unknown")
        self._tools: Dict[str, BaseTool] = {}
        self._tool_usage_history: List[Dict[str, Any]] = []
        self._metrics = ToolUsageMetrics()
        self._execution_lock: Dict[str, asyncio.Lock] = {}
        self._registry = get_registry()
        self._error_manager = ErrorManager(self.agent_id)

        # MCP client for tool integration
        self._mcp_client: Optional[AgentMCPClient] = None
        self._mcp_initialized = False
        self._tool_cache: Dict[str, Dict[str, Any]] = {}
        self._capabilities: Set[str] = set()

        logger.info(f"Initialized tool manager for agent {self.agent_id}")

    @property
    def capabilities(self) -> Set[str]:
        """Get the capabilities of this tool manager."""
        return self._capabilities.copy()

    def add_capability(self, capability: Union[str, ToolCapability]) -> None:
        """Add a capability to this tool manager.

        Args:
            capability: The capability to add
        """
        if isinstance(capability, ToolCapability):
            self._capabilities.add(capability.value)
        else:
            self._capabilities.add(capability)

    def remove_capability(self, capability: Union[str, ToolCapability]) -> bool:
        """Remove a capability from this tool manager.

        Args:
            capability: The capability to remove

        Returns:
            True if the capability was removed, False if not found
        """
        cap_value = capability.value if isinstance(capability, ToolCapability) else capability

        if cap_value in self._capabilities:
            self._capabilities.remove(cap_value)
            return True
        return False

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the agent's available tools.

        Args:
            tool: The tool to add
        """
        self._tools[tool.name] = tool

        # Add an execution lock for this tool
        self._execution_lock[tool.name] = asyncio.Lock()

        # Extract tool capabilities
        if hasattr(tool, "capabilities"):
            for capability in tool.capabilities:
                self.add_capability(capability)

        logger.debug(f"Added tool '{tool.name}' to agent {self.agent_id}")

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the agent's available tools.

        Args:
            tool_name: Name of the tool to remove

        Returns:
            True if tool was removed, False if not found
        """
        if tool_name in self._tools:
            # Remove the tool
            tool = self._tools[tool_name]
            del self._tools[tool_name]

            # Remove the execution lock
            if tool_name in self._execution_lock:
                del self._execution_lock[tool_name]

            # Remove tool capabilities from the manager if no other tool has them
            if hasattr(tool, "capabilities"):
                remaining_capabilities = set()
                for t in self._tools.values():
                    if hasattr(t, "capabilities"):
                        for cap in t.capabilities:
                            cap_value = cap.value if isinstance(cap, ToolCapability) else cap
                            remaining_capabilities.add(cap_value)

                # Update capabilities - only keep those used by other tools
                self._capabilities = self._capabilities.intersection(remaining_capabilities)

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
            try:
                mcp_tools = self._mcp_client.discover_tools()
                for tool in mcp_tools:
                    if "function" in tool and "name" in tool["function"]:
                        tool_names.append(tool["function"]["name"])
            except Exception as e:
                logger.warning(f"Failed to list MCP tools: {e}")

        return tool_names

    def get_tools_by_capability(self, capability: Union[str, ToolCapability]) -> List[BaseTool]:
        """Get all tools with the specified capability.

        Args:
            capability: Capability to filter by

        Returns:
            List of tools with the specified capability
        """
        cap_value = capability.value if isinstance(capability, ToolCapability) else capability

        tools = []
        for tool in self._tools.values():
            if hasattr(tool, "capabilities"):
                tool_caps = {
                    cap.value if isinstance(cap, ToolCapability) else cap
                    for cap in tool.capabilities
                }
                if cap_value in tool_caps:
                    tools.append(tool)

        return tools

    def get_tool_descriptions(self) -> Dict[str, str]:
        """Get descriptions of all available tools.

        Returns:
            Dictionary mapping tool names to descriptions
        """
        descriptions = {}

        # Local tools
        for name, tool in self._tools.items():
            # Get description with proper fallback
            description = "No description available"
            if hasattr(tool, "description") and tool.description:
                description = tool.description.strip()
            descriptions[name] = description

        # Add MCP tool descriptions if initialized
        if self._mcp_client and self._mcp_initialized:
            try:
                mcp_tools = self._mcp_client.discover_tools()
                for tool in mcp_tools:
                    if "function" in tool and "name" in tool["function"]:
                        name = tool["function"]["name"]
                        desc = tool["function"].get("description", "")
                        descriptions[name] = desc if desc else "No description available"
            except Exception as e:
                logger.warning(f"Failed to get MCP tool descriptions: {e}")

        return descriptions

    @timer("tool_execution")
    async def execute_tool(
        self,
        tool_name: str,
        timeout: Optional[float] = None,
        retry_count: int = 2,
        retry_delay: float = 1.0,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            timeout: Optional timeout in seconds
            retry_count: Number of retries for transient errors
            retry_delay: Delay between retries in seconds
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        success = False
        error_message = None

        # Get the tool configuration
        tool_config = None
        if tool_name in self._tools:
            tool = self._tools[tool_name]
            tool_config = getattr(tool, "config", None)

        # Use timeout from tool config if available and not overridden
        if timeout is None and tool_config and hasattr(tool_config, "timeout"):
            timeout = tool_config.timeout

        # Apply lock for this specific tool if available
        lock = self._execution_lock.get(tool_name)

        try:
            # Create retry options
            retry_options = RetryOptions(
                max_retries=retry_count,
                base_delay=retry_delay,
                max_delay=30.0,  # Cap at 30 seconds
                backoff_factor=2.0,
            )

            # Execute with retry
            result: ToolResult = await retry_async(
                self._execute_tool_internal,
                retry_options,
                (ToolError, asyncio.TimeoutError),
                tool_name=tool_name,
                timeout=timeout,
                use_lock=lock is not None,
                **kwargs,
            )

            # Record execution result
            success = result.error is None
            error_message = result.error

            return result

        except Exception as e:
            # Handle unhandled exceptions
            logger.error(f"Unhandled error executing tool {tool_name}: {e}")

            # Create failure result
            error_message = f"Tool execution error: {str(e)}"
            result = ToolFailure(
                error=error_message, metadata=ToolResultMetadata(tool_name=tool_name)
            )

            success = False
            return result

        finally:
            # Record tool usage regardless of success/failure
            execution_time = (datetime.now() - start_time).total_seconds()
            self._record_tool_usage(tool_name, start_time, kwargs, result, execution_time)

            # Record metrics
            self._metrics.record_execution(tool_name, success, execution_time, error_message)

    async def _execute_tool_internal(
        self, tool_name: str, timeout: Optional[float] = None, use_lock: bool = True, **kwargs: Any
    ) -> ToolResult:
        """Internal method to execute a tool with improved error handling.

        Args:
            tool_name: Name of the tool to execute
            timeout: Optional timeout in seconds
            use_lock: Whether to use a lock for this tool
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        logger.info(f"Executing tool '{tool_name}' with parameters: {list(kwargs.keys())}")
        
        # Check if it's a local tool first
        if tool_name in self._tools:
            tool = self._tools[tool_name]
            lock = self._execution_lock.get(tool_name) if use_lock else None

            logger.debug(f"Executing local tool '{tool_name}'")
            
            # Use the lock if available
            if lock:
                async with lock:
                    result = await self._execute_local_tool(tool, timeout=timeout, **kwargs)
            else:
                result = await self._execute_local_tool(tool, timeout=timeout, **kwargs)

            logger.info(f"Local tool '{tool_name}' execution completed - Success: {result.error is None}")
            return result

        # Check if we should try MCP
        elif self._mcp_client:
            # Initialize MCP client if not already done
            if not self._mcp_initialized:
                logger.info(f"Initializing MCP for tool '{tool_name}'")
                await self._init_mcp_client()

            # Try to execute via MCP
            if self._mcp_initialized:
                logger.info(f"Executing MCP tool '{tool_name}'")
                
                try:
                    result = await self._mcp_client.execute_tool(tool_name, timeout=timeout, **kwargs)
                    logger.info(f"MCP tool '{tool_name}' execution completed - Success: {result.error is None}")
                    
                    # Log the actual output for debugging
                    if result.output:
                        logger.debug(f"Tool '{tool_name}' output: {str(result.output)[:200]}...")
                    if result.error:
                        logger.warning(f"Tool '{tool_name}' error: {result.error}")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Error executing MCP tool '{tool_name}': {e}")
                    return ToolFailure(
                        error=f"MCP execution error: {str(e)}",
                        metadata=ToolResultMetadata(tool_name=tool_name),
                    )
            else:
                # MCP not initialized
                logger.error(f"MCP not initialized for tool: {tool_name}")
                return ToolFailure(
                    error=f"MCP not initialized for tool: {tool_name}",
                    metadata=ToolResultMetadata(tool_name=tool_name),
                )

        else:
            # Tool not found anywhere
            logger.error(f"Tool '{tool_name}' not found for agent {self.agent_id}")
            available_tools = list(self._tools.keys())
            if self._mcp_client:
                mcp_tools = [t.get("name", "") for t in self._mcp_client.discover_tools()]
                available_tools.extend(mcp_tools)
            
            error_msg = f"Tool not found: {tool_name}. Available tools: {available_tools}"
            return ToolFailure(
                error=error_msg,
                metadata=ToolResultMetadata(tool_name=tool_name),
            )

    async def _execute_local_tool(
        self, tool: BaseTool, timeout: Optional[float] = None, **kwargs: Any
    ) -> ToolResult:
        """Execute a local tool with enhanced logging and error handling.

        Args:
            tool: Tool to execute
            timeout: Optional timeout in seconds
            **kwargs: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        tool_name = tool.name
        logger.info(f"Starting local execution of tool '{tool_name}'")
        
        # Update tool state if possible
        try:
            if hasattr(tool, "_update_state"):
                tool._update_state(ToolState.RUNNING)
        except Exception as e:
            logger.warning(f"Error updating tool state: {e}")

        try:
            # Log the parameters being passed
            param_summary = {k: f"{type(v).__name__}" for k, v in kwargs.items()}
            logger.debug(f"Tool '{tool_name}' parameters: {param_summary}")
            
            # Execute with timeout if specified
            if timeout:
                logger.debug(f"Executing tool '{tool_name}' with {timeout}s timeout")
                tool_task = asyncio.create_task(tool.execute(**kwargs))
                try:
                    result = await asyncio.wait_for(tool_task, timeout=timeout)
                except asyncio.TimeoutError:
                    logger.error(f"Tool '{tool_name}' timed out after {timeout} seconds")
                    # Clean up the task
                    if not tool_task.done():
                        tool_task.cancel()
                        try:
                            await tool_task
                        except asyncio.CancelledError:
                            pass

                    return ToolFailure(
                        error=f"Tool execution timed out after {timeout} seconds",
                        metadata=ToolResultMetadata(tool_name=tool_name),
                    )
            else:
                # No timeout specified
                logger.debug(f"Executing tool '{tool_name}' without timeout")
                result = await tool.execute(**kwargs)

            # Log execution result
            if isinstance(result, ToolResult):
                success = result.error is None
                logger.info(f"Tool '{tool_name}' execution completed - Success: {success}")
                
                if success and result.output:
                    output_preview = str(result.output)[:200] + ("..." if len(str(result.output)) > 200 else "")
                    logger.info(f"Tool '{tool_name}' output preview: {output_preview}")
                elif result.error:
                    logger.warning(f"Tool '{tool_name}' error: {result.error}")
                
                # Ensure metadata includes tool name
                if result.metadata is None:
                    result.metadata = ToolResultMetadata(tool_name=tool_name)
                elif result.metadata.tool_name is None:
                    result.metadata.tool_name = tool_name

                return result
            else:
                # Convert to ToolResult
                logger.info(f"Tool '{tool_name}' returned non-ToolResult, converting")
                return ToolResult(output=result, metadata=ToolResultMetadata(tool_name=tool_name))
                
        except Exception as e:
            logger.error(f"Error executing local tool {tool_name}: {e}", exc_info=True)

            # Check if this is already a ToolError
            if isinstance(e, ToolError):
                # Create proper failure result
                return ToolFailure(
                    error=e.message,
                    error_code=getattr(e, "error_code", "TOOL_ERROR"),
                    metadata=ToolResultMetadata(tool_name=tool_name),
                )
            else:
                # General exception
                return ToolFailure(
                    error=f"Tool execution error: {str(e)}",
                    metadata=ToolResultMetadata(tool_name=tool_name),
                )

    def _record_tool_usage(
        self,
        tool_name: str,
        start_time: datetime,
        parameters: Dict[str, Any],
        result: ToolResult,
        execution_time: float,
    ) -> None:
        """Record tool usage for history tracking.

        Args:
            tool_name: Name of the tool
            start_time: Start time of execution
            parameters: Parameters passed to the tool
            result: Tool execution result
            execution_time: Execution time in seconds
        """
        self._tool_usage_history.append(
            {
                "tool_name": tool_name,
                "timestamp": start_time,
                "duration": execution_time,
                "parameters": parameters,
                "success": result.error is None,
                "error": result.error,
                "output_summary": str(result.output)[:100] if result.output else None,
            }
        )

    async def execute_tools_parallel(
        self, executions: List[Dict[str, Any]]
    ) -> List[Tuple[str, ToolResult]]:
        """Execute multiple tools in parallel.

        Args:
            executions: List of execution specifications. Each one should have:
                      - tool_name: Name of the tool to execute
                      - parameters: Dictionary of parameters
                      - timeout: Optional timeout

        Returns:
            List of (tool_name, result) tuples
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

            # Create task
            task = asyncio.create_task(self.execute_tool(tool_name, timeout=timeout, **parameters))

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
                error_result = ToolFailure(
                    error=f"Execution error: {str(result)}",
                    metadata=ToolResultMetadata(tool_name=tool_name, session_id=self.agent_id),
                )
                final_results.append((tool_name, error_result))
            else:
                final_results.append((tool_name, cast(ToolResult, result)))

        return final_results

    def get_usage_history(self) -> List[Dict[str, Any]]:
        """Get the tool usage history for this agent.

        Returns:
            List of tool usage records
        """
        return self._tool_usage_history.copy()

    def get_tool_metrics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific tool or all tools.

        Args:
            tool_name: Optional name of tool to get metrics for

        Returns:
            Dictionary of metrics
        """
        if tool_name:
            return {
                "avg_execution_time": self._metrics.get_avg_execution_time(tool_name),
                "success_rate": self._metrics.get_success_rate(tool_name),
                "execution_count": len(self._metrics.execution_times.get(tool_name, [])),
                "last_execution": self._metrics.last_execution_time.get(tool_name),
            }

        return {
            "total_executions": self._metrics.total_executions,
            "successful_executions": self._metrics.successful_executions,
            "failed_executions": self._metrics.failed_executions,
            "success_rate": self._metrics.get_success_rate(),
            "avg_execution_time": self._metrics.get_avg_execution_time(),
            "error_types": dict(self._metrics.error_counts),
        }

    def get_formatted_tool_descriptions(
        self, include_capabilities: bool = True, include_examples: bool = True
    ) -> str:
        """Get formatted tool descriptions for prompts.

        Args:
            include_capabilities: Whether to include tool capabilities
            include_examples: Whether to include usage examples

        Returns:
            String with formatted tool descriptions
        """
        try:
            # If using MCP client, use its tools and formatter
            if self._mcp_client and self._mcp_initialized:
                tools = self._mcp_client.discover_tools()
                base_descriptions = format_tool_descriptions(tools)

                if not (include_capabilities or include_examples):
                    return base_descriptions

                # Add capabilities and examples if requested
                enhanced_descriptions = []
                for tool in tools:
                    if "function" not in tool:
                        continue

                    tool_name = tool["function"].get("name")
                    if not tool_name:
                        continue

                    enhanced_description = f"Tool: {tool_name}\n"
                    enhanced_description += (
                        f"Description: {tool['function'].get('description', '')}\n"
                    )

                    # Add parameters
                    parameters = tool["function"].get("parameters", {})
                    if parameters and "properties" in parameters:
                        enhanced_description += "Parameters:\n"
                        properties = parameters.get("properties", {})
                        required = parameters.get("required", [])

                        for param_name, param_info in properties.items():
                            param_type = param_info.get("type", "any")
                            description = param_info.get("description", "")
                            is_required = param_name in required

                            req_str = " (required)" if is_required else " (optional)"
                            enhanced_description += f"  - {param_name}: {param_type}{req_str}"
                            if description:
                                enhanced_description += f" - {description}"
                            enhanced_description += "\n"

                    # Add capabilities if available
                    if include_capabilities:
                        info = self._mcp_client.get_tool_info(tool_name)
                        if "capabilities" in info and info["capabilities"]:
                            enhanced_description += "Capabilities:\n"
                            for cap in info["capabilities"]:
                                enhanced_description += f"  - {cap}\n"

                    # Add example if available
                    if include_examples and self._mcp_client:
                        try:
                            # Get tool usage examples if available
                            info = self._mcp_client.get_tool_info(tool_name)
                            if "usage_examples" in info and info["usage_examples"]:
                                example = info["usage_examples"][0]
                                enhanced_description += "Example:\n"
                                enhanced_description += "```\n"
                                if "parameters" in example:
                                    for param, value in example["parameters"].items():
                                        enhanced_description += f"  {param}: {value}\n"
                                enhanced_description += "```\n"
                        except Exception as e:
                            logger.debug(f"Error getting examples for {tool_name}: {e}")

                    enhanced_descriptions.append(enhanced_description)

                return "\n".join(enhanced_descriptions)

            # Format local tools
            tools_list: List[Dict[str, Any]] = []
            for name, tool_item in self._tools.items():
                try:
                    if hasattr(tool_item, "to_param"):
                        tool_dict: Dict[str, Any] = cast(Dict[str, Any], tool_item.to_param())
                        tools_list.append(tool_dict)
                except Exception as e:
                    logger.warning(f"Error formatting tool {name}: {e}")

            base_descriptions = format_tool_descriptions(tools_list)

            if not (include_capabilities or include_examples):
                return base_descriptions

            # Add capabilities and examples if requested
            enhanced_descriptions = []
            for name, tool_item in self._tools.items():
                # Cast to BaseTool to ensure proper type checking
                tool_inst = cast(BaseTool, tool_item)
                enhanced_description = f"Tool: {name}\n"

                # Access description safely
                if hasattr(tool_inst, "description"):
                    enhanced_description += f"Description: {tool_inst.description}\n"
                else:
                    enhanced_description += "Description: No description available\n"

                # Add parameters
                if hasattr(tool_inst, "parameters") and tool_inst.parameters:
                    params = tool_inst.parameters
                    enhanced_description += "Parameters:\n"

                    if "properties" in params:
                        properties = params.get("properties", {})
                        required = params.get("required", [])

                        for param_name, param_info in properties.items():
                            param_type = param_info.get("type", "any")
                            description = param_info.get("description", "")
                            is_required = param_name in required

                            req_str = " (required)" if is_required else " (optional)"
                            enhanced_description += f"  - {param_name}: {param_type}{req_str}"
                            if description:
                                enhanced_description += f" - {description}"
                            enhanced_description += "\n"

                # Add capabilities if available
                if include_capabilities and hasattr(tool, "capabilities"):
                    enhanced_description += "Capabilities:\n"
                    for cap in tool.capabilities:
                        cap_str = cap.value if hasattr(cap, "value") else str(cap)
                        enhanced_description += f"  - {cap_str}\n"

                # Add example if available
                if include_examples and hasattr(tool, "usage_examples") and tool.usage_examples:
                    example = tool.usage_examples[0]
                    enhanced_description += "Example:\n"
                    enhanced_description += "```\n"
                    if "parameters" in example:
                        for param, value in example["parameters"].items():
                            enhanced_description += f"  {param}: {value}\n"
                    enhanced_description += "```\n"

                enhanced_descriptions.append(enhanced_description)

            return "\n".join(enhanced_descriptions)

        except Exception as e:
            logger.error(f"Error formatting tool descriptions: {e}")
            return "Error retrieving tool descriptions"

    async def get_tool_schemas(self, filter_by_capabilities: bool = True) -> List[Dict[str, Any]]:
        """Get schemas for all available tools.

        Args:
            filter_by_capabilities: Whether to filter tools by agent capabilities

        Returns:
            List of tool schemas in function calling format
        """
        schemas = []

        # Local tools
        for tool in self._tools.values():
            # Skip tools that don't match our capabilities if filtering is enabled
            if filter_by_capabilities and hasattr(tool, "capabilities"):
                tool_caps = {
                    cap.value if hasattr(cap, "value") else str(cap) for cap in tool.capabilities
                }

                # Skip if no intersection with agent capabilities
                if not tool_caps.intersection(self._capabilities):
                    continue

            # Add tool schema
            if hasattr(tool, "to_param"):
                schemas.append(tool.to_param())
            else:
                # Create basic schema
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters or {},
                        },
                    }
                )

        # Add MCP tools if initialized
        if self._mcp_client:
            # Initialize MCP client if not already
            if not self._mcp_initialized:
                await self._init_mcp_client()

            if self._mcp_initialized:
                # Get all tools or filter by capabilities
                if filter_by_capabilities and self._capabilities:
                    # Convert capabilities to list
                    cap_list = list(self._capabilities)

                    # Search tools by capabilities
                    mcp_tools = self._mcp_client.search_tools(
                        capabilities=cap_list, match_all_capabilities=False
                    )
                else:
                    # Get all tools
                    mcp_tools = self._mcp_client.discover_tools()

                schemas.extend(mcp_tools)

        return schemas

    async def enable_mcp(
        self,
        tool_categories: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
        tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    ) -> bool:
        """Enable MCP integration with proper tool synchronization.

        Args:
            tool_categories: Optional list of tool categories to include
            tool_names: Optional list of specific tool names to include  
            tool_capabilities: Optional list of capabilities to include

        Returns:
            True if MCP was enabled successfully, False otherwise
        """
        if self._mcp_client:
            logger.info(f"MCP already enabled for agent {self.agent_id}")
            return True

        try:
            # Create MCP client with agent-specific session
            session_id = f"agent-{self.agent_id}"
            
            # Create the MCP client
            self._mcp_client = AgentMCPClient(
                session_id=session_id,
                create_if_not_exists=True,
                config={
                    "tool_timeout": 30.0,
                    "tool_retries": 2,
                    "cache_enabled": True,
                    "cache_ttl": 300,
                    "result_logging": True,
                    "metrics_enabled": True,
                },
            )

            # Initialize the MCP client
            await self._mcp_client.initialize(
                tool_categories=tool_categories,
                tool_names=tool_names,
                tool_capabilities=tool_capabilities,
            )

            # Sync local tools with MCP session
            await self._sync_tools_with_mcp()

            self._mcp_initialized = True
            logger.info(f"MCP enabled for agent {self.agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to enable MCP for agent {self.agent_id}: {e}")
            self._mcp_client = None
            return False

    async def _sync_tools_with_mcp(self) -> None:
        """Synchronize local tools with MCP session."""
        if not self._mcp_client:
            return

        # Register any locally added tools with MCP
        for tool_name, tool in self._tools.items():
            try:
                self._mcp_client.session.register_tool(tool)
                logger.debug(f"Registered local tool {tool_name} with MCP")
            except Exception as e:
                logger.warning(f"Failed to register tool {tool_name} with MCP: {e}")

        # Get available tools from MCP and add them to local cache
        available_tools = self._mcp_client.discover_tools()
        for tool_info in available_tools:
            tool_name = tool_info.get("name", "")
            if tool_name and tool_name not in self._tools:
                self._tool_cache[tool_name] = tool_info

    async def _init_mcp_client(self) -> None:
        """Initialize the MCP client if needed."""
        if not self._mcp_client or self._mcp_initialized:
            return

        try:
            # Discover available tools to cache them
            tools = self._mcp_client.discover_tools()

            # Update tool capabilities from discovered tools
            for tool in tools:
                if "function" in tool and "name" in tool["function"]:
                    tool_name = tool["function"]["name"]

                    # Get tool info to extract capabilities
                    tool_info = self._mcp_client.get_tool_info(tool_name)

                    # Add capabilities to our set
                    if "capabilities" in tool_info:
                        for cap in tool_info["capabilities"]:
                            self.add_capability(cap)

                    # Cache tool info for later
                    self._tool_cache[tool_name] = tool_info

            self._mcp_initialized = True
            logger.info(f"Initialized MCP for agent {self.agent_id}")
        except Exception as e:
            self._error_manager.handle_error(e, error_code=AgentErrorCode.INITIALIZATION_FAILED)
            logger.error(f"Failed to initialize MCP for agent {self.agent_id}: {e}")
            self._mcp_initialized = False

    async def update_mcp_tools(
        self,
        add_categories: Optional[List[str]] = None,
        add_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
        add_tools: Optional[List[str]] = None,
        remove_tools: Optional[List[str]] = None,
    ) -> bool:
        """Update the MCP tools available to this agent.

        Args:
            add_categories: Categories of tools to add
            add_capabilities: Capabilities to add
            add_tools: Specific tool names to add
            remove_tools: Tools to remove

        Returns:
            True if update was successful
        """
        if not self._mcp_client:
            logger.warning(f"MCP not enabled for agent {self.agent_id}")
            return False

        try:
            # Add capabilities to agent capabilities
            if add_capabilities:
                for cap in add_capabilities:
                    self.add_capability(cap)

            # Update MCP client tools
            await self._mcp_client.update_tools(
                add_categories=add_categories,
                add_capabilities=add_capabilities,
                add_tools=add_tools,
                remove_tools=remove_tools,
            )

            # Refresh the tool cache
            self._tool_cache = {}

            # Re-discover tools to update cache
            if self._mcp_initialized:
                tools = self._mcp_client.discover_tools()

                # Update tool capabilities from discovered tools
                for tool in tools:
                    if "function" in tool and "name" in tool["function"]:
                        tool_name = tool["function"]["name"]

                        # Get tool info to extract capabilities
                        tool_info = self._mcp_client.get_tool_info(tool_name)

                        # Add capabilities to our set
                        if "capabilities" in tool_info:
                            for cap in tool_info["capabilities"]:
                                self.add_capability(cap)

                        # Cache tool info for later
                        self._tool_cache[tool_name] = tool_info

            logger.info(f"Updated MCP tools for agent {self.agent_id}")
            return True
        except Exception as e:
            self._error_manager.handle_error(e, error_code=AgentErrorCode.EXECUTION_FAILED)
            logger.error(f"Failed to update MCP tools for agent {self.agent_id}: {e}")
            return False

    async def discover_tools_by_capability(
        self, capabilities: List[Union[str, ToolCapability]], match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """Discover tools that match specific capabilities.

        Args:
            capabilities: List of capabilities to match
            match_all: If True, tools must have all capabilities
                      If False, tools must have at least one capability

        Returns:
            List of tool definitions matching the capabilities
        """
        # Convert capabilities to strings
        cap_strings = [
            cap.value if isinstance(cap, ToolCapability) else cap for cap in capabilities
        ]

        # Local tools that match capabilities
        local_tools = []
        for tool in self._tools.values():
            if hasattr(tool, "capabilities"):
                tool_caps = {
                    cap.value if hasattr(cap, "value") else str(cap) for cap in tool.capabilities
                }

                if match_all:
                    # Must have all capabilities
                    if all(cap in tool_caps for cap in cap_strings):
                        local_tools.append(tool.to_param())
                else:
                    # Must have at least one capability
                    if any(cap in tool_caps for cap in cap_strings):
                        local_tools.append(tool.to_param())

        # MCP tools that match capabilities
        mcp_tools = []
        if self._mcp_client and self._mcp_initialized:
            mcp_tools = self._mcp_client.search_tools(
                capabilities=cap_strings, match_all_capabilities=match_all
            )

        # Combine results
        return local_tools + mcp_tools

    async def cleanup(self) -> None:
        """Clean up resources used by the tool manager."""
        # Clean up MCP client
        if self._mcp_client:
            try:
                await self._mcp_client.close()
                logger.info(f"Closed MCP client for agent {self.agent_id}")
            except Exception as e:
                logger.warning(f"Error closing MCP client: {e}")

        # Clean up local tools
        for tool in list(self._tools.values()):
            if hasattr(tool, "cleanup") and callable(getattr(tool, "cleanup")):
                try:
                    await tool.cleanup()
                except Exception as e:
                    logger.warning(f"Error during tool cleanup for {tool.name}: {e}")

        logger.info(f"Cleaned up tool manager for agent {self.agent_id}")
