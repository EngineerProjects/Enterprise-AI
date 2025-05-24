#!/usr/bin/env python
"""
Team Membership Management

This script demonstrates how to add, remove, and manage
members in teams with different roles.
"""

import asyncio
import sys
import os

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import *

# Set up project path
setup_project_path()

# Import components
from enterprise_ai.team.core import create_team
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

logger = get_logger("team_membership")


async def test_membership():
    """Test team membership operations."""
    print_title("TEAM MEMBERSHIP MANAGEMENT")
    
    # Create a team
    team = create_team(name="Project Team", max_members=10)
    print_success(f"Created team: {team.name}")
    
    # Create agents
    print_section("1. Creating Team Members")
    
    # Manager
    manager = create_agent(
        agent_type="base",
        name="Project Manager",
        agent_id="mgr-001",
        metadata={"role": "manager", "expertise": "leadership"}
    )
    
    # Specialists
    specialists = []
    for i in range(3):
        agent = create_agent(
            agent_type="base",
            name=f"Specialist {i+1}",
            agent_id=f"spec-00{i+1}",
            metadata={"role": "specialist", "expertise": f"domain_{i+1}"}
        )
        specialists.append(agent)
    
    print_success(f"Created 1 manager and {len(specialists)} specialists")
    
    # Add members
    print_section("2. Adding Members to Team")
    
    # Add manager
    result = team.add_member(manager, role=TeamMemberRole.MANAGER)
    print_info(f"Added manager: {result}")
    
    # Add specialists
    for spec in specialists:
        result = team.add_member(spec, role=TeamMemberRole.SPECIALIST)
        print_info(f"Added {spec.name}: {result}")
    
    # Team composition
    print_section("3. Team Composition")
    
    members = team.get_members()
    print_info(f"Total members: {len(members)}")
    
    for member in members:
        print_info(f"  - {member.name} ({member.id})")
    
    # Test retrieval
    print_section("4. Member Retrieval")
    
    retrieved = team.get_member("mgr-001")
    if retrieved:
        print_success(f"Retrieved: {retrieved.name}")
    
    # Remove member
    print_section("5. Member Removal")
    
    removed = team.remove_member("spec-003")
    print_info(f"Removed specialist-003: {removed}")
    print_info(f"Remaining members: {len(team.get_members())}")
    
    return team


async def main():
    """Run membership tests."""
    print_title("TEAM MODULE - MEMBERSHIP TEST", style="double")
    
    try:
        team = await test_membership()
        print_success("\nMembership tests completed!")
    except Exception as e:
        print_error(f"Test failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
