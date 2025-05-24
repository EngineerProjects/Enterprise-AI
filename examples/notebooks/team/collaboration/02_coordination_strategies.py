#!/usr/bin/env python
"""
Coordination Strategies Tests

This script tests team coordination strategies, including:
- Different coordination strategy implementations
- Strategy switching during runtime
- Conflict resolution with various policies
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
from enterprise_ai.team.architecture.coordinator import CoordinationStrategy
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.coordination_strategies")


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


async def test_coordination_strategies(results: TestResults) -> None:
    """Test different coordination strategies.
    
    Args:
        results: Test results tracker
    """
    print_section("1. Coordination Strategies")
    
    try:
        # Create team
        team = create_team(name="Coordination Strategies Team")
        
        # Add agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Coordination Agent {i+1}",
                agent_id=f"coordination-agent-{i+1}"
            )
            team.add_member(agent)
        
        # Test strategy types if available
        coordinator = team._coordinator
        
        # Get current strategy
        current_strategy = coordinator.strategy if hasattr(coordinator, "strategy") else None
        print_info(f"Current strategy: {current_strategy}")
        
        # Try all available strategies
        if hasattr(coordinator, "set_strategy") and hasattr(CoordinationStrategy, "__members__"):
            for strategy_name, strategy_value in CoordinationStrategy.__members__.items():
                print_info(f"Testing strategy: {strategy_name}")
                
                # Set strategy
                coordinator.set_strategy(strategy_value)
                
                # Verify strategy was set
                new_strategy = coordinator.strategy
                assert new_strategy == strategy_value, f"Strategy should be {strategy_value}, got {new_strategy}"
                
                # Test coordination with this strategy
                members = team.get_members()
                resource_id = f"resource_{strategy_name}"
                
                # Request resource
                granted = await team.request_resource(members[0].id, resource_id)
                print_info(f"Resource request with {strategy_name} strategy: {'Granted' if granted else 'Denied'}")
                
                # Second request with higher priority
                second_granted = await team.request_resource(members[1].id, resource_id, priority=5)
                print_info(f"High priority request with {strategy_name}: {'Granted' if second_granted else 'Denied'}")
                
                # Release resource
                released = team.release_resource(members[0].id, resource_id)
                if not released and second_granted:
                    # If second request was granted, release from second agent
                    team.release_resource(members[1].id, resource_id)
        else:
            print_warning("Coordinator does not support strategy switching")
        
        results.add_pass("Coordination strategies test completed")
        
    except Exception as e:
        results.add_fail(f"Coordination strategies test failed: {e}")
        logger.exception("Test failure")


async def test_strategy_switching(results: TestResults) -> None:
    """Test strategy switching during runtime.
    
    Args:
        results: Test results tracker
    """
    print_section("2. Strategy Switching")
    
    try:
        # Create team
        team = create_team(name="Strategy Switching Team")
        
        # Add agents
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"Switching Agent {i+1}",
                agent_id=f"switching-agent-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        coordinator = team._coordinator
        
        # Check if strategy switching is supported
        if hasattr(coordinator, "set_strategy") and hasattr(CoordinationStrategy, "__members__"):
            strategies = list(CoordinationStrategy.__members__.values())
            if len(strategies) >= 2:
                # Use first two strategies for testing
                strategy1 = strategies[0]
                strategy2 = strategies[1]
                
                # Set initial strategy
                coordinator.set_strategy(strategy1)
                print_info(f"Set initial strategy: {strategy1}")
                
                # Request resource with first strategy
                resource_id = "switching_resource"
                granted1 = await team.request_resource(members[0].id, resource_id)
                print_info(f"Resource request with strategy 1: {'Granted' if granted1 else 'Denied'}")
                
                # Switch strategy during runtime
                coordinator.set_strategy(strategy2)
                print_info(f"Switched to strategy: {strategy2}")
                
                # Request resource with new strategy
                resource_id2 = "switching_resource2"
                granted2 = await team.request_resource(members[1].id, resource_id2)
                print_info(f"Resource request with strategy 2: {'Granted' if granted2 else 'Denied'}")
                
                # Release resources
                if granted1:
                    team.release_resource(members[0].id, resource_id)
                if granted2:
                    team.release_resource(members[1].id, resource_id2)
            else:
                print_warning("Not enough strategy types for switching test")
        else:
            print_warning("Coordinator does not support strategy switching")
        
        results.add_pass("Strategy switching test completed")
        
    except Exception as e:
        results.add_fail(f"Strategy switching test failed: {e}")
        logger.exception("Test failure")


async def test_conflict_resolution(results: TestResults) -> None:
    """Test conflict resolution with different policies.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Conflict Resolution")
    
    try:
        # Create team
        team = create_team(name="Conflict Resolution Team")
        
        # Add agents
        agent1 = create_agent(
            agent_type="base",
            name="Conflict Agent 1",
            agent_id="conflict-agent-1"
        )
        
        agent2 = create_agent(
            agent_type="base",
            name="Conflict Agent 2",
            agent_id="conflict-agent-2"
        )
        
        # Add agent with manager role
        manager = create_agent(
            agent_type="base",
            name="Conflict Manager",
            agent_id="conflict-manager"
        )
        
        team.add_member(agent1)
        team.add_member(agent2)
        team.add_member(manager, role=TeamMemberRole.MANAGER)
        
        # Create conflict
        conflict_id = team.register_conflict(
            description="Test conflict for resolution",
            agents=[agent1.id, agent2.id],
            resource_id="contested_resource"
        )
        
        assert conflict_id is not None, "Should get a conflict ID"
        print_info(f"Registered conflict: {conflict_id}")
        
        # Get active conflicts
        conflicts = team.get_active_conflicts()
        assert len(conflicts) > 0, "Should have active conflicts"
        print_info(f"Active conflicts: {len(conflicts)}")
        
        # Resolve conflict
        resolved = team.resolve_conflict(
            conflict_id=conflict_id,
            resolution="Test resolution by manager"
        )
        
        assert resolved, "Conflict should be resolved"
        print_info("Successfully resolved conflict")
        
        # Verify conflict is no longer active
        conflicts_after = team.get_active_conflicts()
        assert len(conflicts_after) < len(conflicts), "Should have fewer active conflicts"
        print_info(f"Active conflicts after resolution: {len(conflicts_after)}")
        
        results.add_pass("Conflict resolution test successful")
        
    except Exception as e:
        results.add_fail(f"Conflict resolution test failed: {e}")
        logger.exception("Test failure")


