"""
Agent module for Enterprise AI.

This module provides the core agent system that forms the foundation
of the Enterprise AI framework, enabling intelligent agents to
collaborate and execute tasks.
"""

from enterprise_ai.agent.types import (
    AgentProtocol,
    AgentRole,
    AgentState,
    AgentMemory,
    AgentMessage,
    Task,
    TaskStatus,
)

from enterprise_ai.agent.memory import (
    DictMemory,
    NamespacedMemory,
    ScopedMemory,
    create_memory,
)

from enterprise_ai.agent.state import (
    BaseAgentState,
    ConversationState,
    create_agent_state,
)

from enterprise_ai.agent.role import (
    BaseAgentRole,
    SimpleRole,
    TemplatedRole,
    DeveloperRole,
    ManagerRole,
    ResearcherRole,
    create_role,
)

from enterprise_ai.agent.message import (
    BaseAgentMessage,
    TaskAssignmentMessage,
    TaskUpdateMessage,
    QueryMessage,
    ResponseMessage,
    BroadcastMessage,
    NotificationMessage,
    ErrorMessage,
    create_message,
)

from enterprise_ai.agent.base import (
    BaseAgent,
    LLMAgent,
)

from enterprise_ai.agent.factory import (
    create_agent,
    AgentBuilder,
    create_developer_agent,
    create_manager_agent,
    create_researcher_agent,
)

from enterprise_ai.agent.tooling import AgentToolManager


__all__ = [
    # Types
    "AgentProtocol",
    "AgentRole",
    "AgentState",
    "AgentMemory",
    "AgentMessage",
    "Task",
    "TaskStatus",
    # Memory
    "DictMemory",
    "NamespacedMemory",
    "ScopedMemory",
    "create_memory",
    # State
    "BaseAgentState",
    "ConversationState",
    "create_agent_state",
    # Roles
    "BaseAgentRole",
    "SimpleRole",
    "TemplatedRole",
    "DeveloperRole",
    "ManagerRole",
    "ResearcherRole",
    "create_role",
    # Messages
    "BaseAgentMessage",
    "TaskAssignmentMessage",
    "TaskUpdateMessage",
    "QueryMessage",
    "ResponseMessage",
    "BroadcastMessage",
    "NotificationMessage",
    "ErrorMessage",
    "create_message",
    # Agents
    "BaseAgent",
    "LLMAgent",
    # Factory
    "create_agent",
    "AgentBuilder",
    "create_developer_agent",
    "create_manager_agent",
    "create_researcher_agent",
    # Tooling
    "AgentToolManager",
]
