#!/usr/bin/env python
"""
Test for Terminate Tool via MCP

This script demonstrates how to use the Terminate tool through the MCP system 
to signal the completion or termination of a task or conversation.
"""

import asyncio
import sys
from typing import Any, Dict, Optional

# Import utilities for better formatting
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    Timer
)

# Set up project path
setup_project_path()

# Import core components
from enterprise_ai.tool.core import (
    ToolConfig,
    ToolResult
)
from enterprise_ai.tool.utility.terminate import Terminate
from enterprise_ai.mcp import (
    MCPClient,
    get_mcp_server
)
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("terminate_test")


async def test_terminate_tool():
    """Test the Terminate tool using the MCP system."""
    print_title("TESTING TERMINATE TOOL VIA MCP")
    
    # Create a test session
    session_id = "terminate-tool-test"
    client = None
    
    try:
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")
        
        # Create tool with configuration
        print_section("Tool Creation and Configuration")
        
        config = ToolConfig(
            timeout=5.0,
            max_retries=0,  # Terminate shouldn't need retries
            cache_results=False,  # Caching termination doesn't make sense
        )
        
        # Create and register the Terminate tool with explicit parameters
        terminate_tool = Terminate(
            # Explicitly provide required parameters
            name="terminate",
            description="Signal the end of an interaction when tasks are completed or cannot proceed.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "The finish status of the interaction.",
                        "enum": ["success", "failure"],
                    },
                    "message": {
                        "type": "string",
                        "description": "Optional message explaining the termination reason.",
                    },
                },
                "required": ["status"],
            },
            config=config
        )
        
        client.session.register_tool(terminate_tool)
        print_success(f"Created and registered Terminate tool with configuration")
        
        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")
        
        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")
        
        # Get detailed tool info
        tool_info = client.get_tool_info(terminate_tool.name)
        print_info(f"\nTool info for {terminate_tool.name}:")
        print_info(f"  Description: {tool_info.get('description', 'N/A')}")
        print_info(f"  State: {tool_info.get('state', 'N/A')}")
        
        separator()
        
        # Test 1: Successful termination
        print_section("Test 1: Successful Termination")
        with Timer("Execution"):
            result = await client.execute_tool(
                terminate_tool.name,
                status="success",
                message="Task completed successfully"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 2: Failure termination
        print_section("Test 2: Failure Termination")
        with Timer("Execution"):
            result = await client.execute_tool(
                terminate_tool.name,
                status="failure",
                message="Task could not be completed due to an error"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_warning(f"Output (failure termination): {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 3: Invalid status
        print_section("Test 3: Invalid Status")
        with Timer("Execution"):
            result = await client.execute_tool(
                terminate_tool.name,
                status="invalid_status",
                message="This should result in an error"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected): {result.error}")
        
        separator()
        
        # Test 4: Missing required parameters
        print_section("Test 4: Missing Required Parameters")
        with Timer("Execution"):
            result = await client.execute_tool(
                terminate_tool.name,
                message="Missing status parameter"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected): {result.error}")
        
        print_success("All tests completed successfully!")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        if client:
            await client.close()
            print_info("Session closed and resources cleaned up")
        separator()


if __name__ == "__main__":
    asyncio.run(test_terminate_tool())