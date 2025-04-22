"""
Agent factory for Enterprise AI.

This module provides factory functions and patterns for creating
different types of agents with various configurations.
"""

import os
from typing import Any, Dict, List, Optional, Set, Type, Union, cast

from enterprise_ai.agent.base import BaseAgent, LLMAgent
from enterprise_ai.agent.role import create_role
from enterprise_ai.agent.types import AgentProtocol, AgentRole
from enterprise_ai.config import get_config
from enterprise_ai.llm import get_default_provider, create_provider
from enterprise_ai.logger import get_logger

logger = get_logger("agent.factory")


def create_agent(
    agent_type: str = "base",
    agent_id: Optional[str] = None,
    name: Optional[str] = None,
    role_type: Optional[str] = None,
    role_kwargs: Optional[Dict[str, Any]] = None,
    state_type: Optional[str] = None,
    state_kwargs: Optional[Dict[str, Any]] = None,
    llm_provider_name: Optional[str] = None,
    reasoning_framework: str = "base",
    use_tools: bool = False,
    enable_mcp: bool = False,
    tool_categories: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
    **kwargs: Any,
) -> AgentProtocol:
    """Create an agent by type.

    This factory function creates agents of different types with
    the specified configuration.

    Args:
        agent_type: Type of agent to create ("base" or "llm")
        agent_id: Optional unique identifier
        name: Optional human-readable name
        role_type: Optional role type to assign
        role_kwargs: Optional arguments for role creation
        state_type: Optional state implementation type
        state_kwargs: Optional arguments for state creation
        llm_provider_name: Optional name of LLM provider to use
        reasoning_framework: Name of the reasoning framework to use
        use_tools: Whether to enable tool usage for the agent
        enable_mcp: Whether to enable MCP for tool discovery
        tool_categories: Optional categories of tools to include
        tool_names: Optional specific tool names to include
        **kwargs: Additional agent-specific parameters

    Returns:
        Agent implementation

    Raises:
        ValueError: If an unknown agent type is specified
    """
    # Apply default configurations
    name = name or f"{agent_type.capitalize()}Agent"
    state_kwargs = state_kwargs or {}

    # Set state directory from config
    if "state_dir" not in state_kwargs:
        state_dir = get_config("agent.state_directory", None)
        if state_dir:
            state_kwargs["state_dir"] = state_dir

    # Create agent based on type
    if agent_type.lower() == "base":
        state_type = state_type or "base"
        # Base agents don't support tools or reasoning frameworks
        if use_tools:
            logger.warning("Base agents don't support tools. Use LLM agents instead.")

        return BaseAgent(
            agent_id=agent_id,
            name=name,
            role_type=role_type,
            role_kwargs=role_kwargs,
            state_type=state_type,
            state_kwargs=state_kwargs,
            **kwargs,
        )
    elif agent_type.lower() == "llm":
        state_type = state_type or "conversation"

        # Get LLM provider
        llm_provider = None
        if llm_provider_name:
            llm_provider = create_provider(llm_provider_name)
        else:
            llm_provider = get_default_provider()

        return LLMAgent(
            agent_id=agent_id,
            name=name,
            role_type=role_type,
            role_kwargs=role_kwargs,
            state_type=state_type,
            state_kwargs=state_kwargs,
            llm_provider=llm_provider,
            reasoning_framework=reasoning_framework,
            use_tools=use_tools,
            enable_mcp=enable_mcp,
            tool_categories=tool_categories,
            tool_names=tool_names,
            **kwargs,
        )
    else:
        logger.error(f"Unknown agent type: {agent_type}")
        raise ValueError(f"Unknown agent type: {agent_type}")


