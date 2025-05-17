#!/usr/bin/env python
"""
Agent Configuration

This script demonstrates how to configure agents using configuration files
and how to create multiple agents from a single configuration.
"""

import asyncio
import os
import json
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
from enterprise_ai.agent.core import create_agent, create_agents_from_config
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_config_test")

# Set a high timeout for our slow devices
TIMEOUT = 1200  # 20 minutes for very slow GPU/CPU

async def test_agent_configuration():
    """Test agent configuration and creation from config files."""
    print_title("TESTING AGENT CONFIGURATION")
    
    # Set environment variable for Ollama timeout
    os.environ["ENTERPRISE_AI_OLLAMA_TIMEOUT"] = str(TIMEOUT)

    # Create a temporary directory for configuration files
    config_dir = "temp_agent_config"
    os.makedirs(config_dir, exist_ok=True)
    
    try:
        # 1. Create a single agent from a config file
        print_section("1. Creating a single agent from config file")
        
        # Create sample configuration
        single_config = {
            "agent_type": "llm",
            "name": "Config Agent",
            "role_type": "researcher",
            "reasoning_framework": "react",
            "use_tools": True,
            "tool_categories": ["research", "utility"],
            "llm_provider_name": "ollama",  # Use llm_provider_name instead of llm_provider
            "llm_provider_kwargs": {
                "model_name": "smollm2",
                "timeout": TIMEOUT
            },
            "model_params": {
                "temperature": 0.7,
                "max_tokens": 1000
            }
        }
        
        # Write configuration to file
        single_config_path = os.path.join(config_dir, "single_agent.json")
        with open(single_config_path, "w") as f:
            json.dump(single_config, f, indent=2)
        
        # Create agent from config
        agent = create_agent(config_path=single_config_path)
        
        print_success(f"Created agent from config: {agent.name} (ID: {agent.id})")
        
        # Test the agent
        query = "What are the latest advancements in quantum computing?"
        print_info(f"Query: '{query}'")
        
        with Timer("Agent Response"):
            response = await agent.aprocess_message(query)
        
        print_info(f"Response snippet: '{response.content}'")
        
        # 2. Create multiple agents from a config file
        print_section("2. Creating multiple agents from config file")
        
        # Create sample configuration for multiple agents
        multi_config = {
            "agents": {
                "manager": {
                    "agent_type": "llm",
                    "name": "Project Manager",
                    "role_type": "manager",
                    "reasoning_framework": "cot",
                    "llm_provider_name": "ollama",  # Use llm_provider_name instead of llm_provider
                    "llm_provider_kwargs": {
                        "model_name": "smollm2",
                        "timeout": TIMEOUT
                    }
                },
                "developer": {
                    "agent_type": "llm",
                    "name": "Developer",
                    "role_type": "developer",
                    "reasoning_framework": "swe",
                    "use_tools": True,
                    "tool_categories": ["development", "utility"],
                    "llm_provider_name": "ollama",  # Use llm_provider_name instead of llm_provider
                    "llm_provider_kwargs": {
                        "model_name": "smollm2",
                        "timeout": TIMEOUT
                    }
                },
                "researcher": {
                    "agent_type": "llm",
                    "name": "Researcher",
                    "role_type": "researcher",
                    "reasoning_framework": "react",
                    "use_tools": True,
                    "tool_categories": ["research", "file"],
                    "llm_provider_name": "ollama",  # Use llm_provider_name instead of llm_provider
                    "llm_provider_kwargs": {
                        "model_name": "smollm2",
                        "timeout": TIMEOUT
                    }
                }
            }
        }
        
        # Write configuration to file
        multi_config_path = os.path.join(config_dir, "multi_agent.json")
        with open(multi_config_path, "w") as f:
            json.dump(multi_config, f, indent=2)
        
        # Create agents from config
        agents = create_agents_from_config(multi_config_path)
        
        print_success(f"Created {len(agents)} agents from config file")
        for agent_id, agent in agents.items():
            print_info(f"  {agent_id}: {agent.name} (ID: {agent.id})")
        
        # Test one of the agents
        developer = agents.get("developer")
        if developer:
            query = "What are the best practices for error handling in REST APIs?"
            print_info(f"Query to developer: '{query}'")
            
            with Timer("Developer Response"):
                response = await developer.aprocess_message(query)
            
            print_info(f"Response snippet: '{response.content}...'")
        
        print_success("All agent configuration tests completed successfully!")
        
    finally:
        # Clean up the temporary directory
        import shutil
        shutil.rmtree(config_dir, ignore_errors=True)
        print_info("Cleaned up temporary configuration directory")
        separator()

if __name__ == "__main__":
    asyncio.run(test_agent_configuration())