#!/usr/bin/env python
"""
Tests for Enterprise AI Teams

This script demonstrates how to create and use teams of agents,
test hierarchical team structures, and coordinate team activities.
"""

import os
import sys
import uuid
from typing import Dict, List, Optional, Tuple

# Import common utilities
from enterprise_ai.llm.providers.ollama import OllamaProvider
from notebooks.agent import CONFIG
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
from enterprise_ai.agent.base import BaseAgent, LLMAgent
from enterprise_ai.agent.factory import (
    create_agent,
    AgentBuilder,
    create_developer_agent,
    create_manager_agent,
    create_researcher_agent
)
from enterprise_ai.agent.types import Task, TaskStatus
from enterprise_ai.agent.message import (
    BaseAgentMessage,
    QueryMessage,
    TaskAssignmentMessage,
    BroadcastMessage,
    ResponseMessage
)
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.hierarchical import HierarchicalTeam
from enterprise_ai.team.coordinator import TeamCoordinator, TaskResult
from enterprise_ai.team.factory import TeamFactory, get_team_factory

def test_create_basic_team():
    """Test creating a basic team with a manager and members."""
    print_section("Creating Basic Team")

    # Create a manager
    manager = create_manager_agent(
        name="Team Manager",
        agent_type="base"
    )

    # Create a team
    team = BaseTeam(
        name="Test Team",
        manager=manager
    )

    print_info(f"Created team: {team.id} ({team.name})")
    print_info(f"Manager: {manager.id} ({manager.name})")

    # Add team members with different roles
    developer = create_developer_agent(name="Developer 1", agent_type="base")
    researcher = create_researcher_agent(name="Researcher 1", agent_type="base")

    # Add members to the team
    team.add_member(developer, "developer")
    team.add_member(researcher, "researcher")

    print_success(f"Added {len(team.members)} members to the team")

    # Get team status
    status = team.get_status()
    print_info("Team status:")
    print(f"- ID: {status['id']}")
    print(f"- Name: {status['name']}")
    print(f"- Member count: {status['member_count']}")
    print(f"- Manager: {status['manager']['name']}")
    print("- Members:")
    for member in status['members']:
        print(f"  - {member['name']} ({member['role']})")

    return team, manager, developer, researcher

def test_hierarchical_team():
    """Test creating a hierarchical team with subteams."""
    print_section("Hierarchical Team Structure")

    # Create the main team with a director
    director = create_manager_agent(name="Director", agent_type="base")
    main_team = HierarchicalTeam(name="Company", manager=director)

    print_info(f"Created main team: {main_team.id} ({main_team.name})")

    # Create subteams for different departments
    # Development subteam
    dev_manager = create_manager_agent(name="Dev Manager", agent_type="base")
    dev_team = BaseTeam(name="Development Team", manager=dev_manager)

    # Add developers to dev team
    frontend_dev = create_developer_agent(name="Frontend Dev", agent_type="base")
    backend_dev = create_developer_agent(name="Backend Dev", agent_type="base")
    dev_team.add_member(frontend_dev, "frontend_dev")
    dev_team.add_member(backend_dev, "backend_dev")

    # Research subteam
    research_manager = create_manager_agent(name="Research Manager", agent_type="base")
    research_team = BaseTeam(name="Research Team", manager=research_manager)

    # Add researchers to research team
    researcher1 = create_researcher_agent(name="Researcher 1", agent_type="base")
    researcher2 = create_researcher_agent(name="Researcher 2", agent_type="base")
    research_team.add_member(researcher1, "researcher")
    research_team.add_member(researcher2, "researcher")

    # Add subteams to main team
    main_team.add_subteam(dev_team)
    main_team.add_subteam(research_team)

    print_success(f"Added {len(main_team.subteams)} subteams to main team")

    # Add some direct reports to the director
    hr_agent = create_agent(
        agent_type="base",
        name="HR Manager",
        role_type="custom",
        role_kwargs={
            "name": "HR Manager",
            "description": "Manages human resources",
            "capabilities": ["hiring", "team_building"]
        }
    )

    main_team.add_member(hr_agent, "hr_manager")

    print_info("Team structure:")
    print(f"- Main Team: {main_team.name}")
    print(f"  - Manager: {director.name}")
    print(f"  - Direct Members: {len(main_team.members)}")
    print(f"  - Subteams: {len(main_team.subteams)}")

    for team_id, subteam in main_team.subteams.items():
        print(f"    - Subteam: {subteam.name}")
        print(f"      - Manager: {subteam.manager.name}")
        print(f"      - Members: {len(subteam.members)}")

    # Get all members (including those in subteams)
    all_members = main_team.get_all_members()
    print_info(f"Total members across all teams: {len(all_members)}")

    return main_team, dev_team, research_team

