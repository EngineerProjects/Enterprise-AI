#!/usr/bin/env python
"""
Agent with Tools

This script demonstrates how to create agents with tool capabilities
and how they can use tools to solve problems.
"""

import asyncio
from typing import Any, Dict, List, Optional

# Import utilities
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    separator,
    Timer
)

# Set up project path
setup_project_path()

# Import core components
from enterprise_ai.agent.core import create_agent, create_tool_agent
from enterprise_ai.tool.core import BaseTool
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_tools_test")

async def test_agent_with_tools():
    """Test creating and using agents with tools."""
    print_title("TESTING AGENTS WITH TOOLS")

    # Create a client session for tool registration
    session_id = "agent-tools-test"
    mcp_client = MCPClient(session_id, create_if_not_exists=True)
    
    try:
        # 1. Create a simple calculator tool
        print_section("1. Creating a simple calculator tool")
        
        class CalculatorTool(BaseTool):
            """A simple calculator tool."""
            
            def __init__(self):
                super().__init__(
                    name="calculator",
                    description="Perform basic calculations",
                    parameters={
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Math expression to evaluate (e.g., '2 + 2')"
                            }
                        },
                        "required": ["expression"]
                    }
                )
            
            async def execute(self, **kwargs):
                expression = kwargs.get("expression", "")
                try:
                    # Use eval with limited scope for simple calculations
                    result = eval(expression, {"__builtins__": {}}, {})
                    return {"output": f"The result of {expression} is {result}"}
                except Exception as e:
                    return {"error": f"Error calculating {expression}: {str(e)}"}
        
        # Create and register the calculator tool
        calculator = CalculatorTool()
        mcp_client.session.register_tool(calculator)
        print_success(f"Created and registered calculator tool")
        
        # 2. Create an agent with tools enabled
        print_section("2. Creating an agent with tools enabled")
        
        tool_agent = create_tool_agent(
            name="ToolAgent",
            reasoning_framework="react",
            tool_names=["calculator"]
        )
        
        print_success(f"Created agent with tools: {tool_agent.name} (ID: {tool_agent.id})")
        
        # 3. Test the agent using tools
        print_section("3. Testing the agent using tools")
        
        calculation_query = "What is 235 * 18?"
        print_info(f"Query: '{calculation_query}'")
        
        with Timer("Agent Response (with tool)"):
            response = await tool_agent.aprocess_message(calculation_query)
        
        print_info(f"Response: '{response.content}'")
        
        # 4. Test more complex tool usage
        print_section("4. Testing more complex tool usage")
        
        complex_query = "If I have 120 items that cost $8.50 each, and I get a 15% discount, how much will I pay in total?"
        print_info(f"Query: '{complex_query}'")
        
        with Timer("Agent Response (complex calculation)"):
            response = await tool_agent.aprocess_message(complex_query)
        
        print_info(f"Response: '{response.content}'")
        
        # 5. Test direct tool execution through agent
        print_section("5. Testing direct tool execution through agent")
        
        try:
            print_info("Directly executing calculator tool")
            with Timer("Direct Tool Execution"):
                result = await tool_agent.execute_tool("calculator", expression="(42 * 3) / 2")
            
            print_info(f"Tool result: {result}")
        except Exception as e:
            print_error(f"Error executing tool: {e}")
        
        print_success("All agent tools tests completed successfully!")
        
    finally:
        # Clean up MCP session
        await mcp_client.close()
        print_info("Closed MCP session and cleaned up resources")
        separator()

if __name__ == "__main__":
    asyncio.run(test_agent_with_tools())