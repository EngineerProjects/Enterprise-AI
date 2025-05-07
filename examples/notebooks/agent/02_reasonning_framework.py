#!/usr/bin/env python
"""
Test script for different reasoning frameworks in Enterprise AI.

This script tests the various reasoning frameworks available for agents,
examining how they structure their thinking and utilize tools.
"""

import os
import sys
import copy
from typing import Any, Dict, List, Optional, Tuple

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
    get_framework,
    list_frameworks,
    get_framework_descriptions
)
from enterprise_ai.agent.message import QueryMessage, ResponseMessage
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.tool.utility.terminate import Terminate

# Configure logging
logger = get_logger("reasoning_test")

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

def list_available_frameworks():
    """List and describe available reasoning frameworks."""
    print_section("Available Reasoning Frameworks")

    try:
        # Get all available frameworks
        frameworks = list_frameworks()
        print_info(f"Found {len(frameworks)} reasoning frameworks:")

        # Get framework descriptions
        descriptions = get_framework_descriptions()

        # Print each framework with its description
        for name in frameworks:
            description = descriptions.get(name, "No description available")
            framework = get_framework(name)
            tools_required = framework.requires_tools
            function_calling = framework.supports_function_calling()

            print(f"\n- {name.upper()}:")
            print(f"  Description: {description}")
            print(f"  Requires tools: {tools_required}")
            print(f"  Supports function calling: {function_calling}")

    except Exception as e:
        print_error(f"Error listing frameworks: {e}")

def create_sample_tools():
    """Create a list of sample tools for testing."""
    tools = []
    try:
        tools.append(PythonExecute())
        tools.append(Terminate())
    except Exception as e:
        print_warning(f"Could not create sample tools: {e}")
    return tools

