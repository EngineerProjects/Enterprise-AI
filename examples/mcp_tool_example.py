"""
MCP Tool Usage Example

This example demonstrates how to use the MCP to execute tools and handle their results.
"""

import asyncio
import sys
import json
import os
from typing import Dict, Any, List, Optional

# Add the project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.mcp.sandbox_config import SandboxConfig, create_sandbox_config
from enterprise_ai.schema import ToolCall


async def simple_echo_tool(message: str) -> str:
    """A simple echo tool."""
    return f"Echo: {message}"


async def simple_math_tool(a: float, b: float, operation: str = "add") -> Dict[str, Any]:
    """A simple math tool."""
    result = None
    if operation == "add":
        result = a + b
    elif operation == "subtract":
        result = a - b
    elif operation == "multiply":
        result = a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    return {
        "operation": operation,
        "result": result,
        "inputs": {"a": a, "b": b}
    }


async def dangerous_tool(command: str) -> str:
    """A tool that would normally be sandboxed."""
    # This simulates a potentially dangerous operation
    if "rm" in command or "delete" in command:
        raise ValueError("Potentially dangerous command detected")
    return f"Executed command: {command}"


async def run_simple_tool(mcp: ToolMCP, tool_name: str, **args):
    """Run a tool and print its result."""
    print(f"\nRunning tool: {tool_name}")
    print(f"Arguments: {args}")
    
    # Create a tool call
    tool_call = ToolCall.create(
        id=f"call_{tool_name}_{hash(str(args)) % 1000}",
        name=tool_name,
        arguments=args
    )
    
    # Execute tool call
    results = await mcp.execute_tool_calls([tool_call])
    result = results[0] if results else None
    
    print("-" * 40)
    if result:
        print(f"Success: {result.success}")
        
        # Handle result based on success
        if result.success:
            if hasattr(result, 'result'):
                if isinstance(result.result, dict):
                    print("Result (dict):")
                    for key, value in result.result.items():
                        print(f"  {key}: {value}")
                elif isinstance(result.result, str):
                    print(f"Result (string): {result.result}")
                else:
                    print(f"Result: {result.result}")
        
        # Print error if present
        if hasattr(result, 'error') and result.error is not None:
            # Don't try to call result.error as a method
            print(f"Error: {result.error}")
    else:
        print("No result returned")
    
    print("-" * 40)
    return result


async def main():
    """Run the MCP tool usage example."""
    print("=== MCP Tool Usage Example ===")
    
    # Create MCP without sandbox
    print("\n1. Creating MCP without sandbox:")
    mcp_no_sandbox = ToolMCP(timeout=30.0, sandbox_config=SandboxConfig(enabled=False))
    
    # Register tools
    mcp_no_sandbox.register_tool("echo", simple_echo_tool)
    mcp_no_sandbox.register_tool("math", simple_math_tool)
    mcp_no_sandbox.register_tool("dangerous", dangerous_tool)
    
    # Run tools
    await run_simple_tool(mcp_no_sandbox, "echo", message="Hello from MCP!")
    await run_simple_tool(mcp_no_sandbox, "math", a=5, b=3, operation="add")
    await run_simple_tool(mcp_no_sandbox, "math", a=10, b=0, operation="divide")
    await run_simple_tool(mcp_no_sandbox, "dangerous", command="ls -la")
    
    # Create MCP with sandbox
    print("\n2. Creating MCP with sandbox:")
    sandbox_config = create_sandbox_config(
        enabled=True,
        dangerous_tools=["dangerous", "bash", "python_execute"],
        always_sandbox=["dangerous"],
        never_sandbox=["echo", "math"]
    )
    
    mcp_with_sandbox = ToolMCP(timeout=30.0, sandbox_config=sandbox_config)
    
    # Register the same tools
    mcp_with_sandbox.register_tool("echo", simple_echo_tool)
    mcp_with_sandbox.register_tool("math", simple_math_tool)
    mcp_with_sandbox.register_tool("dangerous", dangerous_tool)
    
    # Run the same tools
    await run_simple_tool(mcp_with_sandbox, "echo", message="Hello from sandboxed MCP!")
    await run_simple_tool(mcp_with_sandbox, "math", a=7, b=2, operation="multiply")
    await run_simple_tool(mcp_with_sandbox, "dangerous", command="ls -la")
    
    print("\nExample completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