async def test_resource_management(results: TestResults) -> None:
    """Test resource management and coordination.
    
    Args:
        results: Test results tracker
    """
    print_section("4. Resource Management")
    
    try:
        # Create team
        team = create_team(name="Resource Management Team")
        
        # Add agents
        for i in range(3):
            agent = create_agent(
                agent_type="base",
                name=f"Resource Agent {i+1}",
                agent_id=f"resource-mgmt-agent-{i+1}"
            )
            team.add_member(agent)
        
        members = team.get_members()
        
        # Create multiple resources
        resources = ["resource_a", "resource_b", "resource_c"]
        
        # Request multiple resources from different agents
        results_map = {}
        
        # First agent gets all resources
        for resource in resources:
            granted = await team.request_resource(members[0].id, resource)
            results_map[f"{members[0].id}:{resource}"] = granted
            print_info(f"Agent 1 request for {resource}: {'Granted' if granted else 'Denied'}")
        
        # Second agent tries to get same resources
        for resource in resources:
            granted = await team.request_resource(members[1].id, resource)
            results_map[f"{members[1].id}:{resource}"] = granted
            print_info(f"Agent 2 request for {resource}: {'Granted' if granted else 'Denied'}")
        
        # Third agent tries with high priority
        for resource in resources:
            granted = await team.request_resource(members[2].id, resource, priority=10)
            results_map[f"{members[2].id}:{resource}"] = granted
            print_info(f"Agent 3 high-priority request for {resource}: {'Granted' if granted else 'Denied'}")
        
        # Release all resources
        for agent in members:
            for resource in resources:
                if results_map.get(f"{agent.id}:{resource}", False):
                    released = team.release_resource(agent.id, resource)
                    print_info(f"Released {resource} from {agent.id}: {released}")
        
        # Get coordination status
        status = team.get_status()
        if "coordination" in status:
            print_info(f"Coordination status: {status['coordination']}")
        
        results.add_pass("Resource management test successful")
        
    except Exception as e:
        results.add_fail(f"Resource management test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all coordination strategy tests."""
    print_title("TEAM MODULE - COORDINATION STRATEGY TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        await test_coordination_strategies(results)
        await test_strategy_switching(results)
        await test_conflict_resolution(results)
        await test_resource_management(results)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All coordination strategy tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())
