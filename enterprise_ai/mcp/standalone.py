"""
Standalone SimpleMCP - completely independent of existing tool registry.

For testing and manual tool registration.
"""

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, List, Optional

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.mcp.sandbox_config import SandboxConfig, DEFAULT_SANDBOX_CONFIG

logger = get_optimized_logger("new_mcp.standalone")


class StandaloneMCP:
    """
    Standalone MCP - manual tool registration only.
    
    Completely independent of the existing tool registry to avoid import issues.
    """

    def __init__(self, timeout: float = 30.0, sandbox_config: Optional[SandboxConfig] = None):
        """
        Initialize StandaloneMCP.
        
        Args:
            timeout: Default timeout for tool execution
            sandbox_config: Optional sandbox configuration
        """
        self.timeout = timeout
        self.sandbox_config = sandbox_config or DEFAULT_SANDBOX_CONFIG
        self._tools: Dict[str, Callable] = {}
        self._execution_count = 0
        self._failed_count = 0
    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function directly."""
        self._tools[name] = func
    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools at once."""
        self._tools.update(tools)
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self._tools.keys())

    async def execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Execute a list of tool calls."""
        if not tool_calls:
            return []

        results = []
        
        for tool_call in tool_calls:
            result = await self._execute_single_tool(tool_call)
            results.append(result)
            
        return results

    async def _execute_single_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call with error handling."""
        start_time = time.time()
        tool_name = tool_call.function.name
        
        try:
            self._execution_count += 1
            
            # Check if tool exists
            if tool_name not in self._tools:
                self._failed_count += 1
                return self._create_error_result(
                    tool_call.id, tool_name, f"Tool '{tool_name}' not found"
                )
            
            # Get tool function and arguments
            tool_func = self._tools[tool_name]
            args = tool_call.get_arguments()
            
            # Check if should use sandbox
            if self.sandbox_config.should_use_sandbox(tool_name):
                return await self._execute_in_sandbox(tool_call, tool_func, args, start_time)
            else:
                return await self._execute_directly(tool_call, tool_func, args, start_time)
                
        except Exception as e:
            self._failed_count += 1
            execution_time = time.time() - start_time
            logger.error("Tool execution failed for %s: %s", tool_name, e)
            
            return self._create_error_result(
                tool_call.id, tool_name, str(e), execution_time
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
        success_count = self._execution_count - self._failed_count
        success_rate = success_count / self._execution_count if self._execution_count > 0 else 0
        
        return {
            "total_executions": self._execution_count,
            "successful_executions": success_count,
            "failed_executions": self._failed_count,
            "success_rate": success_rate,
            "available_tools": len(self._tools),
            "tool_names": list(self._tools.keys())
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._failed_count = 0
