"""
Agent state management for Enterprise AI.

This module provides implementations of the AgentState protocol
defined in types.py, handling persistent state for agents.
"""

import json
import os
import time
from typing import Any, Dict, Optional, cast

from enterprise_ai.agent.memory import DictMemory, create_memory
from enterprise_ai.agent.types import AgentMemory, AgentRole, AgentState, Task
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
        return state_dict


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
        state_type: Type of state to create ("base" or "conversation")
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
        return ConversationState(agent_id, memory_type, state_dir, **kwargs)
    else:
        raise ValueError(f"Unknown state type: {state_type}")
