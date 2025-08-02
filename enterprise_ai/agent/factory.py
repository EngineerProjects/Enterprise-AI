"""
Enterprise AI Agent - Agent Factory.

Simple factory function for creating agents with minimal configuration.
"""

from typing import Optional, Dict, Any, Union, List

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
    role: Optional[Union[str, AgentRole]] = None,
    role_config: Optional[Dict[str, Any]] = None,
    reasoning_pattern: str = "react",
    llm: Optional[LLMProvider] = None,
    llm_config: Optional[Dict[str, Any]] = None,
    mcp: Optional[ToolMCP] = None,
    mcp_config: Optional[Dict[str, Any]] = None,
    memory: Optional[ConversationMemory] = None,
    verbose: bool = False,
) -> Agent:
    """
    Create an agent with minimal configuration or detailed config dictionaries.
    
    Supports both simple component-based creation and config-based creation:
    
    Config-based (simple):
        agent = create_agent(
            name="DataBot",
            role_config={"name": "Analyst", "system_prompt": "..."},
            mcp_config={"tools": ["python"], "timeout": 1000},
            llm_config={"model_name": "llama3.2", "timeout": 1000}
        )
    
    Component-based (advanced):
        agent = create_agent(name="DataBot", role=custom_role, mcp=custom_mcp, llm=custom_llm)
    
    Args:
        name: Agent name
        role: Agent role instance or role name string
        role_config: Configuration dict for creating role (alternative to role param)
        reasoning_pattern: Pattern name ("react", "cot", "swe")
        llm: LLM provider instance (created from llm_config if not provided)
        llm_config: Configuration for creating LLM provider
        mcp: MCP executor instance (created from mcp_config if not provided)
        mcp_config: Configuration for creating MCP executor
        memory: Conversation memory (defaults to InMemoryConversation)
        verbose: Enable verbose logging
        
    Returns:
        Configured Agent instance with auto-generated profile
        
    Raises:
        ValueError: If invalid parameters or missing required config
    """
    # Create or process role
    if role_config and not role:
        # Create role from configuration dictionary
        role = AgentRole.from_config(role_config)
        if verbose:
            logger.info(f"Created role from config: '{role.name}'")
    elif isinstance(role, str):
        # Create a basic role from the name
        role = AgentRole(
            name=role,
            description=f"{role} Agent"
        )
    elif role is None:
        raise ValueError("Either 'role' or 'role_config' must be provided")
    elif not isinstance(role, AgentRole):
        raise ValueError("Role must be a string, AgentRole instance, or use role_config")
    
    # Create LLM if not provided
    if llm is None:
        # Get default configuration and merge with user config
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
            
    # Create MCP if not provided
    if mcp is None:
        # Get defaults and merge with user config
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
    elif reasoning_pattern.lower() == "enhanced_react":
        from enterprise_ai.agent.reasoning.react import EnhancedReActPattern
        pattern_cls = EnhancedReActPattern
    elif reasoning_pattern.lower() == "metacognitive":
        from enterprise_ai.agent.reasoning.metacognitive import MetaCognitiveEngine
        pattern_cls = MetaCognitiveEngine
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


def create_simple_mcp(
    timeout: float = 30.0,
    tools: Optional[List[str]] = None,
    sandbox_config: Optional[Dict[str, Any]] = None
) -> ToolMCP:
    """
    Create a simple MCP instance with specified tools.
    
    Args:
        timeout: Request timeout in seconds
        tools: List of tool names to enable
        sandbox_config: Optional sandbox configuration
        
    Returns:
        Configured ToolMCP instance
    """
    params = {"timeout": timeout}
    
    if tools is not None:
        params["tools"] = tools
    if sandbox_config is not None:
        params["sandbox_config"] = sandbox_config
        
    return ToolMCP(**params)


def create_simple_llm(
    model_name: str,
    provider: str = "ollama",
    timeout: float = 30.0,
    **kwargs
) -> LLMProvider:
    """
    Create a simple LLM provider instance.
    
    Args:
        model_name: Model name to use
        provider: Provider name (default: "ollama")
        timeout: Request timeout in seconds
        **kwargs: Additional provider-specific parameters
        
    Returns:
        Configured LLMProvider instance
    """
    return create_provider(provider, model_name, timeout=timeout, **kwargs)