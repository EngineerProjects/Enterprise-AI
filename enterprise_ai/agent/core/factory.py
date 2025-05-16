"""
Agent factory for Enterprise AI.

This module provides factory functions and patterns for creating
different types of agents with various configurations.
"""

import os
import json
from typing import Any, Dict, List, Optional, Set, Type, Union, cast

from enterprise_ai.agent.core.base import BaseAgent, LLMAgent
from enterprise_ai.agent.role import create_role
from enterprise_ai.agent.core.types import AgentProtocol, AgentRole
from enterprise_ai.agent.architecture.tools_manager import AgentToolsManager
from enterprise_ai.agent.tools.tooling import AgentToolManager
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.config import get_config, load_config
from enterprise_ai.logger import get_logger
from enterprise_ai.mcp.client import ToolFilterStrategy

logger = get_logger("agent.factory")


def extract_llm_provider_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Extract LLM provider kwargs from the agent creation kwargs.
    
    Args:
        kwargs: Agent creation kwargs
        
    Returns:
        Dictionary of LLM provider kwargs
    """
    # Extract the llm_provider_kwargs if present
    llm_provider_kwargs = kwargs.pop("llm_provider_kwargs", {}).copy()
    
    # Also check for direct provider parameters in kwargs
    direct_provider_params = {}
    for key in list(kwargs.keys()):
        if key in ("model_name", "base_url", "temperature", "max_tokens", "top_p", "timeout"):
            direct_provider_params[key] = kwargs.pop(key)
    
    # Merge them, with llm_provider_kwargs taking precedence
    return {**direct_provider_params, **llm_provider_kwargs}


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
    tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    capability_match_all: bool = False,
    config_path: Optional[str] = None,
    template_id: Optional[str] = None,
    filter_strategy: ToolFilterStrategy = ToolFilterStrategy.INCLUDE,
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
        tool_capabilities: Optional capabilities that tools should have
        capability_match_all: Whether tools must have all capabilities
        config_path: Optional path to configuration file
        template_id: Optional template identifier for agent creation
        filter_strategy: Whether to include or exclude specified tools
        **kwargs: Additional agent-specific parameters

    Returns:
        Agent implementation

    Raises:
        ValueError: If an unknown agent type is specified
    """
    # Load configuration from file if specified
    external_config = {}
    if config_path:
        try:
            external_config = load_config(config_path)
            logger.info(f"Loaded agent configuration from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load configuration from {config_path}: {e}")
    
    # Load from template if specified
    template_config = {}
    if template_id:
        try:
            template_path = os.path.join(get_config("agent.templates_directory", "templates"), f"{template_id}.json")
            if os.path.exists(template_path):
                with open(template_path, "r") as f:
                    template_config = json.load(f)
                logger.info(f"Applied agent template: {template_id}")
        except Exception as e:
            logger.warning(f"Failed to load template {template_id}: {e}")
    
    # Merge configurations (priority: kwargs > external_config > template_config)
    merged_config = {**template_config, **external_config}
    
    # Extract configuration values, preferring function parameters over config
    agent_type = agent_type or merged_config.get("agent_type", "base")
    name = name or merged_config.get("name", f"{agent_type.capitalize()}Agent")
    role_type = role_type or merged_config.get("role_type")
    role_kwargs = role_kwargs or merged_config.get("role", {})
    state_type = state_type or merged_config.get("state_type", "base" if agent_type == "base" else "conversation")
    state_kwargs = state_kwargs or merged_config.get("state", {})
    reasoning_framework = reasoning_framework or merged_config.get("reasoning_framework", "base")
    use_tools = use_tools if use_tools is not None else merged_config.get("use_tools", False)
    enable_mcp = enable_mcp if enable_mcp is not None else merged_config.get("enable_mcp", False)
    
    # Tool selection options
    tool_categories = tool_categories or merged_config.get("tool_categories", [])
    tool_names = tool_names or merged_config.get("tool_names", [])
    tool_capabilities = tool_capabilities or merged_config.get("tool_capabilities", [])
    capability_match_all = capability_match_all if capability_match_all is not None else merged_config.get("capability_match_all", False)
    filter_strategy_str = merged_config.get("filter_strategy", "include")
    if isinstance(filter_strategy_str, str) and not isinstance(filter_strategy, ToolFilterStrategy):
        filter_strategy = ToolFilterStrategy.INCLUDE if filter_strategy_str.lower() == "include" else ToolFilterStrategy.EXCLUDE

    # Set state directory from config if not specified
    if "state_dir" not in state_kwargs:
        state_dir = get_config("agent.state_directory", None)
        if state_dir:
            state_kwargs["state_dir"] = state_dir

    # Create agent based on type
    if agent_type.lower() == "base":
        # Base agents don't support tools or reasoning frameworks
        if use_tools:
            logger.warning("Base agents don't support tools. Use LLM agents instead.")

        agent = BaseAgent(
            agent_id=agent_id,
            name=name,
            role_type=role_type,
            role_kwargs=role_kwargs,
            state_type=state_type,
            state_kwargs=state_kwargs,
            **kwargs,
        )
        
        # Apply any remaining configuration
        if merged_config:
            if hasattr(agent, "update_config"):
                agent.update_config(merged_config)
                
        return agent
    
    elif agent_type.lower() == "llm":
        # Get LLM provider
        llm_provider = None
        provider_name = llm_provider_name or merged_config.get("llm_provider")
        
        # Extract provider parameters
        provider_kwargs = extract_llm_provider_kwargs(kwargs)
        
        # Set reasonable default timeout if not specified
        if "timeout" not in provider_kwargs:
            provider_kwargs["timeout"] = 300.0
        
        # Create the provider
        if provider_name:
            from enterprise_ai.llm import create_provider
            llm_provider = create_provider(provider_name, **provider_kwargs)
            logger.info(f"Created LLM provider: {provider_name} with parameters: {provider_kwargs}")
        else:
            from enterprise_ai.llm import get_default_provider
            llm_provider = get_default_provider(**provider_kwargs)
            logger.info(f"Created default LLM provider with parameters: {provider_kwargs}")

        # Create LLM agent with enhanced tool configuration
        agent = LLMAgent(
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
        
        # Apply any remaining configuration
        if merged_config:
            if hasattr(agent, "update_config"):
                agent.update_config(merged_config)
                
        return agent
    
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
        self._tool_categories: List[str] = []
        self._tool_names: List[str] = []
        self._tool_capabilities: List[Union[str, ToolCapability]] = []
        self._capability_match_all: bool = False
        self._config_path: Optional[str] = None
        self._template_id: Optional[str] = None
        self._filter_strategy: ToolFilterStrategy = ToolFilterStrategy.INCLUDE
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
    
    def with_tool_capabilities(
        self, 
        capabilities: List[Union[str, ToolCapability]], 
        match_all: bool = False
    ) -> "AgentBuilder":
        """Set tool capabilities to filter by.
        
        Args:
            capabilities: List of capabilities
            match_all: Whether tools must have all capabilities or just one
            
        Returns:
            Builder instance for chaining
        """
        self._tool_capabilities = capabilities
        self._capability_match_all = match_all
        return self
    
    def with_filter_strategy(self, strategy: ToolFilterStrategy) -> "AgentBuilder":
        """Set the tool filter strategy.
        
        Args:
            strategy: Include or exclude strategy for tools
            
        Returns:
            Builder instance for chaining
        """
        self._filter_strategy = strategy
        return self
    
    def from_template(self, template_id: str) -> "AgentBuilder":
        """Build agent from a template.
        
        Args:
            template_id: ID of the template to use
            
        Returns:
            Builder instance for chaining
        """
        self._template_id = template_id
        return self
    
    def from_config(self, config_path: str) -> "AgentBuilder":
        """Build agent from a configuration file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Builder instance for chaining
        """
        self._config_path = config_path
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
            tool_capabilities=self._tool_capabilities,
            capability_match_all=self._capability_match_all,
            config_path=self._config_path,
            template_id=self._template_id,
            filter_strategy=self._filter_strategy,
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
    tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    template_id: Optional[str] = "developer",
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
        tool_capabilities: Optional specific capabilities to include
        template_id: Optional template identifier
        **kwargs: Additional agent parameters

    Returns:
        Developer agent
    """
    # Set up developer-focused tool categories
    tool_categories = kwargs.pop("tool_categories", ["development", "file", "execution"])
    
    # Set up developer-focused capabilities if not specified
    if tool_capabilities is None:
        tool_capabilities = [
            "code_generation", 
            "code_execution", 
            "file_access", 
            "version_control", 
            "testing",
            "debugging"
        ]

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
        tool_capabilities=tool_capabilities,
        template_id=template_id,
        **kwargs,
    )


def create_manager_agent(
    agent_id: Optional[str] = None,
    name: str = "Manager",
    agent_type: str = "llm",
    additional_context: str = "",
    use_tools: bool = True,
    reasoning_framework: str = "cot",
    tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    template_id: Optional[str] = "manager",
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
        tool_capabilities: Optional specific capabilities to include
        template_id: Optional template identifier
        **kwargs: Additional agent parameters

    Returns:
        Manager agent
    """
    # Set up manager-focused tool categories
    tool_categories = kwargs.pop("tool_categories", ["planning", "utility", "productivity"])
    
    # Set up manager-focused capabilities if not specified
    if tool_capabilities is None:
        tool_capabilities = [
            "planning", 
            "scheduling", 
            "communication", 
            "task_management", 
            "coordination",
            "reporting"
        ]

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
        tool_capabilities=tool_capabilities,
        template_id=template_id,
        **kwargs,
    )


