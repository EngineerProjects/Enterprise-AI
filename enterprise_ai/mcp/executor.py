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
from enterprise_ai.tool.simple_loader import get_all_tools, get_tool_by_name
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

    def __init__(
        self, 
        timeout: float = 30.0, 
        sandbox_config: Optional[SandboxConfig] = None, 
        tools: Optional[List[str]] = None
    ):
        """
        Initialize ToolMCP with simplified configuration.
        
        Args:
            timeout: Default timeout for tool execution
            sandbox_config: Optional sandbox configuration
            tools: Specific list of tools to load (loads all if None)
        """
        self.timeout = timeout
        self.sandbox_config = sandbox_config or DEFAULT_SANDBOX_CONFIG
        self._execution_count = 0
        self._failed_count = 0
        
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
        
        # Load tools using simplified system
        if tools:
            self._tools = self._load_specific_tools(tools)
        else:
            self._tools = self._load_all_tools()
            
        logger.info(f"ToolMCP initialized with {len(self._tools)} tools")

    def _load_all_tools(self) -> Dict[str, Callable]:
        """Load all available tools using simplified loader."""
        tools = {}
        
        try:
            tool_classes = get_all_tools()
            
            for tool_name, tool_class in tool_classes.items():
                try:
                    tool_instance = tool_class()
                    if hasattr(tool_instance, 'execute'):
                        tools[tool_name] = tool_instance.execute
                        logger.debug(f"Loaded tool: {tool_name}")
                except Exception as e:
                    logger.warning(f"Failed to load tool {tool_name}: {e}")
            
            logger.info(f"Loaded {len(tools)} tools via simple loader")
        except Exception as e:
            logger.error(f"Failed to load tools: {e}")
            
        return tools
    
    def _load_specific_tools(self, tool_names: List[str]) -> Dict[str, Callable]:
        """Load specific tools using simplified loader."""
        tools = {}
        
        for tool_name in tool_names:
            try:
                tool_class = get_tool_by_name(tool_name)
                tool_instance = tool_class()
                if hasattr(tool_instance, 'execute'):
                    tools[tool_name] = tool_instance.execute
                    logger.debug(f"Loaded specific tool: {tool_name}")
            except Exception as e:
                logger.warning(f"Failed to load tool {tool_name}: {e}")
        
        logger.info(f"Loaded {len(tools)} specific tools")
        return tools

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
        Get tool definitions using simplified approach.
        
        Returns:
            List of tool definitions in the format expected by LLM providers
        """
        definitions = []
        
        # Get available tool classes for introspection
        try:
            tool_classes = get_all_tools()
        except Exception as e:
            logger.error(f"Failed to get tool classes: {e}")
            return definitions
        
        # Build definitions for each available tool
        for tool_name in self.get_available_tools():
            try:
                # Find the tool class by name
                tool_class = None
                for class_name, cls in tool_classes.items():
                    if class_name == tool_name:
                        tool_class = cls
                        break
                
                if tool_class:
                    # Create instance for introspection
                    tool_instance = tool_class()
                    
                    # Get description (prefer short_description)
                    description = getattr(tool_instance, 'short_description', None)
                    if not description:
                        description = getattr(tool_instance, 'description', f"Tool: {tool_name}")
                        if isinstance(description, str) and '\n' in description:
                            description = description.split('\n')[0]  # First line only
                    
                    # Get parameters
                    parameters = getattr(tool_instance, 'parameters', {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                    
                    # Create tool definition
                    definition = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": description,
                            "parameters": parameters
                        }
                    }
                    
                    definitions.append(definition)
                else:
                    logger.warning(f"Could not find tool class for {tool_name}")
                    
            except Exception as e:
                logger.error(f"Error creating definition for tool {tool_name}: {e}")
        
        return definitions

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._failed_count = 0


# Factory function for easy creation
def create_simple_mcp(
    timeout: float = 30.0, 
    sandbox_config: Optional[SandboxConfig] = None, 
    tools: Optional[List[str]] = None
) -> ToolMCP:
    """Create a ToolMCP instance with simplified configuration."""
    return ToolMCP(timeout=timeout, sandbox_config=sandbox_config, tools=tools)
