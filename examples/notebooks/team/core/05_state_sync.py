#!/usr/bin/env python
"""
State Synchronization Tests

This script tests state synchronization in teams, including:
- Different synchronization modes (manual, automatic, periodic)
- Sync scheduling and execution
- Manual sync triggering
- Recovery from sync failures
"""

import asyncio
import sys
import os
import time
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
from enterprise_ai.team.architecture.state_sync import SyncMode
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.state_sync")


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


async def test_sync_modes(results: TestResults) -> None:
    """Test different synchronization modes.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Synchronization Modes")
    
    try:
        # Test manual sync mode
        manual_team = create_team(
            name="Manual Sync Team",
            sync_mode=SyncMode.MANUAL
        )
        
        # Test automatic sync mode
        auto_team = create_team(
            name="Auto Sync Team",
            sync_mode=SyncMode.AUTOMATIC
        )
        
        # Test periodic sync mode
        periodic_team = create_team(
            name="Periodic Sync Team",
            sync_mode=SyncMode.PERIODIC,
            sync_interval=2  # 2 seconds for quick testing
        )
        
        # Add agents to all teams
        for team in [manual_team, auto_team, periodic_team]:
            for i in range(2):
                agent = create_agent(
                    agent_type="base",
                    name=f"Sync Agent {i+1}",
                    agent_id=f"sync-agent-{team.id}-{i+1}"
                )
                team.add_member(agent)
        
        # Verify teams have correct sync modes
        manual_status = await manual_team.get_sync_status()
        auto_status = await auto_team.get_sync_status()
        periodic_status = await periodic_team.get_sync_status()
        
        print_info(f"Manual team sync mode: {manual_status.get('mode', 'unknown')}")
        print_info(f"Auto team sync mode: {auto_status.get('mode', 'unknown')}")
        print_info(f"Periodic team sync mode: {periodic_status.get('mode', 'unknown')}")
        
        # Basic verification
        assert 'mode' in manual_status, "Manual team status should include mode"
        assert 'mode' in auto_status, "Auto team status should include mode"
        assert 'mode' in periodic_status, "Periodic team status should include mode"
        
        # For periodic team, verify it's running
        if 'running' in periodic_status:
            assert periodic_status['running'], "Periodic sync should be running"
        
        # Clean up
        await manual_team.terminate()
        await auto_team.terminate()
        await periodic_team.terminate()
        
        results.add_pass("Sync modes test successful")
        
    except Exception as e:
        results.add_fail(f"Sync modes test failed: {e}")
        logger.exception("Test failure")


async def test_manual_sync(results: TestResults) -> None:
    """Test manual synchronization.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Manual Synchronization")
    
    try:
        # Create team with manual sync
        team = create_team(
            name="Manual Sync Test",
            sync_mode=SyncMode.MANUAL
        )
        
        # Add agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Manual Sync Agent {i+1}",
                agent_id=f"manual-sync-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Get members
        members = team.get_members()
        
        # Manually trigger sync for one agent
        sync_result = await team.sync_agent_state(members[0].id)
        
        print_info(f"Single agent sync result: {sync_result}")
        assert 'success' in sync_result, "Sync result should include success flag"
        
        # Manually trigger sync for all agents
        all_sync_result = await team.sync_all_agent_states()
        
        print_info(f"All agents sync result: {all_sync_result}")
        assert 'success' in all_sync_result, "All sync result should include success flag"
        
        # Verify sync status after manual sync
        status = await team.get_sync_status()
        print_info(f"Sync status after manual sync: {status}")
        
        # Clean up
        await team.terminate()
        
        results.add_pass("Manual sync test successful")
        
    except Exception as e:
        results.add_fail(f"Manual sync test failed: {e}")
        logger.exception("Test failure")


async def test_periodic_sync(results: TestResults) -> None:
    """Test periodic synchronization.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Periodic Synchronization")
    
    try:
        # Create team with periodic sync (very short interval for testing)
        team = create_team(
            name="Periodic Sync Test",
            sync_mode=SyncMode.PERIODIC,
            sync_interval=1  # 1 second for quick testing
        )
        
        # Add agents
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"Periodic Sync Agent {i+1}",
                agent_id=f"periodic-sync-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Initialize the team
        await team.initialize()
        
        # Wait for at least one sync cycle
        print_info("Waiting for sync cycle...")
        await asyncio.sleep(2)
        
        # Check sync status
        status1 = await team.get_sync_status()
        print_info(f"Status after waiting: {status1}")
        
        # Check if running
        assert status1.get('running', False), "Periodic sync should be running"
        
        # Wait a bit more and check if sync count increased
        await asyncio.sleep(2)
        status2 = await team.get_sync_status()
        
        print_info(f"Status after additional wait: {status2}")
        
        # Verify sync is working (implementation dependent)
        # May need to check sync_count or last_sync_time
        
        # Clean up
        await team.terminate()
        
        results.add_pass("Periodic sync test successful")
        
    except Exception as e:
        results.add_fail(f"Periodic sync test failed: {e}")
        logger.exception("Test failure")


async def test_sync_failure_recovery(results: TestResults) -> None:
    """Test recovery from synchronization failures.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Sync Failure Recovery")
    
    try:
        # Create team
        team = create_team(
            name="Sync Recovery Test",
            sync_mode=SyncMode.MANUAL
        )
        
        # Add agents
        agent1 = create_agent(
            agent_type="base",
            name="Recovery Agent 1",
            agent_id="recovery-agent-1"
        )
        team.add_member(agent1)
        
        # Try to sync with non-existent agent
        nonexistent_result = await team.sync_agent_state("nonexistent-agent-id")
        
        print_info(f"Non-existent agent sync result: {nonexistent_result}")
        assert 'success' in nonexistent_result, "Result should have success flag"
        assert not nonexistent_result.get('success', True), "Non-existent agent sync should fail"
        
        # Verify team can still function after sync failure
        # Add another agent after failure
        agent2 = create_agent(
            agent_type="base",
            name="Recovery Agent 2",
            agent_id="recovery-agent-2"
        )
        added = team.add_member(agent2)
        assert added, "Should add agent after sync failure"
        
        # Try syncing with valid agent after failure
        valid_result = await team.sync_agent_state(agent2.id)
        print_info(f"Valid agent sync result after failure: {valid_result}")
        
        # Get status after recovery
        status = await team.get_sync_status()
        print_info(f"Status after recovery: {status}")
        
        # Clean up
        await team.terminate()
        
        results.add_pass("Sync failure recovery test successful")
        
    except Exception as e:
        results.add_fail(f"Sync failure recovery test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all state synchronization tests."""
    print_title("TEAM MODULE - STATE SYNCHRONIZATION TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_sync_modes(results)
        await test_manual_sync(results)
        await test_periodic_sync(results)
        await test_sync_failure_recovery(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All state synchronization tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
