#!/usr/bin/env python
"""
Multi-Agent Task

This script demonstrates how multiple agents can work together
to solve a complex task through message passing.
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
from enterprise_ai.agent.core.factory import AgentBuilder, create_agent
from enterprise_ai.agent.core.base import LLMAgent
from enterprise_ai.llm.providers.factory import create_provider
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("multi_agent_test")

# Set a high timeout for our slow devices
TIMEOUT = 1200  # 20 minutes for very slow GPU/CPU

async def create_task_manager_agent() -> LLMAgent:
    """Create a task manager agent that can coordinate other agents."""

    agent = create_agent(
        agent_type="llm",
        name="Task Manager",
        role_type="manager",
        reasoning_framework="cot",
        llm_provider_name="ollama",
        llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"},
        role_kwargs={
            "additional_context": """
            You are a Task Manager who breaks down complex tasks into smaller subtasks.
            You coordinate with other specialized agents to solve the overall task.
            Your main responsibilities are:
            1. Task breakdown: Break a complex request into manageable subtasks
            2. Delegation: Assign subtasks to appropriate specialist agents
            3. Coordination: Integrate results from specialists into a final solution
            4. Communication: Maintain clear communication about task progress
            """
        }
    )

    print_success(f"Created Task Manager agent: {agent.name} (ID: {agent.id})")
    return agent

async def create_researcher_agent() -> LLMAgent:
    """Create a research-focused agent."""

    agent = create_agent(
        agent_type="llm",
        name="Researcher",
        role_type="researcher",
        reasoning_framework="react",
        llm_provider_name="ollama",
        llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"},
        role_kwargs={
            "additional_context": """
            You are a Research Specialist who focuses on gathering information and analyzing data.
            Your main responsibilities are:
            1. Information gathering: Find relevant facts and resources
            2. Analysis: Analyze information to extract key insights
            3. Synthesis: Combine information from multiple sources into coherent summaries
            4. Question answering: Provide factual answers based on your research
            """
        }
    )

    print_success(f"Created Researcher agent: {agent.name} (ID: {agent.id})")
    return agent

async def create_developer_agent() -> LLMAgent:
    """Create a developer-focused agent."""

    agent = create_agent(
        agent_type="llm",
        name="Developer",
        role_type="developer",
        reasoning_framework="swe",
        llm_provider_name="ollama",
        llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"},
        role_kwargs={
            "additional_context": """
            You are a Software Developer specialist who focuses on writing clean, efficient code
            and providing technical solutions.
            Your main responsibilities are:
            1. Code generation: Write code to solve specific technical problems
            2. Code explanation: Explain how code works and why certain design choices were made
            3. Technical architecture: Suggest appropriate technical approaches for problems
            4. Problem solving: Solve algorithm and data structure problems efficiently
            """
        }
    )

    print_success(f"Created Developer agent: {agent.name} (ID: {agent.id})")
    return agent

async def create_content_agent() -> LLMAgent:
    """Create a content-focused agent."""

    agent = create_agent(
        agent_type="llm",
        name="Content Creator",
        role_type="researcher",  # Using a known working role type
        reasoning_framework="cot",
        llm_provider_name="ollama",
        llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"},
        role_kwargs={
            "additional_context": """
            You are a Content Creation specialist who focuses on creating compelling, clear,
            and well-structured content.
            Your main responsibilities are:
            1. Content writing: Create well-structured, engaging content on any topic
            2. Editing and revision: Polish content for clarity, conciseness, and impact
            3. Adaptation: Adjust content tone and style based on audience and purpose
            4. Creative writing: Generate creative narratives, stories, or descriptions

            Although you use research skills, your primary focus is on creating polished content,
            not just gathering information.
            """
        }
    )

    print_success(f"Created Content Creator agent: {agent.name} (ID: {agent.id})")
    return agent

async def agent_conversation(agent1: LLMAgent, agent2: LLMAgent,
                            starting_message: str, rounds: int = 3) -> List[MessageProtocol]:
    """Conduct a multi-round conversation between two agents."""

    conversation = []
    current_message = Message.user_message(starting_message)
    conversation.append(current_message)

    print_info(f"Starting conversation with message: '{starting_message}'")

    for i in range(rounds):
        print_info(f"Round {i+1} of conversation:")

        # Agent 1's turn
        with Timer(f"{agent1.name} Response"):
            response1 = await agent1.aprocess_message(current_message)
        print_info(f"{agent1.name}: '{response1.content}'")
        conversation.append(response1)

        # Agent 2's turn
        with Timer(f"{agent2.name} Response"):
            response2 = await agent2.aprocess_message(response1)
        print_info(f"{agent2.name}: '{response2.content}'")
        conversation.append(response2)

        # Update current message for next round
        current_message = response2

    return conversation

async def task_coordination_workflow(manager: LLMAgent, specialists: List[LLMAgent],
                                    task: str) -> List[MessageProtocol]:
    """Run a task coordination workflow with a manager and specialists."""

    conversation = []

    # Step 1: Manager breaks down the task
    task_message = Message.user_message(f"Task: {task}\n\nPlease break this down into subtasks for specialists to work on. Identify which specialists should handle each subtask.")
    print_info(f"Sending task to {manager.name}: '{task}'")

    with Timer(f"{manager.name} Task Breakdown"):
        breakdown = await manager.aprocess_message(task_message)

    print_info(f"{manager.name} broke down the task into subtasks")
    conversation.append(task_message)
    conversation.append(breakdown)

    # Step 2: Assign subtasks to specialists and collect responses
    specialist_responses = []

    for i, specialist in enumerate(specialists):
        # Generate a subtask message specifically for this specialist
        subtask_prompt = f"""
        You are working with a Task Manager on the overall task: "{task}"

        The Task Manager has provided this breakdown of the task:

        {breakdown.content}

        Based on your expertise as a {specialist.name}, please work on the relevant subtasks
        mentioned in the breakdown that match your specialization. Provide your detailed solution.
        """

        subtask_message = Message.user_message(subtask_prompt)
        print_info(f"Assigning subtask to {specialist.name}")

        with Timer(f"{specialist.name} Response"):
            specialist_response = await specialist.aprocess_message(subtask_message)

        print_info(f"Received response from {specialist.name}")
        specialist_responses.append((specialist.name, specialist_response))
        conversation.append(subtask_message)
        conversation.append(specialist_response)

    # Step 3: Manager integrates responses into final solution
    integration_prompt = f"""
    You previously broke down this task: "{task}" into subtasks.

    Now the specialists have completed their assigned subtasks. Here are their responses:

    """

    for name, response in specialist_responses:
        integration_prompt += f"\n--- {name}'s contribution ---\n{response.content}\n\n"

    integration_prompt += "\nPlease integrate these contributions into a comprehensive final solution to the original task."

    integration_message = Message.user_message(integration_prompt)
    print_info(f"Asking {manager.name} to integrate specialist responses")

    with Timer(f"{manager.name} Final Integration"):
        final_solution = await manager.aprocess_message(integration_message)

    print_info(f"{manager.name} has integrated the responses into a final solution")
    conversation.append(integration_message)
    conversation.append(final_solution)

    return conversation

async def test_multi_agent():
    """Test multi-agent interaction patterns."""
    print_title("TESTING MULTI-AGENT INTERACTIONS")

    # Set environment variable for Ollama timeout
    os.environ["ENTERPRISE_AI_OLLAMA_TIMEOUT"] = str(TIMEOUT)

    # 1. Create the agents
    print_section("1. Creating multiple specialized agents")

    # Create four specialized agents
    task_manager = await create_task_manager_agent()
    researcher = await create_researcher_agent()
    developer = await create_developer_agent()
    content_creator = await create_content_agent()

    print_success("Created all specialized agents")

    # 2. Simple agent conversation
    print_section("2. Testing simple agent conversation")

    conversation_starter = "I'm planning to build a simple e-commerce site. What's a good technology stack to use, and what are some essential features I should implement?"

    conversation = await agent_conversation(
        developer,
        researcher,
        conversation_starter,
        rounds=2
    )

    print_success("Completed agent conversation test")

    # 3. Task coordination workflow
    print_section("3. Testing task coordination workflow")

    complex_task = """
    Create a plan for a personal finance management application with the following requirements:
    1. User authentication and data security
    2. Budget tracking and visualization
    3. Expense categorization
    4. Financial goal setting and tracking
    5. Basic investment portfolio tracking
    """

    specialists = [researcher, developer, content_creator]

    workflow_conversation = await task_coordination_workflow(
        task_manager,
        specialists,
        complex_task
    )

    print_success("Completed task coordination workflow test")

    # 4. Team problem solving
    print_section("4. Final results summary")

    # Extract the final solution from the workflow conversation
    final_solution = workflow_conversation[-1].content
    
    print_info(f"Final solution snippet:\n{final_solution}")

    print_success("All multi-agent tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_multi_agent())
