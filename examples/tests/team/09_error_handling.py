#!/usr/bin/env python
"""
Team Error Handling Test

This script tests edge cases, error scenarios, and
robustness of the team module.
"""

import asyncio
import sys
import os

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import *

setup_project_path()

from enterprise_ai.team.core import create_team
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

logger = get_logger("team_error_handling")

async def test_member_limits():
    """Test team member limits and constraints."""
    print_title("TEAM ERROR HANDLING & EDGE CASES")
    
    print_section("1. Member Limit Enforcement")
    
    # Create team with small limit
    team = create_team(name="Limited Team", max_members=2)
    
    # Add members up to limit
    for i in range(3):
        agent = create_agent(
            agent_type="base",
            name=f"Agent {i+1}",
            agent_id=f"agent-{i+1}"
        )
        
        success = team.add_member(agent)
        
        if i < 2:
            assert success, f"Should be able to add agent {i+1}"
            print_success(f"✓ Added agent {i+1}")
        else:
            assert not success, "Should not exceed member limit"
            print_info("✓ Member limit enforced correctly")
    
    return team


async def test_duplicate_members():
    """Test handling of duplicate member additions."""
    print_section("2. Duplicate Member Handling")
    
    team = create_team(name="Duplicate Test Team")
    
    # Create and add agent
    agent = create_agent(
        agent_type="base",
        name="Unique Agent",
        agent_id="unique-001"
    )
    
    # First addition should succeed
    success1 = team.add_member(agent)
    assert success1, "First addition should succeed"
    print_success("✓ First addition succeeded")
    
    # Second addition should fail
    success2 = team.add_member(agent)