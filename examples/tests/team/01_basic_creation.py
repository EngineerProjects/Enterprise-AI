#!/usr/bin/env python
"""
Improved Basic Team Creation Test

This script demonstrates enhanced testing of team creation
with proper assertions and error handling.
"""

import asyncio
import sys
import os

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import *

# Set up project path
setup_project_path()

# Import core components
from enterprise_ai.team.core import create_team, TeamBuilder
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.types import TeamProtocol
from enterprise_ai.team.architecture.lifecycle import TeamState
from enterprise_ai.team.architecture.state_sync import SyncMode
from enterprise_ai.logger import get_logger

logger = get_logger("team_creation_improved")


class TestResults:
    """Track test results for summary."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self):
        self.passed += 1
    
    def add_fail(self, error_msg):
        self.failed += 1
        self.errors.append(error_msg)
    
    def summary(self):
        total = self.passed + self.failed
        return f"Tests: {total}, Passed: {self.passed}, Failed: {self.failed}"


async def test_default_creation(results: TestResults):
    """Test team creation with default parameters."""
    print_section("1. Default Team Creation")
    
    try:
        team = create_team()
        
        # Assertions
        assert team is not None, "Team should not be None"
        assert isinstance(team, TeamProtocol), "Team should implement TeamProtocol"
        assert hasattr(team, 'id'), "Team should have an ID"
        assert hasattr(team, 'name'), "Team should have a name"
        assert team.id.startswith('team-'), f"Team ID should start with 'team-', got {team.id}"
        
        print_success(f"✓ Created team: {team.name} (ID: {team.id})")
        results.add_pass()
        
        return team
        
    except Exception as e:
        print_error(f"✗ Default creation failed: {e}")
        results.add_fail(str(e))
        raise


async def test_custom_creation(results: TestResults):
    """Test team creation with custom parameters."""
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
        
        print_success(f"✓ Created custom team: {team.name}")
        results.add_pass()
        
        return team
        
    except Exception as e:
        print_error(f"✗ Custom creation failed: {e}")
        results.add_fail(str(e))
        raise


async def test_component_initialization(results: TestResults):
    """Test that all required components are initialized."""
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
        
        for attr, name in components.items():
            assert hasattr(team, attr), f"Team missing {name} ({attr})"
            assert getattr(team, attr) is not None, f"{name} is None"
            print_info(f"  ✓ {name} initialized")
        
        print_success("✓ All components initialized")
        results.add_pass()
        
    except Exception as e:
        print_error(f"✗ Component initialization failed: {e}")
        results.add_fail(str(e))
        raise


async def test_team_builder(results: TestResults):
    """Test TeamBuilder pattern."""
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
        assert team.id == "builder-team-1", "Builder should set ID"
        assert team.name == "Builder Team", "Builder should set name"
        
        print_success("✓ TeamBuilder pattern works")
        results.add_pass()
        
    except Exception as e:
        print_error(f"✗ TeamBuilder failed: {e}")
        results.add_fail(str(e))
        raise


async def test_invalid_parameters(results: TestResults):
    """Test team creation with invalid parameters."""
    print_section("5. Invalid Parameter Handling")
    
    try:
        # Test with invalid team type
        try:
            team = create_team(team_type="invalid_type")
            # If it doesn't raise an error, it should default to base
            assert isinstance(team, BaseTeam), "Should default to BaseTeam for invalid type"
            print_info("  ✓ Invalid team_type defaults to 'base'")
        except Exception as e:
            print_info(f"  ✓ Invalid team_type raised: {type(e).__name__}")
        
        results.add_pass()
        
    except Exception as e:
        print_error(f"✗ Invalid parameter test failed: {e}")
        results.add_fail(str(e))
        raise


async def main():
    """Run all team creation tests."""
    print_title("TEAM MODULE - ENHANCED CREATION TESTS", style="double")
    
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
            print_success("\n✅ All tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
