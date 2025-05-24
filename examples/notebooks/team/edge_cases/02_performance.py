#!/usr/bin/env python
"""
Performance Tests

This script tests performance aspects of the team module, including:
- Scaling with large numbers of agents
- Memory usage profiling
- Response time benchmarking
- Resource utilization optimization
"""

import asyncio
import sys
import os
import time
import gc
import tracemalloc
from typing import Dict, List, Optional, Any, Tuple

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
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.performance")


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


def measure_memory_usage(func) -> Tuple[Any, int]:
    """Measure memory usage of a function.
    
    Args:
        func: Function to measure
        
    Returns:
        Tuple of (function result, memory usage in bytes)
    """
    # Start tracking memory
    tracemalloc.start()
    gc.collect()
    
    # Run function
    result = func()
    
    # Get memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    return result, peak


async def test_team_scaling(results: TestResults) -> None:
    """Test team scaling with increasing number of agents.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Team Scaling")
    
    try:
        # Test with increasing team sizes
        team_sizes = [5, 10, 20]
        
        for size in team_sizes:
            print_info(f"Testing team with {size} agents")
            
            # Create team
            team = create_team(name=f"Scaling Team {size}")
            
            # Measure memory usage when adding agents
            def add_agents():
                for i in range(size):
                    agent = create_agent(
                        agent_type="base",
                        name=f"Scale Agent {i+1}",
                        agent_id=f"scale-agent-{size}-{i+1}"
                    )
                    team.add_member(agent)
                return team
            
            with Timer(f"Creating team with {size} agents"):
                result, memory_usage = measure_memory_usage(add_agents)
            
            print_info(f"Memory usage for {size} agents: {memory_usage / 1024 / 1024:.2f} MB")
            
            # Verify all agents were added
            members = team.get_members()
            assert len(members) == size, f"Team should have {size} members, got {len(members)}"
            
            # Test broadcast performance
            test_message = "Test message for scaling benchmark"
            
            with Timer(f"Broadcasting to {size} agents"):
                responses = team.broadcast_message(test_message)
            
            assert len(responses) == size, f"Should get {size} responses, got {len(responses)}"
            
            # Test async broadcast performance
            with Timer(f"Async broadcasting to {size} agents"):
                async_responses = await team.abroadcast_message(test_message)
            
            assert len(async_responses) == size, f"Should get {size} async responses, got {len(async_responses)}"
            
            # Clean up
            await team.terminate()
            del team
            gc.collect()
        
        results.add_pass("Team scaling test successful")
        
    except Exception as e:
        results.add_fail(f"Team scaling test failed: {e}")
        logger.exception("Test failure")


async def test_task_performance(results: TestResults) -> None:
    """Test task creation and assignment performance.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Task Performance")
    
    try:
        # Create team with moderate number of agents
        team = create_team(name="Task Performance Team")
        
        # Add agents
        for i in range(10):
            agent = create_agent(
                agent_type="base",
                name=f"Task Agent {i+1}",
                agent_id=f"task-perf-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Test task creation performance with increasing number of tasks
        task_counts = [10, 50, 100]
        
        for count in task_counts:
            print_info(f"Testing with {count} tasks")
            
            # Create tasks
            with Timer(f"Creating {count} tasks"):
                for i in range(count):
                    team.assign_task({
                        "id": f"perf-task-{count}-{i}",
                        "description": f"Performance test task {i}",
                        "priority": i % 3 + 1
                    })
            
            # Get all tasks
            with Timer(f"Retrieving {count} tasks"):
                tasks = team.get_all_tasks()
            
            assert len(tasks) >= count, f"Should have at least {count} tasks, got {len(tasks)}"
            
            # Get task tree
            with Timer(f"Building task tree for {count} tasks"):
                tree = team.get_task_tree()
            
            # Get task summary
            with Timer(f"Getting task summary for {count} tasks"):
                summary = team.get_task_summary()
            
            print_info(f"Task summary: {summary}")
        
        # Clean up
        await team.terminate()
        
        results.add_pass("Task performance test successful")
        
    except Exception as e:
        results.add_fail(f"Task performance test failed: {e}")
        logger.exception("Test failure")


async def test_response_time(results: TestResults) -> None:
    """Test response time for various operations.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Response Time")
    
    try:
        # Create team
        team = create_team(name="Response Time Team")
        
        # Add agents
        for i in range(5):
            agent = create_agent(
                agent_type="base",
                name=f"Response Agent {i+1}",
                agent_id=f"response-agent-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        
        # Test response time for common operations
        
        # Message processing
        test_message = "Test message for response time"
        
        with Timer("Team message processing"):
            response = team.process_message(test_message)
        
        # Async message processing
        with Timer("Team async message processing"):
            async_response = await team.aprocess_message(test_message)
        
        # Broadcasting
        with Timer("Team message broadcasting"):
            responses = team.broadcast_message(test_message)
        
        # Async broadcasting
        with Timer("Team async broadcasting"):
            async_responses = await team.abroadcast_message(test_message)
        
        # Task assignment
        with Timer("Task assignment"):
            team.assign_task({
                "id": "response-task-1",
                "description": "Response time test task"
            })
        
        # Task retrieval
        with Timer("Task retrieval"):
            task = team.get_task("response-task-1")
        
        # Status retrieval
        with Timer("Status retrieval"):
            status = team.get_status()
        
        # Resource request
        with Timer("Resource request"):
            granted = await team.request_resource(members[0].id, "response_resource")
        
        # Clean up
        await team.terminate()
        
        results.add_pass("Response time test successful")
        
    except Exception as e:
        results.add_fail(f"Response time test failed: {e}")
        logger.exception("Test failure")


async def test_resource_utilization(results: TestResults) -> None:
    """Test resource utilization optimization.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Resource Utilization")
    
    try:
        # Create team
        team = create_team(name="Resource Utilization Team")
        
        # Add agents
        for i in range(5):
            agent = create_agent(
                agent_type="base",
                name=f"Utilization Agent {i+1}",
                agent_id=f"util-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Test memory usage during operations
        
        # Measure baseline
        gc.collect()
        tracemalloc.start()
        
        # Create tasks
        for i in range(20):
            team.assign_task({
                "id": f"util-task-{i}",
                "description": f"Utilization test task {i}"
            })
        
        # Check memory usage
        current1, peak1 = tracemalloc.get_traced_memory()
        print_info(f"Memory after task creation: {current1 / 1024 / 1024:.2f} MB")
        
        # Broadcast messages
        for i in range(5):
            team.broadcast_message(f"Utilization test message {i}")
        
        # Check memory usage
        current2, peak2 = tracemalloc.get_traced_memory()
        print_info(f"Memory after broadcasts: {current2 / 1024 / 1024:.2f} MB")
        
        # Calculate increase
        increase = (current2 - current1) / 1024 / 1024
        print_info(f"Memory increase from broadcasts: {increase:.2f} MB")
        
        # Stop tracking
        tracemalloc.stop()
        
        # Clean up
        await team.terminate()
        
        results.add_pass("Resource utilization test successful")
        
    except Exception as e:
        results.add_fail(f"Resource utilization test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all performance tests."""
    print_title("TEAM MODULE - PERFORMANCE TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_team_scaling(results)
        await test_task_performance(results)
        await test_response_time(results)
        await test_resource_utilization(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All performance tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
