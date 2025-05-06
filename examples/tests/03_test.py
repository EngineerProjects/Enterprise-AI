#!/usr/bin/env python
"""
Test script for tool discovery and integration in Enterprise AI.

This script tests how agents discover, integrate and manage tools,
including dynamic tool discovery, categorization, and MCP integration.
"""

import os
import sys
import asyncio
from typing import Any, Dict, List, Optional, Tuple, cast

# Import common utilities
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
project_root = setup_project_path()

# Import Enterprise AI components
from enterprise_ai.agent import (
    LLMAgent,
    create_agent,
    create_tool_agent
)
from enterprise_ai.agent.message import QueryMessage
from enterprise_ai.agent.tooling import AgentToolManager
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.tool.execution import PythonExecute, Bash
from enterprise_ai.tool.file import FileEditor
from enterprise_ai.tool.planning import PlanningTool
from enterprise_ai.tool.research import WebSearch, DeepResearch
from enterprise_ai.tool.utility import Terminate
from enterprise_ai.mcp.client import AgentMCPClient
from enterprise_ai.logger import get_logger

# Configure logging
logger = get_logger("tool_discovery_test")

# Configuration for Ollama provider
CONFIG = {
    "model_name": "llama3.2",  # Use any model available in your Ollama setup
    "base_url": "http://localhost:11434",
    "timeout": 1000.0,  # Long timeout for CPU/older GPU
}

def get_ollama_provider():
    """Create and return an Ollama provider with the configured settings."""
    try:
        provider = OllamaProvider(
            model_name=CONFIG["model_name"],
            base_url=CONFIG["base_url"],
            timeout=CONFIG["timeout"]
        )
        print_success(f"Created Ollama provider with model: {CONFIG['model_name']}")
        return provider
    except Exception as e:
        print_error(f"Failed to create Ollama provider: {e}")
        print_warning("Make sure Ollama is running and the model is available")
        return None

def test_available_tools():
    """Test discovery of available tools and categories."""
    print_section("Available Tools")
    
    registry = get_registry()
    
    # Get all tools
    all_tools = registry.get_all_tool_classes()
    print_info(f"Found {len(all_tools)} tools in the registry")
    
    # Get categories
    categories = registry.get_all_category_names()
    print_info(f"Found {len(categories)} tool categories")
    
    # Print tools by category
    for category in sorted(categories):
        tools = registry.get_tools_by_category(category)
        print_info(f"\n- Category: {category} ({len(tools)} tools)")
        
        for tool_cls in tools:
            # Get information from class directly without instantiation
            name = getattr(tool_cls, "name", tool_cls.__name__)
            desc = getattr(tool_cls, "description", "No description available")
            
            # Try instantiation only to verify
            try:
                # Create an instance with explicit parameters
                tool_instance = tool_cls(
                    name=name,
                    description=desc,
                    parameters=getattr(tool_cls, "parameters", {})
                )
                # Update from instance if successful
                if hasattr(tool_instance, "name"):
                    name = tool_instance.name
                if hasattr(tool_instance, "description"):
                    desc = tool_instance.description
            except Exception as e:
                print_warning(f"  Could not instantiate {name}: {e}")
            
            if len(desc) > 100:
                desc = desc[:97] + "..."
            print_info(f"  • {name}: {desc}")
    
    return all_tools, categories

def test_agent_tool_manager():
    """Test the AgentToolManager for basic tool operations."""
    print_section("Agent Tool Manager")
    
    # Create a tool manager for a test agent
    agent_id = "test-agent-001"
    tool_manager = AgentToolManager(agent_id)
    print_success(f"Created tool manager for agent: {agent_id}")
    
    # Test adding tools
    tools_to_add = [
        PythonExecute(),
        Bash(),
        FileEditor(),
        PlanningTool(),
        Terminate()
    ]
    
    for tool in tools_to_add:
        tool_manager.add_tool(tool)
    
    # List available tools
    available_tools = tool_manager.list_tools()
    print_info(f"Added {len(available_tools)} tools to agent:")
    for tool_name in available_tools:
        print_info(f"  • {tool_name}")
    
    # Test tool descriptions
    tool_descriptions = tool_manager.get_formatted_tool_descriptions()
    desc_length = len(tool_descriptions)
    print_info(f"Tool descriptions format (showing first 200 chars of {desc_length} total):")
    print_info(f"\n{tool_descriptions[:200]}...\n")
    
    # Test removing a tool
    if available_tools:
        tool_to_remove = available_tools[0]
        success = tool_manager.remove_tool(tool_to_remove)
        if success:
            print_success(f"Successfully removed tool: {tool_to_remove}")
        else:
            print_error(f"Failed to remove tool: {tool_to_remove}")
        
        # Verify removal
        updated_tools = tool_manager.list_tools()
        print_info(f"Remaining tools: {len(updated_tools)}")
    
    return tool_manager