def test_team_messaging():
    """Test messaging within a team."""
    print_section("Team Messaging")

    # Create a team with a manager and members
    manager = create_manager_agent(name="Communication Manager", agent_type="base")
    team = BaseTeam(name="Communication Team", manager=manager)

    # Add members
    developer1 = create_developer_agent(name="Developer 1", agent_type="base")
    developer2 = create_developer_agent(name="Developer 2", agent_type="base")
    analyst = create_agent(
        agent_type="base",
        name="Data Analyst",
        role_type="custom",
        role_kwargs={
            "name": "Data Analyst",
            "description": "Specializes in data analysis",
            "capabilities": ["data_analysis", "reporting"]
        }
    )

    team.add_member(developer1, "developer")
    team.add_member(developer2, "developer")
    team.add_member(analyst, "analyst")

    print_info(f"Created team with {len(team.members)} members")

    # Test 1: Send message to manager
    query = QueryMessage(
        sender_id="user-123",
        receiver_id=team.id,
        query="What is the team's capacity for new tasks?"
    )

    print_info(f"Sending query to team: {query.content}")
    response = team.process_message(query)

    if response:
        print_success(f"Response from team: {response.content}")
    else:
        print_warning("No response received")

    # Test 2: Broadcast message to all team members
    print_info("Broadcasting message to all team members")
    responses = team.broadcast_message(
        message_type="NOTIFICATION",
        content="Team meeting scheduled for tomorrow at 10 AM",
        sender_id=manager.id
    )

    print_info(f"Received {len(responses)} responses to broadcast")
    for i, resp in enumerate(responses):
        print(f"Response {i+1}: {resp.content[:50]}...")

    # Test 3: Send message to specific team member
    query = QueryMessage(
        sender_id="user-123",
        receiver_id=team.id,
        query="Provide a status update on your current task",
        metadata={"target_agent": developer1.id}
    )

    print_info(f"Sending targeted query to team member: {query.content}")
    response = team.process_message(query)

    if response:
        print_success(f"Response from targeted member: {response.content}")
    else:
        print_warning("No response received from targeted member")

    return team

def test_team_task_assignment():
    """Test assigning tasks to a team and its members."""
    print_section("Team Task Assignment")

    # Create a team
    manager = create_manager_agent(name="Project Manager", agent_type="base")
    team = BaseTeam(name="Project Team", manager=manager)

    # Add members with different capabilities
    developer = create_developer_agent(name="Developer", agent_type="base")
    researcher = create_researcher_agent(name="Researcher", agent_type="base")

    team.add_member(developer, "developer")
    team.add_member(researcher, "researcher")

    print_info(f"Created team with manager and {len(team.members)} members")

    # Task 1: Assign to manager
    task1 = Task(
        id="task-project-plan",
        description="Create a project plan for the new initiative",
        status=TaskStatus.PENDING,
        metadata={"priority": "high"}
    )

    print_info(f"Assigning task to team manager: {task1.id}")
    success = team.assign_task(task1)  # No agent_id means manager

    if success:
        print_success("Task assigned to manager successfully")
    else:
        print_error("Failed to assign task to manager")

    # Task 2: Assign to specific member
    task2 = Task(
        id="task-api-development",
        description="Develop the API endpoints for user authentication",
        status=TaskStatus.PENDING,
        metadata={"language": "Python", "framework": "FastAPI"}
    )

    print_info(f"Assigning task to developer: {task2.id}")
    success = team.assign_task(task2, developer.id)

    if success:
        print_success("Task assigned to developer successfully")
    else:
        print_error("Failed to assign task to developer")

    # Task 3: Assign to team (manager decides)
    task3 = Task(
        id="task-market-research",
        description="Research competitive products in the market",
        status=TaskStatus.PENDING,
        metadata={"required_capability": "research"}
    )

    print_info(f"Assigning task to team (for manager to delegate): {task3.id}")
    success = team.assign_task(task3)

    if success:
        print_success("Task assigned to team successfully")
    else:
        print_error("Failed to assign task to team")

    return team

