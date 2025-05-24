#!/usr/bin/env python
"""
Hierarchical Team Patterns

This script demonstrates hierarchical team structures
with managers and decision-making modes.
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
from enterprise_ai.logger import get_logger

logger = get_logger("hierarchical_team")


async def test_hierarchical_team():
    """Test hierarchical team patterns."""
    print_title("HIERARCHICAL TEAM PATTERNS")
    
    # Try to create hierarchical team
    print_section("1. Creating Hierarchical Team")
    
    try:
        team = create_team(
            team_type="hierarchical",
            name="Engineering Team",
            decision_mode="MANAGER_DELEGATED"
        )
        print_success(f"Created hierarchical team: {team.name}")
        print_info(f"Team type: {type(team).__name__}")
    except Exception as e:
        print_warning(f"Hierarchical team not available: {e}")
        print_info("Creating base team with hierarchical structure")
        team = create_team(name="Engineering Team")
    
    # Create hierarchy
    print_section("2. Building Team Hierarchy")
    
    # Manager
    manager = create_agent(
        agent_type="base",
        name="Engineering Manager",
        metadata={"authority_level": 3}
    )
    team.add_member(manager, role=TeamMemberRole.MANAGER)
    
    # Team leads
    leads = []
    for area in ["Frontend", "Backend"]:
        lead = create_agent(
            agent_type="base",
            name=f"{area} Lead",
            metadata={"authority_level": 2, "area": area}
        )
        team.add_member(lead, role=TeamMemberRole.COORDINATOR)
        leads.append(lead)
    
    # Engineers
    for i in range(4):
        engineer = create_agent(
            agent_type="base",
            name=f"Engineer {i+1}",
            metadata={"authority_level": 1}
        )
        team.add_member(engineer, role=TeamMemberRole.SPECIALIST)
    
    # Display hierarchy
    print_section("3. Team Hierarchy")
    
    members = team.get_members()
    print_info(f"Total members: {len(members)}")
    
    # Group by role
    managers = [m for m in members if hasattr(team._membership, 'get_member_role') and 
                team._membership.get_member_role(m.id) == TeamMemberRole.MANAGER]
    coordinators = [m for m in members if hasattr(team._membership, 'get_member_role') and
                    team._membership.get_member_role(m.id) == TeamMemberRole.COORDINATOR]
    specialists = [m for m in members if hasattr(team._membership, 'get_member_role') and
                   team._membership.get_member_role(m.id) == TeamMemberRole.SPECIALIST]
    
    print_info("\nHierarchy:")
    print_info("  Manager:")
    for m in managers:
        print_info(f"    └─ {m.name}")
    
    print_info("  Coordinators:")
    for c in coordinators:
        print_info(f"    └─ {c.name}")
    
    print_info("  Specialists:")
    for s in specialists:
        print_info(f"    └─ {s.name}")
    
    # Test task delegation
    print_section("4. Task Delegation")
    
    task = {
        "name": "New Feature Development",
        "description": "Implement user authentication",
        "priority": "high"
    }
    
    result = team.assign_task(task)
    print_info(f"Task assigned: {result}")
    
    return team


async def main():
    """Run hierarchical team tests."""
    print_title("TEAM MODULE - HIERARCHICAL TEST", style="double")
    
    try:
        await test_hierarchical_team()
        print_success("\nHierarchical tests completed!")
    except Exception as e:
        print_error(f"Test failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
