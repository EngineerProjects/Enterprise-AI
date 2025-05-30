"""
Specialist roles for team collaboration in Enterprise AI.

This module provides specialized role implementations for different
types of team specialists based on collaboration patterns.
"""

from typing import Any, Dict, List, Optional, Union

from enterprise_ai.agent.role.role import BaseAgentRole
from enterprise_ai.logger import get_logger
from enterprise_ai.team.roles.base import TeamSpecialistRole, TemplatedTeamRole

logger = get_logger("team.roles.specialist")


class HierarchicalSpecialistRole(TeamSpecialistRole):
    """Specialist role for hierarchical teams.
    
    This role specializes in a specific domain while operating
    within a hierarchical reporting structure.
    """
    
    def __init__(
        self,
        specialty: str,
        autonomy_level: str = "moderate",
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ):
        """Initialize hierarchical specialist role.
        
        Args:
            specialty: Specific domain or skill area
            autonomy_level: Level of autonomy ("low", "moderate", "high")
            additional_context: Additional context for instructions
            template_vars: Optional additional template variables
        """
        # Prepare template variables
        vars_dict = template_vars or {}
        vars_dict["autonomy_level"] = autonomy_level
        
        # Get appropriate instruction set based on autonomy level
        style_context = f"You are a {specialty} specialist with {autonomy_level} autonomy in a hierarchical team. "
        
        if autonomy_level == "low":
            style_context += ("You follow detailed instructions from your manager. "
                             "Focus on precise execution of assigned tasks.")
        elif autonomy_level == "high":
            style_context += ("You have significant independence within your area of expertise. "
                             "Focus on proactive problem-solving while keeping manager informed.")
        else:  # moderate
            style_context += ("You have autonomy within defined parameters. "
                             "Focus on execution with regular check-ins with your manager.")
        
        full_context = style_context + "\n" + additional_context
        
        # Initialize parent class with enhanced context
        super().__init__(
            specialty=specialty,
            additional_context=full_context,
            template_vars=vars_dict,
        )
        
        # Add role-specific responsibilities
        self.add_team_responsibility(f"Execute tasks within your {specialty} expertise")
        self.add_team_responsibility("Provide regular status updates to your manager")
        self.add_team_responsibility("Escalate issues that require manager decision")
        self.add_team_responsibility("Collaborate with other specialists as directed")
        
        # Set coordination level based on autonomy
        if autonomy_level == "low":
            self._coordination_level = 2
        elif autonomy_level == "high":
            self._coordination_level = 5
        else:  # moderate
            self._coordination_level = 3
    
    @property
    def autonomy_level(self) -> str:
        """Get the specialist's autonomy level.
        
        Returns:
            Autonomy level string
        """
        return self._template_vars.get("autonomy_level", "moderate")


class PeerSpecialistRole(TeamSpecialistRole):
    """Specialist role for peer teams.
    
    This role specializes in a specific domain while operating
    within a flat, peer-to-peer team structure.
    """
    
    def __init__(
        self,
        specialty: str,
        collaboration_style: str = "integrative",
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ):
        """Initialize peer specialist role.
        
        Args:
            specialty: Specific domain or skill area
            collaboration_style: Collaboration approach ("integrative", "advisory", "contributory")
            additional_context: Additional context for instructions
            template_vars: Optional additional template variables
        """
        # Prepare template variables
        vars_dict = template_vars or {}
        vars_dict["collaboration_style"] = collaboration_style
        
        # Get appropriate instruction set based on collaboration style
        style_context = f"You are a {specialty} specialist with an {collaboration_style} style in a peer team. "
        
        if collaboration_style == "advisory":
            style_context += ("You primarily provide expertise and guidance. "
                             "Focus on sharing knowledge while respecting team decisions.")
        elif collaboration_style == "contributory":
            style_context += ("You focus on executing your specialized tasks. "
                             "Focus on delivery excellence within your domain.")
        else:  # integrative
            style_context += ("You actively integrate your work with other team members. "
                             "Focus on cross-functional collaboration and mutual support.")
        
        full_context = style_context + "\n" + additional_context
        
        # Initialize parent class with enhanced context
        super().__init__(
            specialty=specialty,
            additional_context=full_context,
            template_vars=vars_dict,
        )
        
        # Add role-specific responsibilities
        self.add_team_responsibility(f"Contribute {specialty} expertise to team objectives")
        self.add_team_responsibility("Participate in consensus-building and decisions")
        self.add_team_responsibility("Engage in knowledge sharing across specialties")
        self.add_team_responsibility("Support other team members with complementary skills")
        
        # Set coordination level based on collaboration style
        if collaboration_style == "advisory":
            self._coordination_level = 3
        elif collaboration_style == "contributory":
            self._coordination_level = 2
        else:  # integrative
            self._coordination_level = 5
    
    @property
    def collaboration_style(self) -> str:
        """Get the specialist's collaboration style.
        
        Returns:
            Collaboration style string
        """
        return self._template_vars.get("collaboration_style", "integrative")
