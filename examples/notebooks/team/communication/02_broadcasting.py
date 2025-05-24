#!/usr/bin/env python
"""
Team Broadcasting Tests

This script tests the team broadcasting functionality, including:
- Broadcasting messages to all team members
- Concurrent vs sequential broadcasting
- Handling agent errors during broadcasting
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
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.broadcasting")


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


async def test_broadcast_setup(results: TestResults) -> Any:
    """Set up a team with multiple members for broadcasting tests.
    
    Args:
        results: Test results tracker
    
    Returns:
        Team object with multiple members
    """
    print_section("1. Setting up team for broadcasting")
    
    try:
        # Create a team
        team = create_team(name="Broadcasting Team")
        
        # Add multiple agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Team Member {i+1}",
                agent_id=f"member-{i+1}"
            )
            team.add_member(agent)
        
        # Assertions
        assert len(team.get_members()) == 3, "Team should have 3 members"
        
        print_info(f"Created team with {len(team.get_members())} members")
        results.add_pass("Team setup for broadcasting successful")
        
        return team
        
    except Exception as e:
        results.add_fail(f"Team setup failed: {e}")
        logger.exception("Test failure")
        raise


async def test_sync_broadcast(results: TestResults, team: Any) -> None:
    """Test synchronous message broadcasting.
    
    Tests that messages are correctly broadcast to all team members
    in synchronous mode.
    
    Args:
        results: Test results tracker
        team: Team object from previous test
    """
    print_section("2. Synchronous Broadcasting")
    
    try:
        # Broadcast a message to all members
        test_message = "Attention all team members: This is a test broadcast."
        
        # Use timer to measure broadcast time
        timer = Timer("Sync Broadcast")
        timer.start()
        responses = team.broadcast_message(test_message)
        timer.stop()
        
        # Assertions
        assert responses is not None, "Broadcast responses should not be None"
        assert isinstance(responses, list), "Responses should be a list"
        assert len(responses) == len(team.get_members()), "Should have one response per team member"
        
        # Log responses
        print_info(f"Received {len(responses)} responses:")
        for i, response in enumerate(responses):
            print_info(f"  {i+1}. '{response.content}'")
        
        results.add_pass("Synchronous broadcast successful")
        
    except Exception as e:
        results.add_fail(f"Synchronous broadcast failed: {e}")
        logger.exception("Test failure")


async def test_async_broadcast(results: TestResults, team: Any) -> None:
    """Test asynchronous message broadcasting.
    
    Tests that messages are correctly broadcast to all team members
    in asynchronous mode, with concurrent processing.
    
    Args:
        results: Test results tracker
        team: Team object from previous test
    """
    print_section("3. Asynchronous Broadcasting")
    
    try:
        # Broadcast a message to all members asynchronously
        test_message = "Attention all team members: This is an async test broadcast."
        
        # Use timer to measure broadcast time
        timer = Timer("Async Broadcast")
        timer.start()
        responses = await team.abroadcast_message(test_message)
        timer.stop()
        
        # Assertions
        assert responses is not None, "Async broadcast responses should not be None"
        assert isinstance(responses, list), "Responses should be a list"
        assert len(responses) == len(team.get_members()), "Should have one response per team member"
        
        # Log responses
        print_info(f"Received {len(responses)} async responses:")
        for i, response in enumerate(responses):
            print_info(f"  {i+1}. '{response.content}'")
        
        results.add_pass("Asynchronous broadcast successful")
        
    except Exception as e:
        results.add_fail(f"Asynchronous broadcast failed: {e}")
        logger.exception("Test failure")


async def test_error_handling_broadcast(results: TestResults) -> None:
    """Test broadcasting with error handling.
    
    Tests that broadcasting properly handles errors when agents
    fail to process messages.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Error Handling During Broadcasts")
    
    try:
        # Create a team
        team = create_team(name="Error Handling Team")
        
        # Add a normal agent
        normal_agent = create_agent(
            agent_type="base",
            name="Normal Agent",
            agent_id="normal-001"
        )
        team.add_member(normal_agent)
        
        # Add a "faulty" agent by subclassing
        from enterprise_ai.agent.core.base import BaseAgent
        
        class FaultyAgent(BaseAgent):
            """Agent that raises errors during message processing."""
            
            def process_message(self, message, **kwargs):
                """Raise an error during processing."""
                raise RuntimeError("Simulated error in message processing")
        
        # Create and add the faulty agent
        faulty_agent = FaultyAgent(
            agent_id="faulty-001",
            name="Faulty Agent"
        )
        team.add_member(faulty_agent)
        
        # Broadcast a message
        test_message = "This message should be handled with error recovery."
        responses = team.broadcast_message(test_message)
        
        # Assertions
        assert responses is not None, "Responses should not be None"
        assert len(responses) == 2, "Should have responses for both agents"
        
        # Check error handling
        error_found = False
        for response in responses:
            if "Error" in response.content:
                error_found = True
                print_info(f"Error response found: '{response.content}'")
        
        assert error_found, "Should have an error response from the faulty agent"
        
        results.add_pass("Error handling during broadcast works correctly")
        
    except Exception as e:
        results.add_fail(f"Error handling test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all broadcasting tests."""
    print_title("TEAM MODULE - BROADCASTING TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        team = await test_broadcast_setup(results)
        await test_sync_broadcast(results, team)
        await test_async_broadcast(results, team)
        await test_error_handling_broadcast(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All broadcasting tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())