class AgentBuilder:
    """Builder pattern for creating agents.

    This class provides a fluent interface for constructing agents
    with various configurations.
    """

    def __init__(self) -> None:
        """Initialize a new agent builder."""
        self._agent_type: str = "base"
        self._agent_id: Optional[str] = None
        self._name: Optional[str] = None
        self._role_type: Optional[str] = None
        self._role_kwargs: Dict[str, Any] = {}
        self._state_type: Optional[str] = None
        self._state_kwargs: Dict[str, Any] = {}
        self._llm_provider_name: Optional[str] = None
        self._reasoning_framework: str = "base"
        self._use_tools: bool = False
        self._enable_mcp: bool = False
        self._tool_categories: Optional[List[str]] = None
        self._tool_names: Optional[List[str]] = None
        self._kwargs: Dict[str, Any] = {}

    def with_type(self, agent_type: str) -> "AgentBuilder":
        """Set the agent type.

        Args:
            agent_type: Type of agent to create

        Returns:
            Builder instance for chaining
        """
        self._agent_type = agent_type
        return self

    def with_id(self, agent_id: str) -> "AgentBuilder":
        """Set the agent ID.

        Args:
            agent_id: Unique identifier

        Returns:
            Builder instance for chaining
        """
        self._agent_id = agent_id
        return self

    def with_name(self, name: str) -> "AgentBuilder":
        """Set the agent name.

        Args:
            name: Human-readable name

        Returns:
            Builder instance for chaining
        """
        self._name = name
        return self

    def with_role(self, role_type: str, **kwargs: Any) -> "AgentBuilder":
        """Set the agent role.

        Args:
            role_type: Type of role to assign
            **kwargs: Additional role parameters

        Returns:
            Builder instance for chaining
        """
        self._role_type = role_type
        self._role_kwargs = kwargs
        return self

    def with_state(self, state_type: str, **kwargs: Any) -> "AgentBuilder":
        """Set the agent state configuration.

        Args:
            state_type: Type of state to use
            **kwargs: Additional state parameters

        Returns:
            Builder instance for chaining
        """
        self._state_type = state_type
        self._state_kwargs = kwargs
        return self

    def with_llm_provider(self, provider_name: str) -> "AgentBuilder":
        """Set the LLM provider.

        Args:
            provider_name: Name of LLM provider

        Returns:
            Builder instance for chaining
        """
        self._llm_provider_name = provider_name
        return self

    def with_reasoning(self, framework: str) -> "AgentBuilder":
        """Set the reasoning framework.

        Args:
            framework: Name of reasoning framework to use

        Returns:
            Builder instance for chaining
        """
        self._reasoning_framework = framework
        return self

    def with_tools(self, enable: bool = True) -> "AgentBuilder":
        """Enable or disable tools for the agent.

        Args:
            enable: Whether to enable tools

        Returns:
            Builder instance for chaining
        """
        self._use_tools = enable
        return self

    def with_mcp(self, enable: bool = True) -> "AgentBuilder":
        """Enable or disable MCP for tool discovery.

        Args:
            enable: Whether to enable MCP

        Returns:
            Builder instance for chaining
        """
        self._enable_mcp = enable
        return self

    def with_tool_categories(self, categories: List[str]) -> "AgentBuilder":
        """Set tool categories to include.

        Args:
            categories: List of tool categories

        Returns:
            Builder instance for chaining
        """
        self._tool_categories = categories
        return self

    def with_tool_names(self, tool_names: List[str]) -> "AgentBuilder":
        """Set specific tool names to include.

        Args:
            tool_names: List of tool names

        Returns:
            Builder instance for chaining
        """
        self._tool_names = tool_names
        return self

    def with_param(self, key: str, value: Any) -> "AgentBuilder":
        """Set a custom parameter.

        Args:
            key: Parameter name
            value: Parameter value

        Returns:
            Builder instance for chaining
        """
        self._kwargs[key] = value
        return self

    def build(self) -> AgentProtocol:
        """Build the agent with the configured options.

        Returns:
            Constructed agent
        """
        return create_agent(
            agent_type=self._agent_type,
            agent_id=self._agent_id,
            name=self._name,
            role_type=self._role_type,
            role_kwargs=self._role_kwargs,
            state_type=self._state_type,
            state_kwargs=self._state_kwargs,
            llm_provider_name=self._llm_provider_name,
            reasoning_framework=self._reasoning_framework,
            use_tools=self._use_tools,
            enable_mcp=self._enable_mcp,
            tool_categories=self._tool_categories,
            tool_names=self._tool_names,
            **self._kwargs,
        )


# Specialized factory functions for common agent types


