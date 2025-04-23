"""
Team factory for Enterprise AI.

This module provides factory methods for creating different types of teams
with predefined structures, specialized roles, and tool integration capabilities.
"""

import uuid
import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.factory import create_agent, AgentBuilder
from enterprise_ai.agent.types import AgentProtocol, AgentRole
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.types import (
    TeamProtocol,
    ToolCapableTeamProtocol,
    CollaborativeTeamProtocol,
)
from enterprise_ai.team.registry import get_role_registry, RoleRegistry
from enterprise_ai.team.hierarchical import HierarchicalTeam
from enterprise_ai.team.collaborative import CollaborativeTeam
from enterprise_ai.team.tool_sharing import (
    DefaultToolSharingPolicy,
    HierarchicalToolSharingPolicy,
    SimpleToolRoutingStrategy,
    CapabilityBasedToolRoutingStrategy,
)
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.logger import get_logger

logger = get_logger("team.factory")


class TeamFactory:
    """Factory for creating specialized team structures.

    This class provides methods for creating different types of teams
    with predefined structures, specialized roles, and tool integration.
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
            team_type: Type of team to create ("base", "hierarchical", or "collaborative")
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
        elif team_type == "collaborative":
            return CollaborativeTeam(
                team_id=team_id,
                name=name or "Collaborative Team",
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
        tool_enabled: bool = True,
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
            tool_enabled: Whether to enable tools for team members

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
                .with_tools(tool_enabled)
                .with_param("reasoning_framework", "swe" if tool_enabled else "cot")
                .build()
            )

        team.manager = manager

        # Add standard development roles
        developer = (
            AgentBuilder()
            .with_type("llm")
            .with_role("developer")
            .with_name("Developer")
            .with_tools(tool_enabled)
            .with_tool_categories(["development", "execution", "file"])
            .with_param("reasoning_framework", "swe" if tool_enabled else "cot")
            .build()
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
            .with_tools(tool_enabled)
            .with_tool_categories(["execution", "file"])
            .with_param("reasoning_framework", "tool_cot" if tool_enabled else "cot")
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
            .with_tools(tool_enabled)
            .with_tool_categories(["execution", "file", "utility"])
            .with_param("reasoning_framework", "swe" if tool_enabled else "cot")
            .build()
        )
        team.add_member(devops_agent, "devops")

        # Register tools if enabled
        if tool_enabled and hasattr(manager, "_tool_manager"):
            # Get tools from the manager and share with team
            for tool_name in manager._tool_manager.list_tools():
                try:
                    # Get tool instance
                    tool = manager._tool_manager.get_tool(tool_name)
                    if tool:
                        # Register with team
                        team.register_team_tool(tool, manager.id)
                except Exception as e:
                    logger.warning(f"Error registering tool {tool_name}: {e}")

        # Set hierarchical sharing policy
        manager_ids = {manager.id}
        if isinstance(team, ToolCapableTeamProtocol):
            team.set_tool_sharing_policy(
                cast(
                    DefaultToolSharingPolicy,
                    HierarchicalToolSharingPolicy(
                        manager_ids=manager_ids, allow_lateral_sharing=True
                    ),
                )
            )

        logger.info(f"Created development team: {team.id} ({team.name})")
        return team

    def create_research_team(
        self,
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Research Team",
        tool_enabled: bool = True,
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
            tool_enabled: Whether to enable tools for team members

        Returns:
            Created team
        """
        # Create a collaborative team for flexible tool sharing
        team = CollaborativeTeam(
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
                .with_tools(tool_enabled)
                .with_tool_categories(["research", "content"])
                .with_param("reasoning_framework", "tool_cot" if tool_enabled else "cot")
                .build()
            )

        team.manager = manager

        # Add standard research roles
        researcher = (
            AgentBuilder()
            .with_type("llm")
            .with_role("researcher")
            .with_name("Lead Researcher")
            .with_tools(tool_enabled)
            .with_tool_categories(["research", "content", "browser"])
            .with_param("reasoning_framework", "react" if tool_enabled else "cot")
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
            .with_tools(tool_enabled)
            .with_tool_categories(["content", "file"])
            .with_param("reasoning_framework", "react" if tool_enabled else "cot")
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
            .with_tools(tool_enabled)
            .with_tool_categories(["content", "browser"])
            .with_param("reasoning_framework", "react" if tool_enabled else "cot")
            .build()
        )
        team.add_member(sme_agent, "subject_expert")

        # Register tools if enabled
        if tool_enabled:
            # Create research tool pool
            if isinstance(team, CollaborativeTeamProtocol):
                team.create_tool_pool("research_tools", [])

                # Register tools from all members and add to pool
                for member_id, member in team.members.items():
                    if hasattr(member, "_tool_manager"):
                        for tool_name in member._tool_manager.list_tools():
                            try:
                                # Get tool instance
                                tool = member._tool_manager.get_tool(tool_name)
                                if tool:
                                    # Register with team
                                    team.register_team_tool(tool, member_id)
                                    # Add to pool
                                    team.add_tools_to_pool("research_tools", [tool_name])
                            except Exception as e:
                                logger.warning(f"Error registering tool {tool_name}: {e}")

                # Grant access to all members
                for member_id in team.members:
                    team.grant_pool_access("research_tools", member_id)

                # Set capability-based routing
                capability_map: Dict[str, Dict[str, float]] = {}
                team.set_tool_routing_strategy(
                    cast(
                        SimpleToolRoutingStrategy,
                        CapabilityBasedToolRoutingStrategy(capability_map),
                    )
                )

        logger.info(f"Created research team: {team.id} ({team.name})")
        return team

    def create_analytics_team(
        self,
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Analytics Team",
        tool_enabled: bool = True,
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
            tool_enabled: Whether to enable tools for team members

        Returns:
            Created team
        """
        # Create a collaborative team
        team = CollaborativeTeam(
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
                .with_tools(tool_enabled)
                .with_tool_categories(["content", "file"])
                .with_param("reasoning_framework", "react" if tool_enabled else "cot")
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
            .with_tools(tool_enabled)
            .with_tool_categories(["content", "execution", "file"])
            .with_param("reasoning_framework", "react" if tool_enabled else "cot")
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
            .with_tools(tool_enabled)
            .with_tool_categories(["content", "browser"])
            .with_param("reasoning_framework", "tool_cot" if tool_enabled else "cot")
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
            .with_tools(tool_enabled)
            .with_tool_categories(["execution", "file"])
            .with_param("reasoning_framework", "swe" if tool_enabled else "cot")
            .build()
        )
        team.add_member(data_engineer, "data_engineer")

        # Register tools and create pools if enabled
        if tool_enabled and isinstance(team, CollaborativeTeamProtocol):
            # Create analytics tool pools
            team.create_tool_pool("analysis_tools", [])
            team.create_tool_pool("data_tools", [])

            # Register tools from all members
            for member_id, member in team.members.items():
                if hasattr(member, "_tool_manager"):
                    for tool_name in member._tool_manager.list_tools():
                        try:
                            # Get tool instance
                            tool = member._tool_manager.get_tool(tool_name)
                            if tool:
                                # Register with team
                                team.register_team_tool(tool, member_id)

                                # Add to appropriate pool
                                if any(
                                    kw in tool_name.lower()
                                    for kw in ["analysis", "stat", "chart", "report"]
                                ):
                                    team.add_tools_to_pool("analysis_tools", [tool_name])
                                elif any(
                                    kw in tool_name.lower()
                                    for kw in ["data", "file", "csv", "json"]
                                ):
                                    team.add_tools_to_pool("data_tools", [tool_name])
                        except Exception as e:
                            logger.warning(f"Error registering tool {tool_name}: {e}")

            # Grant access based on roles
            for member_id, role in team._member_roles.items():
                if role == "data_scientist":
                    team.grant_pool_access("analysis_tools", member_id)
                    team.grant_pool_access("data_tools", member_id)
                elif role == "business_analyst":
                    team.grant_pool_access("analysis_tools", member_id)
                elif role == "data_engineer":
                    team.grant_pool_access("data_tools", member_id)

        logger.info(f"Created analytics team: {team.id} ({team.name})")
        return team

    def create_custom_team(
        self,
        member_roles: List[Tuple[str, List[str]]],
        manager: Optional[AgentProtocol] = None,
        team_id: Optional[str] = None,
        name: str = "Custom Team",
        team_type: str = "hierarchical",
        tool_enabled: bool = True,
    ) -> TeamProtocol:
        """Create a custom team with specified roles.

        Args:
            manager: Optional manager agent (created if None)
            member_roles: List of (role_name, capabilities) tuples
            team_id: Optional team ID
            name: Team name
            team_type: Type of team to create
            tool_enabled: Whether to enable tools for team members

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
                .with_tools(tool_enabled)
                .with_param("reasoning_framework", "react" if tool_enabled else "cot")
                .build()
            )

        team.manager = manager

        # Add members with specified roles
        for idx, (role_name, capabilities) in enumerate(member_roles):
            # Determine appropriate tool categories based on role capabilities
            tool_categories = []
            if any(cap in ["coding", "programming", "development"] for cap in capabilities):
                tool_categories.extend(["development", "execution", "file"])
            if any(cap in ["research", "web", "search"] for cap in capabilities):
                tool_categories.extend(["research", "browser", "content"])
            if any(cap in ["data", "analysis", "report"] for cap in capabilities):
                tool_categories.extend(["content", "file"])

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
                .with_tools(tool_enabled)
                .with_tool_categories(tool_categories or [])
                .with_param("reasoning_framework", "react" if tool_enabled else "cot")
                .build()
            )
            team.add_member(agent, role_name.lower().replace(" ", "_"))

        # Register tools if enabled
        if tool_enabled and hasattr(manager, "_tool_manager"):
            # Register manager's tools
            for tool_name in manager._tool_manager.list_tools():
                try:
                    # Get tool instance
                    tool = manager._tool_manager.get_tool(tool_name)
                    if tool:
                        # Register with team
                        if hasattr(team, "register_team_tool"):
                            team.register_team_tool(tool, manager.id)
                except Exception as e:
                    logger.warning(f"Error registering manager tool {tool_name}: {e}")

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
        tool_enabled: bool = True,
    ) -> TeamProtocol:
        """Create a cross-functional team with members from different specializations.

        Args:
            specializations: List of specialization areas
            manager: Optional manager agent (created if None)
            team_id: Optional team ID
            name: Team name
            tool_enabled: Whether to enable tools for team members

        Returns:
            Created team
        """
        # Map specializations to role types and capabilities
        specialization_map = {
            "development": (
                "developer",
                ["coding", "debugging", "software_design"],
                ["development", "execution", "file"],
            ),
            "research": (
                "researcher",
                ["research", "analysis", "reporting"],
                ["research", "browser", "content"],
            ),
            "design": ("custom", ["design", "ux", "visual_communication"], ["content"]),
            "marketing": (
                "custom",
                ["marketing", "communication", "strategy"],
                ["content", "browser"],
            ),
            "analytics": ("custom", ["data_analysis", "insights", "metrics"], ["content", "file"]),
            "product": (
                "custom",
                ["product_management", "roadmapping", "prioritization"],
                ["content", "browser"],
            ),
            "qa": (
                "custom",
                ["testing", "quality_assurance", "bug_reporting"],
                ["execution", "file"],
            ),
        }

        # Create a collaborative team for cross-functional work
        team = CollaborativeTeam(
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
                .with_tools(tool_enabled)
                .with_param("reasoning_framework", "tool_cot" if tool_enabled else "cot")
                .build()
            )

        team.manager = manager

        # Add specialized members
        for spec in specializations:
            spec_lower = spec.lower()
            if spec_lower in specialization_map:
                role_type, capabilities, tool_categories = specialization_map[spec_lower]

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
                        .with_tools(tool_enabled)
                        .with_tool_categories(tool_categories or [])
                        .with_param("reasoning_framework", "react" if tool_enabled else "cot")
                        .build()
                    )
                else:
                    agent = (
                        AgentBuilder()
                        .with_type("llm")
                        .with_role(role_type)
                        .with_name(f"{spec} Specialist")
                        .with_tools(tool_enabled)
                        .with_tool_categories(tool_categories or [])
                        .with_param("reasoning_framework", "react" if tool_enabled else "cot")
                        .build()
                    )

                team.add_member(agent, spec_lower.replace(" ", "_"))
            else:
                logger.warning(f"Unknown specialization: {spec}")

        # Create tool pools for collaborative teams
        if tool_enabled and isinstance(team, CollaborativeTeamProtocol):
            # Create pools based on function areas
            for area in ["development", "research", "design", "content"]:
                if any(area in s.lower() for s in specializations):
                    pool_name = f"{area}_tools"
                    team.create_tool_pool(pool_name, [])

            # Register tools from all members
            for member_id, member in team.members.items():
                if hasattr(member, "_tool_manager"):
                    for tool_name in member._tool_manager.list_tools():
                        try:
                            # Get tool instance
                            tool = member._tool_manager.get_tool(tool_name)
                            if tool:
                                # Register with team
                                team.register_team_tool(tool, member_id)

                                # Add to relevant pools
                                tool_name_lower = tool_name.lower()
                                for area in ["development", "research", "design", "content"]:
                                    if area in tool_name_lower:
                                        pool_name = f"{area}_tools"
                                        if pool_name in team._tool_pool_manager._pools:
                                            team.add_tools_to_pool(pool_name, [tool_name])
                        except Exception as e:
                            logger.warning(f"Error registering tool {tool_name}: {e}")

            # Grant pool access to all members for their specialty area
            for member_id, role in team._member_roles.items():
                base_role = role.replace("_specialist", "")
                pool_name = f"{base_role}_tools"
                if pool_name in team._tool_pool_manager._pools:
                    team.grant_pool_access(pool_name, member_id)

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
