"""
Agent role definitions for Enterprise AI.

This module provides implementations of the AgentRole protocol
defined in types.py, enabling agent specialization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.core.types import AgentRole
from enterprise_ai.logger import get_logger
from enterprise_ai.prompt import PromptTemplate, get_prompt, format_prompt
from enterprise_ai.types import Serializable

logger = get_logger("agent.role")


class BaseAgentRole(AgentRole, Serializable, ABC):
    """Base class for agent roles.

    This abstract class provides a foundation for implementing agent roles
    with common functionality and required abstract methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Get role name.

        Returns:
            Role name
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get role description.

        Returns:
            Role description
        """
        pass

    @property
    @abstractmethod
    def capabilities(self) -> List[str]:
        """Get role capabilities.

        Returns:
            List of capability identifiers
        """
        pass

    @abstractmethod
    def get_instructions(self) -> str:
        """Get role-specific instructions.

        Returns:
            Instruction string for the role
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary representation.

        Returns:
            Dictionary representation of the role
        """
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
        }


@dataclass
class SimpleRole(BaseAgentRole):
    """Simple implementation of agent role with static values.

    This class provides a straightforward way to define roles with
    static values for name, description, capabilities, and instructions.
    """

    _name: str
    _description: str
    _capabilities: List[str] = field(default_factory=list)
    _instructions: str = ""

    @property
    def name(self) -> str:
        """Get role name.

        Returns:
            Role name
        """
        return self._name

    @property
    def description(self) -> str:
        """Get role description.

        Returns:
            Role description
        """
        return self._description

    @property
    def capabilities(self) -> List[str]:
        """Get role capabilities.

        Returns:
            List of capability identifiers
        """
        return self._capabilities.copy()

    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.

        Returns:
            List of required tool names
        """
        return []

    @property
    def preferred_reasoning(self) -> Optional[str]:
        """Get preferred reasoning framework for this role.

        Returns:
            Name of preferred reasoning framework or None
        """
        return None

    def has_capability(self, capability: Union[str, Any]) -> bool:
        """Check if role has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if role has the capability
        """
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return cap_str in self._capabilities

    def get_instructions(self) -> str:
        """Get role-specific instructions.

        Returns:
            Instruction string for the role
        """
        return self._instructions