def test_reasoning_framework(
    framework_name: str,
    query_text: str,
    add_tools: bool = False
) -> Tuple[Optional[LLMAgent], Optional[ResponseMessage]]:
    """Test a specific reasoning framework with a standard query.

    Args:
        framework_name: Name of the reasoning framework to test
        query_text: Text of the query to send to the agent
        add_tools: Whether to add tools to the agent

    Returns:
        Tuple of (agent, response) or (None, None) if test fails
    """
    print_section(f"Testing {framework_name.upper()} Reasoning")

    # Get the Ollama provider
    provider = get_ollama_provider()
    if not provider:
        print_warning(f"Skipping {framework_name} test due to provider initialization failure")
        return None, None

    try:
        # Get framework to check if it requires tools
        framework = get_framework(framework_name)
        requires_tools = framework.requires_tools

        if requires_tools and not add_tools:
            print_warning(f"Framework {framework_name} requires tools but add_tools=False")
            print_info("Enabling tools for this test")
            add_tools = True

        # Create an agent with the specified reasoning framework
        agent = LLMAgent(
            name=f"{framework_name.capitalize()}Agent",
            llm_provider=provider,
            reasoning_framework=framework_name,
            use_tools=add_tools  # Now we're respecting the add_tools parameter
        )

        # Add tools if needed after agent initialization
        if add_tools and requires_tools:
            sample_tools = create_sample_tools()
            for tool in sample_tools:
                agent.add_tool(tool)
            print_info(f"Added {len(sample_tools)} tools to agent for {framework_name} framework")
        else:
            print_info(f"Created agent with {framework_name} reasoning framework (no tools)")

        # Create query message
        query = QueryMessage(
            sender_id="user",
            receiver_id=agent.id,
            query=query_text
        )

        # Process the message
        print_info(f"Sending query to {framework_name} agent (this may take a moment)...")
        with Timer(f"{framework_name} response"):
            # Always use the agent's process_message method, which will properly use the framework
            response = agent.process_message(query)

        if response:
            print_success("Received response")
            print("\nAgent Response:")
            print("-" * 80)
            print(response.content)
            print("-" * 80)

            # Analyze response characteristics
            analyze_response_characteristics(framework_name, response.content)

            return agent, response
        else:
            print_error("No response received")
            return agent, None

    except Exception as e:
        print_error(f"Error testing {framework_name} reasoning: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def analyze_response_characteristics(framework_name: str, response_text: str) -> None:
    """Analyze the response to check for characteristics of the reasoning framework.

    Args:
        framework_name: Name of the reasoning framework
        response_text: Text of the response to analyze
    """
    print_info("Response Characteristics Analysis:")

    # Check length
    print_info(f"Response length: {len(response_text)} characters")

    # Framework-specific characteristics
    if framework_name == "cot":
        # Check for Chain of Thought markers
        has_thinking = "thinking" in response_text.lower() or "step " in response_text.lower()
        has_steps = any(f"step {i}" in response_text.lower() for i in range(1, 6))
        print_info(f"Contains explicit thinking steps: {has_thinking or has_steps}")

    elif framework_name == "react":
        # Check for ReAct markers
        has_thought = "thought:" in response_text.lower()
        has_action = "action:" in response_text.lower()
        has_observation = "observation:" in response_text.lower()
        print_info(f"Contains ReAct pattern: Thought: {has_thought}, Action: {has_action}, Observation: {has_observation}")

    elif framework_name == "swe":
        # Check for SWE markers
        has_design = "design" in response_text.lower()
        has_implementation = "implement" in response_text.lower() or "code" in response_text.lower()
        has_testing = "test" in response_text.lower()
        print_info(f"Contains SWE elements: Design: {has_design}, Implementation: {has_implementation}, Testing: {has_testing}")

    # Check for tool usage in any response
    has_tool_usage = "tool" in response_text.lower() and ("use" in response_text.lower() or "using" in response_text.lower())
    print_info(f"References tool usage: {has_tool_usage}")

def test_base_reasoning():
    """Test base reasoning framework."""
    return test_reasoning_framework(
        "base",
        "Calculate the sum of the first 10 prime numbers.",
        add_tools=False
    )

def test_cot_reasoning():
    """Test Chain of Thought reasoning framework."""
    return test_reasoning_framework(
        "cot",
        "Calculate the sum of the first 10 prime numbers. Walk me through your calculation step by step.",
        add_tools=False
    )

def test_react_reasoning():
    """Test ReAct reasoning framework."""
    return test_reasoning_framework(
        "react",
        "I need to find the prime numbers between 1 and 30, and then calculate their sum.",
        add_tools=True  # Now we'll actually use tools with ReAct
    )

def test_tool_cot_reasoning():
    """Test Tool-augmented Chain of Thought reasoning framework."""
    return test_reasoning_framework(
        "tool_cot",
        "I need to calculate the sum of the first 10 prime numbers. Use tools if needed.",
        add_tools=True  # Now we'll actually use tools with Tool-CoT
    )

def test_swe_reasoning():
    """Test Software Engineering reasoning framework."""
    return test_reasoning_framework(
        "swe",
        "Write a function to find all prime numbers up to n, and then calculate their sum.",
        add_tools=True  # Now we'll actually use tools with SWE
    )

def test_mcp_reasoning():
    """Test Model Context Protocol reasoning framework."""
    return test_reasoning_framework(
        "mcp",
        "I need to calculate the sum of the first 10 prime numbers. Use any available tools.",
        add_tools=True  # Now we'll actually use tools with MCP
    )

def test_reasoning_comparison():
    """Test the same query across different reasoning frameworks to compare outputs."""
    print_section("Reasoning Framework Comparison")

    # Define a standard query to test across frameworks
    standard_query = "I need to calculate the factorial of 5."

    # Test with minimal frameworks for comparison
    frameworks_to_compare = ["base", "cot", "react"]

    results = {}

    for framework in frameworks_to_compare:
        print_info(f"Testing {framework} with standard query...")

        # Create agent and send query - use add_tools=True for ReAct
        add_tools = framework == "react"
        agent, response = test_reasoning_framework(
            framework,
            standard_query,
            add_tools=add_tools
        )

        if response:
            # Store just a summary of the response
            response_preview = response.content[:200] + "..." if len(response.content) > 200 else response.content
            results[framework] = response_preview

    # Print comparison
    print_info("\nComparison of responses:")
    for framework, response in results.items():
        print(f"\n{framework.upper()}:")
        print("-" * 40)
        print(response)
        print("-" * 40)

def main():
    """Run all reasoning framework tests."""
    print_title("Enterprise AI Reasoning Framework Tests")

    try:
        # List available frameworks
        list_available_frameworks()
        separator()

        # Test each reasoning framework
        test_base_reasoning()
        separator()

        test_cot_reasoning()
        separator()

        # Test the tool-based frameworks properly
        test_react_reasoning()
        separator()

        test_tool_cot_reasoning()
        separator()

        test_swe_reasoning()
        separator()

        test_mcp_reasoning()
        separator()

        # Compare reasoning frameworks with the same query
        test_reasoning_comparison()
        separator()

        print_section("Test Summary")
        print_success("All reasoning framework tests completed")

    except Exception as e:
        print_error(f"Error during reasoning framework tests: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
