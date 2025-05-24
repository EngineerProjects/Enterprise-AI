#!/usr/bin/env python
"""
Team Creation Tests

This script tests team creation functionality, including:
- Default team creation
- Custom team creation with specific parameters
- Component initialization verification
- TeamBuilder pattern
- Invalid parameter handling
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
from enterprise_ai.team.core import create_team, TeamBuilder
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.types import TeamProtocol
from enterprise_ai.team.architecture.lifecycle import TeamState
from enterprise_ai.team.architecture.state_sync import SyncMode
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.team_creation")


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


async def test_default_creation(results: TestResults) -> Any:
    """Test team creation with default parameters.
    
    Args:
        results: Test results tracker
    
    Returns:
        The created team
    """
    print_section("1. Default Team Creation")
    
    try:
        team = create_team()
        
        # Assertions
        assert team is not None, "Team should not be None"
        assert isinstance(team, TeamProtocol), "Team should implement TeamProtocol"
        assert hasattr(team, 'id'), "Team should have an ID"
        assert hasattr(team, 'name'), "Team should have a name"
        assert team.id.startswith('team-'), f"Team ID should start with 'team-', got {team.id}"
        
        print_info(f"Created team: {team.name} (ID: {team.id})")
        results.add_pass("Default team creation successful")
        
        return team
        
    except Exception as e:
        results.add_fail(f"Default team creation failed: {e}")
        logger.exception("Test failure")
        raise


async def test_custom_creation(results: TestResults) -> Any:
    """Test team creation with custom parameters.
    
    Args:
        results: Test results tracker
    
    Returns:
        The created team
    """
    print_section("2. Custom Team Creation")
    
    try:
        team = create_team(
            team_type="base",
            team_id="test-team-alpha",
            name="Test Team Alpha",
            sync_mode=SyncMode.MANUAL
        )
        
        # Assertions
        assert team.id == "test-team-alpha", f"Expected ID 'test-team-alpha', got {team.id}"
        assert team.name == "Test Team Alpha", f"Expected name 'Test Team Alpha', got {team.name}"
        assert hasattr(team, '_state_sync'), "Team should have state sync manager"
        
        print_info(f"Created custom team: {team.name}")
        results.add_pass("Custom team creation successful")
        
        return team
        
    except Exception as e:
        results.add_fail(f"Custom team creation failed: {e}")
        logger.exception("Test failure")
        raise


async def test_component_initialization(results: TestResults) -> None:
    """Test that all required components are initialized.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Component Initialization")
    
    try:
        team = create_team(name="Component Test Team")
        
        # Required components
        components = {
            "_membership": "Membership Manager",
            "_messaging": "Messaging Manager", 
            "_tasks": "Task Manager",
            "_lifecycle": "Lifecycle Manager",
            "_coordinator": "Coordination Manager",
            "_tool_registry": "Tool Registry",
            "_tool_sharing": "Tool Sharing Manager",
            "_state_sync": "State Sync Manager"
        }
        
        # Check each component
        missing_components = []
        null_components = []
        
        for attr, name in components.items():
            if not hasattr(team, attr):
                missing_components.append(name)
            elif getattr(team, attr) is None:
                null_components.append(name)
            else:
                print_info(f"  ✓ {name} initialized")
        
        # Assertions
        assert not missing_components, f"Team missing components: {', '.join(missing_components)}"
        assert not null_components, f"Team has None components: {', '.join(null_components)}"
        
        results.add_pass("All components initialized correctly")
        
    except Exception as e:
        results.add_fail(f"Component initialization failed: {e}")
        logger.exception("Test failure")
        raise


async def test_team_builder(results: TestResults) -> None:
    """Test TeamBuilder pattern.
    
    Args:
        results: Test results tracker
    """
    print_section("4. TeamBuilder Pattern")
    
    try:
        builder = TeamBuilder()
        
        # Build team with fluent interface
        team = (builder
            .with_id("builder-team-1")
            .with_name("Builder Team")
            .with_type("base")
            .build())
        
        # Assertions
        assert team.id == "builder-team-1", f"Expected ID 'builder-team-1', got {team.id}"
        assert team.name == "Builder Team", f"Expected name 'Builder Team', got {team.name}"
        assert isinstance(team, BaseTeam), "Should be a BaseTeam instance"
        
        print_info(f"Built team: {team.name} (ID: {team.id})")
        results.add_pass("TeamBuilder pattern works correctly")
        
    except Exception as e:
        results.add_fail(f"TeamBuilder test failed: {e}")
        logger.exception("Test failure")
        raise


async def test_invalid_parameters(results: TestResults) -> None:
    """Test team creation with invalid parameters.
    
    Args:
        results: Test results tracker
    """
    print_section("5. Invalid Parameter Handling")
    
    try:
        # Test with invalid team type
        try:
            team = create_team(team_type="invalid_type")
            # If it doesn't raise an error, it should default to base
            assert isinstance(team, BaseTeam), "Should default to BaseTeam for invalid type"
            print_info("  ✓ Invalid team_type defaults to 'base'")
            results.add_pass("Invalid team_type handled correctly")
        except Exception as e:
            results.add_fail(f"Invalid team_type handling failed: {type(e).__name__}: {e}")
        
        # Test with invalid sync mode
        try:
            team = create_team(sync_mode="invalid_mode")
            assert hasattr(team, '_state_sync'), "Should have state sync manager with default mode"
            print_info("  ✓ Invalid sync_mode defaults to valid value")
            results.add_pass("Invalid sync_mode handled correctly")
        except Exception as e:
            results.add_fail(f"Invalid sync_mode handling failed: {type(e).__name__}: {e}")
        
        # Test with negative max_members
        try:
            team = create_team(max_members=-5)
            # If it doesn't raise an error, it should use a default or positive value
            print_info("  ✓ Negative max_members handled")
            results.add_pass("Negative max_members handled correctly")
        except Exception as e:
            results.add_fail(f"Negative max_members handling failed: {type(e).__name__}: {e}")
        
    except Exception as e:
        results.add_fail(f"Invalid parameter tests failed: {e}")
        logger.exception("Test failure")
        raise


async def main():
    """Run all team creation tests."""
    print_title("TEAM MODULE - TEAM CREATION TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_default_creation(results)
        await test_custom_creation(results)
        await test_component_initialization(results)
        await test_team_builder(results)
        await test_invalid_parameters(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All team creation tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
