"""
Base team implementation for Enterprise AI.

This module provides the foundational team class that implements
the TeamProtocol defined in types.py.
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from enterprise_ai.agent.message import (
    BaseAgentMessage,
    BroadcastMessage,
    ErrorMessage,
    create_message,
)
from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.logger import get_logger
from enterprise_ai.team.types import TeamProtocol

logger = get_logger("team.base")


class BaseTeam(TeamProtocol):
    """Base implementation of a team.

    This class provides a foundation for team implementations with
    basic functionality for organizing agents and handling tasks.
    """

    def __init__(
        self,
        team_id: Optional[str] = None,
        name: str = "Team",
        manager: Optional[AgentProtocol] = None,
    ) -> None:
        """Initialize a base team.

        Args:
            team_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            manager: Team manager agent
        """
        self._id = team_id or str(uuid.uuid4())
        self._name = name
        self._manager = manager
        self._members: Dict[str, AgentProtocol] = {}
        self._member_roles: Dict[str, str] = {}  # Maps agent_id to role
        self._created_at = time.time()

        logger.info(f"Initialized team: {self._id} ({self._name})")

    @property
    def id(self) -> str:
        """Get team ID.

        Returns:
            Team ID
        """
        return self._id

    @property
    def name(self) -> str:
        """Get team name.

        Returns:
            Team name
        """
        return self._name

    @property
    def manager(self) -> AgentProtocol:
        """Get team manager agent.

        Returns:
            Manager agent

        Raises:
            RuntimeError: If no manager is assigned
        """
        if not self._manager:
            raise RuntimeError(f"Team {self._id} has no manager assigned")
        return self._manager

    @manager.setter
    def manager(self, agent: AgentProtocol) -> None:
        """Set team manager.

        Args:
            agent: Agent to assign as manager
        """
        self._manager = agent
        logger.info(f"Assigned manager to team {self._id}: {agent.id} ({agent.name})")

    @property
    def members(self) -> Dict[str, AgentProtocol]:
        """Get team members (excluding manager).

        Returns:
            Dictionary of member agents
        """
        return self._members.copy()

    def add_member(self, agent: AgentProtocol, role: Optional[str] = None) -> bool:
        """Add a member to the team.

        Args:
            agent: Agent to add
            role: Optional role for the agent

        Returns:
            True if agent was added, False if already a member
        """
        if agent.id in self._members:
            logger.warning(f"Agent {agent.id} is already a member of team {self._id}")
            return False

        self._members[agent.id] = agent

        if role:
            self._member_roles[agent.id] = role
            logger.info(
                f"Added agent {agent.id} ({agent.name}) to team {self._id} with role {role}"
            )
        else:
            logger.info(f"Added agent {agent.id} ({agent.name}) to team {self._id}")

        return True

    def remove_member(self, agent_id: str) -> bool:
        """Remove a member from the team.

        Args:
            agent_id: ID of agent to remove

        Returns:
            True if agent was removed, False if not a member
        """
        if agent_id not in self._members:
            logger.warning(f"Agent {agent_id} is not a member of team {self._id}")
            return False

        del self._members[agent_id]
        if agent_id in self._member_roles:
            del self._member_roles[agent_id]

        logger.info(f"Removed agent {agent_id} from team {self._id}")
        return True

    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID.

        Args:
            agent_id: ID of the agent to get

        Returns:
            Agent or None if not found
        """
        return self._members.get(agent_id)

    def get_member_role(self, agent_id: str) -> Optional[str]:
        """Get the role of a team member.

        Args:
            agent_id: ID of the agent

        Returns:
            Role or None if not found
        """
        return self._member_roles.get(agent_id)

    def set_member_role(self, agent_id: str, role: str) -> bool:
        """Set the role of a team member.

        Args:
            agent_id: ID of the agent
            role: Role to assign

        Returns:
            True if role was set, False if agent not a member
        """
        if agent_id not in self._members:
            logger.warning(f"Agent {agent_id} is not a member of team {self._id}")
            return False

        self._member_roles[agent_id] = role
        logger.info(f"Set role {role} for agent {agent_id} in team {self._id}")
        return True

    def get_members_by_role(self, role: str) -> Dict[str, AgentProtocol]:
        """Get team members with a specific role.

        Args:
            role: Role to filter by

        Returns:
            Dictionary of matching members
        """
        return {
            agent_id: agent
            for agent_id, agent in self._members.items()
            if self._member_roles.get(agent_id) == role
        }

    def assign_task(self, task: Task, agent_id: Optional[str] = None) -> bool:
        """Assign a task to a team member or let manager decide.

        Args:
            task: Task to assign
            agent_id: Optional ID of agent to assign task to

        Returns:
            True if task was assigned, False otherwise
        """
        if agent_id:
            # Direct assignment to specific agent
            if agent_id not in self._members:
                logger.warning(f"Agent {agent_id} is not a member of team {self._id}")
                return False

            success = self._members[agent_id].assign_task(task)
            if success:
                logger.info(f"Assigned task {task.id} to agent {agent_id} in team {self._id}")
            return success

        # Let manager decide task assignment
        if self._manager:
            # For now, we simply assign to manager
            # A more sophisticated implementation would have the manager
            # decide which team member to assign the task to
            success = self._manager.assign_task(task)
            if success:
                logger.info(f"Assigned task {task.id} to manager of team {self._id}")
            return success

        logger.warning(f"Cannot assign task {task.id}: team {self._id} has no manager")
        return False

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message sent to the team.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Extract metadata
        metadata = getattr(message, "metadata", {}) or {}

        # Check if message targets a specific member
        target_agent_id = metadata.get("target_agent")
        if target_agent_id:
            if target_agent_id in self._members:
                logger.debug(f"Routing message to team member {target_agent_id}")
                return self._members[target_agent_id].process_message(message)
            else:
                logger.warning(f"Target agent {target_agent_id} not found in team {self._id}")
                return ErrorMessage(
                    message.sender_id,
                    message.receiver_id,
                    f"Agent {target_agent_id} not found in team {self._id}",
                    "AGENT_NOT_FOUND",
                )

        # Default to routing to manager
        if self._manager:
            logger.debug(f"Routing message to team manager {self._manager.id}")
            return self._manager.process_message(message)

        logger.warning(f"Cannot process message: team {self._id} has no manager")
        return ErrorMessage(
            message.sender_id,
            message.receiver_id,
            f"Team {self._id} has no manager to process message",
            "NO_MANAGER",
        )

    def broadcast_message(
        self, message_type: str, content: str, sender_id: str
    ) -> List[AgentMessage]:
        """Broadcast a message to all team members.

        Args:
            message_type: Type of message
            content: Message content
            sender_id: ID of sender

        Returns:
            List of response messages
        """
        responses: List[AgentMessage] = []

        # Create broadcast message
        broadcast = BroadcastMessage(
            sender_id=sender_id,
            content=content,
            metadata={"team_id": self._id, "broadcast_type": message_type},
        )

        # Send to manager
        if self._manager:
            manager_response = self._manager.process_message(broadcast)
            if manager_response:
                responses.append(manager_response)

        # Send to all members
        for agent_id, agent in self._members.items():
            member_response = agent.process_message(broadcast)
            if member_response:
                responses.append(member_response)

        logger.info(f"Broadcast message to team {self._id}: {len(responses)} responses")
        return responses

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary.

        Returns:
            Dictionary with status information
        """
        status = {
            "id": self._id,
            "name": self._name,
            "created_at": self._created_at,
            "uptime": time.time() - self._created_at,
            "member_count": len(self._members),
            "has_manager": self._manager is not None,
        }

        if self._manager:
            status["manager"] = {
                "id": self._manager.id,
                "name": self._manager.name,
            }

        status["members"] = [
            {
                "id": agent.id,
                "name": agent.name,
                "role": self._member_roles.get(agent.id, "member"),
            }
            for agent in self._members.values()
        ]

        return status
