#!/usr/bin/env python
"""
Team Coordination Test

This script demonstrates team coordination, resource management,
and conflict resolution capabilities.
"""

import asyncio
import sys
import os
from typing import List

# Import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils import *

setup_project_path()

from enterprise_ai.team.core import create_team
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.team.architecture.coordinator import (
    CoordinationStrategy,
    ConflictType
)
from enterprise_ai.agent.core import create_agent
from enterprise_ai.logger import get_logger

logger = get_logger("team_coordination")


async def test_resource_management():
    """Test resource allocation and management."""
    print_title("TEAM COORDINATION & RESOURCE MANAGEMENT")
    
    # Create team
    team = create_team(name="Resource Team")
    
    # Add agents
    print_section("1. Setting Up Team")
    
    agents = []
    for i in range(3):
        agent = create_agent(
            agent_type="base",
            name=f"Worker {i+1}",
            agent_id=f"worker-{i+1}"
        )
        team.add_member(agent)
        agents.append(agent)    
    print_success(f"Created team with {len(agents)} workers")
    
    # Test resource requests
    print_section("2. Resource Requests")
    
    # Multiple agents request same resource
    resource_id = "database_connection"
    
    results = []
    for agent in agents[:2]:  # First two agents
        granted = await team.request_resource(
            agent_id=agent.id,
            resource_id=resource_id,
            priority=1
        )
        results.append((agent.id, granted))
        print_info(f"  {agent.id} requested {resource_id}: {'Granted' if granted else 'Denied'}")
    
    # Check resource status
    resource_status = team._coordinator.get_resource_status()
    print_info(f"\nResource status: {resource_status}")
    
    return team, agents


async def test_conflict_resolution():
    """Test conflict detection and resolution."""
    print_section("3. Conflict Resolution")
    
    team, agents = await test_resource_management()
    
    # Register a conflict
    conflict_id = team.register_conflict(
        description="Two agents need exclusive database access",
        agents=[agents[0].id, agents[1].id],
        resource_id="database_connection"
    )
    
    print_info(f"Registered conflict: {conflict_id}")
    
    # Check active conflicts
    conflicts = team.get_active_conflicts()
    print_info(f"Active conflicts: {len(conflicts)}")
    
    for conflict in conflicts:
        print_info(f"  - {conflict['description']}")
        print_info(f"    Agents: {conflict['agents']}")
        print_info(f"    Status: {conflict['status']}")    
    # Resolve conflict
    resolved = team.resolve_conflict(
        conflict_id=conflict_id,
        resolution="Implement connection pooling with shared access"
    )
    
    print_success(f"Conflict resolved: {resolved}")
    
    return team


async def test_coordination_strategies():
    """Test different coordination strategies."""
    print_section("4. Coordination Strategies")
    
    # Test different strategies
    strategies = [
        CoordinationStrategy.CENTRALIZED,
        CoordinationStrategy.DECENTRALIZED,
        CoordinationStrategy.HYBRID
    ]
    
    for strategy in strategies:
        print_info(f"\nTesting {strategy.value} strategy:")
        
        team = create_team(name=f"{strategy.value} Team")
        team.set_coordination_strategy(strategy)
        
        # Add agents
        for i in range(2):
            agent = create_agent(
                agent_type="base",
                name=f"Agent {i+1}",
                agent_id=f"agent-{strategy.value}-{i+1}"
            )
            team.add_member(agent)
        
        # Test resource allocation with this strategy
        resource_id = f"resource_{strategy.value}"
        
        # Both agents request
        for agent in team.get_members():
            granted = await team.request_resource(
                agent_id=agent.id,
                resource_id=resource_id,
                priority=1
            )
            print_info(f"    {agent.id}: {'Granted' if granted else 'Queued'}")

async def test_priority_allocation():
    """Test priority-based resource allocation."""
    print_section("5. Priority-Based Allocation")
    
    team = create_team(name="Priority Team")
    
    # Add agents with different roles
    manager = create_agent(agent_type="base", name="Manager", agent_id="mgr-001")
    specialist = create_agent(agent_type="base", name="Specialist", agent_id="spec-001")
    member = create_agent(agent_type="base", name="Member", agent_id="mem-001")
    
    team.add_member(manager, role=TeamMemberRole.MANAGER)
    team.add_member(specialist, role=TeamMemberRole.SPECIALIST)
    team.add_member(member, role=TeamMemberRole.MEMBER)
    
    # Request same resource with different priorities
    resource_id = "critical_resource"
    
    # Low priority request first
    await team.request_resource(member.id, resource_id, priority=1)
    print_info(f"Member requested with priority 1")
    
    # High priority request
    granted = await team.request_resource(manager.id, resource_id, priority=10)
    print_info(f"Manager requested with priority 10: {'Granted' if granted else 'Queued'}")
    
    # Medium priority
    await team.request_resource(specialist.id, resource_id, priority=5)
    print_info(f"Specialist requested with priority 5")
    
    # Check queue
    print_info("\nResource queue order should reflect priorities")


async def main():
    """Run coordination tests."""
    print_title("TEAM MODULE - COORDINATION TEST", style="double")
    
    try:
        await test_resource_management()
        await test_conflict_resolution()
        await test_coordination_strategies()
        await test_priority_allocation()
        
        print_success("\nAll coordination tests completed!")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())