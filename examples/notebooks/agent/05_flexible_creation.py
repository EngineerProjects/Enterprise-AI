#!/usr/bin/env python
"""
Enhanced Agent Creation and Configuration

This script demonstrates the improved flexibility in creating and configuring
agents with direct LLM providers and roles.
"""

import asyncio
import sys
import os
from typing import Any, Dict, List, Optional

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
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.agent.role import create_role
from enterprise_ai.llm import create_provider

# Configure logger
logger = get_logger("agent_flexible_test")

async def test_flexible_agent_creation():
    """Test the enhanced agent creation and configuration."""
    print_title("TESTING ENHANCED AGENT CREATION")

    # 1. Create agent with direct LLM provider
    print_section("1. Creating agent with direct LLM provider")

    # Create LLM provider first
    try:
        ollama_provider = OllamaProvider(model_name="smollm2", timeout=300.0)
        print_success("Created Ollama provider directly")

        # Create agent with the provider
        direct_provider_agent = create_agent(
            agent_type="llm",
            name="DirectProviderAgent",
            llm_provider=ollama_provider,
            role_type="researcher"
        )

        print_success(f"Created agent with direct provider: {direct_provider_agent.name}")
        print_info(f"Using model: {direct_provider_agent._llm_provider.model_name}")

        # Test the agent
        message = "Hello, who are you?"
        print_info(f"Testing with message: '{message}'")

        with Timer("Agent Response"):
            response = await direct_provider_agent.aprocess_message(message)

        print_info(f"Response: '{response.content}'")

    except Exception as e:
        print_error(f"Error creating agent with direct provider: {e}")

    # 2. Create agent with direct role
    print_section("2. Creating agent with direct role")

    try:
        # Create a custom role
        custom_role = create_role(
            "custom",
            name="Technical Writer",
            description="Specialized in technical writing and documentation",
            capabilities=["technical_writing", "documentation", "content_creation"],
            instructions=(
                "You are a technical writer specializing in clear, concise documentation. "
                "Focus on making complex topics accessible to all readers. "
                "Use examples, diagrams, and step-by-step instructions when appropriate."
            )
        )
        print_success("Created custom Technical Writer role")

        # Create agent with the role
        direct_role_agent = create_agent(
            agent_type="llm",
            name="TechnicalWriterAgent",
            role=custom_role,
            llm_provider_name="ollama",
            llm_provider_kwargs={"model_name": "smollm2", "timeout": 300.0}
        )

        print_success(f"Created agent with direct role: {direct_role_agent.name}")

        # Test the agent
        message = "Explain how to use a REST API."
        print_info(f"Testing with message: '{message}'")

        with Timer("Role-specific Response"):
            response = await direct_role_agent.aprocess_message(message)

        print_info(f"Response: '{response.content}'")

    except Exception as e:
        print_error(f"Error creating agent with direct role: {e}")

    # 3. Combine both approaches
    print_section("3. Creating agent with both direct provider and role")

    try:
        # Create LLM provider
        llama_provider = OllamaProvider(model_name="llama3.2", timeout=500.0)
        print_success("Created Llama provider directly")

        # Create a custom role
        data_analyst_role = create_role(
            "custom",
            name="Data Analyst",
            description="Specialized in data analysis and visualization",
            capabilities=["data_analysis", "visualization", "statistics"],
            instructions=(
                "You are a data analyst specializing in interpreting complex datasets. "
                "When addressing problems, think step-by-step about the data cleaning, "
                "analysis, and visualization approach. Always consider statistical "
                "validity and potential biases in your analysis."
            )
        )
        print_success("Created custom Data Analyst role")

        # Create agent with both
        combined_agent = create_agent(
            agent_type="llm",
            name="DataAnalystLlama",
            role=data_analyst_role,
            llm_provider=llama_provider
        )

        print_success(f"Created combined agent: {combined_agent.name}")
        print_info(f"Using model: {combined_agent._llm_provider.model_name}")

        # Test the agent
        message = "What steps would you take to analyze customer purchase patterns?"
        print_info(f"Testing with message: '{message}'")

        with Timer("Combined Agent Response"):
            response = await combined_agent.aprocess_message(message)

        print_info(f"Response: '{response.content}'")

    except Exception as e:
        print_error(f"Error creating combined agent: {e}")

    # Clean up resources
    print_section("4. Cleaning up resources")
    try:
        await direct_provider_agent.terminate()
        await direct_role_agent.terminate()
        await combined_agent.terminate()
        print_success("All agents terminated properly")
    except Exception as e:
        print_error(f"Error during cleanup: {e}")

    separator()
    print_success("All tests completed!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_flexible_agent_creation())
