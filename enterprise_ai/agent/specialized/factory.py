"""
Agent factory for creating specialized Enterprise AI agents.
Provides easy creation of pre-configured agent types.
"""

from typing import Any, Dict, Optional

from enterprise_ai.agent.specialized.general_purpose import GeneralPurposeAgent
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.specialized.factory")


def create_agent(
    agent_type: str,
    name: str,
    llm_provider,
    mcp_server,
    **kwargs
) -> Any:
    """
    Create a specialized agent of the specified type.
    
    Args:
        agent_type: Type of agent ("general", "developer", "researcher", "browser")
        name: Name for the agent instance
        llm_provider: LLM provider instance
        mcp_server: MCP server instance
        **kwargs: Additional configuration options
        
    Returns:
        Configured agent instance
    """
    
    if agent_type.lower() == "general":
        return GeneralPurposeAgent(
            name=name,
            llm_provider=llm_provider,
            mcp_server=mcp_server,
            **kwargs
        )
    elif agent_type.lower() == "developer":
        # Create developer-focused general agent
        return GeneralPurposeAgent(
            name=name,
            llm_provider=llm_provider,
            mcp_server=mcp_server,
            specialization="coding",
            **kwargs
        )
    elif agent_type.lower() == "researcher":
        # Create research-focused general agent
        return GeneralPurposeAgent(
            name=name,
            llm_provider=llm_provider,
            mcp_server=mcp_server,
            specialization="research",
            **kwargs
        )
    elif agent_type.lower() == "browser":
        # Create browser-focused general agent
        return GeneralPurposeAgent(
            name=name,
            llm_provider=llm_provider,
            mcp_server=mcp_server,
            specialization="browser",
            **kwargs
        )
    else:
        raise ValueError(f"Unknown agent type: {agent_type}")


def get_available_agent_types() -> Dict[str, str]:
    """Get available agent types and descriptions."""
    return {
        "general": "Versatile agent for various tasks (coding, research, automation)",
        "developer": "Specialized for software development and coding tasks", 
        "researcher": "Optimized for information gathering and research",
        "browser": "Focused on web automation and browser interactions"
    }


# Convenience functions
async def create_general_agent(name: str, llm_provider, mcp_server, **kwargs):
    """Create a general-purpose agent."""
    return create_agent("general", name, llm_provider, mcp_server, **kwargs)


async def create_developer_agent(name: str, llm_provider, mcp_server, **kwargs):
    """Create a developer agent."""
    return create_agent("developer", name, llm_provider, mcp_server, **kwargs)


async def create_researcher_agent(name: str, llm_provider, mcp_server, **kwargs):
    """Create a researcher agent."""
    return create_agent("researcher", name, llm_provider, mcp_server, **kwargs)


async def create_browser_agent(name: str, llm_provider, mcp_server, **kwargs):
    """Create a browser automation agent."""
    return create_agent("browser", name, llm_provider, mcp_server, **kwargs)
