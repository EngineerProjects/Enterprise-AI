#!/usr/bin/env python
"""
Team Lifecycle Tests

This script tests team lifecycle functionality, including:
- Initialization with various parameters
- Graceful termination and resource cleanup
- Lifecycle state transitions
- Event handlers and callbacks
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
from enterprise_ai.team.architecture.lifecycle import TeamState
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.lifecycle")


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


async def test_team_initialization(results: TestResults) -> None:
    """Test team initialization with various parameters.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Team Initialization")
    
    try:
        # Create team with initialization parameters
        team = create_team(
            name="Lifecycle Init Team",
            max_members=5
        )
        
        # Verify team creation
        assert team is not None, "Team should be created"
        assert team.name == "Lifecycle Init Team", f"Team should have correct name, got {team.name}"
        
        # Add some agents
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"Init Agent {i+1}",
                agent_id=f"init-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Initialize with discover_tools=True
        init_result = await team.initialize(discover_tools=True)
        
        assert init_result, "Initialization should succeed"
        print_info("Team initialized successfully")
        
        # Get lifecycle status
        lifecycle_manager = team._lifecycle
        state = lifecycle_manager.state if hasattr(lifecycle_manager, "state") else "Unknown"
        
        print_info(f"Team state after initialization: {state}")
        
        # Check if team is initialized
        assert state != TeamState.UNINITIALIZED, "Team should not be in UNINITIALIZED state after initialization"
        
        results.add_pass("Team initialization test successful")
        
    except Exception as e:
        results.add_fail(f"Team initialization test failed: {e}")
        logger.exception("Test failure")


async def test_lifecycle_state_transitions(results: TestResults) -> None:
    """Test team lifecycle state transitions.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Lifecycle State Transitions")
    
    try:
        # Create team
        team = create_team(name="State Transition Team")
        
        # Check initial state
        lifecycle_manager = team._lifecycle
        initial_state = lifecycle_manager.state if hasattr(lifecycle_manager, "state") else "Unknown"
        
        print_info(f"Initial team state: {initial_state}")
        
        # Initialize team
        init_result = await team.initialize()
        assert init_result, "Initialization should succeed"
        
        # Check state after initialization
        init_state = lifecycle_manager.state if hasattr(lifecycle_manager, "state") else "Unknown"
        print_info(f"Team state after initialization: {init_state}")
        
        # Verify state transition
        assert init_state != initial_state, "State should change after initialization"
        
        # Add a member after initialization
        agent = create_agent(
            agent_type="base",
            name="Lifecycle Agent",
            agent_id="lifecycle-agent-1"
        )
        added = team.add_member(agent)
        assert added, "Should add member after initialization"
        
        # Terminate team
        term_result = await team.terminate()
        assert term_result, "Termination should succeed"
        
        # Check state after termination
        term_state = lifecycle_manager.state if hasattr(lifecycle_manager, "state") else "Unknown"
        print_info(f"Team state after termination: {term_state}")
        
        # Verify termination state
        assert term_state != init_state, "State should change after termination"
        
        # Try adding member after termination (should fail)
        agent2 = create_agent(
            agent_type="base",
            name="Post-Term Agent",
            agent_id="post-term-agent"
        )
        added2 = team.add_member(agent2)
        assert not added2, "Should not add member after termination"
        
        results.add_pass("Lifecycle state transitions test successful")
        
    except Exception as e:
        results.add_fail(f"Lifecycle state transitions test failed: {e}")
        logger.exception("Test failure")


async def test_resource_cleanup(results: TestResults) -> None:
    """Test resource cleanup during termination.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Resource Cleanup")
    
    try:
        # Create team with resources
        team = create_team(name="Resource Cleanup Team")
        
        # Add agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Resource Agent {i+1}",
                agent_id=f"resource-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Initialize team
        await team.initialize()
        
        # Start sync if supported
        if hasattr(team, "_state_sync"):
            state_sync = team._state_sync
            if hasattr(state_sync, "start_periodic_sync"):
                state_sync.start_periodic_sync()
                print_info("Started periodic sync")
        
        # Create some tasks
        for i in range(5):
            team.assign_task({
                "id": f"cleanup-task-{i}",
                "description": f"Cleanup test task {i}"
            })
        
        # Verify resources are created
        tasks_before = team.get_all_tasks()
        print_info(f"Tasks before termination: {len(tasks_before)}")
        
        # Get status before termination
        status_before = team.get_status()
        print_info(f"Team status before termination: {status_before.keys()}")
        
        # Terminate team
        term_result = await team.terminate()
        assert term_result, "Termination should succeed"
        
        # Verify resources are cleaned up
        # This depends on the implementation, but we can check a few things
        
        # If state sync is running, it should be stopped
        if hasattr(team, "_state_sync") and hasattr(team._state_sync, "_running"):
            assert not team._state_sync._running, "State sync should be stopped after termination"
        
        # Try to verify task cleanup (implementation dependent)
        if hasattr(team._tasks, "_tasks"):
            active_tasks = len(team._tasks._tasks)
            print_info(f"Active tasks after termination: {active_tasks}")
        
        results.add_pass("Resource cleanup test completed")
        
    except Exception as e:
        results.add_fail(f"Resource cleanup test failed: {e}")
        logger.exception("Test failure")


async def test_lifecycle_events(results: TestResults) -> None:
    """Test lifecycle events and callbacks.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Lifecycle Events")
    
    try:
        # Event tracking for testing
        events = []
        
        # Create event handlers
        def on_init(team_id: str):
            events.append(f"init:{team_id}")
            print_info(f"Init event for team: {team_id}")
        
        def on_term(team_id: str):
            events.append(f"term:{team_id}")
            print_info(f"Term event for team: {team_id}")
        
        # Create team
        team = create_team(name="Event Team")
        
        # Register event handlers if supported
        lifecycle_manager = team._lifecycle
        if hasattr(lifecycle_manager, "register_event_handler"):
            lifecycle_manager.register_event_handler("initialized", on_init)
            lifecycle_manager.register_event_handler("terminated", on_term)
            print_info("Registered event handlers")
        else:
            print_warning("Lifecycle manager does not support event handlers")
        
        # Initialize team
        await team.initialize()
        
        # Terminate team
        await team.terminate()
        
        # Check events
        print_info(f"Recorded events: {events}")
        
        # Verify events if supported
        if hasattr(lifecycle_manager, "register_event_handler"):
            assert len(events) > 0, "Should have recorded some events"
            
            # Check for init event
            init_events = [e for e in events if e.startswith("init:")]
            assert len(init_events) > 0, "Should have recorded init event"
            
            # Check for term event
            term_events = [e for e in events if e.startswith("term:")]
            assert len(term_events) > 0, "Should have recorded term event"
        
        results.add_pass("Lifecycle events test completed")
        
    except Exception as e:
        results.add_fail(f"Lifecycle events test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all team lifecycle tests."""
    print_title("TEAM MODULE - LIFECYCLE TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_team_initialization(results)
        await test_lifecycle_state_transitions(results)
        await test_resource_cleanup(results)
        await test_lifecycle_events(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All team lifecycle tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
