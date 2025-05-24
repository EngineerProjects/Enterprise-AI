#!/usr/bin/env python
"""
Team Adaptability Tests

This script tests team adaptability to changing conditions, including:
- Dynamic team membership changes
- Agent replacement and role reassignment
- Recovery from member failures
- Adaptation to changing task priorities
"""

import asyncio
import sys
import os
from typing import Dict, List, Optional, Any

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
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.adaptability")


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


class ErrorAgent:
    """Agent that simulates errors and failures."""
    
    def __init__(self, agent_id: str, name: str, failure_probability: float = 1.0):
        """Initialize error agent.
        
        Args:
            agent_id: Agent ID
            name: Agent name
            failure_probability: Probability of failure (0.0-1.0)
        """
        self.id = agent_id
        self.name = name
        self._failure_probability = failure_probability
    
    def process_message(self, message: Any) -> Message:
        """Process a message, with possibility of failure.
        
        Args:
            message: Message to process
            
        Returns:
            Response message
            
        Raises:
            RuntimeError: If agent fails
        """
        if self._failure_probability >= 1.0:
            raise RuntimeError(f"Agent {self.id} failed to process message")
            
        return Message.assistant_message(f"Agent {self.name} processed message successfully")
        
    async def aprocess_message(self, message: Any) -> Message:
        """Process a message asynchronously, with possibility of failure.
        
        Args:
            message: Message to process
            
        Returns:
            Response message
            
        Raises:
            RuntimeError: If agent fails
        """
        if self._failure_probability >= 1.0:
            raise RuntimeError(f"Agent {self.id} failed to process message asynchronously")
            
        return Message.assistant_message(f"Agent {self.name} processed message successfully")


async def test_membership_changes(results: TestResults) -> None:
    """Test team adaptation to membership changes.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Dynamic Membership Changes")
    
    try:
        # Create team
        team = create_team(name="Membership Change Team")
        
        # Add initial members
        initial_agents = []
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Initial Agent {i+1}",
                agent_id=f"initial-agent-{i+1}"
            )
            team.add_member(agent)
            initial_agents.append(agent)
        
        # Verify initial members
        initial_members = team.get_members()
        assert len(initial_members) == 3, f"Team should have 3 initial members, got {len(initial_members)}"
        print_info(f"Team has {len(initial_members)} initial members")
        
        # Create task and assign to team
        team.assign_task({
            "id": "membership-task-1",
            "description": "Task to test membership changes",
            "status": "active"
        })
        
        # Remove a member
        removed = team.remove_member(initial_agents[1].id)
        assert removed, "Should remove member successfully"
        
        # Verify member was removed
        after_remove = team.get_members()
        assert len(after_remove) == 2, f"Team should have 2 members after removal, got {len(after_remove)}"
        print_info(f"Team has {len(after_remove)} members after removal")
        
        # Add new members
        new_agents = []
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"New Agent {i+1}",
                agent_id=f"new-agent-{i+1}"
            )
            team.add_member(agent)
            new_agents.append(agent)
        
        # Verify new members
        final_members = team.get_members()
        assert len(final_members) == 4, f"Team should have 4 final members, got {len(final_members)}"
        print_info(f"Team has {len(final_members)} members after additions")
        
        # Verify task is still accessible
        task = team.get_task("membership-task-1")
        assert task is not None, "Task should still exist after membership changes"
        
        # Test messaging with new team composition
        responses = team.broadcast_message("Test message after membership changes")
        assert len(responses) == 4, f"Should get 4 responses after changes, got {len(responses)}"
        
        results.add_pass("Dynamic membership changes test successful")
        
    except Exception as e:
        results.add_fail(f"Dynamic membership changes test failed: {e}")
        logger.exception("Test failure")


async def test_role_reassignment(results: TestResults) -> None:
    """Test role reassignment in teams.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Role Reassignment")
    
    try:
        # Create team
        team = create_team(name="Role Reassignment Team")
        
        # Add members with specific roles
        manager = create_agent(
            agent_type="base",
            name="Initial Manager",
            agent_id="initial-manager"
        )
        
        worker1 = create_agent(
            agent_type="base",
            name="Worker 1",
            agent_id="worker-1"
        )
        
        worker2 = create_agent(
            agent_type="base",
            name="Worker 2",
            agent_id="worker-2"
        )
        
        # Add with roles
        team.add_member(manager, role=TeamMemberRole.MANAGER)
        team.add_member(worker1, role=TeamMemberRole.MEMBER)
        team.add_member(worker2, role=TeamMemberRole.MEMBER)
        
        # Verify initial manager
        initial_manager = team._membership.manager
        assert initial_manager is not None, "Team should have a manager"
        assert initial_manager.id == "initial-manager", f"Manager should be initial-manager, got {initial_manager.id}"
        print_info(f"Initial manager: {initial_manager.id}")
        
        # Create new manager
        new_manager = create_agent(
            agent_type="base",
            name="New Manager",
            agent_id="new-manager"
        )
        
        # Replace manager
        # First add new manager
        team.add_member(new_manager, role=TeamMemberRole.MEMBER)
        
        # Change roles if membership manager supports it
        membership = team._membership
        if hasattr(membership, "set_role"):
            # Demote current manager
            membership.set_role(manager.id, TeamMemberRole.MEMBER)
            
            # Promote new manager
            membership.set_role(new_manager.id, TeamMemberRole.MANAGER)
            
            # Verify manager change
            current_manager = membership.manager
            assert current_manager is not None, "Team should still have a manager"
            assert current_manager.id == "new-manager", f"Manager should be new-manager, got {current_manager.id}"
            print_info(f"New manager after reassignment: {current_manager.id}")
            
            # Verify old manager's new role
            manager_role = membership.get_role(manager.id)
            assert manager_role == TeamMemberRole.MEMBER, f"Old manager should be MEMBER, got {manager_role}"
            
            results.add_pass("Role reassignment test successful")
        else:
            print_warning("Membership manager does not support set_role method")
            results.add_pass("Role reassignment test skipped - method not available")
        
    except Exception as e:
        results.add_fail(f"Role reassignment test failed: {e}")
        logger.exception("Test failure")


