"""
Agent module for Enterprise AI.

This module provides the core agent system that forms the foundation
of the Enterprise AI framework, enabling intelligent agents to
collaborate and execute tasks.
"""

# Re-export all public components for backward compatibility

# Core agent components
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

# Memory and state
from enterprise_ai.agent.state.memory import (
    DictMemory,
    NamespacedMemory,
    ScopedMemory,
    create_memory,
)
from enterprise_ai.agent.state.state import (
    BaseAgentState,
    ConversationState,
    ToolAwareState,
    MCPSessionState,
    create_agent_state,
)

# Role definitions
from enterprise_ai.agent.role.role import (
    BaseAgentRole,
    SimpleRole,
    TemplatedRole,
    DeveloperRole,
    ManagerRole,
    ResearcherRole,
    create_role,
)

# Messaging
from enterprise_ai.agent.messaging.message import (
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

# Tool integration
from enterprise_ai.agent.tools.tooling import (
    AgentToolManager,
    ToolUsageMetrics,
)
from enterprise_ai.agent.tools.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
    validate_tool_parameters,
    get_tool_error_handling_prompt,
    get_tool_capabilities_description,
    execute_tool_with_retry,
    ToolIntegrationError,
    FunctionCallingFormatter,
    merge_tool_schemas,
)

# Import and re-export reasoning frameworks
from enterprise_ai.agent.reasoning import (
    ReasoningFramework,
    ToolBasedReasoning,
    BaseReasoning,
    register_framework,
    get_framework,
    list_frameworks,
    get_framework_descriptions,
    ReActReasoning,
    ChainOfThoughtReasoning,
    ToolAugmentedCoT,
    SoftwareEngineeringReasoning,
    MCPReasoning,
)

# Import and re-export architectural components
from enterprise_ai.agent.architecture import (
    AgentLifecycleManager,
    ConversationManager,
    ExecutionManager,
    ReasoningManager,
    IntrospectionManager,
    AgentToolsManager as ArchToolsManager,
    AgentError,
    ErrorManager,
    AgentState as ArchAgentState,
    ConversationMode,
    MessageType,
    ExecutionStatus,
    ExecutionType,
    ExecutionContext,
    ReasoningMode,
    IntrospectionLevel,
    AgentErrorCode,
    ErrorSeverity,
    ErrorCategory,
    ToolError,
    LLMError,
    StateError,
    RetryOptions,
    retry_async,
    retry_sync,
)

# Import patches
try:
    from enterprise_ai.agent.patches import llm_agent_fix
except ImportError:
    pass

__all__ = [
    # Core types
    "AgentProtocol",
    "AgentRole",
    "AgentState",
    "AgentMemory",
    "AgentMessage",
    "Task",
    "TaskStatus",
    "ToolCapabilityProtocol",
    "ToolInteractionType",
    # Base agent classes
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
    # Memory implementations
    "DictMemory",
    "NamespacedMemory",
    "ScopedMemory",
    "create_memory",
    # State implementations
    "BaseAgentState",
    "ConversationState",
    "ToolAwareState",
    "MCPSessionState",
    "create_agent_state",
    # Role implementations
    "BaseAgentRole",
    "SimpleRole",
    "TemplatedRole",
    "DeveloperRole",
    "ManagerRole",
    "ResearcherRole",
    "create_role",
    # Message implementations
    "BaseAgentMessage",
    "TaskAssignmentMessage",
    "TaskUpdateMessage",
    "QueryMessage",
    "ResponseMessage",
    "BroadcastMessage",
    "NotificationMessage",
    "ErrorMessage",
    "create_message",
    # Tool integration
    "AgentToolManager",
    "ToolUsageMetrics",
    "parse_message_for_tool_calls",
    "format_tool_response_message",
    "get_tool_prompt_for_reasoning",
    "validate_tool_parameters",
    "get_tool_error_handling_prompt",
    "get_tool_capabilities_description",
    "execute_tool_with_retry",
    "ToolIntegrationError",
    "FunctionCallingFormatter",
    "merge_tool_schemas",
    # Reasoning frameworks
    "ReasoningFramework",
    "ToolBasedReasoning",
    "BaseReasoning",
    "register_framework",
    "get_framework",
    "list_frameworks",
    "get_framework_descriptions",
    "ReActReasoning",
    "ChainOfThoughtReasoning",
    "ToolAugmentedCoT",
    "SoftwareEngineeringReasoning",
    "MCPReasoning",
    # Architecture components
    "AgentLifecycleManager",
    "ConversationManager",
    "ExecutionManager",
    "ReasoningManager",
    "IntrospectionManager",
    "ArchToolsManager",
    "AgentError",
    "ErrorManager",
    "ArchAgentState",
    "ConversationMode",
    "MessageType",
    "ExecutionStatus",
    "ExecutionType",
    "ExecutionContext",
    "ReasoningMode",
    "IntrospectionLevel",
    "AgentErrorCode",
    "ErrorSeverity",
    "ErrorCategory",
    "ToolError",
    "LLMError",
    "StateError",
    "RetryOptions",
    "retry_async",
    "retry_sync",
]
