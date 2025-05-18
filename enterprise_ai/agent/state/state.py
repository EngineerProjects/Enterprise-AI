"""
Agent state management for Enterprise AI.

This module provides implementations of the AgentState protocol
defined in types.py, handling persistent state for agents.
"""

import json
import os
import time
import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from enterprise_ai.mcp.client import MCPClient

from enterprise_ai.agent.state.memory import DictMemory, NamespacedMemory, create_memory
from enterprise_ai.agent.core.types import AgentMemory, AgentRole, AgentState, Task, TaskStatus
from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol, Serializable

logger = get_logger("agent.state")


class BaseAgentState(AgentState):
    """Base implementation of agent state.

    This class provides a concrete implementation of the AgentState
    protocol with basic persistence capabilities.
    """

    def __init__(
        self,
        agent_id: str,
        memory_type: str = "dict",
        state_dir: Optional[str] = None,
    ) -> None:
        """Initialize agent state.

        Args:
            agent_id: Unique identifier for the agent
            memory_type: Type of memory to use
            state_dir: Directory to store persistent state
        """
        self._agent_id = agent_id
        self._memory = create_memory(memory_type)
        self._current_task: Optional[Task] = None
        self._role: Optional[AgentRole] = None
        self._state_dir = state_dir
        self._last_saved: float = 0
        self._capabilities: Set[str] = set()
        self._mcp_session_id: Optional[str] = None

        # Create state directory if specified and doesn't exist
        if self._state_dir and not os.path.exists(self._state_dir):
            os.makedirs(self._state_dir, exist_ok=True)

    @property
    def agent_id(self) -> str:
        """Get agent ID.

        Returns:
            Agent ID
        """
        return self._agent_id

    @property
    def current_task(self) -> Optional[Task]:
        """Get current task.

        Returns:
            Current task or None if no task is assigned
        """
        return self._current_task

    @current_task.setter
    def current_task(self, task: Optional[Task]) -> None:
        """Set current task.

        Args:
            task: Task to set as current or None to clear
        """
        self._current_task = task
        # Update task in memory for persistence
        if task:
            self._memory.add("current_task", task.to_dict())
        else:
            self._memory.add("current_task", None)

    @property
    def memory(self) -> AgentMemory:
        """Get agent memory.

        Returns:
            Agent memory implementation
        """
        return self._memory

    @property
    def role(self) -> AgentRole:
        """Get agent role.

        Returns:
            Agent role

        Raises:
            RuntimeError: If role is not set
        """
        if self._role is None:
            raise RuntimeError("Agent role is not set")
        return self._role

    @role.setter
    def role(self, role: AgentRole) -> None:
        """Set agent role.

        Args:
            role: Role to assign to the agent
        """
        self._role = role
        # Store role information in memory for persistence
        if role and hasattr(role, "to_dict") and callable(getattr(role, "to_dict")):
            # If role implements to_dict, use it
            self._memory.add("role", cast(Serializable, role).to_dict())
        else:
            # Otherwise store basic role information
            self._memory.add(
                "role",
                {
                    "name": role.name,
                    "description": role.description,
                    "capabilities": role.capabilities,
                },
            )

        # Update capabilities from role
        if hasattr(role, "capabilities"):
            self._capabilities.update(role.capabilities)

    @property
    def capabilities(self) -> Set[str]:
        """Get agent capabilities.

        Returns:
            Set of capabilities
        """
        return self._capabilities.copy()

    def add_capability(self, capability: str) -> None:
        """Add a capability to the agent.

        Args:
            capability: Capability to add
        """
        self._capabilities.add(capability)
        self._memory.add("capabilities", list(self._capabilities))

    def has_capability(self, capability: str) -> bool:
        """Check if agent has a capability.

        Args:
            capability: Capability to check

        Returns:
            True if agent has the capability, False otherwise
        """
        return capability in self._capabilities

    def get_mcp_session_id(self) -> Optional[str]:
        """Get the ID of the associated MCP session.

        Returns:
            MCP session ID or None if not set
        """
        return self._mcp_session_id

    def set_mcp_session_id(self, session_id: str) -> None:
        """Set the ID of the associated MCP session.

        Args:
            session_id: MCP session ID
        """
        self._mcp_session_id = session_id
        self._memory.add("mcp_session_id", session_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state
        """
        result: Dict[str, Any] = {
            "agent_id": self._agent_id,
            "timestamps": {
                "last_saved": self._last_saved,
                "last_active": time.time(),
            },
            "capabilities": list(self._capabilities),
            "mcp_session_id": self._mcp_session_id,
        }

        # Add task if available
        if self._current_task:
            result["current_task"] = self._current_task.to_dict()

        # Add role if available
        if self._role:
            if hasattr(self._role, "to_dict") and callable(getattr(self._role, "to_dict")):
                result["role"] = cast(Serializable, self._role).to_dict()
            else:
                result["role"] = {
                    "name": self._role.name,
                    "description": self._role.description,
                    "capabilities": self._role.capabilities,
                }

        return result

    def save(self) -> None:
        """Save state to persistent storage.

        Raises:
            RuntimeError: If state directory is not configured
        """
        if not self._state_dir:
            logger.warning("State directory not configured, state will not be saved")
            return

        state_file = os.path.join(self._state_dir, f"{self._agent_id}.json")
        try:
            with open(state_file, "w") as f:
                state_data = self.to_dict()
                json.dump(state_data, f, indent=2, default=str)
                self._last_saved = time.time()
                logger.debug(f"Saved agent state: {self._agent_id}")
        except Exception as e:
            logger.error(f"Failed to save agent state: {e}")
            raise RuntimeError(f"Failed to save agent state: {e}")

    def load(self) -> None:
        """Load state from persistent storage.

        Raises:
            RuntimeError: If state directory is not configured
            FileNotFoundError: If state file does not exist
        """
        if not self._state_dir:
            logger.warning("State directory not configured, state will not be loaded")
            return

        state_file = os.path.join(self._state_dir, f"{self._agent_id}.json")
        if not os.path.exists(state_file):
            logger.warning(f"State file not found: {state_file}")
            raise FileNotFoundError(f"State file not found: {state_file}")

        try:
            with open(state_file, "r") as f:
                state_data = json.load(f)

                # Load capabilities
                if "capabilities" in state_data:
                    self._capabilities = set(state_data["capabilities"])

                # Load MCP session ID
                if "mcp_session_id" in state_data:
                    self._mcp_session_id = state_data["mcp_session_id"]

                # Restore task if available
                if "current_task" in state_data and state_data["current_task"]:
                    task_data = state_data["current_task"]
                    # Task needs to be reconstructed from the factory or similar
                    # This is just a placeholder - proper implementation would depend
                    # on how tasks are created in your system
                    self._memory.add("current_task", task_data)

                # Role needs to be set externally since we can't reconstruct it from data alone
                if "role" in state_data:
                    self._memory.add("role", state_data["role"])

                logger.debug(f"Loaded agent state: {self._agent_id}")
        except Exception as e:
            logger.error(f"Failed to load agent state: {e}")
            raise RuntimeError(f"Failed to load agent state: {e}")

    async def save_async(self) -> bool:
        """Save state asynchronously.

        Returns:
            True if successful, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.save)
            return True
        except Exception as e:
            logger.error(f"Failed to save agent state asynchronously: {e}")
            return False

    async def load_async(self) -> bool:
        """Load state asynchronously.

        Returns:
            True if successful, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.load)
            return True
        except FileNotFoundError:
            logger.warning(f"State file not found for agent {self._agent_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to load agent state asynchronously: {e}")
            return False


class ConversationState(BaseAgentState):
    """Agent state with conversation history.

    This implementation extends BaseAgentState with functionality for
    tracking conversation history with other agents or users.
    """

    def __init__(
        self,
        agent_id: str,
        memory_type: str = "dict",
        state_dir: Optional[str] = None,
        max_history: int = 100,
    ) -> None:
        """Initialize conversation state.

        Args:
            agent_id: Unique identifier for the agent
            memory_type: Type of memory to use
            state_dir: Directory to store persistent state
            max_history: Maximum number of messages to keep in history
        """
        super().__init__(agent_id, memory_type, state_dir)
        self.max_history = max_history
        self._conversation_history: Dict[str, list] = {}
        self._memory.add("conversation_history", self._conversation_history)
        self._active_sessions: Set[str] = set()

    def add_message(self, message: MessageProtocol, conversation_id: str = "default") -> None:
        """Add a message to conversation history.

        Args:
            message: Message to add
            conversation_id: ID of the conversation
        """
        if conversation_id not in self._conversation_history:
            self._conversation_history[conversation_id] = []

        # Add message to history
        self._conversation_history[conversation_id].append(message.to_dict())

        # Trim history if needed
        if (
            self.max_history > 0
            and len(self._conversation_history[conversation_id]) > self.max_history
        ):
            self._conversation_history[conversation_id] = self._conversation_history[
                conversation_id
            ][-self.max_history :]

        # Update in memory for persistence
        self._memory.add("conversation_history", self._conversation_history)

    def get_conversation_history(
        self, conversation_id: str = "default", limit: Optional[int] = None
    ) -> list:
        """Get conversation history.

        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of messages to return (most recent)

        Returns:
            List of messages in the conversation
        """
        if conversation_id not in self._conversation_history:
            return []

        history = self._conversation_history[conversation_id]
        if limit and limit > 0:
            return history[-limit:]
        return history.copy()

    def clear_conversation(self, conversation_id: str = "default") -> None:
        """Clear a conversation history.

        Args:
            conversation_id: ID of the conversation to clear
        """
        if conversation_id in self._conversation_history:
            self._conversation_history[conversation_id] = []
            self._memory.add("conversation_history", self._conversation_history)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state including conversation history
        """
        state_dict = super().to_dict()
        state_dict["conversation_history"] = self._conversation_history
        state_dict["active_sessions"] = list(self._active_sessions)
        return state_dict

    def start_session(self, session_id: str) -> None:
        """Start a new session.

        Args:
            session_id: Session ID
        """
        self._active_sessions.add(session_id)
        self._memory.add("active_sessions", list(self._active_sessions))

    def end_session(self, session_id: str) -> None:
        """End an active session.

        Args:
            session_id: Session ID
        """
        if session_id in self._active_sessions:
            self._active_sessions.remove(session_id)
            self._memory.add("active_sessions", list(self._active_sessions))

    def has_active_session(self, session_id: str) -> bool:
        """Check if a session is active.

        Args:
            session_id: Session ID

        Returns:
            True if session is active, False otherwise
        """
        return session_id in self._active_sessions

    def get_active_sessions(self) -> Set[str]:
        """Get all active sessions.

        Returns:
            Set of active session IDs
        """
        return self._active_sessions.copy()


