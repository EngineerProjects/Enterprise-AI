#!/usr/bin/env python
"""
Team Messaging Tests

This script tests the team messaging functionality, including:
- Direct message processing by the team
- Message routing to appropriate team members
- Async vs sync message processing
- Integration with prompt templates
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
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.messaging")


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


async def test_direct_message_processing(results: TestResults) -> Tuple[Any, Any]:
    """Test team handling of direct messages.
    
    Tests sending messages directly to the team and verifying responses.
    
    Args:
        results: Test results tracker
    
    Returns:
        Tuple of (team, test_message)
    """
    print_section("1. Direct Message Processing")
    
    try:
        # Create a team
        team = create_team(name="Messaging Team")
        
        # Test message processing
        test_message = "Hello, team!"
        
        # Process as string
        response = team.process_message(test_message) 
        
        # Assertions
        assert response is not None, "Response should not be None"
        assert hasattr(response, "content"), "Response should have content"
        assert isinstance(response.content, str), "Response content should be a string"
        assert len(response.content) > 0, "Response content should not be empty"
        
        print_info(f"Team response: '{response.content}'")
        results.add_pass("Direct string message processed successfully")
        
        # Test with Message object
        message_obj = Message.user_message("Hello again, team!")
        response = team.process_message(message_obj)
        
        # Assertions
        assert response is not None, "Response should not be None"
        assert hasattr(response, "content"), "Response should have content"
        assert isinstance(response.content, str), "Response content should be a string"
        assert len(response.content) > 0, "Response content should not be empty"
        
        print_info(f"Team response to Message object: '{response.content}'")
        results.add_pass("Direct Message object processed successfully")
        
        return team, test_message
        
    except Exception as e:
        results.add_fail(f"Direct message processing failed: {e}")
        logger.exception("Test failure")
        raise


async def test_async_message_processing(results: TestResults, team: Any, test_message: str) -> None:
    """Test asynchronous message processing.
    
    Tests the async message processing capabilities of the team.
    
    Args:
        results: Test results tracker
        team: Team object from previous test
        test_message: Test message string
    """
    print_section("2. Asynchronous Message Processing")
    
    try:
        # Process message asynchronously
        response = await team.aprocess_message(test_message)
        
        # Assertions
        assert response is not None, "Async response should not be None"
        assert hasattr(response, "content"), "Async response should have content"
        assert isinstance(response.content, str), "Async response content should be a string"
        assert len(response.content) > 0, "Async response content should not be empty"
        
        print_info(f"Async response: '{response.content}'")
        results.add_pass("Async message processing works correctly")
        
    except Exception as e:
        results.add_fail(f"Async message processing failed: {e}")
        logger.exception("Test failure")


async def test_message_routing(results: TestResults) -> None:
    """Test message routing to appropriate team members.
    
    Tests that messages are correctly routed to the right team members
    based on content and member roles.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Message Routing")
    
    try:
        # Create a team with specialized members
        team = create_team(name="Routing Team")
        
        # Add specialized agents
        tech_agent = create_agent(
            agent_type="base",
            name="Tech Specialist",
            agent_id="tech-001",
            metadata={"expertise": "technology"}
        )
        
        finance_agent = create_agent(
            agent_type="base",
            name="Finance Specialist",
            agent_id="finance-001",
            metadata={"expertise": "finance"}
        )
        
        team.add_member(tech_agent)
        team.add_member(finance_agent)
        
        # Test routing - in a real implementation, you would have logic to route
        # For now, we'll just test basic message handling in a team with members
        
        test_message = "Please help with the technical documentation"
        response = team.process_message(test_message)
        
        # Assertions
        assert response is not None, "Response should not be None"
        print_info(f"Team response: '{response.content}'")
        
        results.add_pass("Message handling in team with specialized members works")
        
    except Exception as e:
        results.add_fail(f"Message routing test failed: {e}")
        logger.exception("Test failure")


async def test_prompt_template_integration(results: TestResults) -> None:
    """Test integration with team prompt templates.
    
    Tests that team messaging properly incorporates prompt templates
    to guide agent behavior.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Prompt Template Integration")
    
    try:
        # In a real implementation, you would test with actual LLM agents that use templates
        # For now, we'll just verify that prompt templates are accessible
        
        from enterprise_ai.prompt import get_prompt
        
        # Try to load a team collaboration template
        template = get_prompt("team.collaboration")
        
        # Assertions
        assert template is not None, "Team collaboration template should be loadable"
        assert len(template.template_str) > 0, "Template should not be empty"
        
        print_info(f"Successfully loaded team collaboration template ({len(template.template_str)} chars)")
        results.add_pass("Team prompt template loading works")
        
        # In a more complete test, you would create agents with these templates
        # and test actual message processing behavior
        
    except Exception as e:
        results.add_fail(f"Prompt template integration test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all messaging tests."""
    print_title("TEAM MODULE - MESSAGING TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        team, test_message = await test_direct_message_processing(results)
        await test_async_message_processing(results, team, test_message)
        await test_message_routing(results)
        await test_prompt_template_integration(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All messaging tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
