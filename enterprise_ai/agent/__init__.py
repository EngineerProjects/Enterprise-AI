"""
Enterprise AI Agent Module.

This module provides the agent framework for Enterprise AI, enabling the creation
of AI agents that can process tasks and use tools through various reasoning patterns.
"""

from enterprise_ai.agent.base import Agent
from enterprise_ai.agent.factory import create_agent, create_simple_mcp, create_simple_llm
from enterprise_ai.agent.role import AgentRole

# Reasoning patterns (self-contained classes)
from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.reasoning.react import EnhancedReActPattern
from enterprise_ai.agent.reasoning.metacognitive import MetaCognitiveEngine
from enterprise_ai.agent.reasoning.cot import ChainOfThoughtPattern
from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringPattern

__all__ = [
    # Core agent classes
    'Agent',
    'create_agent',
    'AgentRole',
    
    # Helper factory functions
    'create_simple_mcp',
    'create_simple_llm',
    
    # Reasoning patterns (self-contained)
    'ReActPattern',
    'EnhancedReActPattern', 
    'MetaCognitiveEngine',
    'ChainOfThoughtPattern',
    'SoftwareEngineeringPattern',
]