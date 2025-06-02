"""
Enhanced tool execution for Enterprise AI with approval mechanisms and verbose logging.

This module handles automatic execution of tool calls made by the model,
enabling autonomous reasoning and action loops with human oversight capabilities.
"""

import asyncio
import inspect
import time
import json
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult, Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.base import ExecutionMode, ToolCapability

logger = get_logger("llm.tool_executor")


class ToolExecutor:
    """
    Enhanced tool executor with approval mechanisms and verbose logging.
    
    Supports both sync and async tool execution with comprehensive error handling,
    human approval workflows, and detailed execution logging.
    """

    def __init__(
        self,
        tools: Optional[Dict[str, Callable]] = None,
        max_iterations: int = 5,
        execution_timeout: float = 30.0,
        allowed_tools: Optional[Set[str]] = None,
        forbidden_tools: Optional[Set[str]] = None,
        # Enhanced options
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        approval_callback: Optional[Callable[[ToolCall, str], bool]] = None,
        verbose: bool = False,
        hybrid_danger_threshold: int = 2,
    ):
        """
        Initialize the tool executor with enhanced capabilities.
        
        Args:
            tools: Dictionary mapping tool names to callable functions
            max_iterations: Maximum number of tool execution rounds
            execution_timeout: Timeout for individual tool execution
            allowed_tools: Set of allowed tool names (None = all allowed)
            forbidden_tools: Set of forbidden tool names
            execution_mode: Default execution mode for tools
            approval_callback: Function to call for human approval
            verbose: Whether to log detailed execution information
            hybrid_danger_threshold: Danger level threshold for hybrid mode
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
        
        # Execution tracking
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._failed_executions = 0
        self._approved_executions = 0
        self._denied_executions = 0
        
        logger.info(f"Initialized tool executor with {len(self.tools)} tools | Mode: {execution_mode} | Verbose: {verbose}")

    def register_tool(self, name: str, func: Callable) -> None:
        """Register a tool function for execution."""
        self.tools[name] = func
        if self.verbose:
            logger.info(f"Registered tool: {name}")
        else:
            logger.debug(f"Registered tool: {name}")

    def register_tools(self, tools: Dict[str, Callable]) -> None:
        """Register multiple tools at once."""
        self.tools.update(tools)
        if self.verbose:
            logger.info(f"Registered {len(tools)} tools: {list(tools.keys())}")
        else:
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

    def _should_request_approval(self, tool_call: ToolCall) -> bool:
        """Determine if approval should be requested for a tool call."""
        tool_name = tool_call.function.name
        
        # Check if we have the tool object for more detailed analysis
        if hasattr(self.tools.get(tool_name), 'config'):
            tool = self.tools[tool_name]
            tool_config = getattr(tool, 'config', None)
            if tool_config:
                return tool_config.should_require_approval(self.hybrid_danger_threshold)
        
        # Fallback based on execution mode
        if self.execution_mode == ExecutionMode.MANUAL:
            return True
        elif self.execution_mode == ExecutionMode.AUTO:
            return False
        elif self.execution_mode == ExecutionMode.HYBRID:
            # Simple heuristic for dangerous tools if no tool config available
            dangerous_tools = {'python_execute', 'bash_execute', 'file_write', 'terminal_access'}
            return tool_name in dangerous_tools
        else:  # DISABLED
            return False

    def _request_approval(self, tool_call: ToolCall) -> bool:
        """Request human approval for tool execution with enhanced UI."""
        if not self.approval_callback:
            logger.warning(f"No approval callback set, defaulting to deny for {tool_call.function.name}")
            return False
        
        # Terminal colors for approval UI
        class Colors:
            RESET = '\033[0m'
            BOLD = '\033[1m'
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            MAGENTA = '\033[95m'
            CYAN = '\033[96m'
            WHITE = '\033[97m'
            BG_YELLOW = '\033[43m'
            BG_RED = '\033[41m'
        
        try:
            # Get approval message
            approval_message = self._get_approval_message(tool_call)
            
            if self.verbose:
                print(f"\n{Colors.BG_YELLOW}{Colors.BLACK} ⚠️  APPROVAL REQUIRED ⚠️ {Colors.RESET}")
                print(f"{Colors.YELLOW}{'─'*60}{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.YELLOW}Tool:{Colors.RESET} {Colors.WHITE}{tool_call.function.name}{Colors.RESET}")
                print(f"{Colors.BOLD}{Colors.YELLOW}Arguments:{Colors.RESET}")
                
                args = tool_call.get_arguments()
                for key, value in args.items():
                    print(f"  {Colors.CYAN}{key}:{Colors.RESET} {Colors.WHITE}{str(value)[:100]}{Colors.RESET}")
                
                print(f"{Colors.YELLOW}{'─'*60}{Colors.RESET}")
            
            approved = self.approval_callback(tool_call, approval_message)
            
            if approved:
                self._approved_executions += 1
                if self.verbose:
                    print(f"{Colors.GREEN}✅ APPROVED{Colors.RESET} - Tool execution will proceed")
            else:
                self._denied_executions += 1
                if self.verbose:
                    print(f"{Colors.RED}❌ DENIED{Colors.RESET} - Tool execution cancelled")
            
            return approved
            
        except Exception as e:
            logger.error(f"Error in approval callback: {e}")
            if self.verbose:
                print(f"{Colors.RED}❌ APPROVAL ERROR{Colors.RESET} - Defaulting to deny: {str(e)}")
            return False

    def _get_approval_message(self, tool_call: ToolCall) -> str:
        """Generate approval message for a tool call."""
        tool_name = tool_call.function.name
        args = tool_call.get_arguments()
        
        # Try to get detailed message from tool if available
        if hasattr(self.tools.get(tool_name), 'get_approval_message'):
            tool = self.tools[tool_name]
            try:
                return tool.get_approval_message()
            except Exception:
                pass
        
        # Fallback to basic message
        args_preview = json.dumps(args, indent=2)[:200]
        if len(json.dumps(args, indent=2)) > 200:
            args_preview += "..."
        
        return (
            f"Tool Call Request:\n"
            f"Name: {tool_name}\n"
            f"Arguments: {args_preview}\n"
            f"Approve execution?"
        )

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
        
        if self.verbose:
            logger.info(f"Executing {len(tool_calls)} tool calls in sync mode")
        
        for i, tool_call in enumerate(tool_calls):
            if self.verbose:
                logger.info(f"Processing tool call {i+1}/{len(tool_calls)}: {tool_call.function.name}")
            
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
        if self.verbose:
            logger.info(f"Executing {len(tool_calls)} tool calls in async mode")
        
        tasks = []
        
        for i, tool_call in enumerate(tool_calls):
            if self.verbose:
                logger.info(f"Queuing tool call {i+1}/{len(tool_calls)}: {tool_call.function.name}")
            
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
        """Execute a single tool call with comprehensive error handling and enhanced verbose logging."""
        start_time = time.time()
        tool_name = tool_call.function.name
        
        # Terminal colors
        class Colors:
            RESET = '\033[0m'
            BOLD = '\033[1m'
            DIM = '\033[2m'
            
            # Standard colors
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            MAGENTA = '\033[95m'
            CYAN = '\033[96m'
            WHITE = '\033[97m'
            
            # Background colors
            BG_RED = '\033[41m'
            BG_GREEN = '\033[42m'
            BG_YELLOW = '\033[43m'
            BG_BLUE = '\033[44m'
            
            # Emojis for visual appeal
            ROBOT = '🤖'
            TOOL = '🔧'
            GEAR = '⚙️'
            CHECK = '✅'
            CROSS = '❌'
            WARNING = '⚠️'
            CLOCK = '⏱️'
            ROCKET = '🚀'
            SEARCH = '🔍'
            FIRE = '🔥'
            LOCK = '🔒'
            SHIELD = '🛡️'
        
        if self.verbose:
            print(f"\n{Colors.CYAN}{'='*80}{Colors.RESET}")
            print(f"{Colors.ROBOT} {Colors.BOLD}{Colors.BLUE}MODEL DECISION:{Colors.RESET} {Colors.YELLOW}Call tool '{tool_name}'{Colors.RESET}")
            print(f"{Colors.CYAN}{'='*80}{Colors.RESET}")
            
            print(f"{Colors.TOOL} {Colors.BOLD}Tool Call Details:{Colors.RESET}")
            print(f"   {Colors.MAGENTA}Function:{Colors.RESET} {Colors.WHITE}{tool_call.function.name}{Colors.RESET}")
            print(f"   {Colors.MAGENTA}Call ID:{Colors.RESET} {Colors.DIM}{tool_call.id or 'auto-generated'}{Colors.RESET}")
            
            # Pretty print arguments with syntax highlighting
            args = tool_call.get_arguments()
            print(f"   {Colors.MAGENTA}Arguments:{Colors.RESET}")
            
            if args:
                args_json = json.dumps(args, indent=6, ensure_ascii=False)
                # Add basic syntax highlighting
                args_json = args_json.replace('"', f'{Colors.GREEN}"{Colors.RESET}')
                args_json = args_json.replace(':', f'{Colors.YELLOW}:{Colors.RESET}')
                args_json = args_json.replace('{', f'{Colors.BLUE}{{{Colors.RESET}')
                args_json = args_json.replace('}', f'{Colors.BLUE}}}{Colors.RESET}')
                print(f"{Colors.DIM}{args_json}{Colors.RESET}")
            else:
                print(f"      {Colors.DIM}(no arguments){Colors.RESET}")
            
            print(f"\n{Colors.ROCKET} {Colors.BOLD}Starting Execution...{Colors.RESET}")
            logger.info(f"Starting execution of tool: {tool_name}")
        
        try:
            # Check execution permissions
            if not self.can_execute_tool(tool_name):
                self._failed_executions += 1
                error_msg = f"Tool '{tool_name}' execution not allowed"
                
                if self.verbose:
                    print(f"{Colors.CROSS} {Colors.RED}{Colors.BOLD}EXECUTION DENIED{Colors.RESET}")
                    print(f"   {Colors.RED}Reason: {error_msg}{Colors.RESET}")
                    print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")
                
                logger.warning(error_msg)
                return self._create_error_result(
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
            
            # Check if approval is required
            if self._should_request_approval(tool_call):
                if self.verbose:
                    print(f"{Colors.LOCK} {Colors.YELLOW}{Colors.BOLD}APPROVAL REQUIRED{Colors.RESET}")
                    print(f"   {Colors.YELLOW}Tool requires human approval before execution{Colors.RESET}")
                
                if not self._request_approval(tool_call):
                    self._denied_executions += 1
                    error_msg = f"Tool '{tool_name}' execution denied by user"
                    
                    if self.verbose:
                        print(f"{Colors.CROSS} {Colors.RED}{Colors.BOLD}EXECUTION DENIED BY USER{Colors.RESET}")
                        print(f"   {Colors.RED}User chose not to approve execution{Colors.RESET}")
                        print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")
                    
                    logger.info(error_msg)
                    return self._create_error_result(
                        tool_call_id=tool_call.id,
                        name=tool_name,
                        error=error_msg
                    )
                else:
                    if self.verbose:
                        print(f"{Colors.CHECK} {Colors.GREEN}{Colors.BOLD}EXECUTION APPROVED{Colors.RESET}")
                        print(f"   {Colors.GREEN}User approved tool execution{Colors.RESET}")
            
            # Get the tool function
            tool_func = self.tools[tool_name]
            
            # Prepare arguments
            args = tool_call.get_arguments()
            if context:
                args.update(context)
            
            if self.verbose:
                print(f"\n{Colors.GEAR} {Colors.BOLD}Executing Tool Function...{Colors.RESET}")
                print(f"   {Colors.BLUE}Function:{Colors.RESET} {Colors.WHITE}{tool_func.__name__ if hasattr(tool_func, '__name__') else 'callable'}{Colors.RESET}")
                print(f"   {Colors.BLUE}Timeout:{Colors.RESET} {Colors.WHITE}{self.execution_timeout}s{Colors.RESET}")
                
                # Show processed arguments (might be different from original)
                if args != tool_call.get_arguments():
                    print(f"   {Colors.BLUE}Processed args:{Colors.RESET} {Colors.DIM}{json.dumps(args, default=str)[:100]}...{Colors.RESET}")
            
            # Execute with timeout
            execution_start = time.time()
            raw_result = self._execute_with_timeout(tool_func, args)
            execution_time = time.time() - start_time
            actual_exec_time = time.time() - execution_start
            
            self._track_execution(execution_time, success=True)
            
            if self.verbose:
                print(f"\n{Colors.CHECK} {Colors.GREEN}{Colors.BOLD}EXECUTION COMPLETED{Colors.RESET}")
                print(f"   {Colors.GREEN}Status:{Colors.RESET} {Colors.WHITE}Success{Colors.RESET}")
                print(f"   {Colors.CLOCK} {Colors.GREEN}Total time:{Colors.RESET} {Colors.WHITE}{execution_time:.3f}s{Colors.RESET}")
                print(f"   {Colors.CLOCK} {Colors.GREEN}Execution time:{Colors.RESET} {Colors.WHITE}{actual_exec_time:.3f}s{Colors.RESET}")
                
                # Show result preview with smart truncation
                result_preview = str(raw_result)
                if len(result_preview) > 200:
                    truncated = result_preview[:200] + f"{Colors.DIM}... (truncated, {len(result_preview)} total chars){Colors.RESET}"
                else:
                    truncated = result_preview
                
                print(f"   {Colors.FIRE} {Colors.GREEN}Result:{Colors.RESET}")
                
                # Try to pretty-print JSON results
                if isinstance(raw_result, dict):
                    try:
                        pretty_result = json.dumps(raw_result, indent=4, ensure_ascii=False)[:300]
                        if len(pretty_result) > 300:
                            pretty_result += f"{Colors.DIM}...{Colors.RESET}"
                        print(f"{Colors.DIM}{pretty_result}{Colors.RESET}")
                    except:
                        print(f"      {Colors.WHITE}{truncated}{Colors.RESET}")
                else:
                    print(f"      {Colors.WHITE}{truncated}{Colors.RESET}")
                
                print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")
            
            logger.info(f"Tool {tool_name} completed successfully in {execution_time:.3f}s")
            
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
            
            if self.verbose:
                print(f"\n{Colors.CROSS} {Colors.RED}{Colors.BOLD}EXECUTION FAILED{Colors.RESET}")
                print(f"   {Colors.RED}Error type:{Colors.RESET} {Colors.WHITE}{type(e).__name__}{Colors.RESET}")
                print(f"   {Colors.RED}Error message:{Colors.RESET} {Colors.WHITE}{str(e)[:200]}{Colors.RESET}")
                print(f"   {Colors.CLOCK} {Colors.RED}Failed after:{Colors.RESET} {Colors.WHITE}{execution_time:.3f}s{Colors.RESET}")
                
                # Show stack trace for debugging if it's not a simple error
                if not isinstance(e, (ValueError, TypeError, KeyError)):
                    import traceback
                    trace = traceback.format_exc()
                    print(f"   {Colors.RED}Stack trace:{Colors.RESET}")
                    print(f"{Colors.DIM}{trace[:500]}{'...' if len(trace) > 500 else ''}{Colors.RESET}")
                
                print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")
            
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
        
        if self.verbose:
            logger.info(f"Starting async execution of tool: {tool_name}")
        
        try:
            if not self.can_execute_tool(tool_name):
                self._failed_executions += 1
                error_msg = f"Tool '{tool_name}' execution not allowed"
                if self.verbose:
                    logger.warning(error_msg)
                return self._create_error_result(
                    tool_call_id=tool_call.id,
                    name=tool_name,
                    error=error_msg
                )
            
            # Check if approval is required (in async context, might need different handling)
            if self._should_request_approval(tool_call):
                if not self._request_approval(tool_call):
                    self._denied_executions += 1
                    error_msg = f"Tool '{tool_name}' execution denied by user"
                    if self.verbose:
                        logger.info(error_msg)
                    return self._create_error_result(
                        tool_call_id=tool_call.id,
                        name=tool_name,
                        error=error_msg
                    )
            
            tool_func = self.tools[tool_name]
            args = tool_call.get_arguments()
            if context:
                args.update(context)
            
            if self.verbose:
                logger.info(f"Async executing {tool_name} with arguments: {json.dumps(args, default=str)}")
            
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
            
            if self.verbose:
                logger.info(f"Async tool {tool_name} completed successfully in {execution_time:.2f}s")
            
            return self._create_success_result_safe(
                tool_call_id=tool_call.id,
                name=tool_name,
                raw_result=raw_result,
                execution_time=execution_time
            )
            
        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            self._track_execution(execution_time, success=False)
            error_msg = f"Tool execution timed out after {self.execution_timeout}s"
            if self.verbose:
                logger.warning(f"Timeout for {tool_name}: {error_msg}")
            return self._create_error_result(
                tool_call_id=tool_call.id,
                name=tool_name,
                error=error_msg,
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
            "approved_executions": self._approved_executions,
            "denied_executions": self._denied_executions,
            "success_rate": success_rate,
            "total_execution_time": self._total_execution_time,
            "average_execution_time": avg_time,
            "registered_tools": list(self.tools.keys()),
            "allowed_tools": list(self.allowed_tools) if self.allowed_tools else None,
            "forbidden_tools": list(self.forbidden_tools),
            "execution_mode": self.execution_mode,
            "verbose_logging": self.verbose,
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
                
                if self.verbose:
                    logger.info(f"Created tool message for {result.name}: success={result.success}")
                
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
        self._approved_executions = 0
        self._denied_executions = 0
        if self.verbose:
            logger.info("Tool execution statistics reset")
        else:
            logger.debug("Tool execution statistics reset")

    # Enhanced control methods
    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Change the execution mode."""
        old_mode = self.execution_mode
        self.execution_mode = mode
        if self.verbose or old_mode != mode:
            logger.info(f"Execution mode changed from {old_mode} to {mode}")

    def set_approval_callback(self, callback: Optional[Callable[[ToolCall, str], bool]]) -> None:
        """Set or update the approval callback."""
        self.approval_callback = callback
        if self.verbose:
            logger.info(f"Approval callback {'set' if callback else 'removed'}")

    def set_verbose(self, verbose: bool) -> None:
        """Enable or disable verbose logging."""
        old_verbose = self.verbose
        self.verbose = verbose
        if old_verbose != verbose:
            logger.info(f"Verbose logging {'enabled' if verbose else 'disabled'}")