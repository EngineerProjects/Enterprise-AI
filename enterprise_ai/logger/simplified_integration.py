"""
Simplified MCP Integration - Log Files Only

This patch modifies the MCP Executor to use the simplified log-only tool logger.
Much cleaner - only structured .log files, no JSON complexity.
"""

from typing import List, TYPE_CHECKING
from enterprise_ai.schema import ToolCall

# Avoid circular import
if TYPE_CHECKING:
    from enterprise_ai.tool.core.result import ToolResult

from enterprise_ai.logger.simplified_logger import get_simplified_tool_logger


async def execute_tool_calls_with_simplified_logging(
    self, 
    tool_calls: List[ToolCall],
    agent_name: str = None,
    reasoning_context: str = None
) -> List["ToolResult"]:
    """
    Enhanced execute_tool_calls method with simplified log-only logging.
    
    This method:
    1. Logs all tool call commands to tool_calls.log (structured format)
    2. Executes the tools using existing logic
    3. Logs all tool outputs to tool_outputs.log (structured format)
    4. Large outputs stored in separate .txt files
    
    Args:
        tool_calls: List of tool calls to execute
        agent_name: Name of the agent making the calls
        reasoning_context: Context about why these tools were called
        
    Returns:
        List of tool execution results (same as original)
    """
    # Import locally to avoid circular import
    from enterprise_ai.tool.core.result import ToolResult
    if not tool_calls:
        return []

    # Get simplified logger
    simplified_logger = get_simplified_tool_logger()
    session_id = getattr(self, 'session_id', None)
    
    # 1. LOG ALL TOOL CALLS (COMMANDS) TO .LOG FILE
    for tool_call in tool_calls:
        simplified_logger.log_tool_call(
            tool_call=tool_call,
            session_id=session_id,
            agent_name=agent_name,
            reasoning_context=reasoning_context
        )
    
    # 2. EXECUTE TOOLS USING EXISTING LOGIC (unchanged)
    results = []
    self._execution_count += len(tool_calls)
    
    # Update tool executors with current tools
    self.tool_executor.tools = self._tools
    if self.sandbox_executor:
        self.sandbox_executor.tools = self._tools
    
    try:
        # Use existing sandbox routing logic
        if self.sandbox_executor and self.sandbox_config.enabled:
            dangerous_tools = [
                tc for tc in tool_calls 
                if tc.function.name in self.sandbox_config.dangerous_tools
            ]
            safe_tools = [tc for tc in tool_calls if tc not in dangerous_tools]
            
            if dangerous_tools:
                sandbox_results = await self.sandbox_executor.aexecute_tool_calls(dangerous_tools)
                results.extend(sandbox_results)
            
            if safe_tools:
                safe_results = await self.tool_executor.aexecute_tool_calls(safe_tools)
                results.extend(safe_results)
        else:
            results = await self.tool_executor.aexecute_tool_calls(tool_calls)
            
        # Track failures (existing logic)
        self._failed_count += sum(1 for r in results if not r.success)
        
        # 3. LOG ALL TOOL OUTPUTS (RESULTS) TO .LOG FILE
        for tool_call, result in zip(tool_calls, results):
            simplified_logger.log_tool_output(
                tool_call=tool_call,
                result=result,
                session_id=session_id,
                agent_name=agent_name
            )
        
        return results
        
    except Exception as e:
        # Log error results
        self._failed_count += len(tool_calls)
        error_results = []
        
        for tool_call in tool_calls:
            error_result = ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
                result="",
                success=False,
                error=f"MCP execution error: {str(e)}"
            )
            error_results.append(error_result)
            
            # Log the error result
            simplified_logger.log_tool_output(
                tool_call=tool_call,
                result=error_result,
                session_id=session_id,
                agent_name=agent_name
            )
        
        return error_results


def patch_mcp_simplified_logging():
    """
    Monkey patch the ToolMCP class to add simplified log-only logging.
    
    Call this function before creating any agents to enable log-only comprehensive logging.
    """
    from enterprise_ai.mcp.executor import ToolMCP
    
    # Store original method for fallback
    ToolMCP._original_execute_tool_calls = ToolMCP.execute_tool_calls
    
    # Replace with simplified logging version
    ToolMCP.execute_tool_calls = execute_tool_calls_with_simplified_logging
    
    print("✅ Simplified tool logging enabled (log files only)")


def unpatch_mcp_simplified_logging():
    """Remove the simplified logging patch and restore original behavior."""
    from enterprise_ai.mcp.executor import ToolMCP
    
    if hasattr(ToolMCP, '_original_execute_tool_calls'):
        ToolMCP.execute_tool_calls = ToolMCP._original_execute_tool_calls
        delattr(ToolMCP, '_original_execute_tool_calls')
        print("✅ Simplified tool logging disabled")
    else:
        print("⚠️ No logging patch found to remove")