class TemplatedRole(BaseAgentRole):
    """Template-based agent role.

    This class implements an agent role that uses a prompt template
    for generating instructions dynamically.
    """

    def __init__(
        self,
        name: str,
        description: str,
        template_id: str,
        capabilities: Optional[List[str]] = None,
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a templated role.

        Args:
            name: Role name
            description: Role description
            template_id: Prompt template identifier
            capabilities: Optional list of capability identifiers
            template_vars: Optional variables for the template
        """
        self._name = name
        self._description = description
        self._template_id = template_id
        self._capabilities = capabilities or []
        self._template_vars = template_vars or {}

        # Validate template exists
        if get_prompt(template_id) is None:
            logger.warning(f"Prompt template not found: {template_id}")

    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.

        Returns:
            List of required tool names
        """
        return []

    @property
    def preferred_reasoning(self) -> Optional[str]:
        """Get preferred reasoning framework for this role.

        Returns:
            Name of preferred reasoning framework or None
        """
        return None

    def has_capability(self, capability: Union[str, Any]) -> bool:
        """Check if role has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if role has the capability
        """
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return cap_str in self._capabilities

    @property
    def name(self) -> str:
        """Get role name.

        Returns:
            Role name
        """
        return self._name

    @property
    def description(self) -> str:
        """Get role description.

        Returns:
            Role description
        """
        return self._description

    @property
    def capabilities(self) -> List[str]:
        """Get role capabilities.

        Returns:
            List of capability identifiers
        """
        return self._capabilities.copy()

    def get_instructions(self) -> str:
        """Get role-specific instructions.

        Returns:
            Instruction string for the role generated from template

        Raises:
            ValueError: If template is not found
        """
        instructions = format_prompt(self._template_id, **self._template_vars)
        if instructions is None:
            raise ValueError(f"Failed to format instructions from template: {self._template_id}")
        return instructions

    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary representation.

        Returns:
            Dictionary representation of the role
        """
        base_dict = super().to_dict()
        base_dict.update(
            {
                "template_id": self._template_id,
                "template_vars": self._template_vars,
            }
        )
        return base_dict


# Built-in role implementations


class DeveloperRole(TemplatedRole):
    """Developer role implementation.

    This role specializes in software development tasks, including
    coding, debugging, and code review.
    """

    def __init__(
        self,
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize developer role.

        Args:
            additional_context: Additional context to include in instructions
            template_vars: Optional additional template variables
        """
        vars_dict = template_vars or {}
        vars_dict["additional_context"] = additional_context

        super().__init__(
            name="Developer",
            description="Specializes in software development, coding, and debugging",
            template_id="roles.developer",
            capabilities=[
                "code_generation",
                "code_review",
                "debugging",
                "technical_design",
            ],
            template_vars=vars_dict,
        )

    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.

        Returns:
            List of required tool names
        """
        return ["code_interpreter", "code_review"]

    @property
    def preferred_reasoning(self) -> Optional[str]:
        """Get preferred reasoning framework for this role.

        Returns:
            Name of preferred reasoning framework or None
        """
        return "systematic"

    def has_capability(self, capability: Union[str, Any]) -> bool:
        """Check if role has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if role has the capability
        """
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return cap_str in self._capabilities


class ManagerRole(TemplatedRole):
    """Manager role implementation.

    This role specializes in coordinating teams, planning work,
    and ensuring project goals are met.
    """

    def __init__(
        self,
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize manager role.

        Args:
            additional_context: Additional context to include in instructions
            template_vars: Optional additional template variables
        """
        vars_dict = template_vars or {}
        vars_dict["additional_context"] = additional_context

        super().__init__(
            name="Manager",
            description="Specializes in team coordination, planning, and decision-making",
            template_id="roles.manager",
            capabilities=[
                "planning",
                "task_delegation",
                "progress_tracking",
                "decision_making",
            ],
            template_vars=vars_dict,
        )

    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.

        Returns:
            List of required tool names
        """
        return ["task_manager", "scheduler"]

    @property
    def preferred_reasoning(self) -> Optional[str]:
        """Get preferred reasoning framework for this role.

        Returns:
            Name of preferred reasoning framework or None
        """
        return "executive"

    def has_capability(self, capability: Union[str, Any]) -> bool:
        """Check if role has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if role has the capability
        """
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return cap_str in self._capabilities


class ResearcherRole(TemplatedRole):
    """Researcher role implementation.

    This role specializes in research, information synthesis,
    and analytical tasks.
    """

    def __init__(
        self,
        additional_context: str = "",
        template_vars: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize researcher role.

        Args:
            additional_context: Additional context to include in instructions
            template_vars: Optional additional template variables
        """
        vars_dict = template_vars or {}
        vars_dict["additional_context"] = additional_context

        super().__init__(
            name="Researcher",
            description="Specializes in research, information synthesis, and analysis",
            template_id="roles.researcher",
            capabilities=[
                "research",
                "information_synthesis",
                "analysis",
                "reporting",
            ],
            template_vars=vars_dict,
        )

    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role.

        Returns:
            List of required tool names
        """
        return ["search", "document_analysis"]

    @property
    def preferred_reasoning(self) -> Optional[str]:
        """Get preferred reasoning framework for this role.

        Returns:
            Name of preferred reasoning framework or None
        """
        return "analytical"

    def has_capability(self, capability: Union[str, Any]) -> bool:
        """Check if role has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if role has the capability
        """
        cap_str = capability.value if hasattr(capability, "value") else str(capability)
        return cap_str in self._capabilities


# Factory function to create roles
def create_role(role_type: str, **kwargs: Any) -> AgentRole:
    """Create a role implementation by type.

    Args:
        role_type: Type of role to create
        **kwargs: Additional arguments passed to the role constructor

    Returns:
        AgentRole implementation

    Raises:
        ValueError: If an unknown role type is specified
    """
    if role_type == "developer":
        return DeveloperRole(**kwargs)
    elif role_type == "manager":
        return ManagerRole(**kwargs)
    elif role_type == "researcher":
        return ResearcherRole(**kwargs)
    elif role_type == "custom":
        if "name" not in kwargs or "description" not in kwargs:
            raise ValueError("Custom role requires 'name' and 'description'")

        if "template_id" in kwargs:
            return TemplatedRole(**kwargs)
        else:
            return SimpleRole(
                _name=kwargs["name"],
                _description=kwargs["description"],
                _capabilities=kwargs.get("capabilities", []),
                _instructions=kwargs.get("instructions", ""),
            )
    else:
        raise ValueError(f"Unknown role type: {role_type}")
