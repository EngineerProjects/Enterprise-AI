#!/usr/bin/env python
"""
Team Messaging

This script demonstrates team messaging and communication
using mock LLM providers to avoid API calls.
"""

import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import *

setup_project_path()

from enterprise_ai.team.core import create_team
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

logger = get_logger("team_messaging")


class MockLLMProvider:
    """Mock LLM for testing without API calls."""
    def __init__(self, role="default"):
        self.role = role
        self.call_count = 0
    
    def complete(self, messages):
        self.call_count += 1
        if self.role == "manager":
            return Message.assistant_message(
                f"As manager, I'll coordinate this task. (Call #{self.call_count})"
            )
        elif self.role == "specialist":
            return Message.assistant_message(
                f"I'll handle the technical aspects. (Call #{self.call_count})"
            )
        else:
            return Message.assistant_message(
                f"Acknowledged. Working on it. (Call #{self.call_count})"
            )
    
    async def acomplete(self, messages):
        await asyncio.sleep(0.1)  # Simulate API delay
        return self.complete(messages)


async def test_messaging():
    """Test team messaging capabilities."""
    print_title("TEAM MESSAGING")
    
    # Create team
    team = create_team(name="Communication Team")
    
    # Add members with mock LLMs
    print_section("1. Creating Team with Mock Agents")
    
    # Manager
    manager = create_agent(
        agent_type="llm",
        name="Team Manager",
        llm_provider=MockLLMProvider("manager")
    )
    team.add_member(manager, role=TeamMemberRole.MANAGER)
    
    # Members
    for i in range(2):
        member = create_agent(
            agent_type="llm",
            name=f"Member {i+1}",
            llm_provider=MockLLMProvider("specialist")
        )
        team.add_member(member)
    
    print_success(f"Team has {len(team.get_members())} members")
    
    # Test team message
    print_section("2. Team Message Processing")
    
    response = team.process_message("Team, please start the new project.")
    print_info(f"Team response: {response.content}")
    
    # Test broadcast
    print_section("3. Broadcasting Message")
    
    msg = Message.user_message("Meeting at 3 PM. Please confirm.")
    responses = team.broadcast_message(msg)
    
    print_info(f"Sent to {len(team.get_members())} members")
    print_info(f"Received {len(responses)} responses:")
    
    for i, resp in enumerate(responses[:3]):  # Show first 3
        print_info(f"  - Member {i+1}: {resp.content}")
    
    # Test async
    print_section("4. Async Processing")
    
    timer = Timer("Async Message")
    timer.start()
    
    async_resp = await team.aprocess_message("Status update please.")
    
    timer.stop()
    print_info(f"Async response: {async_resp.content}")
    
    return team


async def main():
    """Run messaging tests."""
    print_title("TEAM MODULE - MESSAGING TEST", style="double")
    
    try:
        await test_messaging()
        print_success("\nMessaging tests completed!")
    except Exception as e:
        print_error(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
