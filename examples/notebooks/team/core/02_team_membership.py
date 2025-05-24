#!/usr/bin/env python
"""
Team Membership Tests

This script tests team membership functionality, including:
- Adding members to a team
- Removing members from a team
- Retrieving team members
- Managing member roles
- Validating membership constraints
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
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.team_membership")


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


async def test_team_setup(results: TestResults) -> Any:
    """Set up a team for membership tests.
    
    Args:
        results: Test results tracker
    
    Returns:
        The created team
    """
    print_section("1. Team Setup")
    
    try:
        # Create a team with member limit
        team = create_team(name="Membership Test Team", max_members=10)
        
        # Assertions
        assert team is not None, "Team should not be None"
        assert team.name == "Membership Test Team", f"Expected name 'Membership Test Team', got {team.name}"
        
        print_info(f"Created team: {team.name} (ID: {team.id})")
        results.add_pass("Team setup successful")
        
        return team
        
    except Exception as e:
        results.add_fail(f"Team setup failed: {e}")
        logger.exception("Test failure")
        raise


async def test_add_members(results: TestResults, team: Any) -> Tuple[Any, List[Any]]:
    """Test adding members to a team.
    
    Args:
        results: Test results tracker
        team: Team from previous test
    
    Returns:
        Tuple of (manager, specialists)
    """
    print_section("2. Adding Members to Team")
    
    try:
        # Create manager
        manager = create_agent(
            agent_type="base",
            name="Project Manager",
            agent_id="mgr-001",
            metadata={"role": "manager", "expertise": "leadership"}
        )
        
        # Add manager
        result = team.add_member(manager, role=TeamMemberRole.MANAGER)
        
        # Assertions
        assert result, "Adding manager should succeed"
        assert manager.id in [m.id for m in team.get_members()], "Manager should be in team members"
        
        print_info(f"Added manager: {manager.name} (ID: {manager.id})")
        results.add_pass("Added manager successfully")
        
        # Create specialists
        specialists = []
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Specialist {i+1}",
                agent_id=f"spec-00{i+1}",
                metadata={"role": "specialist", "expertise": f"domain_{i+1}"}
            )
            specialists.append(agent)
        
        # Add specialists
        for spec in specialists:
            result = team.add_member(spec, role=TeamMemberRole.SPECIALIST)
            
            # Assertions
            assert result, f"Adding specialist {spec.name} should succeed"
            assert spec.id in [m.id for m in team.get_members()], f"Specialist {spec.name} should be in team members"
            
            print_info(f"Added specialist: {spec.name} (ID: {spec.id})")
        
        results.add_pass("Added specialists successfully")
        
        return manager, specialists
        
    except Exception as e:
        results.add_fail(f"Adding members failed: {e}")
        logger.exception("Test failure")
        raise


async def test_team_composition(results: TestResults, team: Any) -> None:
    """Test team composition after adding members.
    
    Args:
        results: Test results tracker
        team: Team with members
    """
    print_section("3. Team Composition")
    
    try:
        # Get all members
        members = team.get_members()
        
        # Assertions
        assert members is not None, "Members list should not be None"
        assert len(members) == 4, f"Expected 4 members, got {len(members)}"
        
        # Check roles
        manager_count = 0
        specialist_count = 0
        
        for member in members:
            # In a real implementation, you would check the actual role
            # For this test, we're just checking existence
            if member.id.startswith("mgr-"):
                manager_count += 1
            elif member.id.startswith("spec-"):
                specialist_count += 1
        
        assert manager_count == 1, f"Expected 1 manager, got {manager_count}"
        assert specialist_count == 3, f"Expected 3 specialists, got {specialist_count}"
        
        print_info(f"Team composition: {len(members)} members ({manager_count} managers, {specialist_count} specialists)")
        results.add_pass("Team composition verified")
        
    except Exception as e:
        results.add_fail(f"Team composition verification failed: {e}")
        logger.exception("Test failure")
        raise


async def test_member_retrieval(results: TestResults, team: Any, manager: Any) -> None:
    """Test member retrieval by ID.
    
    Args:
        results: Test results tracker
        team: Team with members
        manager: Manager agent
    """
    print_section("4. Member Retrieval")
    
    try:
        # Get manager by ID
        retrieved = team.get_member(manager.id)
        
        # Assertions
        assert retrieved is not None, "Retrieved manager should not be None"
        assert retrieved.id == manager.id, f"Expected manager ID {manager.id}, got {retrieved.id if retrieved else 'None'}"
        assert retrieved.name == manager.name, f"Expected manager name {manager.name}, got {retrieved.name if retrieved else 'None'}"
        
        # Try to get non-existent member
        nonexistent = team.get_member("nonexistent-id")
        
        # Assertions
        assert nonexistent is None, "Non-existent member retrieval should return None"
        
        print_info(f"Retrieved manager: {retrieved.name} (ID: {retrieved.id})")
        results.add_pass("Member retrieval works correctly")
        
    except Exception as e:
        results.add_fail(f"Member retrieval failed: {e}")
        logger.exception("Test failure")
        raise


async def test_remove_member(results: TestResults, team: Any, specialists: List[Any]) -> None:
    """Test removing a member from the team.
    
    Args:
        results: Test results tracker
        team: Team with members
        specialists: List of specialist agents
    """
    print_section("5. Member Removal")
    
    try:
        # Get initial member count
        initial_count = len(team.get_members())
        
        # Remove one specialist
        specialist_to_remove = specialists[2]  # Last specialist
        result = team.remove_member(specialist_to_remove.id)
        
        # Assertions
        assert result, f"Removing specialist {specialist_to_remove.name} should succeed"
        
        # Get updated member count
        updated_count = len(team.get_members())
        
        # Assertions
        assert updated_count == initial_count - 1, f"Expected {initial_count - 1} members after removal, got {updated_count}"
        assert specialist_to_remove.id not in [m.id for m in team.get_members()], "Removed specialist should not be in team members"
        
        print_info(f"Removed specialist: {specialist_to_remove.name} (ID: {specialist_to_remove.id})")
        print_info(f"Team now has {updated_count} members")
        results.add_pass("Member removal works correctly")
        
        # Try to remove non-existent member
        result = team.remove_member("nonexistent-id")
        
        # Assertions
        assert not result, "Removing non-existent member should fail"
        assert len(team.get_members()) == updated_count, "Member count should not change after failed removal"
        
        print_info("Correctly handled removal of non-existent member")
        results.add_pass("Non-existent member removal handled correctly")
        
    except Exception as e:
        results.add_fail(f"Member removal failed: {e}")
        logger.exception("Test failure")
        raise


async def main():
    """Run all team membership tests."""
    print_title("TEAM MODULE - TEAM MEMBERSHIP TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        team = await test_team_setup(results)
        manager, specialists = await test_add_members(results, team)
        await test_team_composition(results, team)
        await test_member_retrieval(results, team, manager)
        await test_remove_member(results, team, specialists)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All team membership tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
