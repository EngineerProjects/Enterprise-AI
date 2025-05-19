"""
Tests for the team module membership functionality.

This module tests the integration between team, membership manager,
and role system components.
"""

import asyncio
import unittest
from typing import Optional, List, Dict, Any
from unittest.mock import MagicMock, patch

from enterprise_ai.agent.core.types import AgentProtocol, MessageProtocol, Task
from enterprise_ai.schema import Message
from enterprise_ai.team import (
    BaseTeam,
    TeamProtocol,
    TeamMemberRole,
    TeamMessageType,
    MembershipManager,
    BaseTeamRole,
    TeamManagerRole,
    TeamSpecialistRole,
    TeamCoordinatorRole,
    create_team_role,
    create_team,
)


# Mock implementation of agent for testing
class MockAgent(AgentProtocol):
    """Mock agent for testing team functionality."""
    
    def __init__(self, agent_id: str, name: Optional[str] = None) -> None:
        self.id = agent_id
        self.name = name or f"Agent-{agent_id}"
        self.messages: List[MessageProtocol] = []
        self.tasks: List[Dict[str, Any]] = []
    
    def process_message(self, message: MessageProtocol) -> MessageProtocol:
        """Process a message."""
        self.messages.append(message)
        return Message.assistant_message(f"Response from {self.name}")
    
    async def aprocess_message(self, message: MessageProtocol) -> MessageProtocol:
        """Process a message asynchronously."""
        return self.process_message(message)
    
    def assign_task(self, task: Task) -> bool:
        """Assign a task to the agent."""
        self.tasks.append(task if isinstance(task, dict) else task.to_dict())
        return True
    
    async def initialize(self) -> bool:
        """Initialize the agent."""
        return True
    
    async def terminate(self) -> bool:
        """Terminate the agent."""
        return True


class TestTeamMembership(unittest.TestCase):
    """Test cases for team membership functionality."""
    
    def setUp(self) -> None:
        """Set up test case."""
        self.team = BaseTeam(team_id="test-team", name="Test Team")
        self.agent1 = MockAgent("agent-1", "Agent One")
        self.agent2 = MockAgent("agent-2", "Agent Two")
        self.agent3 = MockAgent("agent-3", "Agent Three")
    
    def test_add_member(self) -> None:
        """Test adding a member to the team."""
        # Add a member with default role
        self.assertTrue(self.team.add_member(self.agent1))
        
        # Add a member with specified role
        self.assertTrue(self.team.add_member(self.agent2, TeamMemberRole.MANAGER))
        
        # Add a member with role as string
        self.assertTrue(self.team.add_member(self.agent3, "SPECIALIST"))
        
        # Check member count
        self.assertEqual(self.team._membership.count, 3)
        
        # Check that agent is in the team
        self.assertIsNotNone(self.team.get_member("agent-1"))
        self.assertIsNotNone(self.team.get_member("agent-2"))
        self.assertIsNotNone(self.team.get_member("agent-3"))
        
        # Check member roles
        self.assertEqual(self.team._membership.get_role("agent-1"), TeamMemberRole.MEMBER)
        self.assertEqual(self.team._membership.get_role("agent-2"), TeamMemberRole.MANAGER)
        self.assertEqual(self.team._membership.get_role("agent-3"), TeamMemberRole.SPECIALIST)
        
        # Check that manager is set correctly
        self.assertEqual(self.team._membership.manager.id, "agent-2")
    
    def test_add_duplicate_member(self) -> None:
        """Test adding a duplicate member."""
        self.team.add_member(self.agent1)
        self.assertFalse(self.team.add_member(self.agent1))
    
    def test_remove_member(self) -> None:
        """Test removing a member from the team."""
        self.team.add_member(self.agent1)
        self.team.add_member(self.agent2, TeamMemberRole.MANAGER)
        
        # Remove a member
        self.assertTrue(self.team.remove_member("agent-1"))
        
        # Check that member is removed
        self.assertIsNone(self.team.get_member("agent-1"))
        self.assertEqual(self.team._membership.count, 1)
    
    def test_get_members_by_role(self) -> None:
        """Test getting members by role."""
        self.team.add_member(self.agent1, TeamMemberRole.SPECIALIST)
        self.team.add_member(self.agent2, TeamMemberRole.MANAGER)
        self.team.add_member(self.agent3, TeamMemberRole.SPECIALIST)
        
        # Check that we can get members by role
        specialists = self.team._membership.get_members_by_role(TeamMemberRole.SPECIALIST)
        self.assertEqual(len(specialists), 2)
        self.assertIn(self.agent1, specialists)
        self.assertIn(self.agent3, specialists)
        
        managers = self.team._membership.get_members_by_role(TeamMemberRole.MANAGER)
        self.assertEqual(len(managers), 1)
        self.assertIn(self.agent2, managers)
    
    def test_get_members(self) -> None:
        """Test getting all members."""
        self.team.add_member(self.agent1)
        self.team.add_member(self.agent2)
        
        # Check that we can get all members
        members = self.team.get_members()
        self.assertEqual(len(members), 2)
        self.assertIn(self.agent1, members)
        self.assertIn(self.agent2, members)
    
    def test_get_status(self) -> None:
        """Test getting team status."""
        self.team.add_member(self.agent1, TeamMemberRole.SPECIALIST)
        self.team.add_member(self.agent2, TeamMemberRole.MANAGER)
        
        # Get status
        status = self.team.get_status()
        
        # Check basic information
        self.assertEqual(status["id"], "test-team")
        self.assertEqual(status["name"], "Test Team")
        self.assertEqual(status["member_count"], 2)
        self.assertEqual(status["manager"], "agent-2")
        
        # Check member information
        self.assertIn("agent-1", status["members"])
        self.assertIn("agent-2", status["members"])
        self.assertEqual(status["members"]["agent-1"]["role"], "SPECIALIST")
        self.assertEqual(status["members"]["agent-2"]["role"], "MANAGER")


