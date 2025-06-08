"""
Enhanced tool execution engine for Enterprise AI MCP with comprehensive control.

This module handles tool execution with approval mechanisms, sandbox routing,
session management, and agent communication support.
"""

import asyncio
import inspect
import time
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.schema import ToolCall, ToolResult, Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.base import ExecutionMode, ToolCapability
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client
from enterprise_ai.config import get_config

from enterprise_ai.mcp.config import MCPConfig
from enterprise_ai.mcp.session_manager import SessionManager

logger = get_optimized_logger("mcp.executor")


class ToolExecutor:
    """
    Enhanced tool executor with MCP integration and comprehensive control.
    
    Supports sync/async execution, approval workflows, sandbox routing,
    session management, and agent communication.
    """

    def __init__(
        self,
        config: Optional[MCPConfig] = None,
        session_manager: Optional[SessionManager] = None,
        tools: Optional[Dict[str, Callable]] = None,
        approval_callback: Optional[Callable] = None,
    ):
        """
        Initialize the tool executor.
        
        Args:
            config: MCP configuration
            session_manager: Session manager instance
            tools: Dictionary mapping tool names to callable functions
            approval_callback: Async function to request approval for tool execution
        """
        self.config = config or MCPConfig.from_config()
        self.session_manager = session_manager
        self.tools = tools or {}
        self._approval_callback = approval_callback
        
        # Initialize sandbox client
        self.sandbox_client = None
        if self.config.sandbox_enabled:
            try:
                self.sandbox_client = create_sandbox_client()
            except Exception as e:
                logger.warning("Failed to initialize sandbox client: %s", e)
        
        # Execution tracking
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._failed_executions = 0
        self._approved_executions = 0
        self._denied_executions = 0
        self._sandbox_executions = 0
        
        logger.info("ToolExecutor initialized with %d tools | Mode: %s | Sandbox: %s", 
                   len(self.tools), self.config.execution_mode, 
                   "enabled" if self.sandbox_client else "disabled")

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function for execution."""
        self.tools[name] = func
        if self.config.verbose_logging:
            logger.info("Registered tool: %s", name)

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools at once."""
        self.tools.update(tools)
        if self.config.verbose_logging:
            logger.info("Registered %d tools: %s", len(tools), list(tools.keys()))

    def set_approval_callback(self, callback: Optional[Callable]) -> None:
        """Set or update the approval callback."""
        self._approval_callback = callback
        if callback and self.config.verbose_logging:
            logger.info("Approval callback updated")

    def can_execute_tool(self, tool_name: str) -> bool:
        """Check if a tool can be executed based on policies."""
        if tool_name not in self.tools:
            return False
        
        return self.config.is_tool_allowed(tool_name)

    def should_use_sandbox(self, tool_name: str) -> bool:
        """Determine if a tool should be executed in sandbox."""
        if not self.sandbox_client or not self.config.sandbox_auto_routing:
            return False
        
        tool = self.tools.get(tool_name)
        if not tool:
            return False
        
        # Check if tool has dangerous capabilities
        if hasattr(tool, 'capabilities'):
            dangerous_capabilities = {
                ToolCapability.CODE_EXECUTION,
                ToolCapability.TERMINAL_ACCESS,
                ToolCapability.SHELL_ACCESS,
                ToolCapability.FILE_ACCESS
            }
            tool_capabilities = getattr(tool, 'capabilities', set())
            return any(cap in dangerous_capabilities for cap in tool_capabilities)
        
        # Fallback: check tool name for dangerous patterns
        dangerous_patterns = ['execute', 'bash', 'shell', 'terminal', 'python', 'code']
        return any(pattern in tool_name.lower() for pattern in dangerous_patterns)

    def _should_request_approval(self, tool_call: ToolCall) -> bool:
        """Determine if approval should be requested for a tool call."""
        tool_name = tool_call.function.name
        
        # If we have an approval callback, check config
        if hasattr(self, '_approval_callback') and self._approval_callback:
            # Check tool-specific danger level
            tool = self.tools.get(tool_name)
            danger_level = 0
            
            if hasattr(tool, 'config') and hasattr(tool.config, 'danger_level'):
                danger_level = tool.config.danger_level
            
            return self.config.should_require_approval(tool_name, danger_level)
        
        # No callback available - don't require approval
        return False

    async def _request_approval(self, tool_call: ToolCall) -> bool:
        """Request human approval for tool execution."""
        if hasattr(self, '_approval_callback') and self._approval_callback:
            try:
                # Use the agent's approval callback
                if asyncio.iscoroutinefunction(self._approval_callback):
                    return await self._approval_callback(tool_call)
                else:
                    # Handle sync callback
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, self._approval_callback, tool_call)
            except Exception as e:
                logger.error("Approval callback failed: %s", e)
                return False
        
        # Fallback: console-based approval for testing
        tool_name = tool_call.function.name
        args = tool_call.get_arguments()
        
        print(f"\n🔒 TOOL EXECUTION APPROVAL REQUIRED")
        print(f"Tool: {tool_name}")
        print(f"Arguments: {json.dumps(args, indent=2)}")
        
        # Auto-approve for testing when no callback is set
        logger.info("Tool approval requested for %s (auto-approved - no callback)", tool_name)
        self._approved_executions += 1
        return True

    async def execute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """
        Execute a list of tool calls and return results.
        
        Args:
            tool_calls: List of tool calls to execute
            session_id: Optional session ID for tracking
            context: Optional context to pass to tools
            
        Returns:
            List of tool execution results
        """
        results = []
        
        if self.config.verbose_logging:
            logger.info("Executing %s tool calls", len(tool_calls))
        
        for i, tool_call in enumerate(tool_calls):
            if self.config.verbose_logging:
                logger.info("Processing tool call %s/%s: %s", i+1, len(tool_calls), tool_call.function.name)
            
            result = await self._execute_single_tool(tool_call, session_id, context)
            results.append(result)
            
            # Update session if provided
            if session_id and self.session_manager:
                self.session_manager.add_tool_execution(session_id, tool_call, result)
        
        return results

    async def _execute_single_tool(
        self, 
        tool_call: ToolCall, 
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a single tool call with comprehensive error handling."""
        start_time = time.time()
        tool_name = tool_call.function.name
        
        if self.config.verbose_logging:
            logger.info("Starting execution of tool: %s", tool_name)
        
        try:
            # Check execution permissions
            if not self.can_execute_tool(tool_name):
                self._failed_executions += 1
                error_msg = f"Tool '{tool_name}' execution not allowed"
                logger.warning(error_msg)
                return self._create_error_result(
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
            
            # Check if approval is required - FIXED: Make it async
            if self._should_request_approval(tool_call):
                approved = await self._request_approval(tool_call)
                if not approved:
                    self._denied_executions += 1
                    error_msg = f"Tool '{tool_name}' execution denied by user"
                    logger.info(error_msg)
                    return self._create_error_result(
                        tool_call_id=tool_call.id,
                        name=tool_name,
                        error=error_msg
                    )
            
            # Determine execution environment
            use_sandbox = self.should_use_sandbox(tool_name)
            
            if use_sandbox and self.sandbox_client:
                result = await self._execute_in_sandbox(tool_call, context)
                self._sandbox_executions += 1
            else:
                result = await self._execute_directly(tool_call, context)
            
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=True)
            
            if self.config.verbose_logging:
                logger.info("Tool %s completed successfully in %.3fs", tool_name, execution_time)
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=False)
            
            error_msg = str(e)
            logger.error("Tool execution failed for %s: %s", tool_name, error_msg)
            
            return self._create_error_result(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=error_msg,
                execution_time=execution_time
            )

    async def _execute_directly(
        self, 
        tool_call: ToolCall, 
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute tool directly in the current environment."""
        tool_name = tool_call.function.name
        tool_func = self.tools[tool_name]
        
        # Prepare arguments
        args = tool_call.get_arguments()
        if context:
            args.update(context)
        
        # Execute with timeout
        try:
            if inspect.iscoroutinefunction(tool_func):
                raw_result = await asyncio.wait_for(
                    tool_func(**args), 
                    timeout=self.config.tool_execution_timeout
                )
            else:
                # Run sync function in thread pool
                loop = asyncio.get_event_loop()
                raw_result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool_func(**args)),
                    timeout=self.config.tool_execution_timeout
                )
            
            return self._create_success_result(
                tool_call_id=tool_call.id,
                name=tool_name,
                raw_result=raw_result
            )
            
        except asyncio.TimeoutError:
            raise Exception(f"Tool execution timed out after {self.config.tool_execution_timeout}s")

    async def _execute_in_sandbox(
        self, 
        tool_call: ToolCall, 
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute tool in sandbox environment."""
        if not self.sandbox_client:
            raise Exception("Sandbox client not available")
        
        tool_name = tool_call.function.name
        args = tool_call.get_arguments()
        if context:
            args.update(context)
        
        if self.config.verbose_logging:
            logger.info("Executing %s in sandbox", tool_name)
        
        # Execute through sandbox client
        sandbox_result = await self.sandbox_client.execute_tool(
            tool_name=tool_name,
            arguments=args,
            timeout=self.config.tool_execution_timeout
        )
        
        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_name,
            result=sandbox_result.get("result", ""),
            success=sandbox_result.get("success", False),
            error=sandbox_result.get("error"),
            execution_time=sandbox_result.get("execution_time"),
            metadata={"executed_in_sandbox": True}
        )

    def _create_success_result(
        self,
        tool_call_id: str,
        name: str,
        raw_result: Any
    ) -> ToolResult:
        """Create a success ToolResult from raw result."""
        try:
            # Process the result safely
            safe_result = self._make_result_safe(raw_result)
            
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                result=safe_result,
                success=True,
                error=None,
                metadata={}
            )
        except Exception as e:
            logger.error("Failed to create success result for %s: %s", name, str(e))
            return ToolResult(
                tool_call_id=tool_call_id,
                name=name,
                result=f"Tool executed but result processing failed: {str(e)}",
                success=False,
                error=f"Result processing error: {str(e)}",
                metadata={}
            )

    def _create_error_result(
        self,
        tool_call_id: str,
        name: str,
        error: str,
        execution_time: Optional[float] = None
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

    def _make_result_safe(self, result: Any) -> Any:
        """Make the result safe for serialization."""
        try:
            if isinstance(result, dict):
                # Wrap to avoid field conflicts
                return {"tool_output": result}
            elif isinstance(result, (str, int, float, bool)):
                return result
            elif isinstance(result, list):
                return result
            else:
                return str(result)
        except Exception as e:
            logger.warning("Error making result safe: %s", e)
            return f"Result: {str(result)}"

    def _track_execution(self, execution_time: float, success: bool = True) -> None:
        """Track execution metrics."""
        self._execution_count += 1
        self._total_execution_time += execution_time
        if not success:
            self._failed_executions += 1

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
                
                if self.config.verbose_logging:
                    logger.info("Created tool message for %s: success=%s", result.name, result.success)
                
            except Exception as e:
                logger.error("Failed to create tool message for %s: %s", result.name, e)
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
                # Handle wrapped tool_output format
                if "tool_output" in result.result and len(result.result) == 1:
                    return json.dumps(result.result["tool_output"], indent=2, default=str)
                else:
                    return json.dumps(result.result, indent=2, default=str)
            elif isinstance(result.result, list):
                return json.dumps(result.result, indent=2, default=str)
            else:
                return str(result.result)
                
        except Exception as e:
            logger.warning("Error converting result to content: %s", e)
            return f"Tool executed but result formatting failed: {str(e)}"

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
            "approved_executions": self._approved_executions,
            "denied_executions": self._denied_executions,
            "sandbox_executions": self._sandbox_executions,
            "success_rate": success_rate,
            "total_execution_time": self._total_execution_time,
            "average_execution_time": avg_time,
            "registered_tools": list(self.tools.keys()),
            "execution_mode": self.config.execution_mode,
            "sandbox_enabled": self.sandbox_client is not None,
        }

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._failed_executions = 0
        self._approved_executions = 0
        self._denied_executions = 0
        self._sandbox_executions = 0
        
        if self.config.verbose_logging:
            logger.info("Tool execution statistics reset")