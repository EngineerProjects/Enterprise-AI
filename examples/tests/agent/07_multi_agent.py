#!/usr/bin/env python
"""
Multi-Agent Task

This script demonstrates how multiple agents can work together
to solve a complex task through message passing.
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
from enterprise_ai.agent.core import create_developer_agent, create_researcher_agent, create_manager_agent
from enterprise_ai.agent.messaging.message import create_message
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("multi_agent_test")

async def test_multi_agent_task():
    """Test multiple agents collaborating on a task."""
    print_title("TESTING MULTI-AGENT TASK COLLABORATION")

    # 1. Create a set of agents with different roles
    print_section("1. Creating agents with different roles")
    
    manager = create_manager_agent(name="Project Manager")
    researcher = create_researcher_agent(name="Research Specialist")
    developer = create_developer_agent(name="Developer")
    
    print_success(f"Created manager agent: {manager.name} (ID: {manager.id})")
    print_success(f"Created researcher agent: {researcher.name} (ID: {researcher.id})")
    print_success(f"Created developer agent: {developer.name} (ID: {developer.id})")
    
    # 2. Define a complex task
    print_section("2. Defining a complex task")
    
    task_description = """
    We need to build an application that predicts stock prices using historical data and machine learning.
    The application should include data visualization and a simple web interface.
    """
    
    print_info(f"Task: {task_description}")
    
    # 3. Task planning by manager
    print_section("3. Task planning by manager")
    
    plan_request = f"Create a project plan for the following task: {task_description}"
    print_info(f"Request to Manager: '{plan_request}'")
    
    with Timer("Manager Planning"):
        plan_response = await manager.aprocess_message(plan_request)
    
    project_plan = plan_response.content
    print_info(f"Project Plan: '{project_plan[:300]}...'")
    
    # 4. Research phase
    print_section("4. Research phase with Researcher")
    
    research_request = f"""
    Based on this project plan: 
    '{project_plan[:300]}...'
    
    Research the most appropriate machine learning algorithms for stock price prediction.
    What data sources should we use? What are the key features we should extract?
    """
    
    print_info(f"Request to Researcher: '{research_request[:150]}...'")
    
    with Timer("Research"):
        research_response = await researcher.aprocess_message(research_request)
    
    research_findings = research_response.content
    print_info(f"Research Findings: '{research_findings[:300]}...'")
    
    # 5. Development planning
    print_section("5. Development planning with Developer")
    
    dev_request = f"""
    Based on this project plan:
    '{project_plan[:200]}...'
    
    And these research findings:
    '{research_findings[:300]}...'
    
    Create a technical implementation plan, including technology stack, architecture,
    and key components we'll need to build.
    """
    
    print_info(f"Request to Developer: '{dev_request[:150]}...'")
    
    with Timer("Development Planning"):
        dev_response = await developer.aprocess_message(dev_request)
    
    tech_plan = dev_response.content
    print_info(f"Technical Plan: '{tech_plan[:300]}...'")
    
    # 6. Final integration by manager
    print_section("6. Final integration by Manager")
    
    integration_request = f"""
    Integrate the following components into a final project brief:
    
    1. Project Plan:
    '{project_plan[:200]}...'
    
    2. Research Findings:
    '{research_findings[:200]}...'
    
    3. Technical Implementation Plan:
    '{tech_plan[:200]}...'
    
    Create a comprehensive project brief that combines all these elements.
    """
    
    print_info(f"Request to Manager: '{integration_request[:150]}...'")
    
    with Timer("Final Integration"):
        integration_response = await manager.aprocess_message(integration_request)
    
    final_brief = integration_response.content
    print_info(f"Final Project Brief: '{final_brief[:500]}...'")
    
    print_success("Multi-agent task collaboration completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_multi_agent_task())