"""
Team protocols and type definitions for Enterprise AI.

This module defines the core protocols and type definitions for the team
management system, enabling team structure and coordination.
"""

from abc import abstractmethod
from typing import Any, Dict, List, Optional, Protocol, Set, Union

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus


class TeamProtocol(Protocol):
    """Protocol defining team capabilities."""

    @property
    def id(self) -> str:
        """Get team ID."""
        ...

    @property
    def name(self) -> str:
        """Get team name."""
        ...

    @property
    def manager(self) -> AgentProtocol:
        """Get team manager agent."""
        ...

    @manager.setter
    def manager(self, agent: AgentProtocol) -> None:
        """Set team manager."""
        ...

    @property
    def members(self) -> Dict[str, AgentProtocol]:
        """Get team members (excluding manager)."""
        ...

    def add_member(self, agent: AgentProtocol, role: Optional[str] = None) -> bool:
        """Add a member to the team with an optional role."""
        ...

    def remove_member(self, agent_id: str) -> bool:
        """Remove a member from the team."""
        ...

    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID."""
        ...

    def assign_task(self, task: Task, agent_id: Optional[str] = None) -> bool:
        """Assign a task to a team member or let manager decide."""
        ...

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message sent to the team."""
        ...

    def broadcast_message(
        self, message_type: str, content: str, sender_id: str
    ) -> List[AgentMessage]:
        """Broadcast a message to all team members."""
        ...

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary."""
        ...


class TeamMemberRole(Protocol):
    """Protocol for team member roles."""

    @property
    def team_id(self) -> str:
        """Get the associated team ID."""
        ...

    @property
    def position(self) -> str:
        """Get the position in the team (e.g., manager, lead, member)."""
        ...

    @property
    def responsibilities(self) -> List[str]:
        """Get the responsibilities associated with this role."""
        ...
