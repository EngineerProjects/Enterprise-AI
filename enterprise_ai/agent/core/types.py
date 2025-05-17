"""
Agent-specific types and protocols for Enterprise AI.

This module defines the core type definitions, enums, and protocols
that form the foundation of the agent system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    Tuple,
    Union,
    Awaitable,
    TypeVar,
    Generic,
)

from enterprise_ai.types import MessageProtocol, Serializable


class TaskStatus(Enum):
    """Task execution status enum."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()
    CANCELED = auto()  # Added CANCELED status for explicit task cancellation


@dataclass
class Task(Serializable):
    """Represents a task to be executed by an agent."""

    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    dependencies: List[str] = field(default_factory=list)  # IDs of tasks this task depends on
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "dependencies": self.dependencies or [],
            "metadata": self.metadata or {},
        }


class ToolCapabilityProtocol(Protocol):
    """Protocol for tool capability definitions."""

    @property
    def value(self) -> str:
        """Get the string value of the capability."""
        ...

    @property
    def description(self) -> str:
        """Get a human-readable description of the capability."""
        ...

    @property
    def category(self) -> Optional[str]:
        """Get the category this capability belongs to."""
        ...

    def __eq__(self, other: Any) -> bool:
        """Compare capabilities for equality."""
        ...


T = TypeVar("T")


class AgentMemory(Protocol, Generic[T]):
    """Protocol for agent memory implementations."""

    def add(self, key: str, value: Any) -> None:
        """Add an item to memory.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        ...

    def get(self, key: str, default: T = None) -> T:
        """Get an item from memory.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default if not found
        """
        ...

    def forget(self, key: str) -> None:
        """Remove an item from memory.

        Args:
            key: The key to remove
        """
        ...

    def clear(self) -> None:
        """Clear all memory."""
        ...

    def contains(self, key: str) -> bool:
        """Check if memory contains a key.

        Args:
            key: The key to check

        Returns:
            True if the key exists, False otherwise
        """
        ...

    async def add_async(self, key: str, value: Any) -> None:
        """Add an item to memory asynchronously.

        Args:
            key: The key to store the value under
            value: The value to store
        """
        ...

    async def get_async(self, key: str, default: T = None) -> T:
        """Get an item from memory asynchronously.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default if not found
        """
        ...

    def get_all(self) -> Dict[str, Any]:
        """Get all stored memory items.

        Returns:
            Dictionary of all memory items
        """
        ...


class AgentRole(Protocol):
    """Protocol defining an agent's role."""

    @property
    def name(self) -> str:
        """Get role name."""
        ...

    @property
    def description(self) -> str:
        """Get role description."""
        ...

    @property
    def capabilities(self) -> List[str]:
        """Get role capabilities."""
        ...

    @property
    def required_tools(self) -> List[str]:
        """Get tools required by this role."""
        ...

    @property
    def preferred_reasoning(self) -> Optional[str]:
        """Get preferred reasoning framework for this role."""
        ...

    def get_instructions(self) -> str:
        """Get role-specific instructions.

        Returns:
            Instruction string for the role
        """
        ...

    def has_capability(self, capability: Union[str, ToolCapabilityProtocol]) -> bool:
        """Check if role has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if role has the capability
        """
        ...


class AgentState(Protocol):
    """Protocol for agent state implementations."""

    @property
    def agent_id(self) -> str:
        """Get agent ID."""
        ...

    @property
    def current_task(self) -> Optional[Task]:
        """Get current task."""
        ...

    @current_task.setter
    def current_task(self, task: Optional[Task]) -> None:
        """Set current task."""
        ...

    @property
    def memory(self) -> AgentMemory:
        """Get agent memory."""
        ...

    @property
    def role(self) -> AgentRole:
        """Get agent role."""
        ...

    @role.setter
    def role(self, role: AgentRole) -> None:
        """Set agent role."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state
        """
        ...

    def save(self) -> None:
        """Save state to persistent storage."""
        ...

    def load(self) -> None:
        """Load state from persistent storage."""
        ...

    async def save_async(self) -> bool:
        """Save state asynchronously.

        Returns:
            True if state was saved successfully
        """
        ...

    async def load_async(self) -> bool:
        """Load state asynchronously.

        Returns:
            True if state was loaded successfully
        """
        ...


class ToolInteractionType(str, Enum):
    """Types of tool interactions."""

    TOOL_REQUEST = "tool_request"
    TOOL_RESPONSE = "tool_response"
    TOOL_ERROR = "tool_error"
    TOOL_STATUS = "tool_status"


