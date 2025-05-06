#!/usr/bin/env python
"""
Enhanced MCP Testing Script

This script tests the functionality of the Model Context Protocol (MCP) system,
verifying tool registration, discovery, execution, and compatibility features.
"""

import os
import sys
import asyncio
from typing import List, Dict, Any, Optional

# Import common utilities for better formatting
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

# Setup project path
project_root = setup_project_path()

# Import Enterprise AI components
from enterprise_ai.mcp import (
    MCPClient, 
    AgentMCPClient, 
    get_mcp_server,
    format_tool_descriptions,
    get_tool_schema,
    get_compatible_tools,
    create_tool_usage_guide
)
from enterprise_ai.tool.core import (
    BaseTool,
    ToolCapability,
    register_tool,
    get_registry
)
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.utility.terminate import Terminate
from enterprise_ai.tool.planning.planning import PlanningTool
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("mcp_test")

def verify_tools_registered():
    """Verify that tools are properly registered in the system."""
    print_section("Verifying Tool Registration")
    
    registry = get_registry()
    tools = registry.get_all_tool_classes()
    
    if not tools:
        print_warning("No tools found in registry. Attempting to import common tools...")
        
        # Import some common tools to ensure they're registered
        try:
            from enterprise_ai.tool.utility.terminate import Terminate
            from enterprise_ai.tool.planning.planning import PlanningTool
            
            # Check again after imports
            tools = registry.get_all_tool_classes()
            
            if tools:
                print_success(f"Successfully loaded {len(tools)} tools after imports")
            else:
                print_warning("Still no tools found after imports")
                
                # Create and register a simple test tool for testing
                create_test_tool()
                tools = registry.get_all_tool_classes()
        except ImportError as e:
            print_error(f"Failed to import tools: {e}")
    
    print_info(f"Found {len(tools)} registered tools in the system")
    
    if tools:
        print_info("Tool names:")
        for i, (name, _) in enumerate(tools.items(), 1):
            print(f"  {i}. {name}")
    
    return bool(tools)

