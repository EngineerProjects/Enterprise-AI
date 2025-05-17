#!/usr/bin/env python
"""
Agent Builder Pattern

This script demonstrates how to use the AgentBuilder pattern to create
customized agents with fluent API.
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
from enterprise_ai.agent.core.factory import AgentBuilder
from enterprise_ai.llm.providers.factory import create_provider
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_builder_test")

async def test_agent_builder():
    """Test creating agents using the builder pattern."""
    print_title("TESTING AGENT BUILDER PATTERN")
    
    # Set a high timeout for our slow devices
    TIMEOUT = 1200  # 20 minutes for very slow GPU/CPU
    
    # Set environment variable for Ollama timeout
    os.environ["ENTERPRISE_AI_OLLAMA_TIMEOUT"] = str(TIMEOUT)

    # 1. Create a simple agent with the builder
    print_section("1. Creating a simple agent with builder")
    
    basic_agent = (
        AgentBuilder()
        .with_type("llm")
        .with_name("Simple Builder Agent")
        .with_reasoning("cot")
        .with_llm_provider_name("ollama", model_name="smollm2", timeout=1200)
        .build()
    )
    
    print_success(f"Created basic agent: {basic_agent.name} (ID: {basic_agent.id})")
    
    # Test the basic agent
    query = "What are the benefits of using a builder pattern in software design?"
    print_info(f"Query: '{query}'")
    
    with Timer("Basic Agent Response"):
        response = await basic_agent.aprocess_message(query)
    
    print_info(f"Response snippet: '{response.content}'")
    
    # 2. Creating a complex agent with builder
    print_section("2. Creating a complex agent with builder")
    
    complex_agent = (
        AgentBuilder()
        .with_type("llm")
        .with_name("Complex Builder Agent")
        .with_role("developer", additional_context="Specialized in Python backend development")
        .with_reasoning("swe")
        .with_tools(True)
        .with_tool_categories(["development", "utility"])
        .with_llm_provider_name("ollama", model_name="smollm2", timeout=1200)
        .with_param("temperature", 0.7)
        .build()
    )
    
    print_success(f"Created complex agent: {complex_agent.name} (ID: {complex_agent.id})")
    
    # Test the complex agent
    query = "What's the best way to implement a web API for a machine learning model?"
    print_info(f"Query: '{query}'")
    
    with Timer("Complex Agent Response"):
        response = await complex_agent.aprocess_message(query)
    
    print_info(f"Response snippet: '{response.content}'")
    
    # 3. Create an agent with custom configuration
    print_section("3. Creating an agent with custom configuration")
    
    custom_agent = (
        AgentBuilder()
        .with_type("llm")
        .with_name("Custom Config Agent")
        .with_reasoning("react")
        .with_tools(True)
        .with_tool_names(["calculator", "web_search"])
        .with_llm_provider_name("ollama", model_name="smollm2", timeout=1200)
        .with_param("max_tokens", 1000)
        .with_param("top_p", 0.9)
        .build()
    )
    
    print_success(f"Created custom agent: {custom_agent.name} (ID: {custom_agent.id})")
    
    print_info("Inspecting agent configuration:")
    config = custom_agent.get_config() if hasattr(custom_agent, "get_config") else {}
    for key, value in config.items():
        print_info(f"  {key}: {value}")
    
    print_success("All agent builder tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_agent_builder())