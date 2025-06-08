"""
Factory for creating Enterprise AI agents.
"""

from typing import Any, Dict, List, Optional, Type

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.agent.config import AgentConfig, LLMProvider
from enterprise_ai.agent.core import EnterpriseAgent
from enterprise_ai.agent.base import BaseAgent

logger = get_optimized_logger("agent.factory")


def create_agent(
    llm_provider: Optional[str] = None, 
    model_name: Optional[str] = None,
    agent_id: Optional[str] = None,
    name: Optional[str] = None,
    **kwargs: Any
) -> BaseAgent:
    """
    Create an agent with simplified parameters.
    
    Args:
        llm_provider: LLM provider ("openai" or "ollama")
        model_name: Model name to use
        agent_id: Optional agent ID
        name: Optional agent name
        **kwargs: Additional configuration
        
    Returns:
        Configured agent instance
    """
    config = AgentConfig(
        llm_provider=LLMProvider(llm_provider),
        model_name=model_name,
        agent_id=agent_id,
        name=name,
        **kwargs
    )
    
    return EnterpriseAgent(config)