async def test_mcp_integration():
    """Test MCP integration for dynamic tool discovery."""
    print_section("MCP Integration")
    
    # Create MCP client
    agent_id = "mcp-test-agent"
    print_info(f"Creating MCP client for agent: {agent_id}")
    
    try:
        # Initialize MCP client
        client = AgentMCPClient(agent_id)
        print_success("Created MCP client")
        
        # Test tool discovery
        tools = client.discover_tools()
        print_info(f"Discovered {len(tools)} tools via MCP")
        
        # Test tool categories
        print_info("Testing MCP tool filtering by category")
        categories = ["execution", "utility"]
        await client.update_tools(add_categories=categories)
        filtered_tools = client.discover_tools()
        print_info(f"Filtered to {len(filtered_tools)} tools in categories: {', '.join(categories)}")
        
        # Test specific tool discovery
        print_info("Testing MCP specific tool selection")
        specific_tools = ["python_execute", "bash", "terminate"]
        await client.update_tools(add_tools=specific_tools)
        specific_tools_discovered = client.discover_tools()
        print_info(f"Selected {len(specific_tools_discovered)} specific tools")
        
        # Clean up
        await client.close()
        print_success("MCP client closed")
        return True
    except Exception as e:
        print_error(f"MCP integration test failed: {e}")
        return False

def test_agent_with_tools():
    """Test creating agents with various tool configurations."""
    print_section("Agents with Tools")
    
    # Get LLM provider
    provider = get_ollama_provider()
    if not provider:
        print_warning("Skipping agent with tools test due to provider initialization failure")
        return None
    
    # Test 1: Create agent with specific tools
    print_info("Test 1: Creating agent with specific tools")
    agent = LLMAgent(
        name="ToolTestAgent",
        llm_provider=provider,
        reasoning_framework="react",
        use_tools=True
    )
    
    # Add specific tools
    agent.add_tool(PythonExecute())
    agent.add_tool(PlanningTool())
    agent.add_tool(Terminate())
    
    tools = agent.list_tools()
    print_success(f"Created agent with {len(tools)} specific tools: {', '.join(tools)}")
    
    # Test 2: Create agent with tool categories via factory
    print_info("\nTest 2: Creating agent with tool categories")
    category_agent = create_tool_agent(
        name="CategoryToolAgent",
        tool_categories=["research", "planning"],
        reasoning_framework="react",
        llm_provider=provider,
    )
    
    category_tools = category_agent.list_tools()
    print_success(f"Created agent with tools from categories: {len(category_tools)} tools available")
    
    # Test 3: Create specialized agent
    print_info("\nTest 3: Creating specialized developer agent")
    dev_agent = create_agent(
        agent_type="llm",
        name="DevAgent",
        role_type="developer",
        reasoning_framework="swe",
        use_tools=True,
        tool_categories=["execution", "file"],
        llm_provider=provider
    )
    
    dev_tools = dev_agent.list_tools()
    print_success(f"Created developer agent with {len(dev_tools)} tools")
    
    return agent, category_agent, dev_agent

async def test_tool_query_handling():
    """Test how agents handle queries requiring tools."""
    print_section("Tool Query Handling")
    
    # Get LLM provider
    provider = get_ollama_provider()
    if not provider:
        print_warning("Skipping tool query test due to provider initialization failure")
        return None
    
    # Create agent with Python execution tool
    agent = LLMAgent(
        name="PythonAgent",
        llm_provider=provider,
        reasoning_framework="tool_cot",
        use_tools=True
    )
    
    # Add Python execution tool
    agent.add_tool(PythonExecute())
    print_success("Created agent with Python execution tool")
    
    # Create query that may trigger tool usage
    query = "Can you help me calculate the Fibonacci sequence up to the 10th number?"
    print_info(f"Sending query: {query}")
    
    # Create query message
    query_msg = QueryMessage(
        sender_id="user",
        receiver_id=agent.id,
        query=query
    )
    
    # Process the message
    print_info("Processing query (this may take a moment)...")
    with Timer("Agent response"):
        response = agent.process_message(query_msg)
    
    if response:
        print_success("Received response")
        print("\nAgent Response:")
        print("-" * 80)
        print(response.content)
        print("-" * 80)
        
        # Analyze if tool was used
        tool_usage = "python_execute" in response.content.lower() or "code execution" in response.content.lower()
        print_info(f"Tool usage detected: {tool_usage}")
    else:
        print_error("No response received")
    
    return response

def main():
    """Run all tool discovery and integration tests."""
    print_title("Enterprise AI Tool Discovery and Integration Tests")
    
    try:
        # Test discovery of available tools
        all_tools, categories = test_available_tools()
        separator()
        
        # Test tool manager
        tool_manager = test_agent_tool_manager()
        separator()
        
        # Test agents with tools
        agents = test_agent_with_tools()
        separator()
        
        # Test MCP integration
        mcp_success = asyncio.run(test_mcp_integration())
        separator()
        
        # Test tool query handling
        response = asyncio.run(test_tool_query_handling())
        separator()
        
        # Print test summary
        print_section("Test Summary")
        
        print_info(f"Total tools found: {len(all_tools)}")
        print_info(f"Total tool categories: {len(categories)}")
        
        if agents and isinstance(agents, tuple) and len(agents) == 3:
            agent_tools = sum(len(a.list_tools()) for a in agents if hasattr(a, "list_tools"))
            print_info(f"Tools added to test agents: {agent_tools}")
        
        print_info(f"MCP integration test: {'Successful' if mcp_success else 'Failed'}")
        print_info(f"Tool query handling: {'Successful' if response else 'Failed'}")
        
        print_success("All tool discovery and integration tests completed!")
        
    except Exception as e:
        print_error(f"Tests failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()