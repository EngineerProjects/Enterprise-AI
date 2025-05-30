"""
Team role implementations for Enterprise AI.

This module extends the agent role system to provide team-specific
roles with team coordination capabilities.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.role.role import BaseAgentRole, SimpleRole, TemplatedRole
from enterprise_ai.logger import get_logger

logger = get_logger("team.roles.base")


class BaseTeamRole(BaseAgentRole):
    """Base class for team roles extending agent roles.
    
    This abstract class provides a foundation for implementing team roles
    with additional team coordination capabilities.
    """
    
    def __init__(
        self,
        *args: Any,
        coordination_level: int = 0,
        team_responsibilities: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with team-specific attributes.
        
        Args:
            *args: Arguments for the parent class
            coordination_level: Level of coordination capability (0-10)
            team_responsibilities: List of team-specific responsibilities
            **kwargs: Keyword arguments for the parent class
        """
        super().__init__(*args, **kwargs)
        self._coordination_level = coordination_level
        self._team_responsibilities = team_responsibilities or []
    
    @property
    def coordination_level(self) -> int:
        """Get the role's coordination capability level.
        
        Returns:
            Coordination level (0-10)
        """
        return self._coordination_level
    
    @property
    def team_responsibilities(self) -> List[str]:
        """Get the role's team-specific responsibilities.
        
        Returns:
            List of team responsibility descriptions
        """
        return self._team_responsibilities.copy()
    
    def add_team_responsibility(self, responsibility: str) -> None:
        """Add a team responsibility to the role.
        
        Args:
            responsibility: Team responsibility description
        """
        if responsibility not in self._team_responsibilities:
            self._team_responsibilities.append(responsibility)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary representation.
        
        Returns:
            Dictionary representation of the role
        """
        base_dict = super().to_dict()
        base_dict.update({
            "coordination_level": self._coordination_level,
            "team_responsibilities": self._team_responsibilities,
        })
        return base_dict


class SimpleTeamRole(SimpleRole, BaseTeamRole):
    """Simple implementation of team role with static values.
    
    This class extends SimpleRole and BaseTeamRole to provide a
    straightforward way to define team roles with static values.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        capabilities: Optional[List[str]] = None,
        instructions: str = "",
        coordination_level: int = 0,
        team_responsibilities: Optional[List[str]] = None,
    ) -> None:
        """Initialize a simple team role.
        
        Args:
            name: Role name
            description: Role description
            capabilities: Optional list of capability identifiers
            instructions: Role-specific instructions
            coordination_level: Level of coordination capability (0-10)
            team_responsibilities: List of team-specific responsibilities
        """
        SimpleRole.__init__(
            self,
            _name=name,
            _description=description,
            _capabilities=capabilities or [],
            _instructions=instructions,
        )
        BaseTeamRole.__init__(
            self,
            coordination_level=coordination_level,
            team_responsibilities=team_responsibilities,
        )


class TemplatedTeamRole(TemplatedRole, BaseTeamRole):
    """Template-based team role.
    
    This class implements a team role that uses a prompt template
    for generating instructions dynamically.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        template_id: str,
        capabilities: Optional[List[str]] = None,
        template_vars: Optional[Dict[str, Any]] = None,
        coordination_level: int = 0,
        team_responsibilities: Optional[List[str]] = None,
    ) -> None:
        """Initialize a templated team role.
        
        Args:
            name: Role name
            description: Role description
            template_id: Prompt template identifier
            capabilities: Optional list of capability identifiers
            template_vars: Optional variables for the template
            coordination_level: Level of coordination capability (0-10)
            team_responsibilities: List of team-specific responsibilities
        """
        TemplatedRole.__init__(
            self,
            name=name,
            description=description,
            template_id=template_id,
            capabilities=capabilities,
            template_vars=template_vars,
        )
        BaseTeamRole.__init__(
            self,
            coordination_level=coordination_level,
            team_responsibilities=team_responsibilities,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary representation.
        
        Returns:
            Dictionary representation of the role
        """
        base_dict = TemplatedRole.to_dict(self)
        team_dict = {
            "coordination_level": self._coordination_level,
            "team_responsibilities": self._team_responsibilities,
        }
        base_dict.update(team_dict)
        return base_dict


# Common team role implementations

