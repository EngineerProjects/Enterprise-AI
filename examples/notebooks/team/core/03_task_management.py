#!/usr/bin/env python
"""
Team Task Management Tests

This script tests team task management functionality, including:
- Creating tasks in a team
- Assigning tasks to team members
- Tracking task status
- Decomposing tasks into subtasks
- Retrieving task information
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional, Tuple, Any

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import (
    setup_project_path, 
    print_title, 
    print_section, 
    print_info, 
    print_success, 
    print_error,
    print_warning,
    Timer
)

# Set up project path
setup_project_path()

# Import required components
from enterprise_ai.team.core import create_team
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.task_management")


class TestResults:
    """Track test results for better reporting."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, message: str = ""):
        """Record a passed test."""
        self.passed += 1
        if message:
            print_success(f"✓ {message}")
    
    def add_fail(self, message: str):
        """Record a failed test."""
        self.failed += 1
        self.errors.append(message)
        print_error(f"✗ {message}")
    
    def summary(self) -> str:
        """Generate a summary of test results."""
        total = self.passed + self.failed
        return f"Tests: {total}, Passed: {self.passed}, Failed: {self.failed}"


async def test_team_setup(results: TestResults) -> Any:
    """Set up a team with members for task management tests.
    
    Args:
        results: Test results tracker
    
    Returns:
        Team with members
    """
    print_section("1. Team Setup")
    
    try:
        # Create a team
        team = create_team(name="Task Force")
        
        # Add workers
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Worker {i+1}",
                agent_id=f"worker-00{i+1}"
            )
            team.add_member(agent)
        
        # Assertions
        assert team is not None, "Team should not be None"
        assert len(team.get_members()) == 3, f"Expected 3 members, got {len(team.get_members())}"
        
        print_info(f"Created team: {team.name} with {len(team.get_members())} members")
        results.add_pass("Team setup successful")
        
        return team
        
    except Exception as e:
        results.add_fail(f"Team setup failed: {e}")
        logger.exception("Test failure")
        raise


async def test_task_creation(results: TestResults, team: Any) -> List[Any]:
    """Test creating tasks in a team.
    
    Args:
        results: Test results tracker
        team: Team with members
    
    Returns:
        List of created tasks
    """
    print_section("2. Task Creation")
    
    try:
        # Create tasks
        tasks = [
            {"name": "Code Review", "priority": "high", "description": "Review pull request #42"},
            {"name": "Documentation", "priority": "medium", "description": "Update API docs"},
            {"name": "Bug Fix", "priority": "critical", "description": "Fix authentication issue"}
        ]
        
        task_ids = []
        
        for task in tasks:
            print_info(f"Creating task: {task['name']} (Priority: {task['priority']})")
            result = team.assign_task(task)
            
            # Assertions
            assert result, f"Creating task {task['name']} should succeed"
            
        # Get all tasks
        all_tasks = team.get_all_tasks()
        
        # Assertions
        assert all_tasks is not None, "Tasks list should not be None"
        assert len(all_tasks) == len(tasks), f"Expected {len(tasks)} tasks, got {len(all_tasks)}"
        
        # Verify task names match
        task_names = [t.name for t in all_tasks]
        expected_names = [t["name"] for t in tasks]
        
        for name in expected_names:
            assert name in task_names, f"Expected task '{name}' not found in tasks"
        
        print_info(f"Created {len(all_tasks)} tasks successfully")
        results.add_pass("Task creation successful")
        
        return all_tasks
        
    except Exception as e:
        results.add_fail(f"Task creation failed: {e}")
        logger.exception("Test failure")
        raise


async def test_task_assignment(results: TestResults, team: Any, tasks: List[Any]) -> None:
    """Test assigning tasks to specific team members.
    
    Args:
        results: Test results tracker
        team: Team with members
        tasks: List of created tasks
    """
    print_section("3. Task Assignment")
    
    try:
        # Get team members
        members = team.get_members()
        
        # Assign each task to a different member
        for i, task in enumerate(tasks):
            member_index = i % len(members)
            member = members[member_index]
            
            # Assign task to specific member
            print_info(f"Assigning task '{task.name}' to {member.name}")
            result = team.assign_task(task, member.id)
            
            # Assertions
            assert result, f"Assigning task to member should succeed"
            
        # Verify assignments
        for i, member in enumerate(members):
            member_tasks = team.get_agent_tasks(member.id)
            
            print_info(f"{member.name} has {len(member_tasks)} assigned tasks")
            for task in member_tasks:
                print_info(f"  - {task.name}")
        
        results.add_pass("Task assignment successful")
        
    except Exception as e:
        results.add_fail(f"Task assignment failed: {e}")
        logger.exception("Test failure")
        raise