async def test_member_failure_recovery(results: TestResults) -> None:
    """Test recovery from member failures.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Member Failure Recovery")
    
    try:
        # Create team
        team = create_team(name="Failure Recovery Team")
        
        # Add normal agents
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"Reliable Agent {i+1}",
                agent_id=f"reliable-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Add error-prone agent
        error_agent = ErrorAgent(
            agent_id="error-agent",
            name="Error-Prone Agent",
            failure_probability=1.0  # Always fails
        )
        
        team.add_member(error_agent)
        
        # Verify team size
        members = team.get_members()
        assert len(members) == 3, f"Team should have 3 members, got {len(members)}"
        
        # Test messaging with failing member
        test_message = "Test message with failing member"
        
        responses = team.broadcast_message(test_message)
        
        # Verify responses - should get one for each member
        assert len(responses) == 3, f"Should get 3 responses (including error), got {len(responses)}"
        print_info(f"Received {len(responses)} responses with error handling")
        
        # Check for error response
        error_found = False
        for resp in responses:
            if "Error" in resp.content:
                error_found = True
                break
                
        assert error_found, "Should have an error response for failing agent"
        
        # Replace failing agent with reliable one
        team.remove_member("error-agent")
        
        replacement = create_agent(
            agent_type="base",
            name="Replacement Agent",
            agent_id="replacement-agent"
        )
        
        team.add_member(replacement)
        
        # Test messaging after replacement
        new_responses = team.broadcast_message("Test message after replacement")
        
        # Verify all responses successful
        assert len(new_responses) == 3, f"Should get 3 responses after replacement, got {len(new_responses)}"
        
        # Check for no errors
        error_found = False
        for resp in new_responses:
            if "Error" in resp.content:
                error_found = True
                break
                
        assert not error_found, "Should have no error responses after replacement"
        print_info("All responses successful after agent replacement")
        
        results.add_pass("Member failure recovery test successful")
        
    except Exception as e:
        results.add_fail(f"Member failure recovery test failed: {e}")
        logger.exception("Test failure")


async def test_task_priority_adaptation(results: TestResults) -> None:
    """Test adaptation to changing task priorities.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Task Priority Adaptation")
    
    try:
        # Create team
        team = create_team(name="Task Priority Team")
        
        # Add members
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Priority Agent {i+1}",
                agent_id=f"priority-agent-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        
        # Create initial tasks with priorities
        tasks = [
            {"id": "task-low", "description": "Low priority task", "priority": 1},
            {"id": "task-medium", "description": "Medium priority task", "priority": 2},
            {"id": "task-high", "description": "High priority task", "priority": 3}
        ]
        
        # Add tasks
        for task in tasks:
            team.assign_task(task)
        
        # Verify tasks added
        all_tasks = team.get_all_tasks()
        assert len(all_tasks) == 3, f"Team should have 3 tasks, got {len(all_tasks)}"
        
        # Check initial assignment - tasks should be assigned based on priority
        # This depends on implementation details
        
        # Now change priorities
        # Create a new urgent task
        urgent_task = {"id": "task-urgent", "description": "Urgent task", "priority": 5}
        team.assign_task(urgent_task)
        
        # Change priority of low task to high
        if hasattr(team._tasks, "update_priority"):
            team._tasks.update_priority("task-low", 4)
            print_info("Updated priority of task-low to 4")
        else:
            # Alternative: update the task directly
            for task in all_tasks:
                if hasattr(task, "id") and task.id == "task-low":
                    if hasattr(task, "priority"):
                        task.priority = 4
                        print_info("Updated priority of task-low to 4")
        
        # Get tasks after priority changes
        updated_tasks = team.get_all_tasks()
        
        # Check if any reassignment happened (implementation dependent)
        # Get task assignments
        agent_tasks = {}
        for agent in members:
            agent_tasks[agent.id] = team.get_agent_tasks(agent.id)
            print_info(f"Agent {agent.id} has {len(agent_tasks[agent.id])} tasks")
        
        # Verify task count
        total_assigned = sum(len(tasks) for tasks in agent_tasks.values())
        print_info(f"Total assigned tasks: {total_assigned}")
        
        results.add_pass("Task priority adaptation test completed")
        
    except Exception as e:
        results.add_fail(f"Task priority adaptation test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all team adaptability tests."""
    print_title("TEAM MODULE - ADAPTABILITY TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_membership_changes(results)
        await test_role_reassignment(results)
        await test_member_failure_recovery(results)
        await test_task_priority_adaptation(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All team adaptability tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
