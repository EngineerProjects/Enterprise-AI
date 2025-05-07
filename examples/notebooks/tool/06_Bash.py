#!/usr/bin/env python
"""
Simplified Test for Bash Tool via MCP

This script tests just the Bash tool directly to avoid import issues.
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

# Import only what we need directly
from enterprise_ai.tool.core.base import ToolConfig
from enterprise_ai.tool.execution.bash import Bash  # Direct import of just the Bash tool
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("bash_test")


async def test_bash_tool():
    """Test the Bash tool using the MCP system."""
    print_title("TESTING BASH TOOL VIA MCP")
    
    # Create a test session
    session_id = "bash-tool-test"
    client = None
    
    try:
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")
        
        # Create tool with configuration
        print_section("Tool Creation and Configuration")
        
        config = ToolConfig(
            timeout=15.0,  # Timeout for shell commands
            max_retries=1,  # Allow one retry
            sandbox_enabled=True,  # Run in sandbox for safety
        )
        
        # Create and register the Bash tool with explicit parameters
        bash_tool = Bash(
            name="bash",
            description="Execute bash commands in an interactive terminal environment.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
                    },
                    "restart": {
                        "type": "boolean",
                        "description": "Whether to restart the bash session.",
                        "default": False,
                    },
                },
                "required": ["command"],
            },
            config=config
        )
        
        client.session.register_tool(bash_tool)
        print_success(f"Created and registered Bash tool with configuration")
        
        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")
        
        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")
        
        # Get detailed tool info
        tool_info = client.get_tool_info(bash_tool.name)
        print_info(f"\nTool info for {bash_tool.name}:")
        print_info(f"  Description: {tool_info.get('description', 'N/A')}")
        print_info(f"  State: {tool_info.get('state', 'N/A')}")
        
        separator()
        
        # Test 1: Basic command execution - echo
        print_section("Test 1: Basic Command Execution - Echo")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                command="echo 'Hello from Bash Tool!'"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 2: Check current directory and create a test directory
        print_section("Test 2: Directory Operations")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                command="pwd && mkdir -p test_dir && ls -la"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 3: Create and read a file
        print_section("Test 3: Create and Read File")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                command="echo 'Test content' > test_dir/test_file.txt && cat test_dir/test_file.txt"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 4: File operations
        print_section("Test 4: File Operations")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                command="ls -la test_dir && echo 'More content' >> test_dir/test_file.txt && cat test_dir/test_file.txt"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 5: Command with error
        print_section("Test 5: Command With Error")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                command="cat /nonexistent/file.txt"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 6: Environment variables
        print_section("Test 6: Environment Variables")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                command="TEST_VAR='Hello from bash' && echo $TEST_VAR && env | grep -i test"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 7: Bash script creation and execution
        print_section("Test 7: Bash Script Creation and Execution")
        script_content = """
#!/bin/bash
# Simple bash script for testing
echo "Running test script..."
echo "Arguments provided: $@"
echo "Current directory: $(pwd)"
echo "Creating a simple file listing:"
ls -la | grep -v "^total" | head -5
echo "Script completed successfully."
        """
        
        # First create a script file
        with Timer("Script Creation"):
            create_result = await client.execute_tool(
                bash_tool.name,
                command=f'mkdir -p scripts && cat > scripts/test_script.sh << \'EOF\'\n{script_content}\nEOF\n\nchmod +x scripts/test_script.sh'
            )
        
        print_info("Script creation result:")
        if hasattr(create_result, 'output') and create_result.output:
            print_info(create_result.output)
        if hasattr(create_result, 'error') and create_result.error:
            print_error(f"Error creating script: {create_result.error}")
        
        # Now execute the script
        print_info("\nExecuting the script:")
        with Timer("Script Execution"):
            exec_result = await client.execute_tool(
                bash_tool.name,
                command="./scripts/test_script.sh arg1 arg2"
            )
        
        if hasattr(exec_result, 'output') and exec_result.output is not None:
            print_success(f"Output:")
            print_info(exec_result.output)
        if hasattr(exec_result, 'error') and exec_result.error is not None and exec_result.error.strip():
            print_error(f"Error: {exec_result.error}")
        
        separator()
        
        # Test 8: Session restart
        print_section("Test 8: Session Restart")
        with Timer("Execution"):
            result = await client.execute_tool(
                bash_tool.name,
                restart=True
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None and result.error.strip():
            print_error(f"Error: {result.error}")
        
        # Verify session restarted by checking for our previous files
        print_info("\nVerifying session restart by checking for previous directory:")
        with Timer("Verification"):
            verify_result = await client.execute_tool(
                bash_tool.name,
                command="ls -la test_dir 2>/dev/null || echo 'Directory not found - session was reset'"
            )
        
        if hasattr(verify_result, 'output') and verify_result.output is not None:
            print_info(f"Verification output:")
            print_info(verify_result.output)
        
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
    asyncio.run(test_bash_tool())