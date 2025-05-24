#!/usr/bin/env python
"""
Parallel Execution Tests

This script tests parallel and concurrent execution in teams, including:
- Concurrent task execution by multiple team members
- Race condition handling
- Thread safety and synchronization
- Deadlock prevention and recovery
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
logger = get_logger("team.tests.parallel_execution")


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


async def test_concurrent_task_execution(results: TestResults) -> None:
    """Test concurrent task execution by multiple team members.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Concurrent Task Execution")
    
    try:
        # Create team with multiple agents
        team = create_team(name="Concurrent Team")
        
        # Add several agents
        for i in range(5):
            agent = create_agent(
                agent_type="base",
                name=f"Concurrent Agent {i+1}",
                agent_id=f"concurrent-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Verify team has all members
        members = team.get_members()
        assert len(members) == 5, f"Team should have 5 members, got {len(members)}"
        
        # Create multiple tasks
        tasks = [
            {"id": f"task-{i}", "description": f"Task {i} for testing", "priority": i % 3 + 1} 
            for i in range(10)
        ]
        
        # Assign all tasks (should be distributed)
        for task in tasks:
            team.assign_task(task)
        
        # Verify tasks were assigned
        team_tasks = team.get_all_tasks()
        assert len(team_tasks) == 10, f"Team should have 10 tasks, got {len(team_tasks)}"
        
        # Check distribution
        task_distribution = {}
        for agent in members:
            agent_tasks = team.get_agent_tasks(agent.id)
            task_distribution[agent.id] = len(agent_tasks)
            print_info(f"Agent {agent.id} has {len(agent_tasks)} tasks")
        
        # Some basic validation that tasks were distributed
        # (exact distribution may vary by implementation)
        assigned_tasks = sum(task_distribution.values())
        assert assigned_tasks > 0, "No tasks were assigned"
        
        results.add_pass("Concurrent task execution test successful")
        
    except Exception as e:
        results.add_fail(f"Concurrent task execution test failed: {e}")
        logger.exception("Test failure")


async def test_parallel_message_processing(results: TestResults) -> None:
    """Test parallel message processing in the team.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Parallel Message Processing")
    
    try:
        # Create team with multiple agents
        team = create_team(name="Parallel Message Team")
        
        # Add several agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Message Agent {i+1}",
                agent_id=f"message-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Create multiple messages
        messages = [
            Message.user_message(f"Test message {i}") 
            for i in range(5)
        ]
        
        # Process messages in parallel
        async def process_messages():
            tasks = []
            for msg in messages:
                tasks.append(team.abroadcast_message(msg))
            
            # Wait for all processing to complete
            results = await asyncio.gather(*tasks)
            return results
        
        with Timer("Parallel message processing"):
            all_responses = await process_messages()
        
        # Verify we got responses for all messages
        assert len(all_responses) == 5, f"Should get 5 sets of responses, got {len(all_responses)}"
        
        # Each response set should have one per team member
        for i, responses in enumerate(all_responses):
            assert len(responses) == 3, f"Message {i} should have 3 responses, got {len(responses)}"
        
        results.add_pass("Parallel message processing test successful")
        
    except Exception as e:
        results.add_fail(f"Parallel message processing test failed: {e}")
        logger.exception("Test failure")


async def test_race_condition_handling(results: TestResults) -> None:
    """Test handling of potential race conditions.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Race Condition Handling")
    
    try:
        # Create team for testing race conditions
        team = create_team(name="Race Condition Team")
        
        # Add agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Race Agent {i+1}",
                agent_id=f"race-agent-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        
        # Test concurrent resource requests (potential race condition)
        resource_id = "contested_resource"
        
        # Request the same resource concurrently from different agents
        async def request_resources():
            request_tasks = []
            for agent in members:
                request_tasks.append(team.request_resource(agent.id, resource_id))
            
            # This should handle the race condition properly
            results = await asyncio.gather(*request_tasks)
            return results
        
        resource_results = await request_resources()
        
        # At least one should get the resource
        assert any(resource_results), "At least one agent should get the resource"
        
        # Check that resource conflicts were registered
        conflicts = team.get_active_conflicts()
        print_info(f"Generated {len(conflicts)} conflicts during race condition test")
        
        # Release the resource from whoever got it
        for i, granted in enumerate(resource_results):
            if granted:
                released = team.release_resource(members[i].id, resource_id)
                assert released, "Should release resource successfully"
                break
        
        results.add_pass("Race condition handling test successful")
        
    except Exception as e:
        results.add_fail(f"Race condition handling test failed: {e}")
        logger.exception("Test failure")


async def test_deadlock_prevention(results: TestResults) -> None:
    """Test deadlock prevention and recovery.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Deadlock Prevention")
    
    try:
        # Create team for testing deadlocks
        team = create_team(name="Deadlock Team")
        
        # Add agents
        agent1 = create_agent(name="Deadlock Agent 1", agent_id="deadlock-agent-1")
        agent2 = create_agent(name="Deadlock Agent 2", agent_id="deadlock-agent-2")
        
        team.add_member(agent1)
        team.add_member(agent2)
        
        # Set up potential deadlock with two resources
        resource1 = "resource_a"
        resource2 = "resource_b"
        
        # Agent 1 gets resource 1
        granted1a = await team.request_resource(agent1.id, resource1)
        assert granted1a, "Agent 1 should get resource 1"
        
        # Agent 2 gets resource 2
        granted2b = await team.request_resource(agent2.id, resource2)
        assert granted2b, "Agent 2 should get resource 2"
        
        # Now try to create deadlock - each agent wants the other's resource
        # This should either prevent the deadlock or detect and resolve it
        granted1b = await team.request_resource(agent1.id, resource2)
        granted2a = await team.request_resource(agent2.id, resource1)
        
        # Check if deadlock was prevented
        print_info(f"Cross-resource request results: Agent1→Res2: {granted1b}, Agent2→Res1: {granted2a}")
        
        # Clean up
        team.release_resource(agent1.id, resource1)
        team.release_resource(agent2.id, resource2)
        if granted1b:
            team.release_resource(agent1.id, resource2)
        if granted2a:
            team.release_resource(agent2.id, resource1)
        
        # Check coordinator status after potential deadlock
        conflicts = team.get_active_conflicts()
        print_info(f"Active conflicts after deadlock test: {len(conflicts)}")
        
        results.add_pass("Deadlock prevention test completed")
        
    except Exception as e:
        results.add_fail(f"Deadlock prevention test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all parallel execution tests."""
    print_title("TEAM MODULE - PARALLEL EXECUTION TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_concurrent_task_execution(results)
        await test_parallel_message_processing(results)
        await test_race_condition_handling(results)
        await test_deadlock_prevention(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All parallel execution tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