class AgentMessage(MessageProtocol):
    """Protocol for agent-to-agent messages."""

    sender_id: str
    receiver_id: Optional[str]
    message_type: str  # e.g., "task_assignment", "response", "request"
    tool_interaction: Optional[ToolInteractionType] = None
    tool_data: Optional[Dict[str, Any]] = None

    @property
    @abstractmethod
    def is_broadcast(self) -> bool:
        """Check if message is a broadcast (no specific receiver)."""
        ...

    @property
    def contains_tool_call(self) -> bool:
        """Check if the message contains a tool call."""
        ...

    @property
    def contains_tool_result(self) -> bool:
        """Check if the message contains a tool result."""
        ...

    def to_message(self) -> MessageProtocol:
        """Convert to a standard message.

        Returns:
            Standard message representation
        """
        ...


class AgentProtocol(Protocol):
    """Protocol defining agent capabilities."""

    @property
    def id(self) -> str:
        """Get agent ID."""
        ...

    @property
    def name(self) -> str:
        """Get agent name."""
        ...

    @property
    def state(self) -> AgentState:
        """Get agent state."""
        ...

    @property
    def capabilities(self) -> Set[str]:
        """Get agent capabilities.

        Returns:
            Set of capability identifiers
        """
        ...

    def process_message(
        self, message: Union[str, MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a message and generate a response.

        Args:
            message: Input message or string
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        ...

    async def aprocess_message(
        self, message: Union[str, MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a message asynchronously.

        Args:
            message: Input message or string
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        ...

    def process_conversation(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a conversation and generate a response.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        ...

    async def aprocess_conversation(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a conversation asynchronously.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        ...

    def assign_task(self, task: Task) -> bool:
        """Assign a task to the agent.

        Args:
            task: Task to assign

        Returns:
            True if task assigned successfully, False otherwise
        """
        ...

    async def aassign_task(self, task: Task) -> bool:
        """Assign a task to the agent asynchronously.

        Args:
            task: Task to assign

        Returns:
            True if task assigned successfully, False otherwise
        """
        ...

    def process_task(self) -> Any:
        """Process the current task.

        Returns:
            Task status
        """
        ...

    async def aprocess_task(self) -> Any:
        """Process the current task asynchronously.

        Returns:
            Task status
        """
        ...

    def get_status(self) -> Dict[str, Any]:
        """Get agent status summary.

        Returns:
            Dictionary of status information
        """
        ...

    async def execute_tool(
        self, tool_name: str, timeout: Optional[float] = None, retry_count: int = 2, **kwargs: Any
    ) -> Any:
        """Execute a tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            timeout: Optional timeout in seconds
            retry_count: Number of retries for transient errors
            **kwargs: Parameters for the tool

        Returns:
            Tool execution result
        """
        ...

    async def execute_tools_parallel(
        self, executions: List[Dict[str, Any]]
    ) -> List[Tuple[str, Any]]:
        """Execute multiple tools in parallel.

        Args:
            executions: List of execution specifications, each containing:
                       - tool_name: Name of the tool to execute
                       - parameters: Dictionary of parameters
                       - timeout: Optional timeout

        Returns:
            List of (tool_name, result) tuples
        """
        ...

    def get_available_tools(
        self, filter_by_capability: Optional[Union[str, List[str]]] = None, match_all: bool = False
    ) -> List[str]:
        """Get available tools, optionally filtered by capability.

        Args:
            filter_by_capability: Optional capability or list of capabilities to filter by
            match_all: Whether all capabilities must be present (True) or any (False)

        Returns:
            List of available tool names
        """
        ...

    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema or None if not found
        """
        ...

    def get_tool_metrics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get metrics for a specific tool or all tools.

        Args:
            tool_name: Optional name of tool to get metrics for

        Returns:
            Dictionary of metrics
        """
        ...

    def has_capability(self, capability: Union[str, ToolCapabilityProtocol]) -> bool:
        """Check if agent has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if agent has the capability
        """
        ...

    def get_capabilities(self) -> Dict[str, Any]:
        """Get detailed information about agent capabilities.

        Returns:
            Dictionary of capabilities info
        """
        ...

    async def save_state(self) -> bool:
        """Save agent state.

        Returns:
            True if state saved successfully, False otherwise
        """
        ...

    async def load_state(self) -> bool:
        """Load agent state.

        Returns:
            True if state loaded successfully, False otherwise
        """
        ...

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the agent.

        Args:
            **kwargs: Initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        ...

    async def terminate(self) -> bool:
        """Terminate the agent and clean up resources.

        Returns:
            True if termination succeeded, False otherwise
        """
        ...
