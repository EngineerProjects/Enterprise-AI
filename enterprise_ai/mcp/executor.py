"""
Simplified MCP Executor - Tool execution focused.

Leverages existing tool infrastructure for clean, simple tool execution.
"""

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, List, Optional, Set

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import ToolCall
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import ToolRegistry
from enterprise_ai.tool.core.base import ToolCapability, ExecutionMode
from enterprise_ai.mcp.sandbox_config import SandboxConfig, DEFAULT_SANDBOX_CONFIG
from enterprise_ai.mcp.sandbox_executor import SimpleMCPExecutor, SandboxToolExecutor

logger = get_optimized_logger("new_mcp.executor")


class ToolMCP:
    """
    Simplified MCP for Enterprise AI - Tool execution only.
    
    Leverages existing ToolRegistry and focuses purely on executing tools
    and returning clean, structured results.
    """

    def __init__(self, timeout: float = 30.0, sandbox_config: Optional[SandboxConfig] = None, auto_load_tools: bool = True):
        """
        Initialize SimpleMCP.
        
        Args:
            timeout: Default timeout for tool execution
            sandbox_config: Optional sandbox configuration for manual control
            auto_load_tools: Whether to automatically load tools from registry
        """
        self.timeout = timeout
        self.sandbox_config = sandbox_config or DEFAULT_SANDBOX_CONFIG
        self._execution_count = 0
        self._failed_count = 0
        self._tools = {}
        
        # Initialize tool executor
        self.tool_executor = SimpleMCPExecutor(
            tools={},
            execution_timeout=timeout,
            verbose=False
        )
        
        # Initialize sandbox executor if enabled
        self.sandbox_executor = None
        if self.sandbox_config.enabled:
            self.sandbox_executor = SandboxToolExecutor(
                tools={},
                execution_timeout=timeout,
                default_sandbox_mode=self.sandbox_config.default_mode,
                enable_sandbox_routing=True,
                verbose=False
            )
        
        # Load available tools from registry if requested
        if auto_load_tools:
            try:
                self.registry = ToolRegistry()
                self._tools = self._load_tools_from_registry()
                
                if self._tools:
                    logger.info("SimpleMCP initialized with %d tools", len(self._tools))
                else:
                    logger.error("No tools loaded from registry")
            except Exception as e:
                logger.error("Failed to load tools from registry: %s", e)
                logger.info("SimpleMCP initialized without auto-loading tools")
        else:
            logger.info("SimpleMCP initialized without auto-loading tools")

    def _load_tools_from_registry(self) -> Dict[str, Callable]:
        """Load tool functions from the existing registry."""
        tools = {}
        
        if not hasattr(self, 'registry'):
            return tools
        
        try:
            # Get all tool classes from registry
            tool_classes = self.registry.get_all_tool_classes()
            
            for tool_name, tool_class in tool_classes.items():
                try:
                    # Create tool instance
                    tool_instance = tool_class()
                    
                    # Get the execute method
                    if hasattr(tool_instance, 'execute') and callable(tool_instance.execute):
                        # Register with class name (e.g., 'WebSearch')
                        tools[tool_name] = tool_instance.execute
                        
                        # Also register with snake_case name if tool has a name attribute
                        if hasattr(tool_instance, 'name') and isinstance(tool_instance.name, str):
                            instance_name = tool_instance.name
                            if instance_name != tool_name:
                                tools[instance_name] = tool_instance.execute
                                logger.debug("Registered tool alias: %s -> %s", instance_name, tool_name)
                        
                        # Also add normalized version of class name (e.g., 'web_search')
                        snake_name = self._normalize_tool_name(tool_name)
                        if snake_name != tool_name:
                            tools[snake_name] = tool_instance.execute
                            logger.debug("Registered normalized name: %s -> %s", snake_name, tool_name)
                    else:
                        logger.error("Tool %s has no execute method", tool_name)
                        
                except Exception as e:
                    logger.error("Failed to load tool %s: %s", tool_name, e)
                    
        except Exception as e:
            logger.error("Failed to load tools from registry: %s", e)
            
        return tools
        
    def _normalize_tool_name(self, name: str) -> str:
        """Convert CamelCase to snake_case for consistent tool naming."""
        import re
        # Convert CamelCase to snake_case
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function directly."""
        self._tools[name] = func
        self.tool_executor.register_tool(name, func)
        
        # Also register with sandbox executor if enabled
        if self.sandbox_executor:
            self.sandbox_executor.register_tool(name, func)
        
        logger.info("Registered tool: %s", name)

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tools.keys())

    async def execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute a list of tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of tool execution results
        """
        if not tool_calls:
            return []

        results = []
        self._execution_count += len(tool_calls)
        
        # Update tool executors with current tools
        self.tool_executor.tools = self._tools
        if self.sandbox_executor:
            self.sandbox_executor.tools = self._tools
        
        try:
            # Determine if we should use sandbox based on config and tool types
            if self.sandbox_executor and self.sandbox_config.enabled:
                # Check if any tools are in the dangerous list
                dangerous_tools = [
                    tc for tc in tool_calls 
                    if tc.function.name in self.sandbox_config.dangerous_tools
                ]
                
                # Split tool calls between dangerous and safe
                safe_tools = [tc for tc in tool_calls if tc not in dangerous_tools]
                
                # Process dangerous tools with sandbox
                if dangerous_tools:
                    sandbox_results = await self.sandbox_executor.aexecute_tool_calls(dangerous_tools)
                    results.extend(sandbox_results)
                
                # Process safe tools directly
                if safe_tools:
                    safe_results = await self.tool_executor.aexecute_tool_calls(safe_tools)
                    results.extend(safe_results)
            else:
                # Process all tools directly
                results = await self.tool_executor.aexecute_tool_calls(tool_calls)
                
            # Track failures
            self._failed_count += sum(1 for r in results if not r.success)
            
            return results
        except Exception as e:
            self._failed_count += len(tool_calls)
            # Create error results for all tool calls
            for tool_call in tool_calls:
                results.append(
                    ToolResult(
                        tool_call_id=tool_call.id,
                        name=tool_call.function.name,
                        result="",
                        success=False,
                        error=f"MCP execution error: {str(e)}"
                    )
                )
            return results

    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with error handling."""
        # This method is deprecated but kept for backward compatibility
        # It now delegates to the tool executor
        if self.sandbox_executor and self.sandbox_config.enabled and tool_call.function.name in self.sandbox_config.dangerous_tools:
            results = await self.sandbox_executor.aexecute_tool_calls([tool_call])
        else:
            results = await self.tool_executor.aexecute_tool_calls([tool_call])
            
        return results[0] if results else ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.function.name,
            result="",
            success=False,
            error="No result returned from tool executor"
        )

    async def _execute_directly(self, tool_call: ToolCall, tool_func: Callable, args: Dict[str, Any], start_time: float) -> ToolResult:
        """Execute tool directly."""
        try:
            if inspect.iscoroutinefunction(tool_func):
                result = await asyncio.wait_for(
                    tool_func(**args), 
                    timeout=self.timeout
                )
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_func(**args)),
                    timeout=self.timeout
                )
            
            execution_time = time.time() - start_time
            
            return self._create_success_result(
                tool_call.id, tool_call.function.name, result, execution_time
            )
            
        except asyncio.TimeoutError:
            self._failed_count += 1
            return self._create_error_result(
                tool_call.id, tool_call.function.name, f"Tool execution timed out after {self.timeout}s"
            )

    async def _execute_in_sandbox(self, tool_call: ToolCall, tool_func: Callable, args: Dict[str, Any], start_time: float) -> ToolResult:
        """Execute tool in sandbox (placeholder for now)."""
        # For now, just execute directly with a note
        # You can integrate actual sandbox execution here later
        logger.info("Tool %s marked for sandbox execution", tool_call.function.name)
        
        result = await self._execute_directly(tool_call, tool_func, args, start_time)
        
        # Add sandbox metadata
        if result.metadata is None:
            result.metadata = {}
        result.metadata["sandbox_intended"] = True
        result.metadata["sandbox_available"] = False  # Change when you integrate actual sandbox
        
        return result

    def _create_success_result(
        self, tool_call_id: str, name: str, result: Any, execution_time: float
    ) -> ToolResult:
        """Create a success ToolResult."""
        # Clean up the result for safe serialization
        cleaned_result = self._clean_result(result)
        
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            result=cleaned_result,
            success=True,
            error=None,
            execution_time=execution_time,
            metadata={}
        )

    def _create_error_result(
        self, tool_call_id: str, name: str, error: str, execution_time: Optional[float] = None
    ) -> ToolResult:
        """Create an error ToolResult."""
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            result="",
            success=False,
            error=error,
            execution_time=execution_time,
            metadata={}
        )

    def _clean_result(self, result: Any) -> Any:
        """Clean result for safe serialization."""
        try:
            if isinstance(result, (str, int, float, bool, list, dict)):
                return result
            else:
                return str(result)
        except Exception:
            return "Result could not be serialized"

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        stats = {
            "total_executions": self._execution_count,
            "successful_executions": self._execution_count - self._failed_count,
            "failed_executions": self._failed_count,
            "success_rate": (self._execution_count - self._failed_count) / max(1, self._execution_count),
            "available_tools": len(self._tools),
            "tool_names": list(self._tools.keys())
        }
        
        # Add executor stats if available
        if hasattr(self.tool_executor, 'get_execution_stats'):
            stats["executor_stats"] = self.tool_executor.get_execution_stats()
            
        # Add sandbox stats if available
        if self.sandbox_executor and hasattr(self.sandbox_executor, 'get_execution_stats'):
            stats["sandbox_stats"] = self.sandbox_executor.get_execution_stats()
            
        return stats

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for all available tools in a format suitable for LLMs.
        
        Returns:
            List of tool definitions in the format expected by LLM providers
        """
        from enterprise_ai.tool.core.registry import ToolRegistry
        from enterprise_ai.schema.tool import ToolDefinition
        
        registry = ToolRegistry()
        tool_definitions = []
        
        # Get the actual tool keys from the MCP
        tool_keys = self.get_available_tools()
        
        # Build definitions for each tool
        for tool_name in tool_keys:
            try:
                # Try to get more info from registry if available
                tool_class = None
                # First try with exact name
                tool_class = registry.get_tool_class(tool_name)
                
                # If not found and name is lowercase with underscores, try with CamelCase
                if not tool_class and "_" in tool_name:
                    # Convert snake_case to CamelCase
                    camel_name = "".join(word.capitalize() for word in tool_name.split("_"))
                    tool_class = registry.get_tool_class(camel_name)
                    
                if tool_class:
                    # Get tool info from registry
                    tool_info = registry.get_tool_info(tool_class.__name__)
                    
                    # Try to get parameters directly from class instance if possible
                    tool_instance = None
                    try:
                        tool_instance = tool_class()
                    except Exception as e:
                        logger.debug(f"Could not instantiate tool {tool_name}: {e}")
                    
                    # Get parameters with priority: instance > class > registry > fallback
                    if tool_instance and hasattr(tool_instance, 'parameters') and tool_instance.parameters:
                        parameters = tool_instance.parameters
                    elif hasattr(tool_class, 'parameters') and getattr(tool_class, 'parameters', None):
                        parameters = getattr(tool_class, 'parameters')
                    else:
                        parameters = tool_info.get("parameters", {})
                        
                    # Try to get description with proper priority hierarchy
                    if tool_instance and hasattr(tool_instance, 'short_description') and tool_instance.short_description:
                        # Use short_description attribute if available
                        description = tool_instance.short_description
                    elif hasattr(tool_class, 'short_description') and getattr(tool_class, 'short_description', None):
                        # Use class short_description if available
                        description = getattr(tool_class, 'short_description')
                    elif tool_instance and hasattr(tool_instance, 'description') and tool_instance.description:
                        # If no short description but regular description exists on instance
                        full_desc = tool_instance.description
                        # Extract first line only for concise LLM tool description
                        if isinstance(full_desc, str):
                            description = full_desc.strip().split('\n')[0]
                        else:
                            description = str(full_desc)
                    elif hasattr(tool_class, 'description') and getattr(tool_class, 'description', None):
                        # If no short description but regular description exists on class
                        full_desc = getattr(tool_class, 'description')
                        if isinstance(full_desc, str):
                            description = full_desc.strip().split('\n')[0]
                        else:
                            description = str(full_desc)
                    else:
                        # Fall back to registry info or generic description
                        description = tool_info.get("description", f"Tool: {tool_name}")
                else:
                    # Fallback to minimal definition
                    parameters = {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                    description = f"Tool: {tool_name}"
                    
                # Create a tool definition with the EXACT name from MCP
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool_name,  # Use exact name from MCP
                        "description": description,
                        "parameters": parameters
                    }
                }
                
                # Add the tool definition
                tool_definitions.append(tool_def)
                
            except Exception as e:
                logger.error("Error creating definition for tool %s: %s", tool_name, e)
        
        return tool_definitions

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._failed_count = 0


# Factory function for easy creation
def create_simple_mcp(timeout: float = 30.0, sandbox_config: Optional[SandboxConfig] = None, auto_load_tools: bool = True) -> ToolMCP:
    """Create a SimpleMCP instance with optional sandbox configuration."""
    return ToolMCP(timeout=timeout, sandbox_config=sandbox_config, auto_load_tools=auto_load_tools)
