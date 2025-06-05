"""
Sandbox execution handler for MCP requests.

This module handles requests that require sandbox execution,
providing secure isolation for dangerous operations.
"""

from typing import Any, Dict, List, Optional

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.sandbox.client import SandboxClient

logger = get_logger("mcp.handlers.sandbox")


class SandboxHandler:
    """Handles sandbox execution requests for the MCP server."""
    
    def __init__(self, sandbox_client: Optional[SandboxClient] = None):
        """Initialize the sandbox handler."""
        self.sandbox_client = sandbox_client
        
        if not self.sandbox_client:
            try:
                self.sandbox_client = SandboxClient()
                logger.info("Initialized sandbox client")
            except Exception as e:
                logger.warning("Failed to initialize sandbox client: %s", e)
    
    def is_available(self) -> bool:
        """Check if sandbox execution is available."""
        return self.sandbox_client is not None
    
    async def execute_in_sandbox(
        self,
        tool_call: ToolCall,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> ToolResult:
        """
        Execute a tool call in the sandbox environment.
        
        Args:
            tool_call: The tool call to execute
            context: Optional execution context
            timeout: Execution timeout in seconds
            
        Returns:
            Tool execution result
        """
        if not self.sandbox_client:
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
                result="",
                success=False,
                error="Sandbox not available",
                metadata={}
            )
        
        try:
            tool_name = tool_call.function.name
            args = tool_call.get_arguments()
            
            if context:
                args.update(context)
            
            logger.info("Executing %s in sandbox", tool_name)
            
            # Execute through sandbox
            sandbox_result = await self.sandbox_client.execute_tool(
                tool_name=tool_name,
                arguments=args,
                timeout=timeout
            )
            
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_name,
                result=sandbox_result.get("result", ""),
                success=sandbox_result.get("success", False),
                error=sandbox_result.get("error"),
                execution_time=sandbox_result.get("execution_time"),
                metadata={
                    "executed_in_sandbox": True,
                    "sandbox_id": sandbox_result.get("sandbox_id")
                }
            )
            
        except Exception as e:
            logger.error("Sandbox execution failed for %s: %s", tool_call.function.name, e)
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.function.name,
                result="",
                success=False,
                error=f"Sandbox execution failed: {str(e)}",
                metadata={"executed_in_sandbox": True}
            )
    
    async def get_sandbox_status(self) -> Dict[str, Any]:
        """Get sandbox environment status."""
        if not self.sandbox_client:
            return {
                "available": False,
                "error": "Sandbox client not initialized"
            }
        
        try:
            # Get status from sandbox client
            status = await self.sandbox_client.get_status()
            return {
                "available": True,
                "status": status
            }
        except Exception as e:
            logger.error("Failed to get sandbox status: %s", e)
            return {
                "available": False,
                "error": str(e)
            }
    
    async def cleanup_sandbox(self, sandbox_id: Optional[str] = None) -> bool:
        """Clean up sandbox environment."""
        if not self.sandbox_client:
            return False
        
        try:
            await self.sandbox_client.cleanup(sandbox_id)
            return True
        except Exception as e:
            logger.error("Failed to cleanup sandbox: %s", e)
            return False