"""
Reasoning frameworks for Enterprise AI agents.

This module provides different reasoning frameworks that agents can use
to structure their thinking and decision-making processes, including
specialized approaches for different types of tasks.
"""

from typing import Dict, List, Type

from enterprise_ai.agent.reasoning.base import (
    ReasoningFramework,
    ToolBasedReasoning,
    BaseReasoning,
    register_framework,
    get_framework,
    list_frameworks,
    get_framework_descriptions,
)

# Import reasoning framework implementations
from enterprise_ai.agent.reasoning.react import ReActReasoning
from enterprise_ai.agent.reasoning.cot import ChainOfThoughtReasoning, ToolAugmentedCoT
from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringReasoning
from enterprise_ai.agent.reasoning.mcp import MCPReasoning

# Register the available frameworks
register_framework("react", ReActReasoning())
register_framework("cot", ChainOfThoughtReasoning())
register_framework("tool_cot", ToolAugmentedCoT())
register_framework("swe", SoftwareEngineeringReasoning())
register_framework("mcp", MCPReasoning())

__all__ = [
    # Base classes
    "ReasoningFramework",
    "ToolBasedReasoning",
    "BaseReasoning",
    # Framework registry functions
    "register_framework",
    "get_framework",
    "list_frameworks",
    "get_framework_descriptions",
    # Framework implementations
    "ReActReasoning",
    "ChainOfThoughtReasoning",
    "ToolAugmentedCoT",
    "SoftwareEngineeringReasoning",
    "MCPReasoning",
]