def create_researcher_agent(
    agent_id: Optional[str] = None,
    name: str = "Researcher",
    agent_type: str = "llm",
    additional_context: str = "",
    use_tools: bool = True,
    reasoning_framework: str = "react",
    tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    template_id: Optional[str] = "researcher",
    **kwargs: Any,
) -> AgentProtocol:
    """Create a researcher agent with appropriate tools and reasoning.

    Args:
        agent_id: Optional unique identifier
        name: Human-readable name
        agent_type: Type of agent to create
        additional_context: Additional role-specific context
        use_tools: Whether to enable research tools
        reasoning_framework: Reasoning framework to use (default: 'react')
        tool_capabilities: Optional specific capabilities to include
        template_id: Optional template identifier
        **kwargs: Additional agent parameters

    Returns:
        Researcher agent
    """
    # Set up researcher-focused tool categories
    tool_categories = kwargs.pop("tool_categories", ["research", "file", "content", "analysis"])
    
    # Set up researcher-focused capabilities if not specified
    if tool_capabilities is None:
        tool_capabilities = [
            "research", 
            "information_retrieval", 
            "data_analysis", 
            "document_processing", 
            "search",
            "synthesis"
        ]

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
        tool_capabilities=tool_capabilities,
        template_id=template_id,
        **kwargs,
    )