class TeamManagerRole(TemplatedTeamRole):
    """Team manager role implementation.
    
    This role specializes in coordinating team members, facilitating
    communication, and ensuring team objectives are met.
    """
    
    def __init__(
        self,
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize team manager role.
        
        Args:
            additional_context: Additional context to include in instructions
            template_vars: Optional additional template variables
        """
        vars_dict = template_vars or {}
        vars_dict["additional_context"] = additional_context
        
        super().__init__(
            name="Team Manager",
            description="Coordinates team activities, facilitates communication, and ensures team objectives are met",
            template_id="team.roles.manager",  # This template should be created
            capabilities=[
                "team_coordination",
                "task_delegation",
                "progress_monitoring",
                "conflict_resolution",
            ],
            template_vars=vars_dict,
            coordination_level=8,
            team_responsibilities=[
                "Coordinate team activities",
                "Delegate tasks based on member capabilities",
                "Monitor team progress",
                "Resolve conflicts between team members",
                "Ensure team objectives are met",
            ],
        )
    
    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.
        
        Returns:
            List of required tool names
        """
        return ["task_manager", "communication", "performance_tracker"]


class TeamSpecialistRole(TemplatedTeamRole):
    """Team specialist role implementation.
    
    This role specializes in a specific domain or skill area, providing
    expertise to the team while participating in collaborative activities.
    """
    
    def __init__(
        self,
        specialty: str,
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize team specialist role.
        
        Args:
            specialty: Specific domain or skill area
            additional_context: Additional context to include in instructions
            template_vars: Optional additional template variables
        """
        vars_dict = template_vars or {}
        vars_dict["additional_context"] = additional_context
        vars_dict["specialty"] = specialty
        
        # Derive name from specialty
        name = f"{specialty.title()} Specialist"
        
        super().__init__(
            name=name,
            description=f"Provides expertise in {specialty} while collaborating with team members",
            template_id="team.roles.specialist",  # This template should be created
            capabilities=[
                "domain_expertise",
                "task_execution",
                "knowledge_sharing",
                "collaborative_problem_solving",
            ],
            template_vars=vars_dict,
            coordination_level=4,
            team_responsibilities=[
                f"Provide expertise in {specialty}",
                "Execute specialized tasks",
                "Share knowledge with team members",
                "Contribute to collaborative problem-solving",
                "Support team objectives",
            ],
        )
    
    @property
    def specialty(self) -> str:
        """Get the specialist's area of expertise.
        
        Returns:
            Specialty name
        """
        return self._template_vars.get("specialty", "")


class TeamCoordinatorRole(TemplatedTeamRole):
    """Team coordinator role implementation.
    
    This role specializes in facilitating team communication, tracking
    progress, and ensuring smooth collaboration between team members.
    """
    
    def __init__(
        self,
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize team coordinator role.
        
        Args:
            additional_context: Additional context to include in instructions
            template_vars: Optional additional template variables
        """
        vars_dict = template_vars or {}
        vars_dict["additional_context"] = additional_context
        
        super().__init__(
            name="Team Coordinator",
            description="Facilitates communication, tracks progress, and ensures smooth collaboration",
            template_id="team.roles.coordinator",  # This template should be created
            capabilities=[
                "communication_facilitation",
                "progress_tracking",
                "documentation",
                "workflow_optimization",
            ],
            template_vars=vars_dict,
            coordination_level=6,
            team_responsibilities=[
                "Facilitate communication between team members",
                "Track team progress and deadlines",
                "Maintain team documentation",
                "Identify and address bottlenecks",
                "Optimize team workflows",
            ],
        )
    
    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.
        
        Returns:
            List of required tool names
        """
        return ["communication", "progress_tracker", "documentation"]


# Factory function for creating team roles
def create_team_role(
    role_type: str,
    additional_context: str = "",
    specialty: Optional[str] = None,
    **kwargs: Any
) -> BaseTeamRole:
    """Create a team role by type.
    
    Args:
        role_type: Type of team role to create
        additional_context: Additional context for role instructions
        specialty: Required for specialist roles
        **kwargs: Additional role-specific parameters
        
    Returns:
        Team role implementation
        
    Raises:
        ValueError: If an unknown role type is specified
    """
    if role_type.lower() == "manager":
        return TeamManagerRole(additional_context=additional_context, **kwargs)
    elif role_type.lower() == "specialist":
        if specialty is None:
            raise ValueError("Specialist role requires a specialty")
        return TeamSpecialistRole(specialty=specialty, additional_context=additional_context, **kwargs)
    elif role_type.lower() == "coordinator":
        return TeamCoordinatorRole(additional_context=additional_context, **kwargs)
    elif role_type.lower() == "custom":
        if "name" not in kwargs or "description" not in kwargs:
            raise ValueError("Custom role requires 'name' and 'description'")
        
        # Create a SimpleTeamRole or TemplatedTeamRole based on parameters
        if "template_id" in kwargs:
            return TemplatedTeamRole(**kwargs)
        else:
            return SimpleTeamRole(
                name=kwargs["name"],
                description=kwargs["description"],
                capabilities=kwargs.get("capabilities", []),
                instructions=kwargs.get("instructions", ""),
                coordination_level=kwargs.get("coordination_level", 0),
                team_responsibilities=kwargs.get("team_responsibilities", []),
            )
    else:
        raise ValueError(f"Unknown team role type: {role_type}")
