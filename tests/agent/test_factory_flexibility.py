#!/usr/bin/env python
"""
Test Agent Factory Flexibility

This script tests the improved flexibility in the agent factory module, allowing
for different ways to create and configure agents with LLM providers and roles.
"""

import asyncio
import pytest
from typing import Any, Dict, List, Optional

# Import core components
from enterprise_ai.agent.core import create_agent, BaseAgent, LLMAgent
from enterprise_ai.agent.role import create_role
from enterprise_ai.llm import create_provider
from enterprise_ai.llm.providers.ollama import OllamaProvider


async def test_direct_llm_provider():
    """Test creating an agent with a direct LLM provider object."""
    # Create LLM provider directly
    ollama_provider = OllamaProvider(model_name="smollm2", timeout=300.0)
    
    # Create agent with direct provider
    agent = create_agent(
        agent_type="llm",
        name="DirectProviderAgent",
        llm_provider=ollama_provider
    )
    
    # Verify the provider is correctly set
    assert agent._llm_provider is ollama_provider
    assert agent._llm_provider.model_name == "smollm2"
    
    # Clean up
    await agent.terminate()


async def test_llm_provider_kwargs():
    """Test creating an agent with provider kwargs."""
    # Create agent with provider kwargs
    agent = create_agent(
        agent_type="llm",
        name="ProviderKwargsAgent",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": 300.0}
    )
    
    # Verify the provider is correctly set
    assert agent._llm_provider is not None
    assert agent._llm_provider.model_name == "smollm2"
    
    # Clean up
    await agent.terminate()


async def test_model_params_backward_compatibility():
    """Test backward compatibility with model_params."""
    # Create agent with model_params
    agent = create_agent(
        agent_type="llm",
        name="ModelParamsAgent",
        llm_provider_name="ollama",
        model_params={"model_name": "smollm2", "timeout": 300.0}
    )
    
    # Verify the provider is correctly set
    assert agent._llm_provider is not None
    assert agent._llm_provider.model_name == "smollm2"
    
    # Clean up
    await agent.terminate()


async def test_direct_role_object():
    """Test creating an agent with a direct role object."""
    # Create custom role
    custom_role = create_role(
        "custom",
        name="Test Role",
        description="Role for testing",
        capabilities=["testing"],
        instructions="This is a test role."
    )
    
    # Create agent with direct role
    agent = create_agent(
        agent_type="llm",
        name="DirectRoleAgent",
        role=custom_role,
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": 300.0}
    )
    
    # Verify the role is correctly set
    assert agent._role is custom_role
    
    # Clean up
    await agent.terminate()


async def test_combined_approach():
    """Test creating an agent with both direct provider and role."""
    # Create LLM provider directly
    ollama_provider = OllamaProvider(model_name="smollm2", timeout=300.0)
    
    # Create custom role
    custom_role = create_role(
        "custom",
        name="Combined Test Role",
        description="Role for combined testing",
        capabilities=["testing"],
        instructions="This is a combined test role."
    )
    
    # Create agent with both direct objects
    agent = create_agent(
        agent_type="llm",
        name="CombinedAgent",
        role=custom_role,
        llm_provider=ollama_provider
    )
    
    # Verify both objects are correctly set
    assert agent._llm_provider is ollama_provider
    assert agent._role is custom_role
    
    # Clean up
    await agent.terminate()


if __name__ == "__main__":
    asyncio.run(test_direct_llm_provider())
    asyncio.run(test_llm_provider_kwargs())
    asyncio.run(test_model_params_backward_compatibility())
    asyncio.run(test_direct_role_object())
    asyncio.run(test_combined_approach())
    print("All tests passed!")
