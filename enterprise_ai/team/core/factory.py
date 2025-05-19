"""
Factory functions for creating teams in Enterprise AI.

This module provides factory functions and builders for creating
different types of team implementations.
"""

from typing import Any, Dict, List, Optional, Union

from enterprise_ai.agent.architecture.utils import generate_id
from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.logger import get_logger
from enterprise_ai.team.core.base import BaseTeam
from enterprise_ai.team.core.types import TeamMemberRole

logger = get_logger("team.core.factory")

# Import collaboration patterns
try:
    from enterprise_ai.team.collaboration.hierarchical import HierarchicalTeam, DecisionMode
    from enterprise_ai.team.collaboration.peer import PeerTeam, ConsensusMode
    from enterprise_ai.team.roles.manager import HierarchicalManagerRole, PeerCoordinatorRole
    from enterprise_ai.team.roles.specialist import HierarchicalSpecialistRole, PeerSpecialistRole
    COLLABORATION_PATTERNS_AVAILABLE = True
except ImportError:
    logger.warning("Collaboration patterns not available. Using BaseTeam fallback.")
    COLLABORATION_PATTERNS_AVAILABLE = False


def create_team(
    team_type: str = "base",
    team_id: Optional[str] = None,
    name: Optional[str] = None,
    manager_agent: Optional[AgentProtocol] = None,
    members: Optional[List[AgentProtocol]] = None,
    **kwargs: Any
) -> BaseTeam:
    """Create a team by type.
    
    Args:
        team_type: Type of team to create ("base", "hierarchical", "peer")
        team_id: Optional unique identifier
        name: Optional human-readable name
        manager_agent: Optional manager agent for hierarchical teams
        members: Optional list of member agents to add
        **kwargs: Additional team-specific parameters
        
    Returns:
        Team implementation
        
    Raises:
        ValueError: If an unknown team type is specified
    """
    # Normalize team type
    team_type = team_type.lower()
    
    # Generate ID if not provided
    if team_id is None:
        team_id = generate_id("team-")
    
    # Generate name if not provided
    if name is None:
        name = f"Team-{team_id[-4:]}"
    
    # Create appropriate team type
    if team_type == "base" or not COLLABORATION_PATTERNS_AVAILABLE:
        team = BaseTeam(team_id=team_id, name=name, **kwargs)
    elif team_type == "hierarchical":
        if not COLLABORATION_PATTERNS_AVAILABLE:
            logger.warning("Hierarchical team not available. Using BaseTeam fallback.")
            team = BaseTeam(team_id=team_id, name=name, **kwargs)
        else:
            # Extract hierarchical-specific parameters
            decision_mode = kwargs.pop("decision_mode", DecisionMode.MANAGER_DELEGATED)
            
            team = HierarchicalTeam(
                team_id=team_id,
                name=name,
                decision_mode=decision_mode,
                **kwargs
            )
    elif team_type == "peer":
        if not COLLABORATION_PATTERNS_AVAILABLE:
            logger.warning("Peer team not available. Using BaseTeam fallback.")
            team = BaseTeam(team_id=team_id, name=name, **kwargs)
        else:
            # Extract peer-specific parameters
            consensus_mode = kwargs.pop("consensus_mode", ConsensusMode.MAJORITY)
            consensus_threshold = kwargs.pop("consensus_threshold", 0.51)
            quorum_size = kwargs.pop("quorum_size", 2)
            
            team = PeerTeam(
                team_id=team_id,
                name=name,
                consensus_mode=consensus_mode,
                consensus_threshold=consensus_threshold,
                quorum_size=quorum_size,
                **kwargs
            )
    else:
        raise ValueError(f"Unknown team type: {team_type}")
    
    # Add manager if provided (for hierarchical teams)
    if manager_agent:
        if team_type == "hierarchical" and COLLABORATION_PATTERNS_AVAILABLE:
            # For hierarchical teams, use internal method to set manager
            team._set_manager(manager_agent)
        else:
            # For other team types, add as regular member with manager role
            team.add_member(manager_agent, TeamMemberRole.MANAGER)
    
    # Add members if provided
    if members:
        for agent in members:
            team.add_member(agent)
    
    logger.info(f"Created {team_type} team {team_id} ({name})")
    return team