@register_tool(category="test")
class TestTool(BaseTool):
    """A simple test tool for MCP testing purposes."""
    
    name: str = "test_tool"
    description: str = "A simple test tool for MCP testing"
    parameters: dict = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Test message to echo"
            }
        },
        "required": ["message"]
    }
    
    def __init__(self, **data: Any) -> None:
        """Initialize the test tool with all required attributes."""
        super().__init__(**data)
        # The BaseTool constructor should now handle these, but we'll be extra safe
        self._on_state_change = []
        self._execution_count = 0
        self._last_execution_time = None
        
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Echo the input message."""
        message = kwargs.get("message", "No message provided")
        # Create a basic result without calling any methods on it
        return ToolResult(output=f"Test tool executed with message: {message}")
    
def create_test_tool():
    """Create and register a test tool."""
    print_info("Creating test tool for MCP testing")
    
    # Create and register test tool
    @register_tool(category="test")
    class TestTool(BaseTool):
        """A simple test tool for MCP testing."""
        
        name: str = "test_tool"
        description: str = "A simple test tool for MCP testing"
        parameters: dict = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Test message to echo"
                }
            },
            "required": ["message"]
        }
        
        async def execute(self, **kwargs: Any) -> ToolResult:
            """Echo the input message."""
            message = kwargs.get("message", "No message provided")
            return ToolResult(output=f"Test tool executed with message: {message}")
    
    print_success(f"Test tool 'test_tool' registered")
    
    # Return an instance for direct use
    return TestTool()

async def test_mcp_functionality():
    """Test basic MCP functionality"""
    print_section("Testing MCP Server and Client")
    
    # Create a test session
    client = MCPClient("test-session", create_if_not_exists=True)
    
    # Create and register a test tool
    test_tool = TestTool(name="test_tool", description="A simple test tool")
    client.session.register_tool(test_tool)
    
    # Discover available tools
    tools = client.discover_tools()
    print_info(f"Found {len(tools)} tools available")
    
    # Get detailed tool information for the first tool
    if tools:
        first_tool = tools[0]["function"]["name"]
        print_success(f"Testing with tool: {first_tool}")
        
        tool_info = client.get_tool_info(first_tool)
        print_info(f"Tool info for {first_tool}:")
        print_info(f"- Description: {tool_info.get('description', 'N/A')}")
        print_info(f"- Version: {tool_info.get('version', 'N/A')}")
        
        # Get usage guide
        guide = create_tool_usage_guide(first_tool)
        print_info("Usage guide sample (first 3 lines):")
        print("\n".join(guide.split("\n")[:3]) + "...")
    else:
        print_warning("No tools available. MCP client cannot proceed with tool tests.")
    
    # Clean up
    await client.close()
    print_success("Basic MCP test completed!")
    separator()

async def test_agent_client():
    """Test the agent-specific client"""
    print_section("Testing Agent MCP Client")
    
    # Get available tools from registry first
    registry = get_registry()
    available_tools = registry.get_all_tool_classes()
    
    # Check if our test tool is available
    test_tool_available = "test_tool" in available_tools
    tool_names_to_use = ["test_tool"] if test_tool_available else None
    
    # Create an agent client with specific tools
    agent_client = AgentMCPClient(
        "test-agent",
        tool_names=tool_names_to_use
    )
    
    # Get tools
    tools = agent_client.discover_tools()
    print_info(f"Agent client found {len(tools)} tools")
    
    # Prepare tool to add - either test_tool or the first available tool
    tools_to_add = []
    if test_tool_available:
        tools_to_add = ["test_tool"]
    elif available_tools:
        # Get the first available tool name
        first_tool_name = next(iter(available_tools.keys()), None)
        if first_tool_name:
            tools_to_add = [first_tool_name]
    
    # Update tools
    await agent_client.update_tools(add_tools=tools_to_add)
    
    # Check updated tools
    updated_tools = agent_client.discover_tools()
    print_info(f"After updates: {len(updated_tools)} tools available")
    
    # Get filter status
    filter_status = agent_client.get_filter_status()
    print_info(f"Filter status: {filter_status}")
    
    # Clean up
    await agent_client.close()
    print_success("Agent client test completed!")
    separator()
    
async def test_tool_execution():
    """Test tool execution features"""
    print_section("Testing Tool Execution")
    
    # Create client and test tool
    client = MCPClient("execution-test", create_if_not_exists=True)
    
    # Create test tool and manually register it with the session
    test_tool = create_test_tool()
    
    # Directly register the tool with the session
    try:
        client.session.register_tool(test_tool)
        print_info(f"Test tool '{test_tool.name}' directly registered with session")
    except Exception as e:
        print_error(f"Error registering test tool: {e}")
    
    # Get tools and verify registration
    tools = client.discover_tools()
    print_info(f"Found {len(tools)} tools in session")
    
    if not tools:
        print_error("Failed to register test tool with session")
        await client.close()
        return
    
    # Execute the tool with error handling
    print_info(f"Executing tool: {test_tool.name}")
    with Timer("Tool execution"):
        try:
            result = await client.execute_tool(
                test_tool.name,
                message="Hello from MCP test!"
            )
            
            # Print result safely
            if result:
                if hasattr(result, 'output') and result.output is not None:
                    print_success(f"Execution result: {result.output}")
                elif hasattr(result, 'error') and result.error is not None:
                    print_error(f"Execution error: {result.error}")
                else:
                    print_warning(f"Execution result has no output or error: {result}")
            else:
                print_error("No result returned from tool execution")
        except Exception as e:
            print_error(f"Error executing tool: {e}")
    
    # Clean up
    await client.close()
    print_success("Execution test completed!")
    separator()


async def main():
    """Run all tests"""
    print_title("MCP ENHANCED FUNCTIONALITY TESTS")
    
    try:
        # First verify tools are registered
        tools_available = verify_tools_registered()
        separator()
        
        # Run the tests
        await test_mcp_functionality()
        await test_agent_client()
        await test_tool_execution()
        
        print_success("All tests completed successfully!")
        
    except Exception as e:
        print_error(f"Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())