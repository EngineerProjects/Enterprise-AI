#!/usr/bin/env python
"""
Agent Introspection

This script demonstrates how to use agent introspection capabilities
to examine and understand agent behavior and performance.
"""

import asyncio
import os
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
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_introspection_test")

# Set a high timeout for our slow devices
TIMEOUT = 1200  # 20 minutes for very slow GPU/CPU

async def test_agent_introspection():
    """Test agent introspection capabilities."""
    print_title("TESTING AGENT INTROSPECTION")
    
    # Set environment variable for Ollama timeout
    os.environ["ENTERPRISE_AI_OLLAMA_TIMEOUT"] = str(TIMEOUT)

    # 1. Create an agent with different capabilities
    print_section("1. Creating an agent with various capabilities")
    
    agent = create_agent(
        agent_type="llm",
        name="Introspectable Agent",
        role_type="researcher",
        reasoning_framework="react",
        use_tools=True,
        enable_mcp=True,
        tool_categories=["research", "utility"],
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": TIMEOUT}
    )
    
    print_success(f"Created agent: {agent.name} (ID: {agent.id})")
    
    # 2. Examine agent status
    print_section("2. Examining agent status")
    
    status = agent.get_status()
    print_info("Agent Status:")
    for key, value in status.items():
        # Format complex nested structures
        if isinstance(value, dict):
            print_info(f"  {key}:")
            for subkey, subvalue in value.items():
                print_info(f"    {subkey}: {subvalue}")
        else:
            print_info(f"  {key}: {value}")
    
    # 3. Get agent capabilities
    print_section("3. Getting agent capabilities")
    
    if hasattr(agent, "get_capabilities"):
        capabilities = agent.get_capabilities()
        print_info("Agent Capabilities:")
        for category, items in capabilities.items():
            print_info(f"  {category}:")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        print_info(f"    - {item}")
                    elif isinstance(item, dict):
                        for k, v in item.items():
                            print_info(f"    - {k}: {v}")
            elif isinstance(items, dict):
                for k, v in items.items():
                    print_info(f"    - {k}: {v}")
    else:
        print_info("Agent does not support capability introspection")
    
    # 4. Get agent metrics
    print_section("4. Getting agent performance metrics")
    
    # Ensure agent.tools_manager has MCP initialized if needed
    if hasattr(agent, "_tools") and agent._tools:
        if hasattr(agent, "initialize_mcp") and callable(getattr(agent, "initialize_mcp")):
            await agent.initialize_mcp()
        elif hasattr(agent._tools, "_mcp_config") and agent._tools._mcp_config and agent._tools._mcp_config.get("enable"):
            await agent._tools.enable_mcp(
                tool_categories=agent._tools._mcp_config.get("categories"),
                tool_names=agent._tools._mcp_config.get("names")
            )
    
    if hasattr(agent, "get_metrics"):
        # Process a request to generate some metrics
        await agent.aprocess_message("What is quantum computing?")
        
        metrics = agent.get_metrics()
        print_info("Agent Metrics:")
        for key, value in metrics.items():
            print_info(f"  {key}: {value}")
    else:
        print_info("Agent does not support metrics introspection")
    
    # 5. Get available tools
    print_section("5. Getting available tools")
    
    if hasattr(agent, "get_tools_description"):
        tools_description = agent.get_tools_description()
        print_info("Available Tools:")
        print_info(tools_description)
    else:
        print_info("Agent does not support tool introspection")
    
    # Properly clean up and close MCP session
    try:
        # Set _explicitly_closed flag on the agent's MCP client
        if hasattr(agent, "_tools") and agent._tools is not None:
            if hasattr(agent._tools, "_mcp_client") and agent._tools._mcp_client is not None:
                agent._tools._mcp_client._explicitly_closed = True
                
        # Terminate the agent properly
        if hasattr(agent, "terminate"):
            await agent.terminate()
            
        # Close the agent-specific MCP session through the server
        agent_session_id = f"agent-{agent.id}"
        from enterprise_ai.mcp.server import get_mcp_server
        mcp_server = get_mcp_server()
        await mcp_server.close_session(agent_session_id)
    except Exception as e:
        print_error(f"Error during cleanup: {e}")
    
    print_success("All agent introspection tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_agent_introspection())