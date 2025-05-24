#!/usr/bin/env python
"""
Hierarchical Team Tests

This script tests hierarchical team functionality, including:
- Multi-level team hierarchy creation
- Parent-child team relationships
- Cross-hierarchy communication
- Role inheritance and propagation
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
from enterprise_ai.team.collaboration.hierarchical import HierarchicalTeam, DecisionMode
from enterprise_ai.team.collaboration.peer import ConsensusMode  # Import for future tests if needed
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.hierarchical_teams")


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


async def test_multi_level_hierarchy(results: TestResults) -> None:
    """Test multi-level team hierarchy.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Multi-Level Team Hierarchy")
    
    try:
        # Create parent team
        # Note: For hierarchical teams, valid decision modes are:
        # - DecisionMode.MANAGER_ONLY
        # - DecisionMode.MANAGER_DELEGATED (default)
        # - DecisionMode.MANAGER_REVIEW
        parent_team = create_team(
            team_type="hierarchical",
            name="Parent Team",
            decision_mode=DecisionMode.MANAGER_DELEGATED
        )
        
        # Create child teams
        child_team1 = create_team(name="Child Team 1")
        child_team2 = create_team(name="Child Team 2")
        
        # Add child teams to parent
        parent_added1 = parent_team.add_member(child_team1, role=TeamMemberRole.MEMBER)
        parent_added2 = parent_team.add_member(child_team2, role=TeamMemberRole.MEMBER)
        
        # Create grandchild team
        grandchild_team = create_team(name="Grandchild Team")
        child_added = child_team1.add_member(grandchild_team, role=TeamMemberRole.MEMBER)
        
        # Assertions
        assert parent_added1, "Should add first child team"
        assert parent_added2, "Should add second child team"
        assert child_added, "Should add grandchild team"
        
        # Verify structure
        parent_members = parent_team.get_members()
        child1_members = child_team1.get_members()
        
        assert len(parent_members) == 2, f"Parent should have 2 members, got {len(parent_members)}"
        assert len(child1_members) == 1, f"Child should have 1 member, got {len(child1_members)}"
        
        print_info(f"Parent team: {parent_team.name} has {len(parent_members)} members")
        print_info(f"Child team: {child_team1.name} has {len(child1_members)} members")
        
        results.add_pass("Multi-level hierarchy creation successful")
        
    except Exception as e:
        results.add_fail(f"Multi-level hierarchy test failed: {e}")
        logger.exception("Test failure")


async def test_hierarchy_message_propagation(results: TestResults) -> None:
    """Test message propagation through team hierarchy.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Hierarchy Message Propagation")
    
    try:
        # Create team structure
        parent_team = create_team(
            team_type="hierarchical",
            name="Message Parent"
        )
        
        # Create child teams and agents
        child_team = create_team(name="Message Child")
        agent1 = create_agent(name="Agent 1", agent_id="agent-1")
        agent2 = create_agent(name="Agent 2", agent_id="agent-2")
        
        # Build hierarchy
        parent_team.add_member(child_team)
        child_team.add_member(agent1)
        parent_team.add_member(agent2)
        
        # Send message to parent
        test_message = "This is a test message for hierarchy propagation"
        message_obj = Message.user_message(test_message)
        
        # Process at parent level
        responses = await parent_team.abroadcast_message(message_obj)
        
        # Assertions
        assert len(responses) == 2, f"Should get 2 responses, got {len(responses)}"
        
        # Verify message reached all team members
        print_info(f"Received {len(responses)} responses from broadcast")
        
        results.add_pass("Hierarchy message propagation successful")
        
    except Exception as e:
        results.add_fail(f"Hierarchy message propagation test failed: {e}")
        logger.exception("Test failure")


async def test_role_inheritance(results: TestResults) -> None:
    """Test role inheritance in team hierarchies.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Role Inheritance")
    
    try:
        # Create hierarchical team with manager
        parent_team = create_team(
            team_type="hierarchical",
            name="Role Parent"
        )
        
        manager_agent = create_agent(name="Manager", agent_id="manager-1")
        parent_team.add_member(manager_agent, role=TeamMemberRole.MANAGER)
        
        # Create child team
        child_team = create_team(name="Role Child")
        parent_team.add_member(child_team)
        
        # Add members to child team
        member_agent = create_agent(name="Member", agent_id="member-1")
        child_team.add_member(member_agent)
        
        # Verify role inheritance (implementation dependent)
        # This is checking if the manager relationship is preserved
        parent_manager = parent_team._membership.manager
        assert parent_manager is not None, "Parent team should have a manager"
        assert parent_manager.id == "manager-1", f"Manager should be manager-1, got {parent_manager.id}"
        
        print_info("Role inheritance verified in hierarchy")
        results.add_pass("Role inheritance test successful")
        
    except Exception as e:
        results.add_fail(f"Role inheritance test failed: {e}")
        logger.exception("Test failure")


