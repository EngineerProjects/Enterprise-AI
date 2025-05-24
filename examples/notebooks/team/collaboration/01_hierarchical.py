#!/usr/bin/env python
"""
Hierarchical Team Tests

This script tests the hierarchical team implementation, including:
- Team creation with different decision modes
- Manager-worker relationship establishment
- Task delegation through hierarchy
- Decision approval workflows
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
from enterprise_ai.team.collaboration.hierarchical import HierarchicalTeam, DecisionMode
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Initialize logger
logger = get_logger("team.tests.hierarchical")


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


async def test_hierarchical_creation(results: TestResults) -> Tuple[Any, Any]:
    """Test hierarchical team creation with different decision modes.
    
    Args:
        results: Test results tracker
    
    Returns:
        Tuple of (team, manager)
    """
    print_section("1. Hierarchical Team Creation")
    
    try:
        # Create a manager agent first
        manager = create_agent(
            agent_type="base",
            name="Project Manager",
            agent_id="mgr-001"
        )
        
        # Create hierarchical team with manager
        team = create_team(
            team_type="hierarchical",
            name="Hierarchical Team",
            manager_agent=manager,
            decision_mode=DecisionMode.MANAGER_DELEGATED
        )
        
        # Assertions
        assert team is not None, "Team should not be None"
        assert isinstance(team, HierarchicalTeam), "Team should be a HierarchicalTeam"
        assert team.manager is not None, "Team should have a manager"
        assert team.manager.id == manager.id, "Manager should be the one we provided"
        assert team.decision_mode == DecisionMode.MANAGER_DELEGATED, "Decision mode should be MANAGER_DELEGATED"
        
        print_info(f"Created hierarchical team: {team.name}")
        print_info(f"Manager: {team.manager.name}")
        print_info(f"Decision mode: {team.decision_mode}")
        
        results.add_pass("Hierarchical team creation successful")
        
        return team, manager
        
    except Exception as e:
        results.add_fail(f"Hierarchical team creation failed: {e}")
        logger.exception("Test failure")
        raise


async def test_add_workers(results: TestResults, team: Any) -> None:
    """Test adding workers to a hierarchical team.
    
    Args:
        results: Test results tracker
        team: Hierarchical team from previous test
    """
    print_section("2. Adding Workers to Hierarchical Team")
    
    try:
        # Add worker agents
        for i in range(3):
            worker = create_agent(
                agent_type="base",
                name=f"Worker {i+1}",
                agent_id=f"worker-{i+1}"
            )
            success = team.add_member(worker)
            
            # Assertions
            assert success, f"Should successfully add worker {i+1}"
        
        # Verify worker count
        members = team.get_members()
        worker_count = len(members) - 1  # Subtract 1 for manager
        
        assert worker_count == 3, f"Should have 3 workers, got {worker_count}"
        print_info(f"Added {worker_count} workers to team")
        
        # Check reporting relationships
        # In a real test, you would verify the relationships are correctly established
        # This would require access to the internal membership structure
        
        results.add_pass("Successfully added workers to hierarchical team")
        
    except Exception as e:
        results.add_fail(f"Adding workers failed: {e}")
        logger.exception("Test failure")


async def test_decision_modes(results: TestResults) -> None:
    """Test different decision modes in hierarchical teams.
    
    Args:
        results: Test results tracker
    """
    print_section("3. Testing Decision Modes")
    
    try:
        decision_modes = [
            DecisionMode.MANAGER_ONLY,
            DecisionMode.MANAGER_REVIEW,
            DecisionMode.MANAGER_DELEGATED
        ]
        
        for mode in decision_modes:
            # Create team with this decision mode
            manager = create_agent(
                agent_type="base",
                name=f"{mode.name} Manager",
                agent_id=f"mgr-{mode.name}"
            )
            
            team = create_team(
                team_type="hierarchical",
                name=f"{mode.name} Team",
                manager_agent=manager,
                decision_mode=mode
            )
            
            # Assertions
            assert team.decision_mode == mode, f"Decision mode should be {mode}"
            
            # Add a worker
            worker = create_agent(
                agent_type="base",
                name="Worker",
                agent_id=f"worker-{mode.name}"
            )
            team.add_member(worker)
            
            # In a real test, you would verify behavior specific to each decision mode
            # For example, MANAGER_ONLY would require all decisions to go through the manager
            
            print_info(f"Verified {mode.name} decision mode")
        
        results.add_pass("Decision mode tests successful")
        
    except Exception as e:
        results.add_fail(f"Decision mode tests failed: {e}")
        logger.exception("Test failure")


async def test_task_delegation(results: TestResults, team: Any) -> None:
    """Test task delegation in hierarchical teams.
    
    Args:
        results: Test results tracker
        team: Hierarchical team from previous test
    """
    print_section("4. Task Delegation in Hierarchy")
    
    try:
        # Create a task
        task = {
            "name": "Project Planning",
            "description": "Create a project plan for Q3",
            "priority": "high"
        }
        
        # Assign to team (should go to manager by default)
        success = team.assign_task(task)
        
        # Assertions
        assert success, "Task assignment should succeed"
        
        # Get all tasks
        all_tasks = team.get_all_tasks()
        assert len(all_tasks) > 0, "Should have at least one task"
        
        # Find the assigned task
        project_task = None
        for t in all_tasks:
            if t.name == "Project Planning":
                project_task = t
                break
        
        assert project_task is not None, "Should find the assigned task"
        
        # In a hierarchical team, it should be assigned to the manager
        manager_tasks = team.get_agent_tasks(team.manager.id)
        assert len(manager_tasks) > 0, "Manager should have tasks"
        
        # Verify task is assigned to manager
        found = False
        for t in manager_tasks:
            if t.id == project_task.id:
                found = True
                break
        
        assert found, "Task should be assigned to manager"
        print_info("Task correctly assigned to manager")
        
        # Test subtask decomposition and delegation
        subtasks = [
            {"name": "Requirements Gathering", "priority": "medium"},
            {"name": "Timeline Development", "priority": "medium"},
            {"name": "Resource Allocation", "priority": "medium"}
        ]
        
        created_subtasks = team.decompose_task(project_task.id, subtasks)
        
        # Assertions
        assert len(created_subtasks) == 3, "Should create 3 subtasks"
        print_info(f"Created {len(created_subtasks)} subtasks")
        
        # In a real test, you would verify proper delegation to specialists
        
        results.add_pass("Task delegation tests successful")
        
    except Exception as e:
        results.add_fail(f"Task delegation tests failed: {e}")
        logger.exception("Test failure")


async def test_decision_approval(results: TestResults, team: Any) -> None:
    """Test decision approval processes in hierarchical teams.
    
    Args:
        results: Test results tracker
        team: Hierarchical team from previous test
    """
    print_section("5. Decision Approval Process")
    
    try:
        # Set decision mode to require approval
        team.set_decision_mode(DecisionMode.MANAGER_REVIEW)
        assert team.decision_mode == DecisionMode.MANAGER_REVIEW, "Decision mode should be MANAGER_REVIEW"
        
        # Get worker
        workers = [m for m in team.get_members() if m.id != team.manager.id]
        assert len(workers) > 0, "Should have at least one worker"
        worker = workers[0]
        
        # Process a decision (using internal method for testing)
        decision_result = await team.process_decision(
            decision_type="resource_allocation",
            subject="budget increase",
            agent_id=worker.id,
            data={"amount": 5000, "reason": "unexpected costs"}
        )
        
        # Assertions
        assert decision_result is not None, "Decision result should not be None"
        assert "approved" in decision_result, "Decision result should have 'approved' key"
        
        print_info(f"Decision result: {decision_result.get('approved', False)}")
        print_info(f"Decision feedback: {decision_result.get('feedback', 'No feedback')}")
        
        results.add_pass("Decision approval process works")
        
    except Exception as e:
        results.add_fail(f"Decision approval test failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run all hierarchical team tests."""
    print_title("TEAM MODULE - HIERARCHICAL TEAM TESTS", style="double")
    
    results = TestResults()
    
    try:
        # Run all tests
        team, manager = await test_hierarchical_creation(results)
        await test_add_workers(results, team)
        await test_decision_modes(results)
        await test_task_delegation(results, team)
        await test_decision_approval(results, team)
        
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