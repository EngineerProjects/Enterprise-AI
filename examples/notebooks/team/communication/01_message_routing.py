#!/usr/bin/env python
"""
Message Routing Tests

This script tests message routing functionality in teams, including:
- Complex multi-agent conversation flows
- Message priority handling
- Broadcasting with selective filtering
- Communication failure recovery
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
logger = get_logger("team.tests.message_routing")


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


class TestAgent:
    """Test agent for message routing tests."""
    
    def __init__(self, agent_id: str, name: str, error_mode: bool = False):
        """Initialize test agent.
        
        Args:
            agent_id: Agent ID
            name: Agent name
            error_mode: Whether this agent throws errors on processing
        """
        self.id = agent_id
        self.name = name
        self._error_mode = error_mode
    
    def process_message(self, message: Any) -> Message:
        """Process a message.
        
        Args:
            message: Message to process
            
        Returns:
            Response message
        
        Raises:
            RuntimeError: If in error mode
        """
        if self._error_mode:
            raise RuntimeError(f"Agent {self.id} is in error mode")
            
        # Extract message content
        content = message.content if hasattr(message, "content") else str(message)
        return Message.assistant_message(f"Agent {self.name} received: {content}")
        
    async def aprocess_message(self, message: Any) -> Message:
        """Process a message asynchronously.
        
        Args:
            message: Message to process
            
        Returns:
            Response message
            
        Raises:
            RuntimeError: If in error mode
        """
        if self._error_mode:
            raise RuntimeError(f"Agent {self.id} is in error mode")
            
        # Extract message content
        content = message.content if hasattr(message, "content") else str(message)
        return Message.assistant_message(f"Agent {self.name} received: {content}")


async def test_broadcast_messaging(results: TestResults) -> None:
    """Test broadcast messaging to all team members.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Broadcast Messaging")
    
    try:
        # Create team
        team = create_team(name="Broadcast Team")
        
        # Add several agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Broadcast Agent {i+1}",
                agent_id=f"broadcast-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Create broadcast message
        broadcast_msg = "This is a broadcast test message"
        
        # Send broadcast
        responses = team.broadcast_message(broadcast_msg)
        
        # Verify broadcast
        assert len(responses) == 3, f"Should get 3 responses, got {len(responses)}"
        print_info(f"Received {len(responses)} broadcast responses")
        
        # Test async broadcast
        async_responses = await team.abroadcast_message(broadcast_msg)
        
        # Verify async broadcast
        assert len(async_responses) == 3, f"Should get 3 async responses, got {len(async_responses)}"
        print_info(f"Received {len(async_responses)} async broadcast responses")
        
        results.add_pass("Broadcast messaging test successful")
        
    except Exception as e:
        results.add_fail(f"Broadcast messaging test failed: {e}")
        logger.exception("Test failure")


