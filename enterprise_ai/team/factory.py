"""
Enterprise AI Team - Team Factory.

Factory functions for creating teams.
"""

from typing import Dict, List, Optional, Any, Union

from enterprise_ai.agent import Agent, create_agent
from enterprise_ai.agent.role import AgentRole
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.team.base import Team
from enterprise_ai.team.manager import ManagerAgent
from enterprise_ai.team.memory.shared import SharedMemory
from enterprise_ai.team.communication.protocol import CommunicationProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.factory")


def create_empty_team(
    name: str,
    shared_memory: Optional[SharedMemory] = None,
    communication_protocol: Optional[CommunicationProtocol] = None,
    verbose: bool = False
) -> Team:
    """
    Create an empty team without any agents.
    
    Args:
        name: Team name
        shared_memory: Shared memory for the team
        communication_protocol: Protocol for agent communication
        verbose: Enable verbose logging
        
    Returns:
        Empty Team instance
    """
    team = Team(
        name=name,
        shared_memory=shared_memory,
        communication_protocol=communication_protocol,
        verbose=verbose
    )
    
    if verbose:
        logger.info(f"Created empty team '{name}'")
    
    return team


def create_agent_for_team(
    name: str,
    role: AgentRole,
    llm: Optional[LLMProvider] = None,
    mcp: Optional[ToolMCP] = None,
    reasoning_pattern: str = "react",
    llm_config: Optional[Dict[str, Any]] = None,
    mcp_config: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> Agent:
    """
    Create an agent that can be added to a team.
    
    Args:
        name: Agent name
        role: Agent role
        llm: LLM provider (created from llm_config if not provided)
        mcp: MCP executor (created with defaults if not provided)
        reasoning_pattern: Reasoning pattern name
        llm_config: Configuration for creating LLM (if llm not provided)
        mcp_config: Configuration for creating MCP (if mcp not provided)
        verbose: Enable verbose logging
        
    Returns:
        Agent instance
    """
    # Create LLM if not provided
    if llm is None:
        llm_defaults = {
            "provider_name": "ollama",
            "model_name": "llama3.2",
            "timeout": 60.0,
            "verbose": verbose
        }
        
        if llm_config:
            llm_defaults.update(llm_config)
            
        provider_name = llm_defaults.pop("provider_name")
        model_name = llm_defaults.pop("model_name")
            
        llm = create_provider(provider_name, model_name, **llm_defaults)
        if verbose:
            logger.info(f"Created LLM provider: {provider_name}/{model_name}")
            
    # Create MCP if not provided
    if mcp is None:
        mcp_defaults = {
            "timeout": 30.0,
            "auto_load_tools": True
        }
        
        if mcp_config:
            mcp_defaults.update(mcp_config)
            
        mcp = ToolMCP(**mcp_defaults)
        if verbose:
            logger.info(f"Created MCP with {len(mcp.get_available_tools())} tools")
    
    # Create agent
    agent = create_agent(
        name=name,
        role=role,
        llm=llm,
        mcp=mcp,
        reasoning_pattern=reasoning_pattern,
        verbose=verbose
    )
    
    if verbose:
        logger.info(f"Created agent '{name}' with '{reasoning_pattern}' reasoning")
    
    return agent


def create_manager_agent(
    name: str,
    role: AgentRole,
    team_agents: List[str],
    llm: Optional[LLMProvider] = None,
    mcp: Optional[ToolMCP] = None,
    reasoning_pattern: str = "react",
    llm_config: Optional[Dict[str, Any]] = None,
    mcp_config: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> ManagerAgent:
    """
    Create a manager agent for a team.
    
    Args:
        name: Agent name
        role: Agent role
        team_agents: List of worker agent names
        llm: LLM provider (created from llm_config if not provided)
        mcp: MCP executor (created with defaults if not provided)
        reasoning_pattern: Reasoning pattern name
        llm_config: Configuration for creating LLM (if llm not provided)
        mcp_config: Configuration for creating MCP (if mcp not provided)
        verbose: Enable verbose logging
        
    Returns:
        ManagerAgent instance
    """
    # Create LLM if not provided
    if llm is None:
        llm_defaults = {
            "provider_name": "ollama",
            "model_name": "llama3.2",
            "timeout": 60.0,
            "verbose": verbose
        }
        
        if llm_config:
            llm_defaults.update(llm_config)
            
        provider_name = llm_defaults.pop("provider_name")
        model_name = llm_defaults.pop("model_name")
            
        llm = create_provider(provider_name, model_name, **llm_defaults)
        if verbose:
            logger.info(f"Created LLM provider: {provider_name}/{model_name}")
            
    # Create MCP if not provided
    if mcp is None:
        mcp_defaults = {
            "timeout": 30.0,
            "auto_load_tools": True
        }
        
        if mcp_config:
            mcp_defaults.update(mcp_config)
            
        mcp = ToolMCP(**mcp_defaults)
        if verbose:
            logger.info(f"Created MCP with {len(mcp.get_available_tools())} tools")
    
    # Create manager agent
    manager = ManagerAgent(
        name=name,
        role=role,
        llm=llm,
        mcp=mcp,
        reasoning_pattern=reasoning_pattern,
        team_agents=team_agents,
        verbose=verbose
    )
    
    if verbose:
        logger.info(f"Created manager agent '{name}' with '{reasoning_pattern}' reasoning")
    
    return manager


def create_team(
    name: str,
    agent_roles: Dict[str, AgentRole],
    manager_role: Optional[AgentRole] = None,
    llm: Optional[LLMProvider] = None,
    mcp: Optional[ToolMCP] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    mcp_config: Optional[Dict[str, Any]] = None,
    reasoning_patterns: Optional[Dict[str, str]] = None,
    shared_memory: Optional[SharedMemory] = None,
    communication_protocol: Optional[CommunicationProtocol] = None,
    verbose: bool = False
) -> Team:
    """
    Create a complete team with all agents in one go.
    
    Args:
        name: Team name
        agent_roles: Dictionary mapping agent names to their roles
        manager_role: Role for the manager agent (optional)
        llm: LLM provider (created from llm_config if not provided)
        mcp: MCP executor (created with defaults if not provided)
        llm_config: Configuration for creating LLM (if llm not provided)
        mcp_config: Configuration for creating MCP (if mcp not provided)
        reasoning_patterns: Dictionary mapping agent names to reasoning patterns
        shared_memory: Shared memory for the team
        communication_protocol: Protocol for agent communication
        verbose: Enable verbose logging
        
    Returns:
        Configured Team instance
    """
    # Create empty team
    team = create_empty_team(
        name=name,
        shared_memory=shared_memory,
        communication_protocol=communication_protocol,
        verbose=verbose
    )
    
    # Create LLM if not provided
    if llm is None:
        llm_defaults = {
            "provider_name": "ollama",
            "model_name": "llama3.2",
            "timeout": 60.0,
            "verbose": verbose
        }
        
        if llm_config:
            llm_defaults.update(llm_config)
            
        provider_name = llm_defaults.pop("provider_name")
        model_name = llm_defaults.pop("model_name")
            
        llm = create_provider(provider_name, model_name, **llm_defaults)
        if verbose:
            logger.info(f"Created LLM provider: {provider_name}/{model_name}")
            
    # Create MCP if not provided
    if mcp is None:
        mcp_defaults = {
            "timeout": 30.0,
            "auto_load_tools": True
        }
        
        if mcp_config:
            mcp_defaults.update(mcp_config)
            
        mcp = ToolMCP(**mcp_defaults)
        if verbose:
            logger.info(f"Created MCP with {len(mcp.get_available_tools())} tools")
    
    # Set default reasoning patterns if not provided
    if reasoning_patterns is None:
        reasoning_patterns = {name: "react" for name in agent_roles.keys()}
        if manager_role:
            reasoning_patterns["manager"] = "react"
    
    # Create worker agents
    for agent_name, role in agent_roles.items():
        reasoning = reasoning_patterns.get(agent_name, "react")
        
        agent = create_agent_for_team(
            name=agent_name,
            role=role,
            llm=llm,
            mcp=mcp,
            reasoning_pattern=reasoning,
            verbose=verbose
        )
        
        team.add_agent(agent_name, agent)
    
    # Create manager agent if role provided
    if manager_role:
        manager_reasoning = reasoning_patterns.get("manager", "react")
        
        manager = create_manager_agent(
            name="manager",
            role=manager_role,
            llm=llm,
            mcp=mcp,
            reasoning_pattern=manager_reasoning,
            team_agents=list(team.agents.keys()),
            verbose=verbose
        )
        
        team.set_manager(manager)
    
    if verbose:
        logger.info(f"Created team '{name}' with {len(team.agents)} agents")
    
    return team