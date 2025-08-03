"""
Enterprise AI Agent - Reasoning Patterns.

UPDATED: Added BaseReasoningPattern and EnhancedReActPattern exports.
Self-contained reasoning patterns with consistent base functionality.
"""

from enterprise_ai.agent.reasoning.base import BaseReasoningPattern  # ADDED: Base class
from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.reasoning.cot import ChainOfThoughtPattern 
from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringPattern
from enterprise_ai.agent.reasoning.metacognitive import MetaCognitiveEngine
from enterprise_ai.agent.reasoning.structured_react import EnhancedReActPattern  # ADDED: Enhanced ReAct

__all__ = [
    'BaseReasoningPattern',  # ADDED: Base class export
    'ReActPattern',
    'ChainOfThoughtPattern',
    'SoftwareEngineeringPattern',
    'MetaCognitiveEngine',
    'EnhancedReActPattern',  # ADDED: Enhanced ReAct export
]