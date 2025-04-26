#!/usr/bin/env python
"""
Tests for Enterprise AI Agents

This script demonstrates how to create and use agents with different roles,
how agents process messages, and how to assign tasks to agents.
"""

import os
import sys
import asyncio
from typing import Optional, List

# Import common utilities
from utils import (
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

# Import enterprise_ai modules
from enterprise_ai.agent import (
    BaseAgent,
    LLMAgent,
    create_agent,
    AgentBuilder,
    create_developer_agent,
    create_manager_agent,
    create_researcher_agent,
    Task,
    TaskStatus,
    BaseAgentMessage,
    QueryMessage,
    TaskAssignmentMessage,
    ResponseMessage
)
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.schema import Message

# Configuration
CONFIG = {
    "default_model": "smollm2",  # Default small model for basic tests
    "base_url": "http://localhost:11434",
    "timeout": 120.0,              # Default timeout in seconds
}

def test_create_basic_agent():
    """Test creating a basic agent."""
    print_section("Creating Basic Agent")

    agent = BaseAgent(name="TestAgent")

    print_info(f"Created agent: {agent.id} ({agent.name})")
    print_info(f"Agent status: {agent.get_status()}")

    return agent

def test_create_agent_with_role():
    """Test creating an agent with a specific role."""
    print_section("Creating Agent with Role")

    agent = create_agent(
        agent_type="base",
        name="Developer Bot",
        role_type="developer"
    )

    print_info(f"Created agent: {agent.id} ({agent.name})")

    role = agent.role
    if role:
        print_success(f"Role assigned: {role.name}")
        print_info(f"Role description: {role.description}")
        print_info(f"Role capabilities: {', '.join(role.capabilities)}")
    else:
        print_error("No role assigned")

    return agent

def test_create_agent_with_builder():
    """Test creating an agent using the AgentBuilder pattern."""
    print_section("Creating Agent with Builder Pattern")

    agent = (AgentBuilder()
        .with_type("base")
        .with_name("Custom Agent")
        .with_role("custom",
                  name="Data Analyst",
                  description="Specializes in data analysis",
                  capabilities=["data_analysis", "visualization", "statistics"])
        .build())

    print_info(f"Created agent: {agent.id} ({agent.name})")

    role = agent.role
    if role:
        print_success(f"Role assigned: {role.name}")
        print_info(f"Role description: {role.description}")
        print_info(f"Role capabilities: {', '.join(role.capabilities)}")

    return agent

def test_specialized_agents():
    """Test creating specialized agents using factory functions."""
    print_section("Creating Specialized Agents")

    developer = create_developer_agent(
        name="Dev Bot",
        agent_type="base",  # Using base for simplicity, could be 'llm'
        additional_context="Focus on Python development"
    )

    manager = create_manager_agent(
        name="Manager Bot",
        agent_type="base",
        additional_context="Product development focus"
    )

    researcher = create_researcher_agent(
        name="Research Bot",
        agent_type="base",
        additional_context="Focus on data science research"
    )

    print_info("Created specialized agents:")
    print_info(f"Developer: {developer.id} ({developer.name})")
    print_info(f"Manager: {manager.id} ({manager.name})")
    print_info(f"Researcher: {researcher.id} ({researcher.name})")

    return developer, manager, researcher

def test_agent_messaging():
    """Test message exchange between agents."""
    print_section("Agent Messaging")

    # Create two agents
    agent1 = BaseAgent(name="Agent 1")
    agent2 = BaseAgent(name="Agent 2")

    print_info(f"Created agents: {agent1.name} and {agent2.name}")

    # Create a query message from agent1 to agent2
    query = QueryMessage(
        sender_id=agent1.id,
        receiver_id=agent2.id,
        query="What is your status?"
    )

    print_info(f"Agent 1 sends query: {query.content}")

    # Agent2 processes the message
    response = agent2.process_message(query)

    if response:
        print_success(f"Agent 2 responds: {response.content}")
    else:
        print_warning("No response received")

    return agent1, agent2

def test_agent_task_assignment():
    """Test assigning and processing tasks by agents."""
    print_section("Agent Task Assignment")

    # Create an agent
    agent = BaseAgent(name="Task Processor", role_type="developer")

    # Create a task
    task = Task(
        id="task-123",
        description="Write a function to calculate prime numbers",
        status=TaskStatus.PENDING,
        metadata={"language": "Python", "complexity": "medium"}
    )

    # Assign task directly
    print_info(f"Assigning task: {task.id} - {task.description}")
    success = agent.assign_task(task)

    if success:
        print_success(f"Task assigned to {agent.name}")

        # Get agent status to check current task
        status = agent.get_status()
        print_info(f"Agent status: {status}")

        # Process the task
        print_info("Processing task...")
        task_status = agent.process_task()
        print_info(f"Task status after processing: {task_status.name}")
    else:
        print_error("Failed to assign task")

    # Try to assign another task (should fail as agent is busy)
    task2 = Task(
        id="task-456",
        description="Debug a JavaScript application",
        status=TaskStatus.PENDING
    )

    success = agent.assign_task(task2)
    if not success:
        print_success("Correctly rejected second task while busy")
    else:
        print_error("Unexpectedly accepted second task while busy")

    return agent

def test_llm_agent():
    """Test creating and using an LLM-powered agent."""
    print_section("LLM-Powered Agent")

    try:
        # Initialize Ollama provider
        provider = OllamaProvider(
            model_name=CONFIG["default_model"],
            base_url=CONFIG["base_url"],
            timeout=CONFIG["timeout"]
        )

        # Create LLM agent
        agent = LLMAgent(
            name="Ollama Assistant",
            role_type="researcher",
            llm_provider=provider
        )

        print_success(f"Created LLM agent: {agent.id} ({agent.name})")

        # Create a query message
        query = QueryMessage(
            sender_id="user-123",
            receiver_id=agent.id,
            query="Explain the concept of reinforcement learning in a few sentences."
        )

        print_info(f"Sending query to LLM agent: {query.content}")

        # Agent processes the message
        with Timer("LLM agent response"):
            response = agent.process_message(query)

        if response:
            print_success("Response received:")
            print(response.content)
        else:
            print_warning("No response received")

        return agent
    except Exception as e:
        print_error(f"Error testing LLM agent: {e}")
        print_warning("Skipping LLM agent test. Make sure Ollama is running.")
        return None

def main():
    """Run all agent tests."""
    print_title("Enterprise AI Agent Tests")

    try:
        # Basic agent creation
        basic_agent = test_create_basic_agent()
        separator()

        # Agent with role
        agent_with_role = test_create_agent_with_role()
        separator()

        # Builder pattern
        builder_agent = test_create_agent_with_builder()
        separator()

        # Specialized agents
        dev, mgr, res = test_specialized_agents()
        separator()

        # Agent messaging
        agent1, agent2 = test_agent_messaging()
        separator()

        # Task assignment
        task_agent = test_agent_task_assignment()
        separator()

        # LLM agent
        llm_agent = test_llm_agent()
        separator()

        print_success("All agent tests completed!")

    except Exception as e:
        print_error(f"Tests failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
