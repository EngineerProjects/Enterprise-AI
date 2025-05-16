#!/usr/bin/env python
"""
Agent Reasoning Frameworks

This script demonstrates different reasoning frameworks available for agents
and how they affect problem-solving approaches.
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
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_reasoning_test")

async def test_reasoning_frameworks():
    """Test different agent reasoning frameworks."""
    print_title("TESTING AGENT REASONING FRAMEWORKS")

    # 1. Create agents with different reasoning frameworks
    print_section("1. Creating agents with different reasoning frameworks")
    
    base_agent = create_agent(
        agent_type="llm",
        name="Base Reasoning Agent",
        reasoning_framework="base",
        llm_provider_kwargs={"timeout": 300.0, "model_name": "llama3.2"}
    )
    
    cot_agent = create_agent(
        agent_type="llm",
        name="Chain-of-Thought Agent",
        reasoning_framework="cot",
        llm_provider_kwargs={"timeout": 300.0, "model_name": "llama3.2"}
    )
    
    react_agent = create_agent(
        agent_type="llm",
        name="ReAct Agent",
        reasoning_framework="react",
        llm_provider_kwargs={"timeout": 300.0, "model_name": "llama3.2"}
    )
    
    swe_agent = create_agent(
        agent_type="llm",
        name="Software Engineer Agent",
        reasoning_framework="swe",
        llm_provider_kwargs={"timeout": 300.0, "model_name": "llama3.2"}
    )
    
    print_success(f"Created agents with different reasoning frameworks")
    
    # 2. Test reasoning on a math problem
    print_section("2. Testing reasoning on a math problem")
    
    math_problem = "If a train travels at 120 km/h and needs to cover a distance of 450 km, how much time will it take to complete the journey?"
    
    print_info(f"Problem: '{math_problem}'")
    
    print_info("Base agent reasoning:")
    with Timer("Base Agent Response"):
        base_response = await base_agent.aprocess_message(math_problem)
    print_info(f"Base agent response: '{base_response.content}'")
    
    print_info("Chain-of-Thought agent reasoning:")
    with Timer("CoT Agent Response"):
        cot_response = await cot_agent.aprocess_message(math_problem)
    print_info(f"CoT agent response: '{cot_response.content}'")
    
    # 3. Test reasoning on a planning problem
    print_section("3. Testing reasoning on a planning problem")
    
    planning_problem = "I need to organize a team meeting with 5 team members across different time zones (NY, London, Tokyo). What steps should I take?"
    
    print_info(f"Problem: '{planning_problem}'")
    
    print_info("Base agent reasoning:")
    with Timer("Base Agent Response"):
        base_response = await base_agent.aprocess_message(planning_problem)
    print_info(f"Base agent response: '{base_response.content}'")
    
    print_info("ReAct agent reasoning:")
    with Timer("ReAct Agent Response"):
        react_response = await react_agent.aprocess_message(planning_problem)
    print_info(f"ReAct agent response: '{react_response.content}'")
    
    # 4. Test reasoning on a software problem
    print_section("4. Testing reasoning on a software problem")
    
    code_problem = "Write a function to find the longest palindromic substring in a given string."
    
    print_info(f"Problem: '{code_problem}'")
    
    print_info("Base agent reasoning:")
    with Timer("Base Agent Response"):
        base_response = await base_agent.aprocess_message(code_problem)
    print_info(f"Base agent response: '{base_response.content}'")
    
    print_info("SWE agent reasoning:")
    with Timer("SWE Agent Response"):
        swe_response = await swe_agent.aprocess_message(code_problem)
    print_info(f"SWE agent response: '{swe_response.content}'")
    
    print_success("All reasoning framework tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_reasoning_frameworks())