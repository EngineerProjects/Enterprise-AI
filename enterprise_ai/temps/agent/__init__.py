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
    create_tool_agent,
)

from enterprise_ai.agent.tooling import AgentToolManager

# Import reasoning framework components
from enterprise_ai.agent.reasoning.base import (
    ReasoningFramework,
    ToolBasedReasoning,
    BaseReasoning,
    register_framework,
    get_framework,
    list_frameworks,
    get_framework_descriptions,
)

# Import specific reasoning implementations
from enterprise_ai.agent.reasoning import (
    ReActReasoning,
    ChainOfThoughtReasoning,
    ToolAugmentedCoT,
    SoftwareEngineeringReasoning,
    MCPReasoning,
)

# Import tool integration utilities
from enterprise_ai.agent.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
)


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
    "create_tool_agent",
    # Tooling
    "AgentToolManager",
    # Reasoning frameworks
    "ReasoningFramework",
    "ToolBasedReasoning",
    "BaseReasoning",
    "register_framework",
    "get_framework",
    "list_frameworks",
    "get_framework_descriptions",
    # Reasoning implementations
    "ReActReasoning",
    "ChainOfThoughtReasoning",
    "ToolAugmentedCoT",
    "SoftwareEngineeringReasoning",
    "MCPReasoning",
    # Tool integration
    "parse_message_for_tool_calls",
    "format_tool_response_message",
    "get_tool_prompt_for_reasoning",
]
