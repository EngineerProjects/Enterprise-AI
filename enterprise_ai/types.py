"""
Core type definitions for Enterprise AI.

This module defines Protocol classes and type aliases that form the foundation
of the type system. These definitions enable proper static type checking while
avoiding circular imports by using abstract interfaces rather than concrete
implementations.
"""

import abc
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
    Union,
    runtime_checkable,
)


# Type variables for generic typing
T = TypeVar("T")
U = TypeVar("U")
P = TypeVar("P", bound="ProviderProtocol")


# -----------------------------------------------------------------------------
# Base Enums and Constants
# -----------------------------------------------------------------------------


class RoleType(str, Enum):
    """Message role options for conversation interactions."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    AGENT = "agent"


class AgentRoleType(str, Enum):
    """Agent role types for team hierarchies."""

    MANAGER = "manager"
    DEVELOPER = "developer"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    CUSTOM = "custom"


class AgentStateType(str, Enum):
    """Agent execution states."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    THINKING = "THINKING"
    ACTING = "ACTING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    BLOCKED = "BLOCKED"
    WAITING = "WAITING"


class TeamStateType(str, Enum):
    """Team execution states."""

    IDLE = "IDLE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class TaskStateType(str, Enum):
    """Task execution states."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ToolChoiceType(str, Enum):
    """Tool choice options for LLM interactions."""

    NONE = "none"
    AUTO = "auto"
    REQUIRED = "required"


# -----------------------------------------------------------------------------
# Base Protocol Definitions
# -----------------------------------------------------------------------------


@runtime_checkable
class Serializable(Protocol):
    """Protocol for serializable objects."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        ...


