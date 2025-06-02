"""
Auto tool execution for Ollama provider.

This module handles automatic execution of tool calls made by the model,
enabling autonomous reasoning and action loops.
"""

import asyncio
import inspect
import time
import json
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
        self._failed_executions = 0
        
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
                logger.error(f"Async tool execution failed for {tool_call.function.name}: {str(result)}")
                error_result = self._create_error_result(
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
                self._failed_executions += 1
                return self._create_error_result(
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
            raw_result = self._execute_with_timeout(tool_func, args)
            
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=True)
            
            # Process the result safely and create ToolResult directly
            return self._create_success_result_safe(
                tool_call_id=tool_call.id,
                name=tool_name,
                raw_result=raw_result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=False)
            
            error_msg = self._format_error_message(e)
            logger.error(f"Tool execution failed for {tool_name}: {error_msg}")
            
            return self._create_error_result(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=error_msg,
                execution_time=execution_time
            )

    def _create_success_result_safe(
        self,
        tool_call_id: str,
        name: str,
        raw_result: Any,
        execution_time: float
    ) -> ToolResult:
        """
        Safely create a success ToolResult by completely avoiding field conflicts.
        
        This method creates the ToolResult directly without using the class methods
        to avoid any potential Pydantic validation issues.
        """
        try:
            # Process the result to be completely safe
            safe_result = self._make_result_completely_safe(raw_result)
            
            # Create ToolResult directly using the constructor
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                result=safe_result,
                success=True,
                error=None,
                execution_time=execution_time,
                metadata={}
            )
        except Exception as e:
            # If even the direct creation fails, create a minimal error result
            logger.error(f"Failed to create success result for {name}: {str(e)}")
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                result=f"Tool executed but result processing failed: {str(e)}",
                success=False,
                error=f"Result processing error: {str(e)}",
                execution_time=execution_time,
                metadata={}
            )

    def _create_error_result(
        self,
        tool_call_id: str,
        name: str,
        error: str,
        execution_time: Optional[float] = None
    ) -> ToolResult:
        """Create an error ToolResult safely."""
        return ToolResult(
            tool_call_id=tool_call_id,
            name=name,
            result="",
            success=False,
            error=error,
            execution_time=execution_time,
            metadata={}
        )

    def _make_result_completely_safe(self, result: Any) -> Any:
        """
        Make the result completely safe by removing any potential conflicts.
        
        This method ensures that no field in the result can conflict with
        ToolResult's fields by wrapping everything in a safe structure.
        """
        try:
            if isinstance(result, dict):
                # Always wrap dictionary results to avoid any field conflicts
                return {"tool_output": result}
            elif isinstance(result, (str, int, float, bool)):
                return result
            elif isinstance(result, list):
                return result
            else:
                # Convert other types to string
                return str(result)
        except Exception as e:
            logger.warning(f"Error making result safe: {e}")
            return f"Result: {str(result)}"

    def _format_error_message(self, error: Exception) -> str:
        """Format error message safely."""
        try:
            error_str = str(error)
            # Handle cases where the error message might be empty or problematic
            if not error_str or error_str.isspace():
                return f"Unknown error of type {type(error).__name__}"
            return error_str
        except Exception:
            return f"Error formatting exception of type {type(error).__name__}"

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
                self._failed_executions += 1
                return self._create_error_result(
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
                raw_result = await asyncio.wait_for(
                    tool_func(**args), 
                    timeout=self.execution_timeout
                )
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                raw_result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_func(**args)),
                    timeout=self.execution_timeout
                )
            
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=True)
            
            return self._create_success_result_safe(
                tool_call_id=tool_call.id,
                name=tool_name,
                raw_result=raw_result,
                execution_time=execution_time
            )
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=False)
            return self._create_error_result(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=f"Tool execution timed out after {self.execution_timeout}s",
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=False)
            
            error_msg = self._format_error_message(e)
            logger.error(f"Async tool execution failed for {tool_name}: {error_msg}")
            
            return self._create_error_result(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=error_msg,
                execution_time=execution_time
            )

    def _execute_with_timeout(self, func: Callable, args: Dict[str, Any]) -> Any:
        """Execute function with timeout (sync version)."""
        try:
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Tool execution timed out after {self.execution_timeout}s")
            
            # Set up timeout for sync execution
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(self.execution_timeout))
            
            try:
                result = func(**args)
                return result
            finally:
                signal.alarm(0)  # Cancel timeout
                signal.signal(signal.SIGALRM, old_handler)
                
        except ImportError:
            # Fallback for systems without signal support (e.g., Windows)
            return func(**args)

    def _track_execution(self, execution_time: float, success: bool = True) -> None:
        """Track execution metrics."""
        self._execution_count += 1
        self._total_execution_time += execution_time
        if not success:
            self._failed_executions += 1

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        avg_time = (
            self._total_execution_time / self._execution_count 
            if self._execution_count > 0 else 0
        )
        
        success_rate = (
            (self._execution_count - self._failed_executions) / self._execution_count
            if self._execution_count > 0 else 0
        )
        
        return {
            "total_executions": self._execution_count,
            "successful_executions": self._execution_count - self._failed_executions,
            "failed_executions": self._failed_executions,
            "success_rate": success_rate,
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
            try:
                content = self._safe_result_to_content(result)
                
                tool_message = Message.tool_message(
                    content=content,
                    name=result.name,
                    tool_call_id=result.tool_call_id,
                    metadata={
                        "execution_success": result.success,
                        "execution_time": result.execution_time,
                        "tool_metadata": result.metadata or {}
                    }
                )
                messages.append(tool_message)
                
            except Exception as e:
                logger.error(f"Failed to create tool message for {result.name}: {e}")
                # Create a fallback error message
                error_message = Message.tool_message(
                    content=f"Error creating tool message: {str(e)}",
                    name=result.name,
                    tool_call_id=result.tool_call_id,
                    metadata={
                        "execution_success": False,
                        "error": "Message creation failed"
                    }
                )
                messages.append(error_message)
        
        return messages

    def _safe_result_to_content(self, result: ToolResult) -> str:
        """Safely convert tool result to message content."""
        try:
            if not result.success and result.error:
                return f"Error: {result.error}"
            
            if isinstance(result.result, str):
                return result.result
            elif isinstance(result.result, dict):
                # Handle our wrapped tool_output format
                if "tool_output" in result.result and len(result.result) == 1:
                    return json.dumps(result.result["tool_output"], indent=2, default=str)
                else:
                    return json.dumps(result.result, indent=2, default=str)
            elif isinstance(result.result, list):
                return json.dumps(result.result, indent=2, default=str)
            else:
                return str(result.result)
                
        except Exception as e:
            logger.warning(f"Error converting result to content: {e}")
            return f"Tool executed but result formatting failed: {str(e)}"

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._failed_executions = 0
        logger.debug("Tool execution statistics reset")