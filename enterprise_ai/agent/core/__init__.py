"""
Core agent components for Enterprise AI.

This module provides the foundational agent types, base classes,
and factory functions for creating various agent implementations.
"""

from enterprise_ai.agent.core.types import (
    AgentProtocol,
    AgentRole,
    AgentState,
    AgentMemory,
    AgentMessage,
    Task,
    TaskStatus,
    ToolCapabilityProtocol,
    ToolInteractionType,
)

from enterprise_ai.agent.core.base import BaseAgent, LLMAgent

from enterprise_ai.agent.core.factory import (
    create_agent,
    AgentBuilder,
    create_developer_agent,
    create_manager_agent,
    create_researcher_agent,
    create_tool_agent,
    create_data_scientist_agent,
    create_agents_from_config,
)

__all__ = [
    # Types and protocols
    "AgentProtocol",
    "AgentRole",
    "AgentState",
    "AgentMemory",
    "AgentMessage",
    "Task",
    "TaskStatus",
    "ToolCapabilityProtocol",
    "ToolInteractionType",
    # Agent implementations
    "BaseAgent",
    "LLMAgent",
    # Factory functions
    "create_agent",
    "AgentBuilder",
    "create_developer_agent",
    "create_manager_agent",
    "create_researcher_agent",
    "create_tool_agent",
    "create_data_scientist_agent",
    "create_agents_from_config",
]