@runtime_checkable
class Configurable(Protocol):
    """Protocol for configurable objects."""

    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the object from a dictionary."""
        ...


# -----------------------------------------------------------------------------
# Message and Content Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class FunctionProtocol(Serializable, Protocol):
    """Protocol for function definitions in tool calls."""

    name: str
    arguments: str


@runtime_checkable
class ToolCallProtocol(Serializable, Protocol):
    """Protocol for tool/function calls in messages."""

    id: str
    type: str
    function: FunctionProtocol


@runtime_checkable
class MessageProtocol(Serializable, Protocol):
    """Protocol for chat messages in conversations."""

    role: RoleType
    content: Optional[str]
    tool_calls: Optional[List[ToolCallProtocol]]
    name: Optional[str]
    tool_call_id: Optional[str]
    base64_image: Optional[str]
    timestamp: Optional[datetime]
    metadata: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        ...

    @classmethod
    def user_message(
        cls, content: str, base64_image: Optional[str] = None, **kwargs: Any
    ) -> "MessageProtocol":
        """Create a user message."""
        ...

    @classmethod
    def system_message(cls, content: str, **kwargs: Any) -> "MessageProtocol":
        """Create a system message."""
        ...

    @classmethod
    def assistant_message(
        cls, content: Optional[str] = None, base64_image: Optional[str] = None, **kwargs: Any
    ) -> "MessageProtocol":
        """Create an assistant message."""
        ...

    @classmethod
    def tool_message(
        cls,
        content: str,
        name: str,
        tool_call_id: str,
        base64_image: Optional[str] = None,
        **kwargs: Any,
    ) -> "MessageProtocol":
        """Create a tool message."""
        ...

    @classmethod
    def agent_message(
        cls, content: str, name: str, base64_image: Optional[str] = None, **kwargs: Any
    ) -> "MessageProtocol":
        """Create an agent message."""
        ...


@runtime_checkable
class MemoryProtocol(Protocol):
    """Protocol for agent memory storage."""

    messages: List[MessageProtocol]
    max_messages: int
    metadata: Dict[str, Any]

    def add_message(self, message: MessageProtocol) -> None:
        """Add a message to memory."""
        ...

    def add_messages(self, messages: List[MessageProtocol]) -> None:
        """Add multiple messages to memory."""
        ...

    def clear(self) -> None:
        """Clear all messages."""
        ...

    def get_recent_messages(self, n: int) -> List[MessageProtocol]:
        """Get n most recent messages."""
        ...

    def to_dict_list(self) -> List[dict]:
        """Convert messages to list of dicts."""
        ...


# -----------------------------------------------------------------------------
# Provider Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class ProviderProtocol(Protocol):
    """Base protocol for LLM providers."""

    def get_model_name(self) -> str:
        """Get the model name."""
        ...

    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion for the given messages."""
        ...

    async def acomplete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate a completion asynchronously."""
        ...

    def count_tokens(self, messages: List[MessageProtocol]) -> int:
        """Count the number of tokens in the messages."""
        ...

    def get_max_tokens(self) -> int:
        """Get the maximum token limit for the model."""
        ...

    def supports_vision(self) -> bool:
        """Check if the model supports vision/images."""
        ...

    def supports_tools(self) -> bool:
        """Check if the model supports tool/function calling."""
        ...


@runtime_checkable
class StreamingProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for providers that support streaming."""

    def complete_stream(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> Any:  # Generator[MessageProtocol, None, None]
        """Generate a streaming completion."""
        ...

    async def acomplete_stream(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> Any:  # AsyncGenerator[MessageProtocol, None]
        """Generate a streaming completion asynchronously."""
        ...


@runtime_checkable
class ConversationManagerProtocol(Protocol):
    """Protocol for conversation management."""

    def add_system_message(self, content: str) -> None:
        """Add a system message to the conversation."""
        ...

    def add_user_message(self, content: str, base64_image: Optional[str] = None) -> None:
        """Add a user message to the conversation."""
        ...

    def add_assistant_message(
        self, content: Optional[str] = None, tool_calls: Optional[List[Any]] = None
    ) -> None:
        """Add an assistant message to the conversation."""
        ...

    def add_tool_message(self, content: str, name: str, tool_call_id: str) -> None:
        """Add a tool message to the conversation."""
        ...

    def get_messages(self) -> List[MessageProtocol]:
        """Get all messages in the conversation."""
        ...

    def count_tokens(self) -> int:
        """Count tokens in the conversation."""
        ...

    def prune_to_fit_context(self, reserve_tokens: int = 0) -> List[MessageProtocol]:
        """Prune messages to fit within context window."""
        ...

    def clear(self, keep_system: bool = True) -> None:
        """Clear the conversation history."""
        ...


# -----------------------------------------------------------------------------
# Configuration Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class ConfigProviderProtocol(Protocol):
    """Protocol for configuration providers."""

    def get_config(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        ...

    def set_config(self, section: str, key: str, value: Any) -> None:
        """Set a configuration value."""
        ...

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get an entire configuration section."""
        ...

    def reload(self) -> None:
        """Reload configuration from source."""
        ...


@runtime_checkable
class ConfigLoaderProtocol(Protocol):
    """Protocol for configuration loaders."""

    def load(self, path: str) -> Dict[str, Any]:
        """Load configuration from a file."""
        ...

    def save(self, config: Dict[str, Any], path: str) -> None:
        """Save configuration to a file."""
        ...


# -----------------------------------------------------------------------------
# Logging Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class LoggerProtocol(Protocol):
    """Protocol for loggers."""

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        ...

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        ...

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        ...

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        ...

    def critical(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        ...

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log an exception."""
        ...


@runtime_checkable
class LogFormatterProtocol(Protocol):
    """Protocol for log formatters."""

    def format(self, record: Any) -> str:
        """Format a log record."""
        ...


@runtime_checkable
class LogHandlerProtocol(Protocol):
    """Protocol for log handlers."""

    def emit(self, record: Any) -> None:
        """Emit a log record."""
        ...

    def setFormatter(self, formatter: LogFormatterProtocol) -> None:
        """Set the formatter for this handler."""
        ...

    def setLevel(self, level: int) -> None:
        """Set the logging level for this handler."""
        ...


# -----------------------------------------------------------------------------
# Tool Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class ToolInputProtocol(Serializable, Protocol):
    """Protocol for tool inputs."""

    def validate(self) -> bool:
        """Validate the input data."""
        ...


@runtime_checkable
class ToolResultProtocol(Serializable, Protocol):
    """Protocol for tool results."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]]


@runtime_checkable
class ToolProtocol(Protocol):
    """Protocol for tools that can be used by agents."""

    name: str
    description: str

    def execute(self, input_data: ToolInputProtocol) -> ToolResultProtocol:
        """Execute the tool with the given input."""
        ...

    async def aexecute(self, input_data: ToolInputProtocol) -> ToolResultProtocol:
        """Execute the tool asynchronously."""
        ...

    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for this tool's input."""
        ...


# -----------------------------------------------------------------------------
# Agent and Team Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class AgentProfileProtocol(Serializable, Protocol):
    """Protocol for agent profiles."""

    name: str
    role: str
    description: Optional[str]
    capabilities: List[str]
    specialties: List[str]
    system_prompt: Optional[str]


@runtime_checkable
class AgentConfigProtocol(Serializable, Protocol):
    """Protocol for agent configurations."""

    profile: AgentProfileProtocol
    model_name: str
    max_steps: int
    tools: List[str]
    allowed_tools: List[str]


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol for agents."""

    name: str
    role: str
    state: AgentStateType
    memory: MemoryProtocol
    config: AgentConfigProtocol

    def initialize(self) -> None:
        """Initialize the agent."""
        ...

    async def process(self, message: MessageProtocol) -> Optional[MessageProtocol]:
        """Process a message and generate a response."""
        ...

    def add_tool(self, tool: ToolProtocol) -> None:
        """Add a tool to the agent."""
        ...

    def get_state(self) -> AgentStateType:
        """Get the current state of the agent."""
        ...


@runtime_checkable
class TaskProtocol(Serializable, Protocol):
    """Protocol for tasks."""

    id: str
    title: str
    description: str
    assigned_to: Optional[str]
    state: TaskStateType
    priority: int
    deadline: Optional[datetime]
    parent_task: Optional[str]
    subtasks: List[str]
    dependencies: List[str]
    metadata: Dict[str, Any]


@runtime_checkable
class TeamConfigProtocol(Serializable, Protocol):
    """Protocol for team configurations."""

    name: str
    description: Optional[str]
    manager: str
    members: List[str]
    max_size: int


@runtime_checkable
class TeamProtocol(Protocol):
    """Protocol for teams."""

    name: str
    config: TeamConfigProtocol
    manager: AgentProtocol
    members: Dict[str, AgentProtocol]
    state: TeamStateType

    def initialize(self) -> None:
        """Initialize the team."""
        ...

    def add_member(self, agent: AgentProtocol) -> bool:
        """Add a member to the team."""
        ...

    def remove_member(self, agent_name: str) -> bool:
        """Remove a member from the team."""
        ...

    def assign_task(self, task: TaskProtocol, agent_name: Optional[str] = None) -> bool:
        """Assign a task to a team member."""
        ...

    def get_state(self) -> TeamStateType:
        """Get the current state of the team."""
        ...
