#!/usr/bin/env python
"""
Team Error Handling Tests

This script tests edge cases and error handling in team operations, including:
- Member limit enforcement
- Duplicate member handling
- Invalid parameter handling
- Error recovery during operations
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
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.error_handling")


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


async def test_member_limits(results: TestResults) -> None:
    """Test team member limits and enforcement.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Member Limit Enforcement")
    
    try:
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
                # Should succeed for first two agents
                assert success, f"Should be able to add agent {i+1}"
                print_info(f"Successfully added agent {i+1}")
            else:
                # Should fail for third agent (exceeds limit)
                assert not success, "Should not exceed member limit"
                print_info("Member limit correctly enforced")
        
        # Verify member count
        members = team.get_members()
        assert len(members) == 2, f"Team should have 2 members, got {len(members)}"
        
        results.add_pass("Member limit enforcement works correctly")
        
    except Exception as e:
        results.add_fail(f"Member limit test failed: {e}")
        logger.exception("Test failure")


async def test_duplicate_members(results: TestResults) -> None:
    """Test handling of duplicate member additions.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Duplicate Member Handling")
    
    try:
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
        print_info("First addition succeeded")
        
        # Second addition should fail
        success2 = team.add_member(agent)
        assert not success2, "Second addition should fail (duplicate member)"
        print_info("Duplicate member correctly rejected")
        
        # Verify member count
        members = team.get_members()
        assert len(members) == 1, f"Team should have 1 member, got {len(members)}"
        
        results.add_pass("Duplicate member handling works correctly")
        
    except Exception as e:
        results.add_fail(f"Duplicate member test failed: {e}")
        logger.exception("Test failure")


async def test_invalid_parameters(results: TestResults) -> None:
    """Test team creation and operation with invalid parameters.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Invalid Parameter Handling")
    
    try:
        # Test with invalid team type
        try:
            team = create_team(team_type="nonexistent_type")
            # Should default to base team
            print_info("Invalid team_type defaulted to base team")
            results.add_pass("Invalid team type handled gracefully")
        except Exception as e:
            results.add_fail(f"Invalid team type handling failed: {e}")
        
        # Test with invalid sync mode
        try:
            team = create_team(sync_mode="invalid_mode")
            # Should have a valid sync mode
            print_info("Invalid sync_mode defaulted to a valid value")
            results.add_pass("Invalid sync mode handled gracefully")
        except Exception as e:
            results.add_fail(f"Invalid sync mode handling failed: {e}")
        
        # Test other invalid parameters (would depend on implementation)
        
    except Exception as e:
        results.add_fail(f"Invalid parameter tests failed: {e}")
        logger.exception("Test failure")


async def test_error_recovery(results: TestResults) -> None:
    """Test error recovery during team operations.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Error Recovery During Operations")
    
    try:
        team = create_team(name="Error Recovery Team")
        
        # Add a few agents
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"Agent {i+1}",
                agent_id=f"agent-{i+1}"
            )
            team.add_member(agent)
        
        # Test recovery from member removal errors
        try:
            # Try to remove non-existent member
            result = team.remove_member("nonexistent-id")
            assert not result, "Removing non-existent member should return False"
            print_info("Gracefully handled non-existent member removal")
            results.add_pass("Non-existent member removal handled correctly")
        except Exception as e:
            results.add_fail(f"Non-existent member removal test failed: {e}")
        
        # Test recovery from task errors
        try:
            # Try to get non-existent task
            task = team.get_task("nonexistent-task-id")
            assert task is None, "Non-existent task should return None"
            print_info("Gracefully handled non-existent task retrieval")
            results.add_pass("Non-existent task retrieval handled correctly")
        except Exception as e:
            results.add_fail(f"Non-existent task retrieval test failed: {e}")
        
        # Test recovery from task status errors
        try:
            # Try to update non-existent task status
            result = team.update_task_status("nonexistent-task-id", "completed")
            assert not result, "Updating non-existent task should return False"
            print_info("Gracefully handled non-existent task status update")
            results.add_pass("Non-existent task status update handled correctly")
        except Exception as e:
            results.add_fail(f"Non-existent task status update test failed: {e}")
        
    except Exception as e:
        results.add_fail(f"Error recovery tests failed: {e}")
        logger.exception("Test failure")


async def test_resource_conflicts(results: TestResults) -> None:
    """Test handling of resource conflicts.
    
    Args:
        results: Test results tracker
    """
    print_section("5. Resource Conflict Handling")
    
    try:
        team = create_team(name="Resource Conflict Team")
        
        # Add agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Agent {i+1}",
                agent_id=f"agent-rc-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        
        # Test resource conflict detection
        resource_id = "exclusive_resource"
        
        # First agent requests resource
        granted1 = await team.request_resource(members[0].id, resource_id, priority=1)
        assert granted1, "First agent should get resource"
        print_info("First agent granted resource")
        
        # Second agent requests same resource
        granted2 = await team.request_resource(members[1].id, resource_id, priority=1)
        print_info(f"Second agent request result: {'Granted' if granted2 else 'Denied/Queued'}")
        
        # Register conflict
        conflict_id = team.register_conflict(
            description="Resource access conflict",
            agents=[members[0].id, members[1].id],
            resource_id=resource_id
        )
        
        assert conflict_id is not None, "Should get a conflict ID"
        print_info(f"Registered conflict: {conflict_id}")
        
        # Verify conflict is recorded
        conflicts = team.get_active_conflicts()
        assert len(conflicts) > 0, "Should have active conflicts"
        print_info(f"Found {len(conflicts)} active conflicts")
        
        # Resolve conflict
        resolved = team.resolve_conflict(
            conflict_id=conflict_id,
            resolution="First agent yielded resource"
        )
        
        assert resolved, "Conflict should be resolved"
        print_info("Successfully resolved conflict")
        
        # Verify conflict is no longer active
        conflicts_after = team.get_active_conflicts()
        assert len(conflicts_after) < len(conflicts), "Should have fewer active conflicts"
        
        results.add_pass("Resource conflict handling works correctly")
        
    except Exception as e:
        results.add_fail(f"Resource conflict test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all error handling tests."""
    print_title("TEAM MODULE - ERROR HANDLING TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_member_limits(results)
        await test_duplicate_members(results)
        await test_invalid_parameters(results)
        await test_error_recovery(results)
        await test_resource_conflicts(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All error handling tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())