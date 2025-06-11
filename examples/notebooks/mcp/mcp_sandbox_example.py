"""
Example demonstrating MCP with Sandbox Integration

This example shows how to use the MCP with different sandbox configurations.
"""

import asyncio
import sys
import json
from typing import Dict, Any

# Add the project root to Python path
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.mcp.sandbox_config import SandboxConfig, create_sandbox_config, SAFE_SANDBOX_CONFIG
from enterprise_ai.schema import ToolCall


async def test_mcp_sandbox():
    """Test MCP with sandbox integration."""
    print("\n=== Testing MCP with Sandbox Integration ===")
    
    # Create MCP with sandbox disabled (default)
    print("\n1. Creating MCP with sandbox disabled (default):")
    mcp = ToolMCP(timeout=30.0, sandbox_config=SandboxConfig(enabled=False))
    
    # Define a simple function to register as a tool
    async def simple_echo_tool(message: str):
        return f"Echo: {message}"
    
    # Register tools
    mcp.register_tool("echo", simple_echo_tool)
    
    # Create a tool call
    tool_call = ToolCall.create(
        id="call_1",
        name="echo",
        arguments={"message": "Hello from the MCP!"}
    )
    
    # Execute tool call
    results = await mcp.execute_tool_calls([tool_call])
    result = results[0] if results else None
    
    print(f"Success: {result.success if result else 'N/A'}")
    print(f"Result: {result.result if result and hasattr(result, 'result') else 'N/A'}")
    if result and hasattr(result, 'error'):
        print(f"Error: {result.error if result.error is not None else 'None'}")
    
    # Get stats
    stats = mcp.get_stats()
    print(f"\nStats: {json.dumps(stats, indent=2, default=str)}")
    
    # Create MCP with sandbox enabled
    print("\n2. Creating MCP with sandbox enabled:")
    sandbox_config = create_sandbox_config(
        enabled=True,
        dangerous_tools=["python_execute", "bash"],
        always_sandbox=["python_execute"],
        never_sandbox=["echo"]
    )
    
    mcp_sandbox = ToolMCP(timeout=30.0, sandbox_config=sandbox_config)
    
    # Register the same tool
    mcp_sandbox.register_tool("echo", simple_echo_tool)
    
    # Execute the same tool call
    results = await mcp_sandbox.execute_tool_calls([tool_call])
    result = results[0] if results else None
    
    print(f"Success: {result.success if result else 'N/A'}")
    print(f"Result: {result.result if result and hasattr(result, 'result') else 'N/A'}")
    if result and hasattr(result, 'error'):
        print(f"Error: {result.error if result.error is not None else 'None'}")
    
    # Get stats
    stats = mcp_sandbox.get_stats()
    print(f"\nStats: {json.dumps(stats, indent=2, default=str)}")
    
    print("\nTest completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_mcp_sandbox())
