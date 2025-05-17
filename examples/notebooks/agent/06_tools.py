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
from enterprise_ai.tool.core.base import BaseTool, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_tools_test")

TIMEOUT = 1200  # 20 minutes for very slow GPU/CPU

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
                    },
                    capabilities={ToolCapability.UTILITY}  # Add the UTILITY capability
                )
                
                # Add a usage example to help the agent
                self.usage_examples = [
                    {
                        "description": "Calculate 235 * 18",
                        "parameters": {
                            "expression": "235 * 18"
                        }
                    }
                ]
            
            async def execute(self, **kwargs):
                expression = kwargs.get("expression", "")
                try:
                    # Use eval with limited scope for simple calculations
                    result = eval(expression, {"__builtins__": {}}, {})
                    return ToolResult(output=f"The result of {expression} is {result}")
                except Exception as e:
                    return ToolResult(error=f"Error calculating {expression}: {str(e)}")
        
        # Create and register the calculator tool
        calculator = CalculatorTool()
        mcp_client.session.register_tool(calculator)
        print_success(f"Created and registered calculator tool")
        
        # 2. Create an agent with tools enabled
        print_section("2. Creating an agent with tools enabled")
        
        # Use create_agent directly with explicit tool and MCP settings
        tool_agent = create_agent(
            agent_type="llm",
            name="ToolAgent",
            reasoning_framework="react",
            use_tools=True,
            enable_mcp=True,
            tool_names=["calculator"],  # Specify the calculator tool
            llm_provider_name="ollama",
            llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"}
        )
        
        # Using the _tools attribute which is the actual name in the LLMAgent class
        if hasattr(tool_agent, "_tools") and tool_agent._tools:
            tool_agent._tools.add_tool(calculator)
            
            # Explicitly add the UTILITY capability to the tools manager
            tool_agent._tools.add_capability(ToolCapability.UTILITY)
        
        # Ensure MCP is properly initialized for the agent
        # This is important because of the coroutine handling issue
        if hasattr(tool_agent, "_tools") and tool_agent._tools:
            if hasattr(tool_agent, "initialize_mcp") and callable(getattr(tool_agent, "initialize_mcp")):
                await tool_agent.initialize_mcp()
            elif hasattr(tool_agent._tools, "_mcp_config") and tool_agent._tools._mcp_config and tool_agent._tools._mcp_config.get("enable"):
                await tool_agent._tools.enable_mcp(
                    tool_categories=tool_agent._tools._mcp_config.get("categories"),
                    tool_names=tool_agent._tools._mcp_config.get("names")
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
        
        # Switch the agent's reasoning framework to Chain of Thought
        if hasattr(tool_agent, "set_reasoning_framework"):
            await tool_agent.set_reasoning_framework("cot")
        elif hasattr(tool_agent, "_reasoning") and hasattr(tool_agent._reasoning, "set_framework"):
            await tool_agent._reasoning.set_framework("cot")
        
        with Timer("Agent Response (complex calculation)"):
            response = await tool_agent.aprocess_message(complex_query)
        
        print_info(f"Response: '{response.content}'")
        
        # 5. Test direct tool execution through agent
        print_section("5. Testing direct tool execution through agent")
        
        try:
            print_info("Directly executing calculator tool")
            with Timer("Direct Tool Execution"):
                # Execute the tool through the agent if possible
                if hasattr(tool_agent, "_tools") and tool_agent._tools:
                    result = await tool_agent._tools.execute_tool(
                        tool_name="calculator",
                        expression="(42 * 3) / 2"
                    )
                else:
                    # Fallback to MCP client
                    result = await mcp_client.execute_tool(
                        tool_name="calculator", 
                        expression="(42 * 3) / 2"
                    )
            
            print_info(f"Tool result: {result}")
        except Exception as e:
            print_error(f"Error executing tool: {e}")
        
        # 6. Test tool discovery
        print_section("6. Testing tool discovery")
        
        try:
            # Get available tools from MCP client
            tools = mcp_client.discover_tools() 
            print_info(f"Discovered {len(tools)} tools")
            
            # Get detailed information about the calculator tool
            calculator_info = mcp_client.get_tool_info("calculator")
            print_info(f"Calculator tool capabilities: {calculator_info.get('capabilities', [])}")
            
            # Get formatted tool descriptions
            if hasattr(tool_agent, "_tools") and tool_agent._tools:
                descriptions = tool_agent._tools.get_formatted_tool_descriptions()
                print_info("Formatted tool descriptions:")
                print_info(descriptions)  # Print the description on a separate line
                
                # Get tool schemas - explicitly set filter_by_capabilities to False
                schemas = await tool_agent._tools.get_tool_schemas(filter_by_capabilities=False)
                print_info(f"Found {len(schemas)} tool schemas")
                
                # Print details of the schemas for verification
                if schemas:
                    for i, schema in enumerate(schemas):
                        if "function" in schema:
                            fn = schema["function"]
                            print_info(f"  Schema {i+1}: {fn.get('name', 'unnamed')} - {fn.get('description', 'no description')}")
                else:
                    print_info("No tool schemas found. This might indicate a registration issue.")
            
        except Exception as e:
            print_error(f"Error during tool discovery: {e}")
            
        print_success("All agent tools tests completed successfully!")
        
    finally:
        # Clean up resources properly
        try:
            # First, try to clean up the agent's resources 
            if 'tool_agent' in locals() and tool_agent is not None:
                if hasattr(tool_agent, 'terminate'):
                    await tool_agent.terminate()
                    print_info(f"Terminated agent {tool_agent.id}")
                    
                    # Set _explicitly_closed flag on the agent's MCP client directly if possible
                    if hasattr(tool_agent, '_tools') and tool_agent._tools is not None:
                        if hasattr(tool_agent._tools, '_mcp_client') and tool_agent._tools._mcp_client is not None:
                            tool_agent._tools._mcp_client._explicitly_closed = True
                            print_info(f"Marked agent MCP client as explicitly closed")
                    
                    # Now explicitly close the agent-specific MCP session through the server
                    agent_session_id = f"agent-{tool_agent.id}"
                    from enterprise_ai.mcp.server import get_mcp_server
                    mcp_server = get_mcp_server()
                    await mcp_server.close_session(agent_session_id)
                    print_info(f"Closed agent MCP session: {agent_session_id}")
            
            # Then close the main MCP session
            # Set the explicitly_closed flag first to avoid warnings during garbage collection
            mcp_client._explicitly_closed = True
            await mcp_client.close()
            print_info("Closed MCP session and cleaned up resources")
        except Exception as e:
            print_error(f"Error during cleanup: {e}")
        finally:
            separator()

if __name__ == "__main__":
    asyncio.run(test_agent_with_tools())