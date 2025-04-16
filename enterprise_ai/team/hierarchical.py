"""
Hierarchical team implementation for Enterprise AI.

This module provides a hierarchical team class that extends BaseTeam
with support for nested subteams, creating organizational structures.
"""

import time
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.message import BroadcastMessage, ErrorMessage, create_message
from enterprise_ai.logger import get_logger
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.types import TeamProtocol

logger = get_logger("team.hierarchical")


class HierarchicalTeam(BaseTeam):
    """Hierarchical team with support for nested subteams.

    This class extends BaseTeam to support organizational hierarchies
    with teams containing other teams, enabling complex organizational
    structures with delegation across multiple levels.
    """

    def __init__(
        self,
        team_id: Optional[str] = None,
        name: str = "Hierarchical Team",
        manager: Optional[AgentProtocol] = None,
    ) -> None:
        """Initialize a hierarchical team.

        Args:
            team_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            manager: Team manager agent
        """
        super().__init__(team_id, name, manager)
        self._subteams: Dict[str, TeamProtocol] = {}
        logger.info(f"Initialized hierarchical team: {self._id} ({self._name})")

    @property
    def subteams(self) -> Dict[str, TeamProtocol]:
        """Get subteams.

        Returns:
            Dictionary of subteams
        """
        return self._subteams.copy()

    def add_subteam(self, team: TeamProtocol) -> bool:
        """Add a subteam to the team.

        Args:
            team: Team to add as subteam

        Returns:
            True if team was added, False if already a subteam
        """
        if team.id in self._subteams:
            logger.warning(f"Team {team.id} is already a subteam of {self._id}")
            return False

        self._subteams[team.id] = team
        logger.info(f"Added team {team.id} ({team.name}) as subteam of {self._id}")
        return True

    def remove_subteam(self, team_id: str) -> bool:
        """Remove a subteam from the team.

        Args:
            team_id: ID of team to remove

        Returns:
            True if team was removed, False if not a subteam
        """
        if team_id not in self._subteams:
            logger.warning(f"Team {team_id} is not a subteam of {self._id}")
            return False

        del self._subteams[team_id]
        logger.info(f"Removed team {team_id} from subteams of {self._id}")
        return True

    def get_subteam(self, team_id: str) -> Optional[TeamProtocol]:
        """Get a subteam by ID.

        Args:
            team_id: ID of the team to get

        Returns:
            Team or None if not found
        """
        return self._subteams.get(team_id)

    def get_all_members(self) -> Dict[str, AgentProtocol]:
        """Get all members including those in subteams.

        Returns:
            Dictionary of all members
        """
        all_members = super().members.copy()

        # Add members from subteams with prefixed keys
        for team_id, team in self._subteams.items():
            team_members = team.members
            # Prefix the agent IDs to avoid collisions
            for agent_id, agent in team_members.items():
                prefixed_id = f"{team_id}.{agent_id}"
                all_members[prefixed_id] = agent

        return all_members

    def assign_task(
        self, task: Task, agent_id: Optional[str] = None, team_id: Optional[str] = None
    ) -> bool:
        """Assign a task to a team member, subteam, or let manager decide.

        Args:
            task: Task to assign
            agent_id: Optional ID of agent to assign task to
            team_id: Optional ID of subteam to assign task to

        Returns:
            True if task was assigned, False otherwise
        """
        # Case 1: Assign to a subteam
        if team_id:
            if team_id not in self._subteams:
                logger.warning(f"Subteam {team_id} not found in team {self._id}")
                return False

            success = self._subteams[team_id].assign_task(task)
            if success:
                logger.info(f"Assigned task {task.id} to subteam {team_id} in team {self._id}")
            return success

        # Case 2: Assign to a member of this team
        if agent_id:
            return super().assign_task(task, agent_id)

        # Case 3: Let manager decide
        return super().assign_task(task)

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message sent to the team.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Extract metadata
        metadata = getattr(message, "metadata", {}) or {}

        # Check if message targets a specific subteam
        target_team_id = metadata.get("target_team")
        if target_team_id and target_team_id in self._subteams:
            logger.debug(f"Routing message to subteam {target_team_id}")
            return self._subteams[target_team_id].process_message(message)

        return super().process_message(message)

    def broadcast_message(
        self, message_type: str, content: str, sender_id: str, include_subteams: bool = True
    ) -> List[AgentMessage]:
        """Broadcast a message to all team members and optionally subteams.

        Args:
            message_type: Type of message
            content: Message content
            sender_id: ID of sender
            include_subteams: Whether to include subteams in broadcast

        Returns:
            List of response messages
        """
        responses = super().broadcast_message(message_type, content, sender_id)

        # Broadcast to subteams if requested
        if include_subteams:
            for team_id, team in self._subteams.items():
                # Create subteam-specific broadcast metadata
                subteam_responses = team.broadcast_message(message_type, content, sender_id)
                responses.extend(subteam_responses)

        return responses

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary including subteams.

        Returns:
            Dictionary with status information
        """
        status = super().get_status()

        # Add subteam information
        status["subteams"] = [
            {
                "id": team.id,
                "name": team.name,
                "member_count": len(team.members),
            }
            for team in self._subteams.values()
        ]

        return status
