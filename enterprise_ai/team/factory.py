"""
Team factory for Enterprise AI.

This module provides factory methods for creating different types of teams
with predefined structures and specialized roles.
"""

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.factory import create_agent, AgentBuilder
from enterprise_ai.agent.types import AgentProtocol, AgentRole
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.types import TeamProtocol
from enterprise_ai.team.registry import get_role_registry, RoleRegistry
from enterprise_ai.team.hierarchical import HierarchicalTeam
from enterprise_ai.logger import get_logger

logger = get_logger("team.factory")


class TeamFactory:
    """Factory for creating specialized team structures.

    This class provides methods for creating different types of teams
    with predefined structures and specialized roles.
    """

    def __init__(self, role_registry: Optional[RoleRegistry] = None):
        """Initialize a team factory.

        Args:
            role_registry: Optional role registry to use
        """
        self._role_registry = role_registry or get_role_registry()
        logger.info("Initialized team factory")

    def create_team(
        self,
        team_type: str = "base",
        name: Optional[str] = None,
        team_id: Optional[str] = None,
        manager: Optional[AgentProtocol] = None,
    ) -> TeamProtocol:
        """Create a team of the specified type.

        Args:
            team_type: Type of team to create ("base" or "hierarchical")
            name: Optional team name
            team_id: Optional team ID
            manager: Optional manager agent

        Returns:
            Created team

        Raises:
            ValueError: If an unknown team type is specified
        """
        if team_type == "base":
            return BaseTeam(
                team_id=team_id,
                name=name or "Team",
                manager=manager,
            )
        elif team_type == "hierarchical":
            return HierarchicalTeam(
                team_id=team_id,
                name=name or "Hierarchical Team",
                manager=manager,
            )
        else:
            logger.error(f"Unknown team type: {team_type}")
            raise ValueError(f"Unknown team type: {team_type}")

    def create_development_team(
        self,
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Development Team",
    ) -> TeamProtocol:
        """Create a development team with predefined roles.

        Creates a team with a manager and specialized development roles:
        - Software Developer
        - Quality Assurance
        - DevOps

        Args:
            manager: Optional manager agent (created if None)
            team_id: Optional team ID
            name: Team name

        Returns:
            Created team
        """
        # Create a hierarchical team
        team = HierarchicalTeam(
            team_id=team_id,
            name=name,
        )

        # Create manager if needed
        if not manager:
            manager = (
                AgentBuilder()
                .with_type("llm")
                .with_role("manager", additional_context="Development focused")
                .with_name("Dev Manager")
                .build()
            )

        team.manager = manager

        # Add standard development roles
        developer = (
            AgentBuilder().with_type("llm").with_role("developer").with_name("Developer").build()
        )
        team.add_member(developer, "developer")

        # Create QA agent with custom capabilities
        qa_agent = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="Quality Assurance",
                description="Specializes in testing and quality assurance",
                capabilities=["testing", "bug_reporting", "quality_control"],
            )
            .with_name("QA Engineer")
            .build()
        )
        team.add_member(qa_agent, "qa")

        # Create DevOps agent
        devops_agent = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="DevOps Engineer",
                description="Specializes in deployment and infrastructure",
                capabilities=["deployment", "infrastructure", "ci_cd"],
            )
            .with_name("DevOps")
            .build()
        )
        team.add_member(devops_agent, "devops")

        logger.info(f"Created development team: {team.id} ({team.name})")
        return team

    def create_research_team(
        self,
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Research Team",
    ) -> TeamProtocol:
        """Create a research team with predefined roles.

        Creates a team with a manager and specialized research roles:
        - Lead Researcher
        - Data Analyst
        - Subject Matter Expert

        Args:
            manager: Optional manager agent (created if None)
            team_id: Optional team ID
            name: Team name

        Returns:
            Created team
        """
        # Create a hierarchical team
        team = HierarchicalTeam(
            team_id=team_id,
            name=name,
        )

        # Create manager if needed
        if not manager:
            manager = (
                AgentBuilder()
                .with_type("llm")
                .with_role("manager", additional_context="Research focused")
                .with_name("Research Director")
                .build()
            )

        team.manager = manager

        # Add standard research roles
        researcher = (
            AgentBuilder()
            .with_type("llm")
            .with_role("researcher")
            .with_name("Lead Researcher")
            .build()
        )
        team.add_member(researcher, "lead_researcher")

        # Create Data Analyst agent
        analyst_agent = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="Data Analyst",
                description="Specializes in data analysis and visualization",
                capabilities=["data_analysis", "statistics", "visualization"],
            )
            .with_name("Data Analyst")
            .build()
        )
        team.add_member(analyst_agent, "data_analyst")

        # Create Subject Matter Expert
        sme_agent = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="Subject Matter Expert",
                description="Specializes in domain expertise",
                capabilities=["domain_knowledge", "expert_review", "context_providing"],
            )
            .with_name("Domain Expert")
            .build()
        )
        team.add_member(sme_agent, "subject_expert")

        logger.info(f"Created research team: {team.id} ({team.name})")
        return team

    def create_analytics_team(
        self,
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Analytics Team",
    ) -> TeamProtocol:
        """Create an analytics team with predefined roles.

        Creates a team with a manager and specialized analytics roles:
        - Data Scientist
        - Business Analyst
        - Data Engineer

        Args:
            manager: Optional manager agent (created if None)
            team_id: Optional team ID
            name: Team name

        Returns:
            Created team
        """
        # Create a hierarchical team
        team = HierarchicalTeam(
            team_id=team_id,
            name=name,
        )

        # Create manager if needed
        if not manager:
            manager = (
                AgentBuilder()
                .with_type("llm")
                .with_role("manager", additional_context="Analytics focused")
                .with_name("Analytics Manager")
                .build()
            )

        team.manager = manager

        # Add standard analytics roles
        data_scientist = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="Data Scientist",
                description="Specializes in data science and machine learning",
                capabilities=["machine_learning", "modeling", "data_science"],
            )
            .with_name("Data Scientist")
            .build()
        )
        team.add_member(data_scientist, "data_scientist")

        # Create Business Analyst
        business_analyst = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="Business Analyst",
                description="Specializes in business analytics and insights",
                capabilities=["business_analysis", "requirements", "reporting"],
            )
            .with_name("Business Analyst")
            .build()
        )
        team.add_member(business_analyst, "business_analyst")

        # Create Data Engineer
        data_engineer = (
            AgentBuilder()
            .with_type("llm")
            .with_role(
                "custom",
                name="Data Engineer",
                description="Specializes in data infrastructure and pipelines",
                capabilities=["data_engineering", "etl", "database"],
            )
            .with_name("Data Engineer")
            .build()
        )
        team.add_member(data_engineer, "data_engineer")

        logger.info(f"Created analytics team: {team.id} ({team.name})")
        return team

    def create_custom_team(
        self,
        member_roles: List[Tuple[str, List[str]]],
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Custom Team",
        team_type: str = "hierarchical",
    ) -> TeamProtocol:
        """Create a custom team with specified roles.

        Args:
            manager: Optional manager agent (created if None)
            member_roles: List of (role_name, capabilities) tuples
            team_id: Optional team ID
            name: Team name
            team_type: Type of team to create

        Returns:
            Created team
        """
        # Create team of specified type
        team = self.create_team(
            team_type=team_type,
            name=name,
            team_id=team_id,
            manager=manager,
        )

        # Create manager if needed
        if not manager:
            manager = (
                AgentBuilder()
                .with_type("llm")
                .with_role("manager")
                .with_name("Team Manager")
                .build()
            )

        team.manager = manager

        # Add members with specified roles
        for idx, (role_name, capabilities) in enumerate(member_roles):
            agent = (
                AgentBuilder()
                .with_type("llm")
                .with_role(
                    "custom",
                    name=role_name,
                    description=f"Specializes in {', '.join(capabilities)}",
                    capabilities=capabilities,
                )
                .with_name(f"{role_name} {idx + 1}")
                .build()
            )
            team.add_member(agent, role_name.lower().replace(" ", "_"))

        logger.info(
            f"Created custom team: {team.id} ({team.name}) with {len(member_roles)} members"
        )
        return team

    def create_cross_functional_team(
        self,
        specializations: List[str],
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Cross-Functional Team",
    ) -> TeamProtocol:
        """Create a cross-functional team with members from different specializations.

        Args:
            specializations: List of specialization areas
            manager: Optional manager agent (created if None)
            team_id: Optional team ID
            name: Team name

        Returns:
            Created team
        """
        # Map specializations to role types and capabilities
        specialization_map = {
            "development": ("developer", ["coding", "debugging", "software_design"]),
            "research": ("researcher", ["research", "analysis", "reporting"]),
            "design": ("custom", ["design", "ux", "visual_communication"]),
            "marketing": ("custom", ["marketing", "communication", "strategy"]),
            "analytics": ("custom", ["data_analysis", "insights", "metrics"]),
            "product": ("custom", ["product_management", "roadmapping", "prioritization"]),
            "qa": ("custom", ["testing", "quality_assurance", "bug_reporting"]),
        }

        # Create a hierarchical team
        team = HierarchicalTeam(
            team_id=team_id,
            name=name,
        )

        # Create manager if needed
        if not manager:
            manager = (
                AgentBuilder()
                .with_type("llm")
                .with_role("manager", additional_context="Cross-functional leadership")
                .with_name("Team Lead")
                .build()
            )

        team.manager = manager

        # Add specialized members
        for spec in specializations:
            spec_lower = spec.lower()
            if spec_lower in specialization_map:
                role_type, capabilities = specialization_map[spec_lower]

                # Create role-specific agent
                if role_type == "custom":
                    agent = (
                        AgentBuilder()
                        .with_type("llm")
                        .with_role(
                            "custom",
                            name=f"{spec} Specialist",
                            description=f"Specializes in {spec}",
                            capabilities=capabilities,
                        )
                        .with_name(f"{spec} Specialist")
                        .build()
                    )
                else:
                    agent = (
                        AgentBuilder()
                        .with_type("llm")
                        .with_role(role_type)
                        .with_name(f"{spec} Specialist")
                        .build()
                    )

                team.add_member(agent, spec_lower.replace(" ", "_"))
            else:
                logger.warning(f"Unknown specialization: {spec}")

        logger.info(f"Created cross-functional team: {team.id} ({team.name})")
        return team


# Singleton instance for global team factory
_global_team_factory: Optional[TeamFactory] = None


def get_team_factory() -> TeamFactory:
    """Get the global team factory instance.

    Returns:
        Global team factory
    """
    global _global_team_factory
    if _global_team_factory is None:
        _global_team_factory = TeamFactory()
    return _global_team_factory
