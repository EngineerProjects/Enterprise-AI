#!/usr/bin/env python
"""
Team Task Management

This script demonstrates task creation, assignment,
and management within teams.
"""

import asyncio
import sys
import os

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import *

setup_project_path()

from enterprise_ai.team.core import create_team
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

logger = get_logger("team_tasks")


async def test_task_management():
    """Test task operations in teams."""
    print_title("TEAM TASK MANAGEMENT")
    
    # Create team with members
    team = create_team(name="Task Force")
    
    # Add workers
    for i in range(2):
        agent = create_agent(
            agent_type="base",
            name=f"Worker {i+1}",
            agent_id=f"worker-00{i+1}"
        )
        team.add_member(agent)
    
    print_success(f"Team has {len(team.get_members())} members")
    
    # Create tasks
    print_section("1. Creating Tasks")
    
    tasks = [
        {"name": "Code Review", "priority": "high"},
        {"name": "Documentation", "priority": "medium"},
        {"name": "Bug Fix", "priority": "critical"}
    ]
    
    for task in tasks:
        result = team.assign_task(task)
        print_info(f"Task '{task['name']}' created: {result}")
    
    # Check tasks
    print_section("2. Task Status")
    
    all_tasks = team.get_all_tasks()
    print_info(f"Total tasks: {len(all_tasks)}")
    
    for task in all_tasks:
        print_info(f"  - {task.name}: {getattr(task, 'status', 'pending')}")
    
    # Update task
    if all_tasks:
        task_id = all_tasks[0].id
        team.update_task_status(task_id, "completed")
        print_success(f"Updated task {task_id} to completed")
    
    return team


async def main():
    """Run task management tests."""
    print_title("TEAM MODULE - TASK TEST", style="double")
    
    try:
        await test_task_management()
        print_success("\nTask tests completed!")
    except Exception as e:
        print_error(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