async def test_task_status_update(results: TestResults, team: Any, tasks: List[Any]) -> None:
    """Test updating task status.
    
    Args:
        results: Test results tracker
        team: Team with members
        tasks: List of created tasks
    """
    print_section("4. Task Status Updates")
    
    try:
        # Update statuses for different tasks
        statuses = ["in_progress", "completed", "blocked"]
        
        for i, task in enumerate(tasks):
            status = statuses[i % len(statuses)]
            
            print_info(f"Updating task '{task.name}' to status: {status}")
            result = team.update_task_status(task.id, status)
            
            # Assertions
            assert result, f"Updating task status should succeed"
            
        # Get task summary
        summary = team.get_task_summary()
        
        # Assertions
        assert summary is not None, "Task summary should not be None"
        
        print_info("Task status summary:")
        for status, count in summary.items():
            print_info(f"  {status}: {count}")
        
        # Verify specific statuses
        for status in statuses:
            assert status in summary, f"Status '{status}' should be in summary"
        
        results.add_pass("Task status updates successful")
        
    except Exception as e:
        results.add_fail(f"Task status update failed: {e}")
        logger.exception("Test failure")
        raise


async def test_task_decomposition(results: TestResults, team: Any, tasks: List[Any]) -> None:
    """Test decomposing tasks into subtasks.
    
    Args:
        results: Test results tracker
        team: Team with members
        tasks: List of created tasks
    """
    print_section("5. Task Decomposition")
    
    try:
        # Choose first task for decomposition
        parent_task = tasks[0]
        
        # Define subtasks
        subtasks = [
            {"name": f"Subtask 1 for {parent_task.name}", "priority": "medium"},
            {"name": f"Subtask 2 for {parent_task.name}", "priority": "low"},
            {"name": f"Subtask 3 for {parent_task.name}", "priority": "high"}
        ]
        
        print_info(f"Decomposing task '{parent_task.name}' into {len(subtasks)} subtasks")
        created_subtasks = team.decompose_task(parent_task.id, subtasks)
        
        # Assertions
        assert created_subtasks is not None, "Created subtasks should not be None"
        assert len(created_subtasks) == len(subtasks), f"Expected {len(subtasks)} subtasks, got {len(created_subtasks)}"
        
        # Verify subtask names
        subtask_names = [t.name for t in created_subtasks]
        expected_names = [t["name"] for t in subtasks]
        
        for name in expected_names:
            assert name in subtask_names, f"Expected subtask '{name}' not found"
        
        # Get task tree
        task_tree = team.get_task_tree(parent_task.id)
        
        # Assertions
        assert task_tree is not None, "Task tree should not be None"
        assert "subtasks" in task_tree, "Task tree should have subtasks"
        assert len(task_tree["subtasks"]) == len(subtasks), f"Task tree should have {len(subtasks)} subtasks"
        
        print_info(f"Task tree for '{parent_task.name}':")
        print_info(f"  Parent: {task_tree.get('name', 'Unknown')}")
        print_info(f"  Subtasks: {len(task_tree.get('subtasks', []))}")
        
        results.add_pass("Task decomposition successful")
        
    except Exception as e:
        results.add_fail(f"Task decomposition failed: {e}")
        logger.exception("Test failure")
        raise


async def test_task_retrieval(results: TestResults, team: Any, tasks: List[Any]) -> None:
    """Test retrieving task information.
    
    Args:
        results: Test results tracker
        team: Team with members
        tasks: List of created tasks
    """
    print_section("6. Task Retrieval")
    
    try:
        # Test getting task by ID
        task = tasks[0]
        retrieved = team.get_task(task.id)
        
        # Assertions
        assert retrieved is not None, "Retrieved task should not be None"
        assert retrieved.id == task.id, f"Expected task ID {task.id}, got {retrieved.id if retrieved else 'None'}"
        assert retrieved.name == task.name, f"Expected task name {task.name}, got {retrieved.name if retrieved else 'None'}"
        
        print_info(f"Retrieved task: {retrieved.name} (ID: {retrieved.id})")
        
        # Test non-existent task
        nonexistent = team.get_task("nonexistent-id")
        assert nonexistent is None, "Non-existent task retrieval should return None"
        
        print_info("Correctly handled non-existent task retrieval")
        
        # Get all tasks
        all_tasks = team.get_all_tasks()
        
        # Assertions
        assert all_tasks is not None, "All tasks should not be None"
        assert len(all_tasks) >= len(tasks), f"Expected at least {len(tasks)} tasks, got {len(all_tasks)}"
        
        print_info(f"Retrieved all {len(all_tasks)} tasks successfully")
        results.add_pass("Task retrieval successful")
        
    except Exception as e:
        results.add_fail(f"Task retrieval failed: {e}")
        logger.exception("Test failure")
        raise


async def main():
    """Run all task management tests."""
    print_title("TEAM MODULE - TASK MANAGEMENT TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        team = await test_team_setup(results)
        tasks = await test_task_creation(results, team)
        await test_task_assignment(results, team, tasks)
        await test_task_status_update(results, team, tasks)
        await test_task_decomposition(results, team, tasks)
        await test_task_retrieval(results, team, tasks)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All task management tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
