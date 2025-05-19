"""
Management roles for team collaboration in Enterprise AI.

This module provides specialized manager role implementations for 
different team collaboration patterns.
"""

from typing import Any, Dict, List, Optional, Union

from enterprise_ai.agent.role.role import BaseAgentRole
from enterprise_ai.logger import get_logger
from enterprise_ai.team.roles.base import TeamManagerRole, TemplatedTeamRole

logger = get_logger("team.roles.manager")


class HierarchicalManagerRole(TeamManagerRole):
    """Manager role for hierarchical teams.
    
    This role specializes in top-down management, decision-making,
    and task delegation within a hierarchical team structure.
    """
    
    def __init__(
        self,
        decision_style: str = "delegative",
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ):
        """Initialize hierarchical manager role.
        
        Args:
            decision_style: Management style ("autocratic", "delegative", "consultative")
            additional_context: Additional context for instructions
            template_vars: Optional additional template variables
        """
        # Prepare template variables
        vars_dict = template_vars or {}
        vars_dict["decision_style"] = decision_style
        
        # Get appropriate instruction set based on decision style
        style_context = f"You are a {decision_style} manager in a hierarchical team. "
        
        if decision_style == "autocratic":
            style_context += ("You make decisions directly and give clear instructions. "
                             "Focus on efficiency and clear direction.")
        elif decision_style == "consultative":
            style_context += ("You gather input from team members before making decisions. "
                             "Focus on team buy-in while maintaining leadership.")
        else:  # delegative
            style_context += ("You delegate decisions and responsibilities to appropriate specialists. "
                             "Focus on empowerment while maintaining accountability.")
        
        full_context = style_context + "\n" + additional_context
        
        # Initialize parent class with enhanced context
        super().__init__(
            additional_context=full_context,
            template_vars=vars_dict,
        )
        
        # Add role-specific responsibilities
        self.add_team_responsibility("Make strategic decisions for the team")
        self.add_team_responsibility("Delegate tasks to appropriate specialists")
        self.add_team_responsibility("Provide clear instructions and expectations")
        self.add_team_responsibility("Review and approve team member work")
        self.add_team_responsibility("Manage deadlines and resource allocation")
        
        # Set higher coordination level for hierarchical managers
        self._coordination_level = 9
    
    @property
    def decision_style(self) -> str:
        """Get the manager's decision-making style.
        
        Returns:
            Decision style string
        """
        return self._template_vars.get("decision_style", "delegative")


class PeerCoordinatorRole(TeamManagerRole):
    """Coordinator role for peer teams.
    
    This role specializes in facilitating collaboration, consensus-building,
    and coordination within a flat, peer-to-peer team structure.
    """
    
    def __init__(
        self,
        facilitation_style: str = "collaborative",
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ):
        """Initialize peer coordinator role.
        
        Args:
            facilitation_style: Coordination style ("collaborative", "supportive", "process-focused")
            additional_context: Additional context for instructions
            template_vars: Optional additional template variables
        """
        # Prepare template variables
        vars_dict = template_vars or {}
        vars_dict["facilitation_style"] = facilitation_style
        
        # Get appropriate instruction set based on facilitation style
        style_context = f"You are a {facilitation_style} coordinator in a peer team. "
        
        if facilitation_style == "supportive":
            style_context += ("You provide resources and remove obstacles. "
                             "Focus on supporting team members in their self-directed work.")
        elif facilitation_style == "process-focused":
            style_context += ("You maintain team processes and workflow. "
                             "Focus on structure while respecting peer decision-making.")
        else:  # collaborative
            style_context += ("You facilitate discussions and build consensus. "
                             "Focus on shared understanding and inclusive participation.")
        
        full_context = style_context + "\n" + additional_context
        
        # Initialize parent class with enhanced context
        super().__init__(
            additional_context=full_context,
            template_vars=vars_dict,
        )
        
        # Add role-specific responsibilities
        self.add_team_responsibility("Facilitate team discussions and decision-making")
        self.add_team_responsibility("Build consensus among team members")
        self.add_team_responsibility("Ensure all perspectives are heard and considered")
        self.add_team_responsibility("Track team decisions and action items")
        self.add_team_responsibility("Support team self-organization")
        
        # Set moderate coordination level for peer coordinators
        self._coordination_level = 7
        
        # Use different name for this role
        self._name = "Team Coordinator"
    
    @property
    def facilitation_style(self) -> str:
        """Get the coordinator's facilitation style.
        
        Returns:
            Facilitation style string
        """
        return self._template_vars.get("facilitation_style", "collaborative")
