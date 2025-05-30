"""
Architecture module for Enterprise AI agents.

This module provides the core architectural components for agents,
including lifecycle management, conversation handling, execution,
tool management, and more.
"""

# Core architectural components
from enterprise_ai.agent.architecture.lifecycle import (
    AgentLifecycleManager,
    AgentState,
    AgentLifecycleEvent,
)

from enterprise_ai.agent.architecture.conversation import (
    ConversationManager,
    ConversationManagerConfig,
    ConversationMode,
    MessageType,
)

from enterprise_ai.agent.architecture.execution import (
    ExecutionManager,
    ExecutionManagerConfig,
    ExecutionStatus,
    ExecutionType,
    ExecutionContext,
)

from enterprise_ai.agent.architecture.reasoning_manager import (
    ReasoningManager,
    ReasoningManagerConfig,
    ReasoningMode,
)

from enterprise_ai.agent.architecture.tools_manager import (
    AgentToolsManager,
    ToolUsageMetrics,
)

from enterprise_ai.agent.architecture.introspection import (
    IntrospectionManager,
    IntrospectionManagerConfig,
    IntrospectionLevel,
)

# Error handling
from enterprise_ai.agent.architecture.errors import (
    AgentError,
    AgentErrorCode,
    ErrorManager,
    ErrorSeverity,
    ErrorCategory,
    ToolError,
    LLMError,
    StateError,
    RetryOptions,
    retry_async,
    retry_sync,
)

# Utility functions
from enterprise_ai.agent.architecture.utils import (
    generate_id,
    ensure_event_loop,
    run_async,
    safe_serialize,
    merge_dicts,
    format_timestamp,
    parse_tool_args,
    deduplicate_list,
    truncate_text,
    timer,
)

__all__ = [
    # Lifecycle
    "AgentLifecycleManager",
    "AgentState",
    "AgentLifecycleEvent",
    # Conversation
    "ConversationManager",
    "ConversationManagerConfig",
    "ConversationMode",
    "MessageType",
    # Execution
    "ExecutionManager",
    "ExecutionManagerConfig",
    "ExecutionStatus",
    "ExecutionType",
    "ExecutionContext",
    # Reasoning
    "ReasoningManager",
    "ReasoningManagerConfig",
    "ReasoningMode",
    # Tool Management
    "AgentToolsManager",
    "ToolUsageMetrics",
    # Introspection
    "IntrospectionManager",
    "IntrospectionManagerConfig",
    "IntrospectionLevel",
    # Error handling
    "AgentError",
    "AgentErrorCode",
    "ErrorManager",
    "ErrorSeverity",
    "ErrorCategory",
    "ToolError",
    "LLMError",
    "StateError",
    "RetryOptions",
    "retry_async",
    "retry_sync",
    # Utils
    "generate_id",
    "ensure_event_loop",
    "run_async",
    "safe_serialize",
    "merge_dicts",
    "format_timestamp",
    "parse_tool_args",
    "deduplicate_list",
    "truncate_text",
    "timer",
]
