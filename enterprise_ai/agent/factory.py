"""
Enterprise AI Agent - Agent Factory.

Simple factory function for creating agents with minimal configuration.
"""

from typing import Optional, Dict, Any, Union

from enterprise_ai.agent.base import Agent
from enterprise_ai.agent.role import AgentRole

from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.reasoning.cot import ChainOfThoughtPattern
from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringPattern
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.defaults import get_default_llm_config, get_default_tool_config
from enterprise_ai.schema.memory import ConversationMemory, InMemoryConversation
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.factory")


def create_agent(
    name: str,
    role: Union[str, AgentRole],
    reasoning_pattern: str = "react",
    llm: Optional[LLMProvider] = None,
    mcp: Optional[ToolMCP] = None,
    memory: Optional[ConversationMemory] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    mcp_config: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
) -> Agent:
    """
    Create an agent with minimal configuration.
    
    Args:
        name: Agent name
        role: Agent role or role name (for creating a basic role)
        reasoning_pattern: Pattern name ("react", "cot", "swe")
        llm: LLM provider (created from llm_config if not provided)
        mcp: MCP executor (created with defaults if not provided)
        memory: Conversation memory (defaults to InMemoryConversation)
        llm_config: Configuration for creating LLM (if llm not provided)
        mcp_config: Configuration for creating MCP (if mcp not provided)
        verbose: Enable verbose logging
        
    Returns:
        Configured Agent instance
        
    Raises:
        ValueError: If invalid reasoning pattern specified
    """
    # Create or process role
    if isinstance(role, str):
        # Create a role from the name - prompt will be auto-generated
        role = AgentRole(
            name=role,
            description=f"{role} Agent"
        )
    elif not isinstance(role, AgentRole):
        raise ValueError("Role must be a string or AgentRole instance")
    
    # Create LLM if not provided using smart defaults
    if llm is None:
        # Get default configuration for the provider
        default_provider = "ollama"
        llm_defaults = get_default_llm_config(default_provider)
        llm_defaults.update({"verbose": verbose})
        
        if llm_config:
            llm_defaults.update(llm_config)
            
        provider = llm_defaults.pop("provider", default_provider)
        model_name = llm_defaults.pop("model_name")
            
        llm = create_provider(provider, model_name, **llm_defaults)
        if verbose:
            logger.info(f"Created LLM provider: {provider}/{model_name}")
            
    # Create MCP if not provided using smart defaults
    if mcp is None:
        mcp_defaults = get_default_tool_config()
        
        if mcp_config:
            mcp_defaults.update(mcp_config)
        
        # Filter parameters to only include what ToolMCP accepts
        mcp_params = {
            "timeout": mcp_defaults.get("timeout", 30.0),
        }
        
        # Add optional parameters if provided in config
        if "sandbox_config" in mcp_defaults:
            mcp_params["sandbox_config"] = mcp_defaults["sandbox_config"]
        if "tools" in mcp_defaults:
            mcp_params["tools"] = mcp_defaults["tools"]
            
        mcp = ToolMCP(**mcp_params)
        if verbose:
            logger.info(f"Created MCP with {len(mcp.get_available_tools())} tools")
    
    # Create appropriate reasoning pattern
    pattern_cls = None
    if reasoning_pattern.lower() == "react":
        pattern_cls = ReActPattern
    elif reasoning_pattern.lower() == "cot":
        pattern_cls = ChainOfThoughtPattern
    elif reasoning_pattern.lower() == "swe":
        pattern_cls = SoftwareEngineeringPattern
    else:
        raise ValueError(f"Unknown reasoning pattern: {reasoning_pattern}")
        
    reasoning = pattern_cls()
    
    # Create memory if not provided
    if memory is None:
        memory = InMemoryConversation()
    
    # Create and return agent
    return Agent(
        name=name,
        role=role,
        llm=llm,
        mcp=mcp,
        reasoning_pattern=reasoning,
        memory=memory,
        verbose=verbose
    )