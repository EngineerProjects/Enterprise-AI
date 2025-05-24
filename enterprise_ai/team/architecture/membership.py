"""
Team membership management for Enterprise AI.

This module provides functionality for managing team membership,
including adding, removing, and querying team members.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.team.core.types import TeamMemberRole, TeamProtocol

logger = get_logger("team.architecture.membership")


class MembershipManager:
    """Team membership manager.
    
    This component handles all aspects of team membership, including:
    - Adding and removing members
    - Tracking member roles and relationships
    - Managing the team manager
    - Providing queries for membership information
    - Enforcing membership rules and constraints
    """
    
    def __init__(self, team: "TeamProtocol", max_members: Optional[int] = None):
        """Initialize the membership manager.
        
        Args:
            team: Team that this manager belongs to
            max_members: Optional maximum number of team members
        """
        self._team = team
        self._max_members = max_members
        self._members: Dict[str, AgentProtocol] = {}
        self._member_roles: Dict[str, TeamMemberRole] = {}
        self._manager_id: Optional[str] = None
        self._relationships: Dict[str, Dict[str, str]] = {}  # Hierarchical relationships
        
        logger.info(f"Initialized membership manager for team {team.id}")
    
    @property
    def max_members(self) -> Optional[int]:
        """Get the maximum number of team members.
        
        Returns:
            Maximum number of members, or None if no limit
        """
        return self._max_members
    
    @property
    def count(self) -> int:
        """Get the number of team members.
        
        Returns:
            Number of team members
        """
        return len(self._members)
    
    @property
    def manager(self) -> Optional[AgentProtocol]:
        """Get the team manager agent.
        
        Returns:
            Manager agent or None if not set
        """
        if self._manager_id and self._manager_id in self._members:
            return self._members[self._manager_id]
        return None
    
    def add_member(self, agent: AgentProtocol, role: Union[TeamMemberRole, str, None] = None) -> bool:
        """Add an agent to the team.
        
        Args:
            agent: Agent to add
            role: Optional role for the agent
            
        Returns:
            True if agent was added successfully, False otherwise
        """
        if agent.id in self._members:
            logger.warning(f"Agent {agent.id} is already a member of team {self._team.id}")
            return False
        
        # Check member limit if set
        if self._max_members is not None and len(self._members) >= self._max_members:
            logger.warning(f"Cannot add agent {agent.id}: team {self._team.id} has reached maximum members ({self._max_members})")
            return False
        
        # Add to members dictionary
        self._members[agent.id] = agent
        
        # Resolve role
        resolved_role = self._resolve_role(role)
        self._member_roles[agent.id] = resolved_role
        
        # If this is a manager role and no manager exists, set as team manager
        if resolved_role == TeamMemberRole.MANAGER and self._manager_id is None:
            self._manager_id = agent.id
            logger.info(f"Set agent {agent.id} as manager for team {self._team.id}")
        
        logger.info(f"Added agent {agent.id} to team {self._team.id} with role {resolved_role.name}")
        return True
    
    def remove_member(self, agent_id: str) -> bool:
        """Remove an agent from the team.
        
        Args:
            agent_id: ID of the agent to remove
            
        Returns:
            True if agent was removed successfully, False otherwise
        """
        if agent_id not in self._members:
            logger.warning(f"Agent {agent_id} is not a member of team {self._team.id}")
            return False
        
        # Check if this is the manager
        if agent_id == self._manager_id:
            self._manager_id = None
            logger.info(f"Removed manager {agent_id} from team {self._team.id}")
        
        # Remove from members and roles dictionaries
        del self._members[agent_id]
        
        if agent_id in self._member_roles:
            del self._member_roles[agent_id]
        
        # Remove relationships
        if agent_id in self._relationships:
            del self._relationships[agent_id]
        
        # Remove as reporter in other relationships
        for member_id in list(self._relationships.keys()):
            reports = self._relationships.get(member_id, {})
            if agent_id in reports:
                del self._relationships[member_id][agent_id]
        
        logger.info(f"Removed agent {agent_id} from team {self._team.id}")
        return True
    
    def get_members(self) -> List[AgentProtocol]:
        """Get all team members.
        
        Returns:
            List of all agents in the team
        """
        return list(self._members.values())
    
    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID.
        
        Args:
            agent_id: ID of the agent to retrieve
            
        Returns:
            Agent with the specified ID, or None if not found
        """
        return self._members.get(agent_id)
    
    def get_members_by_role(self, role: Union[TeamMemberRole, str]) -> List[AgentProtocol]:
        """Get team members with a specific role.
        
        Args:
            role: Role to filter by
            
        Returns:
            List of agents with the specified role
        """
        resolved_role = self._resolve_role(role)
        
        return [
            self._members[agent_id]
            for agent_id, member_role in self._member_roles.items()
            if member_role == resolved_role
        ]
    
    def get_role(self, agent_id: str) -> Optional[TeamMemberRole]:
        """Get the role of a team member.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Role of the agent, or None if not a member
        """
        return self._member_roles.get(agent_id)
    
    def set_role(self, agent_id: str, role: Union[TeamMemberRole, str]) -> bool:
        """Change the role of a team member.
        
        Args:
            agent_id: ID of the agent
            role: New role to assign
            
        Returns:
            True if role was changed successfully, False otherwise
        """
        if agent_id not in self._members:
            logger.warning(f"Cannot set role: agent {agent_id} is not a member of team {self._team.id}")
            return False
        
        resolved_role = self._resolve_role(role)
        old_role = self._member_roles.get(agent_id)
        
        # Update role
        self._member_roles[agent_id] = resolved_role
        
        # Handle manager role changes
        if resolved_role == TeamMemberRole.MANAGER and self._manager_id != agent_id:
            # If there was a previous manager, demote them
            if self._manager_id:
                old_manager_id = self._manager_id
                self._member_roles[old_manager_id] = TeamMemberRole.MEMBER
                logger.info(f"Demoted previous manager {old_manager_id} to member")
            
            # Set new manager
            self._manager_id = agent_id
            logger.info(f"Promoted agent {agent_id} to manager for team {self._team.id}")
        
        # If this was the manager and now isn't, update manager reference
        if agent_id == self._manager_id and resolved_role != TeamMemberRole.MANAGER:
            self._manager_id = None
            logger.info(f"Removed agent {agent_id} as manager for team {self._team.id}")
        
        logger.info(f"Changed role of agent {agent_id} from {old_role} to {resolved_role.name}")
        return True
    
    def set_manager(self, agent_id: str) -> bool:
        """Set an agent as the team manager.
        
        Args:
            agent_id: ID of the agent to make manager
            
        Returns:
            True if manager was set successfully, False otherwise
        """
        return self.set_role(agent_id, TeamMemberRole.MANAGER)
    
    def add_reporting_relationship(self, agent_id: str, reports_to_id: str, relationship_type: str = "reports_to") -> bool:
        """Add a reporting relationship between team members.
        
        Args:
            agent_id: ID of the agent (reporter)
            reports_to_id: ID of the agent they report to (manager)
            relationship_type: Type of relationship
            
        Returns:
            True if relationship was added successfully, False otherwise
        """
        if agent_id not in self._members:
            logger.warning(f"Cannot add relationship: agent {agent_id} is not a member of team {self._team.id}")
            return False
        
        if reports_to_id not in self._members:
            logger.warning(f"Cannot add relationship: agent {reports_to_id} is not a member of team {self._team.id}")
            return False
        
        # Initialize relationship dictionary if needed
        if agent_id not in self._relationships:
            self._relationships[agent_id] = {}
        
        # Set relationship
        self._relationships[agent_id][reports_to_id] = relationship_type
        
        logger.info(f"Added relationship: {agent_id} {relationship_type} {reports_to_id}")
        return True
    
    def remove_reporting_relationship(self, agent_id: str, reports_to_id: str) -> bool:
        """Remove a reporting relationship between team members.
        
        Args:
            agent_id: ID of the agent (reporter)
            reports_to_id: ID of the agent they reported to (manager)
            
        Returns:
            True if relationship was removed successfully, False otherwise
        """
        if agent_id not in self._relationships:
            logger.warning(f"No relationships found for agent {agent_id}")
            return False
        
        if reports_to_id not in self._relationships[agent_id]:
            logger.warning(f"No relationship found between {agent_id} and {reports_to_id}")
            return False
        
        # Remove the relationship
        del self._relationships[agent_id][reports_to_id]
        
        # Clean up empty relationship dictionaries
        if not self._relationships[agent_id]:
            del self._relationships[agent_id]
        
        logger.info(f"Removed relationship between {agent_id} and {reports_to_id}")
        return True
    
    def get_direct_reports(self, agent_id: str) -> List[AgentProtocol]:
        """Get agents that directly report to the specified agent.
        
        Args:
            agent_id: ID of the agent (manager)
            
        Returns:
            List of agents that report to the specified agent
        """
        direct_reports = []
        
        for reporter_id, relationships in self._relationships.items():
            for target_id, rel_type in relationships.items():
                if target_id == agent_id and rel_type == "reports_to":
                    direct_reports.append(self._members[reporter_id])
        
        return direct_reports
    
    def get_manager_of(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get the manager of the specified agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Manager agent or None if not found
        """
        if agent_id not in self._relationships:
            return None
        
        for target_id, rel_type in self._relationships[agent_id].items():
            if rel_type == "reports_to":
                return self._members.get(target_id)
        
        return None
    
    def is_member(self, agent_id: str) -> bool:
        """Check if an agent is a member of the team.
        
        Args:
            agent_id: ID of the agent to check
            
        Returns:
            True if the agent is a member, False otherwise
        """
        return agent_id in self._members
    
    def _resolve_role(self, role: Union[TeamMemberRole, str, None]) -> TeamMemberRole:
        """Resolve a role from various input types.
        
        Args:
            role: Role to resolve (enum, string, or None)
            
        Returns:
            Resolved TeamMemberRole enum value
        """
        if role is None:
            return TeamMemberRole.MEMBER
        
        if isinstance(role, TeamMemberRole):
            return role
        
        # Convert string to enum
        try:
            if role.upper() in [r.name for r in TeamMemberRole]:
                return TeamMemberRole[role.upper()]
        except (AttributeError, KeyError):
            logger.warning(f"Invalid role string: {role}, defaulting to MEMBER")
        
        return TeamMemberRole.MEMBER