def test_team_coordinator():
    """Test using a team coordinator for managing tasks."""
    print_section("Team Coordinator")

    # Create a team
    manager = create_manager_agent(name="Project Director", agent_type="base")
    team = BaseTeam(name="Project Execution Team", manager=manager)

    # Add members with different roles
    frontend_dev = create_developer_agent(
        name="Frontend Developer",
        agent_type="base",
        additional_context="Frontend development specialist"
    )
    backend_dev = create_developer_agent(
        name="Backend Developer",
        agent_type="base",
        additional_context="Backend development specialist"
    )
    qa_engineer = create_agent(
        agent_type="base",
        name="QA Engineer",
        role_type="custom",
        role_kwargs={
            "name": "QA Engineer",
            "description": "Specializes in quality assurance",
            "capabilities": ["testing", "quality_assurance"]
        }
    )

    # Add members to team
    team.add_member(frontend_dev, "frontend_dev")
    team.add_member(backend_dev, "backend_dev")
    team.add_member(qa_engineer, "qa_engineer")

    print_info(f"Created team with {len(team.members)} members")

    # Create a team coordinator
    coordinator = TeamCoordinator(team)
    print_success("Created team coordinator")

    # Create tasks with dependencies
    task1 = Task(
        id="task-db-schema",
        description="Design database schema",
        status=TaskStatus.PENDING,
        metadata={"suggested_agent": backend_dev.id}
    )

    task2 = Task(
        id="task-api-endpoints",
        description="Implement API endpoints",
        status=TaskStatus.PENDING,
        metadata={"required_capability": "coding", "suggested_agent": backend_dev.id}
    )

    task3 = Task(
        id="task-frontend-ui",
        description="Develop frontend UI components",
        status=TaskStatus.PENDING,
        metadata={"suggested_agent": frontend_dev.id}
    )

    task4 = Task(
        id="task-integration-test",
        description="Create integration tests for API and UI",
        status=TaskStatus.PENDING,
        metadata={"required_capability": "testing", "suggested_agent": qa_engineer.id}
    )

    # Submit tasks with dependencies
    print_info("Submitting tasks with dependencies")
    coordinator.submit_task(task1)  # No dependencies
    coordinator.submit_task(task2, dependencies=[task1.id])  # Depends on task1
    coordinator.submit_task(task3)  # No dependencies
    coordinator.submit_task(task4, dependencies=[task2.id, task3.id])  # Depends on task2 and task3

    # Process tasks
    print_info("Processing tasks")
    num_processed = coordinator.process_tasks()
    print_info(f"Processed {num_processed} tasks")

    # Show active tasks
    active_tasks = coordinator.get_active_tasks()
    print_info(f"Active tasks: {len(active_tasks)}")
    for task_id, agent_id in active_tasks.items():
        print(f"- Task {task_id} assigned to agent {agent_id}")

    # Update task statuses
    print_info("Updating task statuses")

    # Mark task1 as completed
    coordinator.update_task_status(
        task_id=task1.id,
        status=TaskStatus.COMPLETED,
        agent_id=backend_dev.id,
        result_data={"schema": "user, product, order tables defined"}
    )
    print_success(f"Marked task {task1.id} as completed")

    # Process more tasks (task2 should be ready now)
    num_processed = coordinator.process_tasks()
    print_info(f"Processed {num_processed} more tasks")

    # Mark task3 as completed
    coordinator.update_task_status(
        task_id=task3.id,
        status=TaskStatus.COMPLETED,
        agent_id=frontend_dev.id,
        result_data={"components": "login, dashboard, profile components created"}
    )
    print_success(f"Marked task {task3.id} as completed")

    # Show pending tasks
    pending_tasks = coordinator.get_pending_tasks()
    print_info(f"Pending tasks: {len(pending_tasks)}")
    for task_id in pending_tasks:
        print(f"- Task {task_id}")

    # Collect completed results
    results = coordinator.collect_all_results()
    print_info(f"Collected {len(results)} task results")
    for task_id, result in results.items():
        print(f"- Task {task_id}: {result.status.name}")
        if result.data:
            print(f"  Data: {result.data}")

    return coordinator