class TeamBuilder:
    """Builder for creating and configuring teams.
    
    This class implements a fluent API for creating and configuring
    teams, making team creation more readable and maintainable.
    """
    
    def __init__(self, team_type: str = "base"):
        """Initialize team builder.
        
        Args:
            team_type: Type of team to create
        """
        self._team_type = team_type
        self._team_id = None
        self._name = None
        self._manager = None
        self._members = []
        self._kwargs = {}
    
    def with_id(self, team_id: str) -> "TeamBuilder":
        """Set team ID.
        
        Args:
            team_id: Team ID to use
            
        Returns:
            Updated builder instance
        """
        self._team_id = team_id
        return self
    
    def with_name(self, name: str) -> "TeamBuilder":
        """Set team name.
        
        Args:
            name: Team name to use
            
        Returns:
            Updated builder instance
        """
        self._name = name
        return self
    
    def with_manager(self, manager: AgentProtocol) -> "TeamBuilder":
        """Set team manager.
        
        Args:
            manager: Manager agent
            
        Returns:
            Updated builder instance
        """
        self._manager = manager
        return self
    
    def with_member(self, member: AgentProtocol) -> "TeamBuilder":
        """Add team member.
        
        Args:
            member: Member agent to add
            
        Returns:
            Updated builder instance
        """
        self._members.append(member)
        return self
    
    def with_members(self, members: List[AgentProtocol]) -> "TeamBuilder":
        """Add multiple team members.
        
        Args:
            members: List of member agents to add
            
        Returns:
            Updated builder instance
        """
        self._members.extend(members)
        return self
    
    def with_option(self, key: str, value: Any) -> "TeamBuilder":
        """Set additional option.
        
        Args:
            key: Option key
            value: Option value
            
        Returns:
            Updated builder instance
        """
        self._kwargs[key] = value
        return self
    
    def build(self) -> BaseTeam:
        """Build the team.
        
        Returns:
            Configured team instance
        """
        return create_team(
            team_type=self._team_type,
            team_id=self._team_id,
            name=self._name,
            manager_agent=self._manager,
            members=self._members,
            **self._kwargs
        )


# Convenience factory functions for specific team types

def create_hierarchical_team(
    name: Optional[str] = None,
    manager_agent: Optional[AgentProtocol] = None,
    decision_mode: Any = None,  # Can be string or DecisionMode enum
    manager_decision_style: str = "delegative",
    specialist_autonomy_level: str = "moderate",
    **kwargs: Any
) -> BaseTeam:
    """Create a hierarchical team.
    
    Args:
        name: Optional team name
        manager_agent: Optional manager agent
        decision_mode: Optional decision mode
        manager_decision_style: Decision style for the manager
        specialist_autonomy_level: Autonomy level for specialists
        **kwargs: Additional team parameters
        
    Returns:
        Hierarchical team instance
    """
    if decision_mode:
        kwargs["decision_mode"] = decision_mode
    
    team = create_team(
        team_type="hierarchical",
        name=name,
        **kwargs
    )
    
    # If collaboration patterns are available, set up with specialized roles
    if COLLABORATION_PATTERNS_AVAILABLE and isinstance(team, HierarchicalTeam):
        # Add manager if provided
        if manager_agent:
            # Create specialized manager role
            manager_role = HierarchicalManagerRole(
                decision_style=manager_decision_style
            )
            
            # Add manager with role
            team._set_manager(manager_agent)
            
        # Store specialist settings for when members are added
        team._specialist_autonomy_level = specialist_autonomy_level
    
    return team


def create_peer_team(
    name: Optional[str] = None,
    consensus_mode: Any = None,  # Can be string or ConsensusMode enum
    consensus_threshold: Optional[float] = None,
    quorum_size: Optional[int] = None,
    coordinator_agent: Optional[AgentProtocol] = None,
    facilitation_style: str = "collaborative",
    collaboration_style: str = "integrative",
    **kwargs: Any
) -> BaseTeam:
    """Create a peer team.
    
    Args:
        name: Optional team name
        consensus_mode: Optional consensus mode
        consensus_threshold: Optional consensus threshold
        quorum_size: Optional quorum size
        coordinator_agent: Optional coordinator agent
        facilitation_style: Facilitation style for coordinator
        collaboration_style: Collaboration style for specialists
        **kwargs: Additional team parameters
        
    Returns:
        Peer team instance
    """
    if consensus_mode:
        kwargs["consensus_mode"] = consensus_mode
    
    if consensus_threshold is not None:
        kwargs["consensus_threshold"] = consensus_threshold
    
    if quorum_size is not None:
        kwargs["quorum_size"] = quorum_size
    
    team = create_team(
        team_type="peer",
        name=name,
        **kwargs
    )
    
    # If collaboration patterns are available, set up with specialized roles
    if COLLABORATION_PATTERNS_AVAILABLE and isinstance(team, PeerTeam):
        # Add coordinator if provided
        if coordinator_agent:
            # Create specialized coordinator role
            coordinator_role = PeerCoordinatorRole(
                facilitation_style=facilitation_style
            )
            
            # Add coordinator
            team.add_member(coordinator_agent, "COORDINATOR")
            
        # Store specialist settings for when members are added
        team._collaboration_style = collaboration_style
    
    return team