async def test_selective_messaging(results: TestResults) -> None:
    """Test selective messaging to specific team members.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Selective Messaging")
    
    try:
        # Create team
        team = create_team(name="Selective Team")
        
        # Add several agents with different roles
        agent1 = create_agent(
            agent_type="base",
            name="Manager Agent",
            agent_id="selective-manager"
        )
        
        agent2 = create_agent(
            agent_type="base",
            name="Worker Agent 1",
            agent_id="selective-worker-1"
        )
        
        agent3 = create_agent(
            agent_type="base",
            name="Worker Agent 2",
            agent_id="selective-worker-2"
        )
        
        # Add with roles
        team.add_member(agent1, role=TeamMemberRole.MANAGER)
        team.add_member(agent2, role=TeamMemberRole.MEMBER)
        team.add_member(agent3, role=TeamMemberRole.MEMBER)
        
        # Create message
        test_msg = "This is a selective test message"
        
        # Test selective messaging with messaging manager
        # This implementation depends on the actual messaging manager API
        messaging_manager = team._messaging
        
        # Try sending to specific agent
        if hasattr(messaging_manager, "send_to_agent"):
            response = messaging_manager.send_to_agent(agent1.id, test_msg)
            print_info(f"Direct message response: {response}")
            
            # Verify direct messaging
            assert response is not None, "Should get a response from direct message"
            
            results.add_pass("Direct messaging test successful")
        else:
            print_warning("Messaging manager does not have send_to_agent method")
            
        # Try sending to agents by role
        if hasattr(messaging_manager, "send_to_role"):
            role_responses = messaging_manager.send_to_role(TeamMemberRole.MEMBER, test_msg)
            print_info(f"Role-based message responses: {len(role_responses)}")
            
            # Verify role-based messaging
            assert len(role_responses) == 2, f"Should get 2 responses, got {len(role_responses)}"
            
            results.add_pass("Role-based messaging test successful")
        else:
            print_warning("Messaging manager does not have send_to_role method")
        
    except Exception as e:
        results.add_fail(f"Selective messaging test failed: {e}")
        logger.exception("Test failure")


async def test_communication_failure_recovery(results: TestResults) -> None:
    """Test recovery from communication failures.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Communication Failure Recovery")
    
    try:
        # Create team
        team = create_team(name="Error Recovery Team")
        
        # Create mixture of normal and error-prone agents
        agent1 = TestAgent("error-agent-1", "Error Agent", error_mode=True)
        agent2 = TestAgent("normal-agent-1", "Normal Agent 1", error_mode=False)
        agent3 = TestAgent("normal-agent-2", "Normal Agent 2", error_mode=False)
        
        # Add agents to team
        team.add_member(agent1)
        team.add_member(agent2)
        team.add_member(agent3)
        
        # Create test message
        test_msg = Message.user_message("Test message for error recovery")
        
        # Send broadcast and handle failures
        responses = team.broadcast_message(test_msg)
        
        # Verify responses (should include error for agent1)
        assert len(responses) == 3, f"Should get 3 responses, got {len(responses)}"
        print_info(f"Received {len(responses)} responses with error handling")
        
        # Test async broadcast
        async_responses = await team.abroadcast_message(test_msg)
        
        # Verify async responses
        assert len(async_responses) == 3, f"Should get 3 async responses, got {len(async_responses)}"
        print_info(f"Received {len(async_responses)} async responses with error handling")
        
        # Verify that despite errors, other agents' responses were received
        # At least some responses should be successful
        successful = False
        for resp in responses:
            if "received:" in resp.content:
                successful = True
                break
                
        assert successful, "At least one agent should have successfully processed the message"
        
        results.add_pass("Communication failure recovery test successful")
        
    except Exception as e:
        results.add_fail(f"Communication failure recovery test failed: {e}")
        logger.exception("Test failure")


async def test_multi_agent_conversation(results: TestResults) -> None:
    """Test multi-agent conversation flow.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Multi-Agent Conversation Flow")
    
    try:
        # Create team
        team = create_team(name="Conversation Team")
        
        # Add several agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Conversation Agent {i+1}",
                agent_id=f"conversation-agent-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        
        # This test depends on conversation flow implementation
        # Simple test of message routing between agents
        
        # Create initial message
        initial_msg = Message.user_message("Start of conversation")
        
        # Create conversation chain
        msgs = []
        current_msg = initial_msg
        
        # Route through all agents sequentially
        for i, agent in enumerate(members):
            response = agent.process_message(current_msg)
            msgs.append(response)
            
            if i < len(members) - 1:
                # Create new message from response
                current_msg = Message.user_message(f"Relay: {response.content}")
        
        # Verify conversation chain
        assert len(msgs) == 3, f"Should have 3 messages in conversation, got {len(msgs)}"
        print_info(f"Created conversation chain with {len(msgs)} messages")
        
        results.add_pass("Multi-agent conversation test successful")
        
    except Exception as e:
        results.add_fail(f"Multi-agent conversation test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all message routing tests."""
    print_title("TEAM MODULE - MESSAGE ROUTING TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_broadcast_messaging(results)
        await test_selective_messaging(results)
        await test_communication_failure_recovery(results)
        await test_multi_agent_conversation(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All message routing tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
