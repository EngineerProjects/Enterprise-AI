"""
Enterprise AI Agent Module.

This module provides the agent framework for Enterprise AI, enabling the creation
of AI agents that can process tasks and use tools through various reasoning patterns.
"""

from enterprise_ai.agent.base import Agent
from enterprise_ai.agent.factory import create_agent
from enterprise_ai.agent.role import AgentRole

# Reasoning patterns (self-contained classes)
from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.reasoning.cot import ChainOfThoughtPattern
from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringPattern

# Profile system - simplified approach
from enterprise_ai.agent.profile import ProfileManager

__all__ = [
    # Core agent classes
    'Agent',
    'create_agent',
    'AgentRole',
    
    # Reasoning patterns (self-contained)
    'ReActPattern',
    'ChainOfThoughtPattern',
    'SoftwareEngineeringPattern',
    
    # Profile system (simplified)
    'ProfileManager',
]