class ToolAwareState(ConversationState):
    """Agent state with enhanced tool tracking.

    This implementation extends ConversationState with features
    specifically for tracking tool usage and state.
    """

    def __init__(
        self,
        agent_id: str,
        memory_type: str = "dict",
        state_dir: Optional[str] = None,
        max_history: int = 100,
    ) -> None:
        """Initialize tool-aware state.

        Args:
            agent_id: Unique identifier for the agent
            memory_type: Type of memory to use
            state_dir: Directory to store persistent state
            max_history: Maximum number of messages to keep in history
        """
        super().__init__(agent_id, memory_type, state_dir, max_history)
        self._tool_history: Dict[str, List[Dict[str, Any]]] = {}
        self._active_tools: Dict[str, Dict[str, Any]] = {}
        self._tool_sessions: Dict[str, str] = {}

        # Initialize tool data in memory
        self._memory.add("tool_history", self._tool_history)
        self._memory.add("active_tools", self._active_tools)

    def record_tool_usage(
        self, tool_name: str, parameters: Dict[str, Any], result: Any, success: bool
    ) -> str:
        """Record a tool usage event.

        Args:
            tool_name: Name of the tool
            parameters: Parameters used for the tool
            result: Result of the tool execution
            success: Whether the execution was successful

        Returns:
            ID of the recorded event
        """
        import uuid

        event_id = str(uuid.uuid4())

        # Create usage record
        usage_record = {
            "id": event_id,
            "tool_name": tool_name,
            "timestamp": time.time(),
            "parameters": parameters,
            "success": success,
            "result_summary": str(result)[:200] if result else None,
        }

        # Add to tool history
        if tool_name not in self._tool_history:
            self._tool_history[tool_name] = []

        self._tool_history[tool_name].append(usage_record)

        # Trim history if needed (keep last 50 entries per tool)
        if len(self._tool_history[tool_name]) > 50:
            self._tool_history[tool_name] = self._tool_history[tool_name][-50:]

        # Update in memory
        self._memory.add("tool_history", self._tool_history)

        return event_id

    def mark_tool_active(self, tool_name: str, session_id: Optional[str] = None) -> None:
        """Mark a tool as active.

        Args:
            tool_name: Name of the tool
            session_id: Optional session ID associated with this tool usage
        """
        self._active_tools[tool_name] = {
            "start_time": time.time(),
            "session_id": session_id,
        }

        # Associate tool with session if provided
        if session_id:
            self._tool_sessions[tool_name] = session_id

        self._memory.add("active_tools", self._active_tools)

    def mark_tool_inactive(self, tool_name: str) -> None:
        """Mark a tool as inactive.

        Args:
            tool_name: Name of the tool
        """
        if tool_name in self._active_tools:
            del self._active_tools[tool_name]
            self._memory.add("active_tools", self._active_tools)

    def is_tool_active(self, tool_name: str) -> bool:
        """Check if a tool is active.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is active, False otherwise
        """
        return tool_name in self._active_tools

    def get_active_tools(self) -> Dict[str, Dict[str, Any]]:
        """Get all active tools.

        Returns:
            Dictionary mapping tool names to activation info
        """
        return self._active_tools.copy()

    def get_tool_history(self, tool_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get tool usage history.

        Args:
            tool_name: Optional name of the tool to get history for

        Returns:
            Dictionary mapping tool names to usage history
        """
        if tool_name:
            return {tool_name: self._tool_history.get(tool_name, [])}
        return self._tool_history.copy()

    def get_tool_session(self, tool_name: str) -> Optional[str]:
        """Get the session ID associated with a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Session ID or None if not associated
        """
        return self._tool_sessions.get(tool_name)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state
        """
        state_dict = super().to_dict()
        state_dict["tool_history"] = self._tool_history
        state_dict["active_tools"] = self._active_tools
        state_dict["tool_sessions"] = self._tool_sessions
        return state_dict


class MCPSessionState(ToolAwareState):
    """Agent state with MCP session integration.

    This implementation extends ToolAwareState with features
    specifically for integrating with MCP sessions.
    """

    def __init__(
        self,
        agent_id: str,
        memory_type: str = "dict",
        state_dir: Optional[str] = None,
        max_history: int = 100,
        mcp_session_id: Optional[str] = None,
    ) -> None:
        """Initialize MCP session state.

        Args:
            agent_id: Unique identifier for the agent
            memory_type: Type of memory to use
            state_dir: Directory to store persistent state
            max_history: Maximum number of messages to keep in history
            mcp_session_id: Optional ID of the MCP session to use
        """
        super().__init__(agent_id, memory_type, state_dir, max_history)

        self._mcp_session_id = mcp_session_id
        self._mcp_client: Optional["MCPClient"] = None
        self._mcp_tools: List[Dict[str, Any]] = []
        self._mcp_history: List[Dict[str, Any]] = []

        # Initialize MCP client if session ID provided
        if self._mcp_session_id:
            self._init_mcp_client()

    def _init_mcp_client(self) -> None:
        """Initialize the MCP client."""
        try:
            # Lazy import to avoid circular imports
            from enterprise_ai.mcp.client import MCPClient

            if self._mcp_session_id is not None:
                self._mcp_client = MCPClient(self._mcp_session_id, create_if_not_exists=True)
                logger.debug(f"Initialized MCP client for session {self._mcp_session_id}")
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            self._mcp_client = None

    def set_mcp_session_id(self, session_id: str) -> None:
        """Set the MCP session ID.

        Args:
            session_id: ID of the MCP session
        """
        self._mcp_session_id = session_id

        # Re-initialize MCP client
        self._init_mcp_client()

        # Save to memory
        self._memory.add("mcp_session_id", session_id)

    def sync_from_mcp(self) -> bool:
        """Sync state from MCP session.

        Returns:
            True if sync succeeded, False otherwise
        """
        if not self._mcp_client:
            logger.warning("Cannot sync from MCP: client not initialized")
            return False

        try:
            # Get available tools
            self._mcp_tools = self._mcp_client.discover_tools()
            self._memory.add("mcp_tools", self._mcp_tools)

            # Get session info
            session_info = self._mcp_client.get_session_info()
            self._memory.add("mcp_session_info", session_info)

            logger.debug(f"Synced state from MCP session {self._mcp_session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to sync from MCP session: {e}")
            return False

    def sync_to_mcp(self) -> bool:
        """Sync state to MCP session.

        Returns:
            True if sync succeeded, False otherwise
        """
        if not self._mcp_client:
            logger.warning("Cannot sync to MCP: client not initialized")
            return False

        try:
            # Set agent state in MCP context
            self._mcp_client.set_context("agent_id", self._agent_id)
            self._mcp_client.set_context("agent_capabilities", list(self._capabilities))

            # Set active tools
            self._mcp_client.set_context("active_tools", self._active_tools)

            logger.debug(f"Synced state to MCP session {self._mcp_session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to sync to MCP session: {e}")
            return False

    def execute_mcp_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool using the MCP session.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters for tool execution

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If MCP client is not initialized
        """
        if not self._mcp_client:
            raise RuntimeError("MCP client not initialized")

        # Import here to avoid circular imports
        import asyncio

        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create a new event loop if none exists
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the tool execution
        return loop.run_until_complete(self._mcp_client.execute_tool(tool_name, **kwargs))

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from MCP session.

        Returns:
            List of available tools
        """
        if not self._mcp_tools and self._mcp_client:
            # Refresh tools
            try:
                self._mcp_tools = self._mcp_client.discover_tools()
            except Exception as e:
                logger.error(f"Failed to discover MCP tools: {e}")

        return self._mcp_tools.copy()

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state
        """
        state_dict = super().to_dict()
        state_dict["mcp_session_id"] = self._mcp_session_id
        state_dict["mcp_tools"] = self._mcp_tools
        return state_dict

    async def sync_from_mcp_async(self) -> bool:
        """Sync state from MCP session asynchronously.

        Returns:
            True if sync succeeded, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_from_mcp)

    async def sync_to_mcp_async(self) -> bool:
        """Sync state to MCP session asynchronously.

        Returns:
            True if sync succeeded, False otherwise
        """
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.sync_to_mcp)

    async def execute_mcp_tool_async(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a tool using the MCP session asynchronously.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters for tool execution

        Returns:
            Tool execution result

        Raises:
            RuntimeError: If MCP client is not initialized
        """
        if not self._mcp_client:
            raise RuntimeError("MCP client not initialized")

        return await self._mcp_client.execute_tool(tool_name, **kwargs)


# Factory function to create agent states
def create_agent_state(
    agent_id: str,
    state_type: str = "base",
    memory_type: str = "dict",
    state_dir: Optional[str] = None,
    **kwargs: Any,
) -> AgentState:
    """Create an agent state implementation by type.

    Args:
        agent_id: Unique identifier for the agent
        state_type: Type of state to create
        memory_type: Type of memory to use
        state_dir: Directory to store persistent state
        **kwargs: Additional arguments passed to the state constructor

    Returns:
        AgentState implementation

    Raises:
        ValueError: If an unknown state type is specified
    """
    if state_type == "base":
        return BaseAgentState(agent_id, memory_type, state_dir)
    elif state_type == "conversation":
        max_history = kwargs.get("max_history", 100)
        return ConversationState(agent_id, memory_type, state_dir, max_history)
    elif state_type == "tool_aware":
        max_history = kwargs.get("max_history", 100)
        return ToolAwareState(agent_id, memory_type, state_dir, max_history)
    elif state_type == "mcp":
        max_history = kwargs.get("max_history", 100)
        mcp_session_id = kwargs.get("mcp_session_id")
        return MCPSessionState(agent_id, memory_type, state_dir, max_history, mcp_session_id)
    else:
        raise ValueError(f"Unknown state type: {state_type}")