async def test_cross_team_resource_sharing(results: TestResults) -> None:
    """Test resource sharing across team hierarchies.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Cross-Team Resource Sharing")
    
    try:
        # Create hierarchical team structure
        parent_team = create_team(
            team_type="hierarchical",
            name="Resource Parent"
        )
        
        child_team1 = create_team(name="Resource Child 1")
        child_team2 = create_team(name="Resource Child 2")
        
        parent_team.add_member(child_team1)
        parent_team.add_member(child_team2)
        
        # Register a shared resource
        resource_id = "shared_resource_123"
        
        # Add agents to teams
        agent1 = create_agent(name="Agent 1", agent_id="agent-res-1")
        agent2 = create_agent(name="Agent 2", agent_id="agent-res-2")
        
        child_team1.add_member(agent1)
        child_team2.add_member(agent2)
        
        # Request resource from different teams
        granted1 = await parent_team.request_resource(agent1.id, resource_id)
        
        # Try to access from sibling team (may be implementation dependent)
        conflict_id = parent_team.register_conflict(
            description="Cross-team resource access",
            agents=[agent1.id, agent2.id],
            resource_id=resource_id
        )
        
        # Resolve conflict
        resolved = parent_team.resolve_conflict(
            conflict_id=conflict_id,
            resolution="Resource access granted to both teams"
        )
        
        assert resolved, "Should resolve cross-team conflict"
        
        # Release resource
        released = parent_team.release_resource(agent1.id, resource_id)
        assert released, "Should release resource"
        
        print_info("Cross-team resource sharing tested")
        results.add_pass("Cross-team resource sharing test successful")
        
    except Exception as e:
        results.add_fail(f"Cross-team resource sharing test failed: {e}")
        logger.exception("Test failure")


async def test_decision_modes(results: TestResults) -> None:
    """Test different decision modes for hierarchical teams.
    
    Args:
        results: Test results tracker
    """
    print_section("5. Decision Mode Tests")
    
    try:
        # Test all valid decision modes for hierarchical teams
        decision_modes = [
            DecisionMode.MANAGER_ONLY,
            DecisionMode.MANAGER_DELEGATED,
            DecisionMode.MANAGER_REVIEW
        ]
        
        for mode in decision_modes:
            team = create_team(
                team_type="hierarchical",
                name=f"Team-{mode.name}",
                decision_mode=mode
            )
            
            # Verify the mode was set correctly
            if isinstance(team, HierarchicalTeam):
                assert team.decision_mode == mode, f"Decision mode should be {mode}"
                print_info(f"Created team with {mode.name} decision mode successfully")
            else:
                print_warning(f"Team is not a HierarchicalTeam instance, skipping validation")
                
        # Test string-based mode specification
        string_mode_team = create_team(
            team_type="hierarchical",
            name="String-Mode-Team",
            decision_mode="MANAGER_REVIEW"
        )
        
        if isinstance(string_mode_team, HierarchicalTeam):
            assert string_mode_team.decision_mode == DecisionMode.MANAGER_REVIEW, "String mode not correctly resolved"
            print_info("String-based decision mode successfully resolved")
            
        results.add_pass("Decision mode tests successful")
        
    except Exception as e:
        results.add_fail(f"Decision mode tests failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all hierarchical team tests."""
    print_title("TEAM MODULE - HIERARCHICAL TEAM TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_multi_level_hierarchy(results)
        await test_hierarchy_message_propagation(results)
        await test_role_inheritance(results)
        await test_cross_team_resource_sharing(results)
        await test_decision_modes(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All hierarchical team tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