def create_data_scientist_agent(
    agent_id: Optional[str] = None,
    name: str = "Data Scientist",
    agent_type: str = "llm",
    additional_context: str = "",
    use_tools: bool = True,
    reasoning_framework: str = "react",
    template_id: Optional[str] = "data_scientist",
    **kwargs: Any,
) -> AgentProtocol:
    """Create a data scientist agent with appropriate tools and reasoning.

    Args:
        agent_id: Optional unique identifier
        name: Human-readable name
        agent_type: Type of agent to create
        additional_context: Additional role-specific context
        use_tools: Whether to enable data science tools
        reasoning_framework: Reasoning framework to use (default: 'react')
        template_id: Optional template identifier
        **kwargs: Additional agent parameters

    Returns:
        Data Scientist agent
    """
    # Set up data science-focused tool categories
    tool_categories = kwargs.pop(
        "tool_categories", ["analysis", "data_processing", "visualization", "file"]
    )
    
    # Set up data science-focused capabilities
    tool_capabilities = kwargs.pop("tool_capabilities", [
        "data_analysis", 
        "data_visualization", 
        "statistical_analysis", 
        "machine_learning", 
        "data_processing",
        "reporting"
    ])

    return create_agent(
        agent_type=agent_type,
        agent_id=agent_id,
        name=name,
        role_type="data_scientist",
        role_kwargs={"additional_context": additional_context},
        reasoning_framework=reasoning_framework,
        use_tools=use_tools,
        enable_mcp=use_tools,
        tool_categories=tool_categories,
        tool_capabilities=tool_capabilities,
        template_id=template_id,
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
    tool_capabilities: Optional[List[Union[str, ToolCapability]]] = None,
    capability_match_all: bool = False,
    filter_strategy: ToolFilterStrategy = ToolFilterStrategy.INCLUDE,
    template_id: Optional[str] = None,
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
        tool_capabilities: Optional tool capabilities to filter by
        capability_match_all: Whether tools must match all capabilities
        filter_strategy: Whether to include or exclude specified tools
        template_id: Optional template identifier
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
        tool_capabilities=tool_capabilities,
        capability_match_all=capability_match_all,
        filter_strategy=filter_strategy,
        template_id=template_id,
        **kwargs,
    )


def create_agents_from_config(config_path: str) -> Dict[str, AgentProtocol]:
    """Create multiple agents from a configuration file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary mapping agent IDs to agent instances
        
    Raises:
        ValueError: If configuration is invalid
    """
    try:
        config = load_config(config_path)
        if not isinstance(config, dict) or "agents" not in config:
            raise ValueError("Invalid configuration: must contain 'agents' section")
            
        agents = {}
        for agent_id, agent_config in config["agents"].items():
            # Ensure agent_id is set in the config
            agent_config["agent_id"] = agent_id
            
            # Create agent from configuration
            try:
                agent = create_agent(**agent_config)
                agents[agent_id] = agent
                logger.info(f"Created agent '{agent_id}' from configuration")
            except Exception as e:
                logger.error(f"Failed to create agent '{agent_id}': {e}")
                
        return agents
    except Exception as e:
        logger.error(f"Failed to load agent configuration: {e}")
        raise ValueError(f"Failed to load agent configuration: {e}")