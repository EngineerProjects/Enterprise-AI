"""
Auto tool execution for Ollama provider.

This module handles automatic execution of tool calls made by the model,
enabling autonomous reasoning and action loops.
"""

import asyncio
import inspect
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult, Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("llm.ollama.executor")


class ToolExecutor:
    """
    Handles automatic execution of tool calls for autonomous reasoning.
    
    Supports both sync and async tool execution with comprehensive error handling.
    """

    def __init__(
        self,
        tools: Optional[Dict[str, Callable]] = None,
        max_iterations: int = 5,
        execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None
    ):
        """
        Initialize the tool executor.
        
        Args:
            tools: Dictionary mapping tool names to callable functions
            max_iterations: Maximum number of tool execution rounds
            execution_timeout: Timeout for individual tool execution
            allowed_tools: Set of allowed tool names (None = all allowed)
            forbidden_tools: Set of forbidden tool names
        """
        self.tools = tools or {}
        self.max_iterations = max_iterations
        self.execution_timeout = execution_timeout
        self.allowed_tools = allowed_tools
        self.forbidden_tools = forbidden_tools or set()
        
        # Execution tracking
        self._execution_count = 0
        self._total_execution_time = 0.0
        
        logger.info(f"Initialized tool executor with {len(self.tools)} tools")

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function for execution."""
        self.tools[name] = func
        logger.debug(f"Registered tool: {name}")

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools at once."""
        self.tools.update(tools)
        logger.debug(f"Registered {len(tools)} tools")

    def can_execute_tool(self, tool_name: str) -> bool:
        """Check if a tool can be executed based on policies."""
        # Check if tool exists
        if tool_name not in self.tools:
            return False
        
        # Check forbidden list
        if tool_name in self.forbidden_tools:
            return False
        
        # Check allowed list (if specified)
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            return False
        
        return True

    def execute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Execute a list of tool calls and return results.
        
        Args:
            tool_calls: List of tool calls to execute
            context: Optional context to pass to tools
            
        Returns:
            List of tool execution results
        """
        results = []
        
        for tool_call in tool_calls:
            result = self._execute_single_tool(tool_call, context)
            results.append(result)
        
        return results

    async def aexecute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Execute tool calls asynchronously.
        
        Args:
            tool_calls: List of tool calls to execute
            context: Optional context to pass to tools
            
        Returns:
            List of tool execution results
        """
        tasks = []
        
        for tool_call in tool_calls:
            task = self._aexecute_single_tool(tool_call, context)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tool_call = tool_calls[i]
                error_result = ToolResult.error(
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                    error=f"Async execution failed: {str(result)}"
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        return final_results

    def _execute_single_tool(
        self, 
        tool_call: ToolCall, 
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a single tool call with comprehensive error handling."""
        start_time = time.time()
        tool_name = tool_call.function.name
        
        try:
            # Check execution permissions
            if not self.can_execute_tool(tool_name):
                return ToolResult.error(
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=f"Tool '{tool_name}' execution not allowed"
                )
            
            # Get the tool function
            tool_func = self.tools[tool_name]
            
            # Prepare arguments
            args = tool_call.get_arguments()
            if context:
                args.update(context)
            
            # Execute with timeout
            result = self._execute_with_timeout(tool_func, args)
            
            execution_time = time.time() - start_time
            self._track_execution(execution_time)
            
            return ToolResult.success(
                tool_call_id=tool_call.id,
                name=tool_name,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            
            return ToolResult.error(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=str(e),
                execution_time=execution_time
            )

    async def _aexecute_single_tool(
        self, 
        tool_call: ToolCall, 
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a single tool call asynchronously."""
        start_time = time.time()
        tool_name = tool_call.function.name
        
        try:
            if not self.can_execute_tool(tool_name):
                return ToolResult.error(
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=f"Tool '{tool_name}' execution not allowed"
                )
            
            tool_func = self.tools[tool_name]
            args = tool_call.get_arguments()
            if context:
                args.update(context)
            
            # Handle both sync and async functions
            if inspect.iscoroutinefunction(tool_func):
                result = await asyncio.wait_for(
                    tool_func(**args), 
                    timeout=self.execution_timeout
                )
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_func(**args)),
                    timeout=self.execution_timeout
                )
            
            execution_time = time.time() - start_time
            self._track_execution(execution_time)
            
            return ToolResult.success(
                tool_call_id=tool_call.id,
                name=tool_name,
                result=result,
                execution_time=execution_time
            )
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            return ToolResult.error(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=f"Tool execution timed out after {self.execution_timeout}s",
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Async tool execution failed for {tool_name}: {e}")
            
            return ToolResult.error(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=str(e),
                execution_time=execution_time
            )

    def _execute_with_timeout(self, func: Callable, args: Dict[str, Any]) -> Any:
        """Execute function with timeout (sync version)."""
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Tool execution timed out after {self.execution_timeout}s")
        
        # Set up timeout for sync execution
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(int(self.execution_timeout))
        
        try:
            result = func(**args)
        finally:
            signal.alarm(0)  # Cancel timeout
            signal.signal(signal.SIGALRM, old_handler)
        
        return result

    def _track_execution(self, execution_time: float) -> None:
        """Track execution metrics."""
        self._execution_count += 1
        self._total_execution_time += execution_time

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        avg_time = (
            self._total_execution_time / self._execution_count 
            if self._execution_count > 0 else 0
        )
        
        return {
            "total_executions": self._execution_count,
            "total_execution_time": self._total_execution_time,
            "average_execution_time": avg_time,
            "registered_tools": list(self.tools.keys()),
            "allowed_tools": list(self.allowed_tools) if self.allowed_tools else None,
            "forbidden_tools": list(self.forbidden_tools),
        }

    def create_tool_messages(self, tool_results: List[ToolResult]) -> List[MessageProtocol]:
        """Convert tool results to tool messages for conversation continuation."""
        messages = []
        
        for result in tool_results:
            tool_message = Message.tool_message(
                content=result.to_message_content(),
                name=result.name,
                tool_call_id=result.tool_call_id,
                metadata={
                    "success": result.success,
                    "execution_time": result.execution_time,
                    "tool_metadata": result.metadata
                }
            )
            messages.append(tool_message)
        
        return messages