"""
Enterprise AI Agent - Reasoning Patterns.

This module provides different reasoning patterns that agents can use to approach tasks.
"""

from enterprise_ai.agent.reasoning.base import ReasoningPattern
from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.reasoning.cot import ChainOfThoughtPattern 
from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringPattern

__all__ = [
    'ReasoningPattern',
    'ReActPattern',
    'ChainOfThoughtPattern',
    'SoftwareEngineeringPattern',
]