def test_team_factory():
    """Test creating teams using the TeamFactory."""
    print_section("Team Factory")

    # Get the team factory
    factory = get_team_factory()

    # Create a development team
    dev_team = factory.create_development_team(
        name="Software Development Team"
    )

    print_info(f"Created development team: {dev_team.id} ({dev_team.name})")
    print_info(f"Manager: {dev_team.manager.name}")
    print_info(f"Members: {len(dev_team.members)}")

    # Create a research team
    research_team = factory.create_research_team(
        name="AI Research Team"
    )

    print_info(f"Created research team: {research_team.id} ({research_team.name})")
    print_info(f"Manager: {research_team.manager.name}")
    print_info(f"Members: {len(research_team.members)}")

    # Create an analytics team
    analytics_team = factory.create_analytics_team(
        name="Data Analytics Team"
    )

    print_info(f"Created analytics team: {analytics_team.id} ({analytics_team.name})")
    print_info(f"Manager: {analytics_team.manager.name}")
    print_info(f"Members: {len(analytics_team.members)}")

    # Create a custom team
    member_roles = [
        ("UX Designer", ["design", "user_experience"]),
        ("Content Writer", ["content_creation", "editing"]),
        ("Marketing Specialist", ["marketing", "analytics"])
    ]

    custom_team = factory.create_custom_team(
        member_roles=member_roles,
        name="Marketing Team"
    )

    print_info(f"Created custom team: {custom_team.id} ({custom_team.name})")
    print_info(f"Manager: {custom_team.manager.name}")
    print_info(f"Members: {len(custom_team.members)}")

    # Create a cross-functional team
    cross_team = factory.create_cross_functional_team(
        specializations=["development", "design", "product", "qa"],
        name="Product Launch Team"
    )

    print_info(f"Created cross-functional team: {cross_team.id} ({cross_team.name})")
    print_info(f"Manager: {cross_team.manager.name}")
    print_info(f"Members: {len(cross_team.members)}")

    return factory, [dev_team, research_team, analytics_team, custom_team, cross_team]


def test_team_with_different_models():
    """Test creating a team with members using different LLM models."""
    print_section("Team with Different LLM Models")

    # Create providers with different models
    ollama_llama3 = OllamaProvider(model_name="llama3.2", base_url=CONFIG["base_url"])
    ollama_smol = OllamaProvider(model_name="smollm2", base_url=CONFIG["base_url"])
    ollama_llava = OllamaProvider(model_name="llava", base_url=CONFIG["base_url"])

    # Create a team with a manager
    manager = LLMAgent(
        name="AI Team Manager",
        role_type="manager",
        llm_provider=ollama_llama3
    )

    team = BaseTeam(name="Multi-Model Team", manager=manager)

    # Add members with different model providers
    developer = LLMAgent(
        name="Developer Agent",
        role_type="developer",
        llm_provider=ollama_llama3
    )

    researcher = LLMAgent(
        name="Research Agent",
        role_type="researcher",
        llm_provider=ollama_smol
    )

    vision_specialist = LLMAgent(
        name="Vision Specialist",
        role_type="custom",
        role_kwargs={
            "name": "Vision Specialist",
            "description": "Specialist in image analysis",
            "capabilities": ["vision", "image_analysis"]
        },
        llm_provider=ollama_llava
    )

    # Add to team
    team.add_member(developer, "developer")
    team.add_member(researcher, "researcher")
    team.add_member(vision_specialist, "vision_specialist")

    print_success(f"Created team with {len(team.members)} members using different LLM models")

    return team

def main():
    """Run all team tests."""
    print_title("Enterprise AI Team Tests")

    try:
        # Basic team tests
        team, manager, dev, researcher = test_create_basic_team()
        separator()

        # Hierarchical team tests
        main_team, dev_team, research_team = test_hierarchical_team()
        separator()

        # Team messaging
        messaging_team = test_team_messaging()
        separator()

        # Team task assignment
        task_team = test_team_task_assignment()
        separator()

        # Team coordinator
        coordinator = test_team_coordinator()
        separator()

        # Team factory
        factory, teams = test_team_factory()
        separator()

        print_success("All team tests completed!")

    except Exception as e:
        print_error(f"Tests failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
