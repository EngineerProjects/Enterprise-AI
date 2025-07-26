"""
Team membership management.

Handles team member lifecycle and capacity management.
"""

from typing import Dict, List, Optional, Set
from enterprise_ai.agent import Agent
from enterprise_ai.team.core import TeamRole, TeamMetrics, TeamMember
from enterprise_ai.team.roles.base import BaseTeamRole
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.membership")


class MembershipManager:
    """Manages team membership and capacity."""
    
    def __init__(self):
        self.members: Dict[str, TeamMember] = {}
        self.role_assignments: Dict[TeamRole, Set[str]] = {role: set() for role in TeamRole}
        
    def register_member(self, agent: Agent, role: BaseTeamRole) -> str:
        """Register new team member."""
        agent_name = self._get_agent_name(agent)
        
        if agent_name in self.members:
            logger.warning(f"Agent '{agent_name}' already registered, updating role")
            
        self.members[agent_name] = role
        self.role_assignments[role.role].add(agent_name)
        
        logger.info(f"Registered '{agent_name}' as {role.role.value}")
        return agent_name
    
    def unregister_member(self, agent_name: str) -> Optional[TeamMember]:
        """Unregister team member."""
        if agent_name not in self.members:
            return None
            
        member = self.members.pop(agent_name)
        self.role_assignments[member.role].discard(agent_name)
        
        logger.info(f"Unregistered '{agent_name}'")
        return member
    
    def get_member(self, agent_name: str) -> Optional[TeamMember]:
        """Get team member by name."""
        return self.members.get(agent_name)
    
    def get_members_by_role(self, role: TeamRole) -> List[TeamMember]:
        """Get all members with specific role."""
        agent_names = self.role_assignments[role]
        return [self.members[name] for name in agent_names if name in self.members]
    
    def get_available_members(self) -> List[TeamMember]:
        """Get members with available capacity."""
        return [member for member in self.members.values() if member.is_available]
    
    def calculate_team_capacity(self) -> float:
        """Calculate total team capacity utilization."""
        if not self.members:
            return 0.0
            
        total_capacity = sum(member.capacity for member in self.members.values())
        total_load = sum(member.current_load for member in self.members.values())
        
        return total_load / total_capacity if total_capacity > 0 else 0.0
    
    def get_team_metrics(self) -> TeamMetrics:
        """Get current team metrics."""
        available_members = self.get_available_members()
        
        return TeamMetrics(
            active_agents=len(available_members),
            task_completion_rate=self.calculate_team_capacity()
        )
    
    def _get_agent_name(self, agent: Agent) -> str:
        """Extract agent name consistently."""
        if hasattr(agent, 'profile') and agent.profile and hasattr(agent.profile, 'name'):
            return agent.profile.name
        if hasattr(agent, 'name'):
            return agent.name
        return agent.__class__.__name__.lower()