def create_developer_agent(
    agent_id: Optional[str] = None,
    name: str = "Developer",
    agent_type: str = "llm",
    additional_context: str = "",
    use_tools: bool = True,
    reasoning_framework: str = "swe",
    **kwargs: Any,
) -> AgentProtocol:
    """Create a developer agent with appropriate tools and reasoning.

    Args:
        agent_id: Optional unique identifier
        name: Human-readable name
        agent_type: Type of agent to create
        additional_context: Additional role-specific context
        use_tools: Whether to enable development tools
        reasoning_framework: Reasoning framework to use (default: 'swe')
        **kwargs: Additional agent parameters

    Returns:
        Developer agent
    """
    # Set up developer-focused tool categories
    tool_categories = kwargs.pop("tool_categories", ["development", "file", "execution"])

    return create_agent(
        agent_type=agent_type,
        agent_id=agent_id,
        name=name,
        role_type="developer",
        role_kwargs={"additional_context": additional_context},
        reasoning_framework=reasoning_framework,
        use_tools=use_tools,
        enable_mcp=use_tools,  # Enable MCP if tools are enabled
        tool_categories=tool_categories,
        **kwargs,
    )


def create_manager_agent(
    agent_id: Optional[str] = None,
    name: str = "Manager",
    agent_type: str = "llm",
    additional_context: str = "",
    use_tools: bool = True,
    reasoning_framework: str = "cot",
    **kwargs: Any,
) -> AgentProtocol:
    """Create a manager agent with appropriate tools and reasoning.

    Args:
        agent_id: Optional unique identifier
        name: Human-readable name
        agent_type: Type of agent to create
        additional_context: Additional role-specific context
        use_tools: Whether to enable management tools
        reasoning_framework: Reasoning framework to use (default: 'cot')
        **kwargs: Additional agent parameters

    Returns:
        Manager agent
    """
    # Set up manager-focused tool categories
    tool_categories = kwargs.pop("tool_categories", ["planning", "utility"])

    return create_agent(
        agent_type=agent_type,
        agent_id=agent_id,
        name=name,
        role_type="manager",
        role_kwargs={"additional_context": additional_context},
        reasoning_framework=reasoning_framework,
        use_tools=use_tools,
        enable_mcp=use_tools,  # Enable MCP if tools are enabled
        tool_categories=tool_categories,
        **kwargs,
    )


def create_researcher_agent(
    agent_id: Optional[str] = None,
    name: str = "Researcher",
    agent_type: str = "llm",
    additional_context: str = "",
    use_tools: bool = True,
    reasoning_framework: str = "cot",
    **kwargs: Any,
) -> AgentProtocol:
    """Create a researcher agent with appropriate tools and reasoning.

    Args:
        agent_id: Optional unique identifier
        name: Human-readable name
        agent_type: Type of agent to create
        additional_context: Additional role-specific context
        use_tools: Whether to enable research tools
        reasoning_framework: Reasoning framework to use (default: 'cot')
        **kwargs: Additional agent parameters

    Returns:
        Researcher agent
    """
    # Set up researcher-focused tool categories
    tool_categories = kwargs.pop("tool_categories", ["research", "file", "content"])

    return create_agent(
        agent_type=agent_type,
        agent_id=agent_id,
        name=name,
        role_type="researcher",
        role_kwargs={"additional_context": additional_context},
        reasoning_framework=reasoning_framework,
        use_tools=use_tools,
        enable_mcp=use_tools,  # Enable MCP if tools are enabled
        tool_categories=tool_categories,
        **kwargs,
    )


def create_tool_agent(
    agent_id: Optional[str] = None,
    name: str = "Tool Agent",
    role_type: Optional[str] = None,
    agent_type: str = "llm",
    reasoning_framework: str = "react",
    tool_categories: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
    **kwargs: Any,
) -> AgentProtocol:
    """Create a generic tool-enabled agent with specified tools.

    Args:
        agent_id: Optional unique identifier
        name: Human-readable name
        role_type: Optional role type to assign
        agent_type: Type of agent to create
        reasoning_framework: Reasoning framework to use (default: 'react')
        tool_categories: Optional categories of tools to include
        tool_names: Optional specific tool names to include
        **kwargs: Additional agent parameters

    Returns:
        Tool-enabled agent
    """
    return create_agent(
        agent_type=agent_type,
        agent_id=agent_id,
        name=name,
        role_type=role_type,
        reasoning_framework=reasoning_framework,
        use_tools=True,
        enable_mcp=True,
        tool_categories=tool_categories,
        tool_names=tool_names,
        **kwargs,
    )
