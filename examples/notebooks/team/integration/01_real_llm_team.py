#!/usr/bin/env python
"""
Team Integration Test with Real LLM Provider

This script tests the team module with actual LLM integration:
- Creating a team with LLM-powered agents
- Hierarchical team functionality with real reasoning
- Task delegation and execution with real LLM agents
- Prompt template incorporation and real language understanding
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
from enterprise_ai.team.core.types import TeamMemberRole
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger
from enterprise_ai.llm.providers.ollama import OllamaProvider

# Initialize logger
logger = get_logger("team.tests.integration_llm")


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


async def test_ollama_connectivity(results: TestResults) -> bool:
    """Test Ollama provider direct connectivity.
    
    This ensures that the Ollama service is running and available
    before proceeding with the main tests.
    
    Args:
        results: Test results tracker
    
    Returns:
        True if Ollama is available, False otherwise
    """
    print_section("0. Testing Ollama Connectivity")
    
    try:
        # Initialize Ollama provider with smollm2
        ollama_provider = OllamaProvider(model_name="smollm2", timeout=2400.0)
        print_info(f"Initialized Ollama provider with model: {ollama_provider.model_name}")
        
        # Test basic completion
        test_message = Message.user_message("Hello!")
        print_info("Sending test message to Ollama...")
        
        timer = Timer("Ollama Response")
        timer.start()
        
        try:
            response = ollama_provider.complete([test_message])
            timer.stop()
            print_info(f"Ollama response: '{response.content}'")
            print_success("Ollama test successful!")
            results.add_pass("Ollama connectivity works")
            return True
        except Exception as e:
            timer.stop()
            print_error(f"Ollama request error: {e}")
            if "timeout" in str(e).lower():
                print_warning("Ollama request timed out. The server might be overloaded or the model is still loading.")
            else:
                print_warning("Error communicating with Ollama.")
            
            results.add_fail(f"Ollama request failed: {e}")
            return False
            
    except Exception as e:
        print_error(f"Ollama provider initialization failed: {e}")
        print_warning("This suggests Ollama is not installed or not running properly.")
        print_warning("Please make sure Ollama is installed and running with the 'smollm2' model.")
        
        results.add_fail(f"Ollama initialization failed: {e}")
        return False


async def create_llm_team(results: TestResults) -> Optional[Any]:
    """Create a team with LLM-powered agents.
    
    Args:
        results: Test results tracker
    
    Returns:
        Team object or None if creation failed
    """
    print_section("1. Creating Team with LLM Agents")
    
    try:
        # Create manager agent with LLM
        manager = create_agent(
            agent_type="llm",
            name="LLM Manager",
            agent_id="llm-mgr-001",
            llm_provider_name="ollama",
            llm_provider_kwargs={"model_name": "smollm2", "timeout": 2400.0}
        )
        print_info(f"Created LLM manager: {manager.name}")
        
        # Create hierarchical team with LLM manager
        team = create_team(
            team_type="hierarchical",
            name="LLM Team",
            manager_agent=manager
        )
        print_info(f"Created team: {team.name}")
        
        # Add worker agents with different specialties
        specialties = [
            "Research", 
            "Development", 
            "Planning"
        ]
        
        for specialty in specialties:
            worker = create_agent(
                agent_type="llm",
                name=f"{specialty} Specialist",
                agent_id=f"llm-{specialty.lower()}",
                llm_provider_name="ollama",
                llm_provider_kwargs={"model_name": "smollm2", "timeout": 2400.0},
                metadata={"specialty": specialty}
            )
            team.add_member(worker)
            print_info(f"Added {worker.name} to team")
        
        print_info(f"Team has {len(team.get_members())} members")
        results.add_pass("LLM team creation successful")
        
        return team
        
    except Exception as e:
        results.add_fail(f"LLM team creation failed: {e}")
        logger.exception("Test failure")
        return None


async def test_llm_task_assignment(results: TestResults, team: Any) -> None:
    """Test task assignment with LLM-powered agents.
    
    Args:
        results: Test results tracker
        team: Team with LLM agents
    """
    print_section("2. Task Assignment with LLM Agents")
    
    try:
        # Create a complex task
        task = {
            "name": "New Product Design",
            "description": "Design a new product based on market research",
            "priority": "high",
            "skills_required": ["research", "planning", "development"]
        }
        
        # Assign to team
        print_info(f"Assigning task: {task['name']}")
        success = team.assign_task(task)
        
        # Assertions
        assert success, "Task assignment should succeed"
        
        # Get all tasks
        all_tasks = team.get_all_tasks()
        assert len(all_tasks) > 0, "Should have at least one task"
        
        # Find the assigned task
        design_task = None
        for t in all_tasks:
            if t.name == "New Product Design":
                design_task = t
                break
        
        assert design_task is not None, "Should find the assigned task"
        print_info(f"Task assigned with ID: {design_task.id}")
        
        # In a hierarchical team, the task should be assigned to the manager
        manager_tasks = team.get_agent_tasks(team.manager.id)
        assert len(manager_tasks) > 0, "Manager should have tasks"
        
        # Let the manager decompose the task
        subtasks = [
            {"name": "Market Research", "priority": "high", "specialty": "Research"},
            {"name": "Product Planning", "priority": "medium", "specialty": "Planning"},
            {"name": "Prototype Design", "priority": "medium", "specialty": "Development"}
        ]
        
        created_subtasks = team.decompose_task(design_task.id, subtasks)
        assert len(created_subtasks) == 3, "Should create 3 subtasks"
        print_info(f"Created {len(created_subtasks)} subtasks")
        
        results.add_pass("Task assignment with LLM agents successful")
        
    except Exception as e:
        results.add_fail(f"Task assignment with LLM agents failed: {e}")
        logger.exception("Test failure")


async def test_llm_messaging(results: TestResults, team: Any) -> None:
    """Test messaging with LLM-powered agents.
    
    Args:
        results: Test results tracker
        team: Team with LLM agents
    """
    print_section("3. Messaging with LLM Agents")
    
    try:
        # Send a message to the team manager
        message = "What's your role in this team?"
        
        print_info(f"Sending message to team manager: '{message}'")
        timer = Timer("Manager Response")
        timer.start()
        
        response = await team.manager.aprocess_message(message)
        timer.stop()
        
        # Assertions
        assert response is not None, "Response should not be None"
        assert hasattr(response, "content"), "Response should have content"
        assert len(response.content) > 0, "Response content should not be empty"
        
        print_info(f"Manager response: '{response.content}'")
        
        # Now broadcast a message to all team members
        broadcast_message = "Briefly describe your specialty."
        
        print_info(f"Broadcasting message: '{broadcast_message}'")
        timer = Timer("Broadcast Responses")
        timer.start()
        
        responses = await team.abroadcast_message(broadcast_message)
        timer.stop()
        
        # Assertions
        assert responses is not None, "Broadcast responses should not be None"
        assert len(responses) == len(team.get_members()), "Should have one response per team member"
        
        # Log responses
        print_info(f"Received {len(responses)} responses:")
        for i, response in enumerate(responses):
            print_info(f"  Member {i+1}: '{response.content}'")
        
        results.add_pass("Messaging with LLM agents successful")
        
    except Exception as e:
        results.add_fail(f"Messaging with LLM agents failed: {e}")
        logger.exception("Test failure")


async def test_prompt_template_integration(results: TestResults, team: Any) -> None:
    """Test prompt template integration with LLM agents.
    
    Args:
        results: Test results tracker
        team: Team with LLM agents
    """
    print_section("4. Prompt Template Integration")
    
    try:
        # Access a collaboration template
        from enterprise_ai.prompt.templates import get_template
        
        # Try to load the collaboration template
        template = get_template("team/collaboration.prompt")
        assert template is not None, "Should load collaboration template"
        
        # In a real implementation, you would test sending messages with template-guided behavior
        # For this test, we'll just verify template loading
        
        print_info(f"Successfully loaded collaboration template ({len(template)} chars)")
        results.add_pass("Prompt template loading successful")
        
        # Note: A full integration would create agents with these templates and test
        # their behavior, but that's beyond the scope of this basic integration test
        
    except Exception as e:
        results.add_fail(f"Prompt template integration failed: {e}")
        logger.exception("Test failure")


async def test_team_termination(results: TestResults, team: Any) -> None:
    """Test team termination with LLM agents.
    
    Args:
        results: Test results tracker
        team: Team with LLM agents
    """
    print_section("5. Team Termination")
    
    try:
        # Get status before termination
        status = team.get_status()
        print_info(f"Team status before termination: {len(team.get_members())} members")
        
        # Terminate the team
        success = await team.terminate()
        
        # Assertions
        assert success, "Team termination should succeed"
        print_info("Team terminated successfully")
        
        results.add_pass("Team termination successful")
        
    except Exception as e:
        results.add_fail(f"Team termination failed: {e}")
        logger.exception("Test failure")


async def main():
    """Run LLM integration tests."""
    print_title("TEAM MODULE - LLM INTEGRATION TESTS", style="double")
    
    results = TestResults()
    
    try:
        # First check Ollama connectivity
        ollama_works = await test_ollama_connectivity(results)
        
        if not ollama_works:
            print_warning("Skipping LLM integration tests since Ollama test failed.")
            return
        
        # Run all tests
        team = await create_llm_team(results)
        
        if team:
            await test_llm_task_assignment(results, team)
            await test_llm_messaging(results, team)
            await test_prompt_template_integration(results, team)
            await test_team_termination(results, team)
        
        # Summary
        print_section("Test Summary")
        print_info(results.summary())
        
        if results.failed > 0:
            print_error("\nFailed tests:")
            for error in results.errors:
                print_error(f"  - {error}")
        else:
            print_success("\n✅ All LLM integration tests passed!")
            
    except Exception as e:
        print_error(f"\n❌ Test suite failed: {e}")
        logger.exception("Test failure")


if __name__ == "__main__":
    asyncio.run(main())