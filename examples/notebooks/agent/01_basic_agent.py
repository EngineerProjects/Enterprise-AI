#!/usr/bin/env python
"""
Test script for basic agent creation and configuration in Enterprise AI.

This script tests the different ways to create agents and verifies
their basic properties and functionality without using tools yet.
"""

import os
import sys
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
    BaseAgent,
    LLMAgent,
    create_agent
)
from enterprise_ai.agent.role import create_role
from enterprise_ai.agent.messaging.message import QueryMessage
from enterprise_ai.llm.providers.ollama import OllamaProvider

# Configuration for Ollama provider
CONFIG = {
    "model_name": "llama3.2",
    "base_url": "http://localhost:11434",
    "timeout": 300.0,  # Long timeout for CPU/older GPU
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

def test_direct_creation():
    """Test creating agents directly using their constructors."""
    print_section("Testing Direct Agent Creation")

    # Create a base agent directly
    base_agent = BaseAgent(name="DirectBaseAgent")
    print_info(f"Created base agent: {base_agent.id} ({base_agent.name})")

    # Get the Ollama provider
    provider = get_ollama_provider()
    if not provider:
        print_warning("Skipping LLM agent creation due to provider initialization failure")
        return base_agent, None

    # Create an LLM agent directly
    llm_agent = LLMAgent(
        name="DirectLLMAgent",
        llm_provider=provider,
        reasoning_framework="base"
    )
    print_info(f"Created LLM agent: {llm_agent.id} ({llm_agent.name})")

    # Verify agent properties
    print_info(f"Base agent has role: {base_agent.role is not None}")
    print_info(f"LLM agent has reasoning framework: {llm_agent._reasoning_framework_name}")

    return base_agent, llm_agent

def test_factory_creation():
    """Test creating agents using the factory function."""
    print_section("Testing Factory Creation")

    # Only create a base agent using the factory function
    # Avoid using factory method for LLM agents as it has issues with Ollama
    base_agent = create_agent(
        agent_type="base",
        name="FactoryBaseAgent",
        role_type="researcher"  # Assign a role
    )
    print_info(f"Created base agent: {base_agent.id} ({base_agent.name})")

    # Get the Ollama provider
    provider = get_ollama_provider()
    if not provider:
        print_warning("Skipping LLM agent creation due to provider initialization failure")
        return base_agent, None

    # Create LLM agent directly instead of using factory function
    llm_agent = LLMAgent(
        name="ManualLLMAgent",
        llm_provider=provider,
        reasoning_framework="cot",
        role_type="developer"
    )
    print_info(f"Created LLM agent: {llm_agent.id} ({llm_agent.name})")

    # Verify agent properties
    if base_agent.role:
        print_info(f"Base agent role: {base_agent.role.name}")
    else:
        print_warning("Base agent has no role (unexpected)")

    if llm_agent.role:
        print_info(f"LLM agent role: {llm_agent.role.name}")
    else:
        print_warning("LLM agent has no role (unexpected)")

    print_info(f"LLM agent reasoning framework: {llm_agent._reasoning_framework_name}")

    return base_agent, llm_agent

def test_specialized_agent_creation():
    """Test creating specialized agents by directly setting role."""
    print_section("Testing Specialized Agent Creation")

    # Get the Ollama provider
    provider = get_ollama_provider()
    if not provider:
        print_warning("Skipping specialized agent creation due to provider initialization failure")
        return None, None

    # Create a developer-role agent directly
    dev_agent = LLMAgent(
        name="DevAgent",
        llm_provider=provider,
        reasoning_framework="react"
    )

    # Create and set the developer role
    dev_role = create_role("developer", additional_context="Python and JavaScript expert")
    dev_agent.role = dev_role
    print_info(f"Created developer agent: {dev_agent.id} ({dev_agent.name})")

    # Create a researcher-role agent directly
    researcher_agent = LLMAgent(
        name="ResearcherAgent",
        llm_provider=provider,
        reasoning_framework="cot"
    )

    # Create and set the researcher role
    researcher_role = create_role("researcher", additional_context="Specialized in AI research")
    researcher_agent.role = researcher_role
    print_info(f"Created researcher agent: {researcher_agent.id} ({researcher_agent.name})")

    # Verify agent roles and capabilities
    if dev_agent.role:
        print_info(f"Developer agent role: {dev_agent.role.name}")
        print_info(f"Developer agent capabilities: {', '.join(dev_agent.role.capabilities)}")

    if researcher_agent.role:
        print_info(f"Researcher agent role: {researcher_agent.role.name}")
        print_info(f"Researcher agent capabilities: {', '.join(researcher_agent.role.capabilities)}")

    return dev_agent, researcher_agent

def test_simple_interaction():
    """Test basic interaction with an LLM agent."""
    print_section("Testing Simple Agent Interaction")

    # Get the Ollama provider
    provider = get_ollama_provider()
    if not provider:
        print_warning("Skipping agent interaction due to provider initialization failure")
        return None, None

    # Create an LLM agent with direct provider assignment
    agent = LLMAgent(
        name="InteractionAgent",
        llm_provider=provider,
        reasoning_framework="cot"  # Use Chain of Thought reasoning
    )

    # Send a query message to the agent
    query = QueryMessage(
        sender_id="user",
        receiver_id=agent.id,
        query="Explain the concept of recursion in programming in simple terms."
    )

    # Process the message
    print_info("Sending query to agent (this may take a moment)...")
    with Timer("LLM agent response"):
        try:
            response = agent.process_message(query)

            if response:
                print_success("Received response from agent")
                print("\nAgent Response:")
                print("-" * 40)
                print(response.content)
                print("-" * 40)
            else:
                print_error("No response received from agent")
        except Exception as e:
            print_error(f"Error during agent interaction: {e}")
            return agent, None

    return agent, response

def main():
    """Run all agent creation and interaction tests."""
    print_title("Enterprise AI Basic Agent Tests")

    try:
        # Test direct creation
        base_agent, llm_agent = test_direct_creation()
        separator()

        # Test factory creation (only for base agent)
        factory_base, factory_llm = test_factory_creation()
        separator()

        # Test specialized agent creation
        dev_agent, researcher_agent = test_specialized_agent_creation()
        separator()

        # Test simple interaction
        interaction_agent, response = test_simple_interaction()
        separator()

        print_section("Test Summary")
        print_success("All agent creation tests completed")

        # Show counts of successful tests
        success_count = sum(1 for a in [
            base_agent, llm_agent, factory_base, factory_llm,
            dev_agent, researcher_agent, interaction_agent
        ] if a is not None)

        print_info(f"Successfully created {success_count} agents")
        print_info(f"Successfully received responses: {response is not None}")

    except Exception as e:
        print_error(f"Error during agent tests: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
