#!/usr/bin/env python
"""
Model Parameter Debugging Script

This script specifically tests model_params handling in the agent factory.
"""

import asyncio
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger
from enterprise_ai.llm.providers.ollama import OllamaProvider
from examples.notebooks.utils import (
    setup_project_path, print_title, print_section, print_info, print_success, print_error
)

# Set up project path and logger
setup_project_path()
logger = get_logger("model_debug")

async def test_model_params():
    """Test how model parameters are handled in create_agent."""
    print_title("TESTING MODEL PARAMETER PASSING")
    
    # Direct provider test
    print_section("1. Direct OllamaProvider creation")
    try:
        smollm2_provider = OllamaProvider(model_name="smollm2", timeout=300.0)
        print_info(f"Direct provider created with model: {smollm2_provider.model_name}")
        
        llama32_provider = OllamaProvider(model_name="llama3.2", timeout=300.0)
        print_info(f"Direct provider created with model: {llama32_provider.model_name}")
    except Exception as e:
        print_error(f"Direct provider creation failed: {e}")
    
    # Factory test with model_params
    print_section("2. Testing create_agent with model_params")
    try:
        # Create with smollm2
        smollm2_agent = create_agent(
            agent_type="llm", 
            name="SmollmAgent",
            llm_provider_name="ollama",
            model_params={"model_name": "smollm2", "timeout": 300.0}
        )
        print_info(f"SmollmAgent provider model: {smollm2_agent._llm_provider.model_name}")
        
        # Create with llama3.2
        llama32_agent = create_agent(
            agent_type="llm", 
            name="LlamaAgent",
            llm_provider_name="ollama",
            model_params={"model_name": "llama3.2", "timeout": 300.0}
        )
        print_info(f"LlamaAgent provider model: {llama32_agent._llm_provider.model_name}")
        
        print_success("Model parameters correctly passed to agents!")
    except Exception as e:
        print_error(f"Agent creation failed: {e}")

    # Try a different approach with kwargs
    print_section("3. Testing create_agent with direct kwargs")
    try:
        kwargs_agent = create_agent(
            agent_type="llm", 
            name="KwargsAgent",
            llm_provider_name="ollama",
            model_name="llama3.2",  # Direct parameter
            timeout=300.0           # Direct parameter
        )
        print_info(f"KwargsAgent provider model: {kwargs_agent._llm_provider.model_name}")
        
        print_success("Direct kwargs approach works!")
    except Exception as e:
        print_error(f"Kwargs approach failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_model_params())