class TestTeamRoles(unittest.TestCase):
    """Test cases for team roles functionality."""
    
    def test_create_team_role(self) -> None:
        """Test creating team roles."""
        # Create a manager role
        manager_role = create_team_role(
            role_type="manager",
            additional_context="Team Lead for Development",
        )
        self.assertIsInstance(manager_role, TeamManagerRole)
        self.assertEqual(manager_role.name, "Team Manager")
        self.assertEqual(manager_role.coordination_level, 8)
        
        # Create a specialist role
        specialist_role = create_team_role(
            role_type="specialist",
            specialty="Frontend Development",
            additional_context="Focus on React and TypeScript",
        )
        self.assertIsInstance(specialist_role, TeamSpecialistRole)
        self.assertEqual(specialist_role.name, "Frontend Development Specialist")
        self.assertEqual(specialist_role.specialty, "Frontend Development")
        self.assertEqual(specialist_role.coordination_level, 4)
        
        # Create a coordinator role
        coordinator_role = create_team_role(
            role_type="coordinator",
            additional_context="Scrum Master responsibilities",
        )
        self.assertIsInstance(coordinator_role, TeamCoordinatorRole)
        self.assertEqual(coordinator_role.name, "Team Coordinator")
        self.assertEqual(coordinator_role.coordination_level, 6)
        
        # Create a custom role
        custom_role = create_team_role(
            role_type="custom",
            name="DevOps Engineer",
            description="Manages CI/CD and infrastructure",
            coordination_level=5,
            team_responsibilities=["Manage CI/CD pipelines", "Infrastructure automation"],
        )
        self.assertIsInstance(custom_role, BaseTeamRole)
        self.assertEqual(custom_role.name, "DevOps Engineer")
        self.assertEqual(custom_role.coordination_level, 5)
        self.assertEqual(len(custom_role.team_responsibilities), 2)
    
    def test_team_role_serialization(self) -> None:
        """Test serializing team roles to dictionaries."""
        # Create a role
        role = TeamManagerRole(additional_context="Tech Lead")
        
        # Convert to dictionary
        role_dict = role.to_dict()
        
        # Check basic properties
        self.assertEqual(role_dict["name"], "Team Manager")
        self.assertIn("coordination_level", role_dict)
        self.assertIn("team_responsibilities", role_dict)
        
        # Add a responsibility and check serialization
        role.add_team_responsibility("Mentor junior team members")
        updated_dict = role.to_dict()
        self.assertIn("Mentor junior team members", updated_dict["team_responsibilities"])


class TestTeamCreation(unittest.TestCase):
    """Test cases for team creation functionality."""
    
    def test_create_team_with_members(self) -> None:
        """Test creating a team with initial members."""
        agent1 = MockAgent("agent-1", "Agent One")
        agent2 = MockAgent("agent-2", "Agent Two")
        
        # Create a team with a manager and member
        team = create_team(
            team_type="base",
            name="Development Team",
            manager_agent=agent1,
            members=[agent2],
        )
        
        # Check team properties
        self.assertEqual(team.name, "Development Team")
        self.assertEqual(team._membership.count, 2)
        self.assertEqual(team._membership.manager.id, "agent-1")
        
        # Check member roles
        self.assertEqual(team._membership.get_role("agent-1"), TeamMemberRole.MANAGER)
        self.assertEqual(team._membership.get_role("agent-2"), TeamMemberRole.MEMBER)


# Main test runner
if __name__ == "__main__":
    unittest.main()
