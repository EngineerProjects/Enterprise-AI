"""
Sandbox-aware tool executor for Enterprise AI.

This module provides a tool executor that can route tool execution between
local execution and sandbox environments based on tool capabilities and configuration.
"""

import asyncio
from typing import Any, Dict, List, Optional, Set, Callable, Union

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.llm.tool_executor import ToolExecutor
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.tool.core.base import ToolCapability, SandboxMode, ExecutionMode
from enterprise_ai.sandbox.client import BaseSandboxClient
from enterprise_ai.config.sandbox import SandboxSettings

logger = get_optimized_logger("sandbox.executor")


class SandboxToolExecutor:
    """
    Enhanced tool executor with sandbox routing capabilities.
    
    Routes tool execution between local and sandbox environments based on
    tool capabilities, configuration, and safety requirements.
    """

    def __init__(
        self,
        tools: Optional[Dict[str, Callable]] = None,
        max_iterations: int = 5,
        execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None,
        # Enhanced execution control
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        approval_callback: Optional[Callable[[ToolCall, str], bool]] = None,
        verbose: bool = False,
        hybrid_danger_threshold: int = 2,
        # Sandbox configuration
        default_sandbox_mode: SandboxMode = SandboxMode.UNIFIED,
        sandbox_settings: Optional[SandboxSettings] = None,
        enable_sandbox_routing: bool = True,
    ):
        """
        Initialize the sandbox-aware tool executor.
        
        Args:
            tools: Dictionary mapping tool names to callable functions
            max_iterations: Maximum number of tool execution rounds
            execution_timeout: Timeout for individual tool execution
            allowed_tools: Set of allowed tool names
            forbidden_tools: Set of forbidden tool names
            execution_mode: Default execution mode for tools
            approval_callback: Function for human approval
            verbose: Whether to enable verbose logging
            hybrid_danger_threshold: Danger level threshold for hybrid mode
            default_sandbox_mode: Default sandbox mode for tools
            sandbox_settings: Configuration for sandbox environments
            enable_sandbox_routing: Whether to enable sandbox routing
        """
        self.tools = tools or {}
        self.max_iterations = max_iterations
        self.execution_timeout = execution_timeout
        self.allowed_tools = allowed_tools
        self.forbidden_tools = forbidden_tools or set()
        
        # Enhanced execution control
        self.execution_mode = execution_mode
        self.approval_callback = approval_callback
        self.verbose = verbose
        self.hybrid_danger_threshold = hybrid_danger_threshold
        
        # Sandbox configuration
        self.default_sandbox_mode = default_sandbox_mode
        self.sandbox_settings = sandbox_settings or SandboxSettings()
        self.enable_sandbox_routing = enable_sandbox_routing
        
        # Initialize local executor for non-sandbox tools
        self._local_executor = ToolExecutor(
            tools=tools,
            max_iterations=1,  # Single execution, we handle iterations
            execution_timeout=execution_timeout,
            allowed_tools=allowed_tools,
            forbidden_tools=forbidden_tools,
            execution_mode=execution_mode,
            approval_callback=approval_callback,
            verbose=verbose,
            hybrid_danger_threshold=hybrid_danger_threshold,
        )
        
        # Sandbox clients for different modes
        self._unified_sandbox: Optional[BaseSandboxClient] = None
        self._individual_sandboxes: Dict[str, BaseSandboxClient] = {}
        
        # Execution tracking
        self._local_executions = 0
        self._sandbox_executions = 0
        self._routing_decisions = []

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool for execution."""
        self.tools[name] = func
        self._local_executor.register_tool(name, func)

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools at once."""
        self.tools.update(tools)
        self._local_executor.register_tools(tools)
        
        if self.verbose:
            logger.info("Registered %s tools", len(tools))

    def _should_use_sandbox(self, tool_call: ToolCall) -> bool:
        """Determine if a tool should be executed in sandbox."""
        if not self.enable_sandbox_routing:
            return False
        
        tool_name = tool_call.function.name
        tool = self.tools.get(tool_name)
        
        if not tool:
            return False
        
        # Check tool configuration
        if hasattr(tool, 'config'):
            tool_config = getattr(tool, 'config', None)
            if tool_config:
                if not tool_config.should_use_sandbox():
                    return False
                
                # Respect explicit sandbox mode setting
                if tool_config.sandbox_mode == SandboxMode.NONE:
                    return False
                elif tool_config.sandbox_mode in (SandboxMode.UNIFIED, SandboxMode.INDIVIDUAL):
                    return True
        
        # Check tool capabilities for dangerous operations
        if hasattr(tool, 'capabilities'):
            dangerous_capabilities = {
                ToolCapability.CODE_EXECUTION,
                ToolCapability.TERMINAL_ACCESS,
                ToolCapability.FILE_ACCESS,
            }
            
            tool_capabilities = getattr(tool, 'capabilities', set())
            if any(cap in tool_capabilities for cap in dangerous_capabilities):
                return True
        
        # Fallback to default mode
        return self.default_sandbox_mode != SandboxMode.NONE

    def _get_sandbox_mode(self, tool_call: ToolCall) -> SandboxMode:
        """Get the sandbox mode for a specific tool."""
        tool_name = tool_call.function.name
        tool = self.tools.get(tool_name)
        
        if tool and hasattr(tool, 'config'):
            tool_config = getattr(tool, 'config', None)
            if tool_config and tool_config.sandbox_mode != SandboxMode.NONE:
                return tool_config.sandbox_mode
        
        return self.default_sandbox_mode

    async def _get_sandbox_client(self, mode: SandboxMode, tool_name: str) -> BaseSandboxClient:
        """Get or create sandbox client based on mode."""
        if mode == SandboxMode.UNIFIED:
            if not self._unified_sandbox:
                self._unified_sandbox = BaseSandboxClient(self.sandbox_settings)
                await self._unified_sandbox.start()
                
                if self.verbose:
                    logger.info("Created unified sandbox")
            
            return self._unified_sandbox
        
        elif mode == SandboxMode.INDIVIDUAL:
            if tool_name not in self._individual_sandboxes:
                self._individual_sandboxes[tool_name] = BaseSandboxClient(self.sandbox_settings)
                await self._individual_sandboxes[tool_name].start()
            
            return self._individual_sandboxes[tool_name]
        
        else:
            raise ValueError(f"Invalid sandbox mode: {mode}")

    async def _execute_in_sandbox(
        self, 
        tool_call: ToolCall, 
        sandbox_client: BaseSandboxClient,
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """Execute a tool call in a sandbox environment."""
        tool_name = tool_call.function.name
        args = tool_call.get_arguments()
        
        try:
            if self.verbose:
                logger.info("Executing %s in sandbox", tool_name)
            
            # For now, we'll serialize the tool call and execute it in the sandbox
            # This is a simplified approach - in practice, you might want to
            # install tools directly in the sandbox environment
            
            # Create execution script for the sandbox
            execution_script = self._create_sandbox_execution_script(tool_call, context)
            
            # Execute in sandbox
            result = await sandbox_client.execute_code(
                code=execution_script,
                timeout=self.execution_timeout
            )
            
            self._sandbox_executions += 1
            
            return ToolResult.create_success(
                result=result,
                tool_name=tool_name,
                tool_call_id=tool_call.id,
                metadata={"execution_environment": "sandbox"}
            )
            
        except Exception as e:
            logger.error("Sandbox execution failed for %s: %s", tool_name, str(e))
            return ToolResult.create_error(
                error=f"Sandbox execution failed: {str(e)}",
                tool_name=tool_name,
                tool_call_id=tool_call.id
            )

    def _create_sandbox_execution_script(
        self, 
        tool_call: ToolCall, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a Python script to execute the tool in sandbox."""
        tool_name = tool_call.function.name
        args = tool_call.get_arguments()
        
        # This is a simplified approach - in practice, you'd want to properly
        # serialize the tool and its dependencies into the sandbox
        script_lines = [
            "import json",
            "import sys",
            "import traceback",
            "",
            "# Tool execution script",
            f"tool_name = '{tool_name}'",
            f"args = {repr(args)}",
            "",
            "try:",
            "    # Import and execute tool",
            f"    # Note: This is a placeholder - actual implementation would",
            f"    # need to properly serialize and execute the tool",
            f"    result = f'Tool {{tool_name}} executed with args {{args}}'",
            "    print(json.dumps({'success': True, 'result': result}))",
            "except Exception as e:",
            "    error_info = {",
            "        'success': False,",
            "        'error': str(e),",
            "        'traceback': traceback.format_exc()",
            "    }",
            "    print(json.dumps(error_info))",
        ]
        
        return "\n".join(script_lines)

    def execute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Execute tool calls with sandbox routing."""
        return asyncio.run(self.aexecute_tool_calls(tool_calls, context))

    async def aexecute_tool_calls(
        self, 
        tool_calls: List[ToolCall],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolResult]:
        """Execute tool calls with sandbox routing (async)."""
        results = []
        
        if self.verbose:
            logger.info("Routing %s tool calls", len(tool_calls))
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            
            # Make routing decision
            use_sandbox = self._should_use_sandbox(tool_call)
            
            self._routing_decisions.append({
                "tool_name": tool_name,
                "use_sandbox": use_sandbox,
                "decision_time": asyncio.get_event_loop().time()
            })
            
            if self.verbose:
                logger.info("Tool %s will execute in %s environment", tool_name, 'sandbox' if use_sandbox else 'local')
            
            if use_sandbox:
                # Execute in sandbox
                sandbox_mode = self._get_sandbox_mode(tool_call)
                sandbox_client = await self._get_sandbox_client(sandbox_mode, tool_name)
                result = await self._execute_in_sandbox(tool_call, sandbox_client, context)
            else:
                # Execute locally
                local_results = await self._local_executor.aexecute_tool_calls([tool_call], context)
                result = local_results[0] if local_results else ToolResult.create_error(
                    error="No result from local execution",
                    tool_name=tool_name,
                    tool_call_id=tool_call.id
                )
                self._local_executions += 1
            
            results.append(result)
        
        return results

    def create_tool_messages(self, tool_results: List[ToolResult]):
        """Create tool messages from results."""
        return self._local_executor.create_tool_messages(tool_results)

    async def cleanup(self) -> None:
        """Clean up sandbox resources."""
        if self.verbose:
            logger.info("Cleaning up sandbox resources")
        
        # Clean up unified sandbox
        if self._unified_sandbox:
            await self._unified_sandbox.stop()
            self._unified_sandbox = None
        
        # Clean up individual sandboxes
        for sandbox in self._individual_sandboxes.values():
            await sandbox.stop()
        self._individual_sandboxes.clear()
        
        if self.verbose:
            logger.info("Sandbox cleanup completed")

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics including sandbox routing info."""
        local_stats = self._local_executor.get_execution_stats()
        
        total_executions = self._local_executions + self._sandbox_executions
        sandbox_ratio = self._sandbox_executions / max(1, total_executions)
        
        return {
            **local_stats,
            "sandbox_executions": self._sandbox_executions,
            "local_executions": self._local_executions,
            "total_executions": total_executions,
            "sandbox_execution_ratio": sandbox_ratio,
            "routing_decisions": len(self._routing_decisions),
            "sandbox_routing_enabled": self.enable_sandbox_routing,
            "default_sandbox_mode": self.default_sandbox_mode,
            "active_unified_sandbox": self._unified_sandbox is not None,
            "active_individual_sandboxes": len(self._individual_sandboxes),
        }

    def get_routing_history(self) -> List[Dict[str, Any]]:
        """Get history of routing decisions."""
        return self._routing_decisions.copy()

    def set_sandbox_mode(self, mode: SandboxMode) -> None:
        """Change the default sandbox mode."""
        old_mode = self.default_sandbox_mode
        self.default_sandbox_mode = mode
        
        if self.verbose:
            logger.info("Default sandbox mode changed from %s to %s", old_mode, mode)

    def enable_sandbox_routing(self, enable: bool = True) -> None:
        """Enable or disable sandbox routing."""
        old_state = self.enable_sandbox_routing
        self.enable_sandbox_routing = enable
        
        if self.verbose:
            logger.info("Sandbox routing %s (was %s)", 'enabled' if enable else 'disabled', 'enabled' if old_state else 'disabled')

    # Delegate methods to local executor for consistency
    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Change the execution mode."""
        self.execution_mode = mode
        self._local_executor.set_execution_mode(mode)

    def set_approval_callback(self, callback: Optional[Callable]) -> None:
        """Set or update the approval callback."""
        self.approval_callback = callback
        self._local_executor.set_approval_callback(callback)

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose logging."""
        old_verbose = self.verbose
        self.verbose = verbose
        self._local_executor.set_verbose(verbose)
        
        if old_verbose != verbose:
            logger.info("Verbose logging %s", 'enabled' if verbose else 'disabled')

    def reset_stats(self) -> None:
        """Reset execution statistics."""
        self._local_executor.reset_stats()
        self._local_executions = 0
        self._sandbox_executions = 0
        self._routing_decisions.clear()
        
        if self.verbose:
            logger.info("Sandbox executor statistics reset")