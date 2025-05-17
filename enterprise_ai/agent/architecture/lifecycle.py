"""
Agent lifecycle management.

This module handles agent initialization, configuration, and cleanup,
including state saving and loading, version management, and event handling.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union, cast, Callable

from enterprise_ai.agent.architecture.errors import (
    AgentError,
    AgentErrorCode,
    ErrorManager,
    StateError,
)
from enterprise_ai.agent.architecture.utils import (
    generate_id,
    ensure_event_loop,
    merge_dicts,
    timer,
)
from enterprise_ai.config import get_config
from enterprise_ai.logger import get_logger

logger = get_logger("agent.lifecycle")


class AgentState(str, Enum):
    """States of an agent throughout its lifecycle."""

    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"


class AgentLifecycleEvent(str, Enum):
    """Events that occur during an agent's lifecycle."""

    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    TERMINATING = "terminating"
    TERMINATED = "terminated"
    CONFIG_CHANGED = "config_changed"
    STATE_SAVED = "state_saved"
    STATE_LOADED = "state_loaded"


class LifecycleEventHandler:
    """Handler for agent lifecycle events."""

    def __init__(self):
        """Initialize the event handler."""
        self._handlers: Dict[AgentLifecycleEvent, List[Callable[[Dict[str, Any]], None]]] = {
            event: [] for event in AgentLifecycleEvent
        }

    def register(
        self, event: AgentLifecycleEvent, handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register a handler for an event.

        Args:
            event: Event to register for
            handler: Handler function to call when the event occurs
        """
        if event not in self._handlers:
            self._handlers[event] = []

        if handler not in self._handlers[event]:
            self._handlers[event].append(handler)

    def unregister(
        self, event: AgentLifecycleEvent, handler: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """Unregister a handler for an event.

        Args:
            event: Event to unregister from
            handler: Handler function to remove

        Returns:
            True if the handler was removed, False if not found
        """
        if event in self._handlers and handler in self._handlers[event]:
            self._handlers[event].remove(handler)
            return True
        return False

    def trigger(self, event: AgentLifecycleEvent, data: Optional[Dict[str, Any]] = None) -> None:
        """Trigger an event.

        Args:
            event: Event to trigger
            data: Optional data to pass to handlers
        """
        event_data = data or {}

        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    handler(event_data)
                except Exception as e:
                    logger.error(f"Error in event handler for {event}: {e}")


class AgentLifecycleManager:
    """Manager for agent lifecycle."""

    def __init__(self, agent: Any):
        """Initialize the lifecycle manager.

        Args:
            agent: The agent instance
        """
        self.agent = agent
        self.agent_id = getattr(agent, "id", generate_id("agent-"))
        self.state = AgentState.CREATED
        self.created_at = datetime.now()
        self.initialized_at: Optional[datetime] = None
        self.last_active_at: Optional[datetime] = None
        self.terminated_at: Optional[datetime] = None
        self.error_manager = ErrorManager(self.agent_id)
        self.event_handler = LifecycleEventHandler()
        self._state_dir = get_config("agent.state_directory")
        self._config = {}
        self._version = "1.0.0"

        # Trigger created event
        self.event_handler.trigger(
            AgentLifecycleEvent.CREATED,
            {"agent_id": self.agent_id, "timestamp": self.created_at.isoformat()},
        )

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize the agent.

        Args:
            config: Optional configuration

        Returns:
            True if initialization succeeded, False otherwise
        """
        # Update state
        self.state = AgentState.INITIALIZING
        self.event_handler.trigger(
            AgentLifecycleEvent.INITIALIZING,
            {"agent_id": self.agent_id, "timestamp": datetime.now().isoformat()},
        )

        try:
            # Store configuration
            if config:
                self._config = config.copy()

            # Initialize agent components
            # This would typically involve initializing other managers and components

            # Update state
            self.state = AgentState.READY
            self.initialized_at = datetime.now()
            self.last_active_at = datetime.now()

            # Trigger initialized event
            self.event_handler.trigger(
                AgentLifecycleEvent.INITIALIZED,
                {
                    "agent_id": self.agent_id,
                    "timestamp": self.initialized_at.isoformat(),
                    "config": self._config,
                },
            )

            logger.info(f"Agent {self.agent_id} initialized successfully")
            return True
        except Exception as e:
            # Handle initialization error
            self.state = AgentState.ERROR
            error = self.error_manager.handle_error(
                e, error_code=AgentErrorCode.INITIALIZATION_FAILED
            )

            # Trigger error event
            self.event_handler.trigger(
                AgentLifecycleEvent.ERROR,
                {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "error": error.to_dict(),
                },
            )

            logger.error(f"Agent {self.agent_id} initialization failed: {e}")
            return False

    async def terminate(self) -> bool:
        """Terminate the agent.

        Returns:
            True if termination succeeded, False otherwise
        """
        if self.state == AgentState.TERMINATED:
            logger.warning(f"Agent {self.agent_id} already terminated")
            return True

        # Trigger terminating event
        self.event_handler.trigger(
            AgentLifecycleEvent.TERMINATING,
            {"agent_id": self.agent_id, "timestamp": datetime.now().isoformat()},
        )

        try:
            # Clean up agent components
            # This would typically involve cleaning up other managers and components

            # Update state
            self.state = AgentState.TERMINATED
            self.terminated_at = datetime.now()

            # Trigger terminated event
            self.event_handler.trigger(
                AgentLifecycleEvent.TERMINATED,
                {"agent_id": self.agent_id, "timestamp": self.terminated_at.isoformat()},
            )

            logger.info(f"Agent {self.agent_id} terminated successfully")
            return True
        except Exception as e:
            # Handle termination error
            self.state = AgentState.ERROR
            error = self.error_manager.handle_error(e)

            # Trigger error event
            self.event_handler.trigger(
                AgentLifecycleEvent.ERROR,
                {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "error": error.to_dict(),
                },
            )

            logger.error(f"Agent {self.agent_id} termination failed: {e}")
            return False

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the agent configuration.

        Args:
            config: New configuration to merge with existing config
        """
        # Merge new config with existing config
        self._config = merge_dicts(self._config, config)

        # Trigger config changed event
        self.event_handler.trigger(
            AgentLifecycleEvent.CONFIG_CHANGED,
            {
                "agent_id": self.agent_id,
                "timestamp": datetime.now().isoformat(),
                "config": self._config,
            },
        )

        logger.info(f"Agent {self.agent_id} configuration updated")

    def get_config(self) -> Dict[str, Any]:
        """Get the agent configuration.

        Returns:
            Current configuration
        """
        return self._config.copy()

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if not isinstance(value, dict) or k not in value:
                return default
            value = value[k]

        return value

    def set_config_value(self, key: str, value: Any) -> None:
        """Set a specific configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        keys = key.split(".")
        config = self._config

        # Navigate to the right level
        for i, k in enumerate(keys[:-1]):
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value

        # Trigger config changed event
        self.event_handler.trigger(
            AgentLifecycleEvent.CONFIG_CHANGED,
            {
                "agent_id": self.agent_id,
                "timestamp": datetime.now().isoformat(),
                "config": self._config,
                "key": key,
                "value": value,
            },
        )

    def mark_active(self) -> None:
        """Mark the agent as active."""
        self.last_active_at = datetime.now()

    def save_state(self) -> bool:
        """Save the agent state to disk.

        Returns:
            True if state was saved successfully, False otherwise
        """
        if not self._state_dir:
            logger.warning(f"Agent {self.agent_id} state directory not set")
            return False

        # Ensure state directory exists
        if not os.path.exists(self._state_dir):
            try:
                os.makedirs(self._state_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create state directory: {e}")
                return False

        # Get state to save
        state_data = self._get_state_data()

        # Save state
        state_file = os.path.join(self._state_dir, f"{self.agent_id}.json")
        try:
            with open(state_file, "w") as f:
                json.dump(state_data, f, indent=2, default=str)

            # Trigger state saved event
            self.event_handler.trigger(
                AgentLifecycleEvent.STATE_SAVED,
                {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "state_file": state_file,
                },
            )

            logger.info(f"Agent {self.agent_id} state saved to {state_file}")
            return True
        except Exception as e:
            # Handle save error
            error = self.error_manager.handle_error(e, error_code=AgentErrorCode.PERSISTENCE_ERROR)

            logger.error(f"Failed to save agent {self.agent_id} state: {e}")
            return False

    def load_state(self) -> bool:
        """Load the agent state from disk.

        Returns:
            True if state was loaded successfully, False otherwise
        """
        if not self._state_dir:
            logger.warning(f"Agent {self.agent_id} state directory not set")
            return False

        # Check if state file exists
        state_file = os.path.join(self._state_dir, f"{self.agent_id}.json")
        if not os.path.exists(state_file):
            logger.warning(f"Agent {self.agent_id} state file not found: {state_file}")
            return False

        # Load state
        try:
            with open(state_file, "r") as f:
                state_data = json.load(f)

            # Apply state
            self._apply_state_data(state_data)

            # Trigger state loaded event
            self.event_handler.trigger(
                AgentLifecycleEvent.STATE_LOADED,
                {
                    "agent_id": self.agent_id,
                    "timestamp": datetime.now().isoformat(),
                    "state_file": state_file,
                },
            )

            logger.info(f"Agent {self.agent_id} state loaded from {state_file}")
            return True
        except Exception as e:
            # Handle load error
            error = self.error_manager.handle_error(e, error_code=AgentErrorCode.PERSISTENCE_ERROR)

            logger.error(f"Failed to load agent {self.agent_id} state: {e}")
            return False

    def _get_state_data(self) -> Dict[str, Any]:
        """Get agent state data for saving.

        Returns:
            Dictionary of state data
        """
        # Get conversation data if available
        conversation_data = {}
        if hasattr(self.agent, "_conversation"):
            try:
                # Extract conversations data
                conversations = {}
                for conv_id, messages in self.agent._conversation._conversations.items():
                    # Convert Message objects to serializable dictionaries
                    conversations[conv_id] = [msg.to_dict() for msg in messages]

                # Extract metadata
                metadata = {}
                for conv_id, meta in self.agent._conversation._conversation_metadata.items():
                    # Convert datetime objects to strings
                    metadata[conv_id] = {
                        "created_at": meta.get("created_at").isoformat()
                        if meta.get("created_at")
                        else None,
                        "updated_at": meta.get("updated_at").isoformat()
                        if meta.get("updated_at")
                        else None,
                        "message_count": meta.get("message_count", 0),
                    }

                conversation_data = {"conversations": conversations, "metadata": metadata}
                logger.info(f"Extracted conversation data with {len(conversations)} conversations")
            except Exception as e:
                logger.warning(f"Failed to extract conversation data: {e}")

        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "terminated_at": self.terminated_at.isoformat() if self.terminated_at else None,
            "config": self._config,
            "version": self._version,
            "timestamp": datetime.now().isoformat(),
            "conversation_data": conversation_data,
        }

    def _apply_state_data(self, state_data: Dict[str, Any]) -> None:
        """Apply loaded state data.

        Args:
            state_data: Dictionary of state data
        """
        # Validate state data
        if "agent_id" not in state_data or state_data["agent_id"] != self.agent_id:
            raise StateError(
                f"State data agent_id mismatch: {state_data.get('agent_id')} != {self.agent_id}",
                agent_id=self.agent_id,
            )

        # Check version compatibility
        state_version = state_data.get("version", "1.0.0")
        if state_version != self._version:
            logger.warning(
                f"Agent {self.agent_id} state version mismatch: {state_version} != {self._version}"
            )

        # Apply state
        if "config" in state_data:
            self._config = state_data["config"]

        if "state" in state_data:
            try:
                self.state = AgentState(state_data["state"])
            except ValueError:
                logger.warning(f"Invalid agent state in state data: {state_data['state']}")

        # Restore conversation data if available
        if "conversation_data" in state_data and hasattr(self.agent, "_conversation"):
            try:
                conversation_data = state_data["conversation_data"]

                # First, clear existing conversations
                self.agent._conversation._conversations = {}
                self.agent._conversation._conversation_metadata = {}

                # Restore conversations
                if "conversations" in conversation_data:
                    from enterprise_ai.schema import Message

                    for conv_id, msg_dicts in conversation_data["conversations"].items():
                        # Initialize the conversation
                        self.agent._conversation._conversations[conv_id] = []

                        # Convert dict representations back to Message objects
                        for msg_dict in msg_dicts:
                            # Create a Message from the dict
                            message = Message.from_dict(msg_dict)
                            # Add to conversation
                            self.agent._conversation._conversations[conv_id].append(message)

                # Restore metadata
                if "metadata" in conversation_data:
                    for conv_id, meta_dict in conversation_data["metadata"].items():
                        # Convert ISO strings back to datetime objects
                        try:
                            created_at = (
                                datetime.fromisoformat(meta_dict["created_at"])
                                if meta_dict["created_at"]
                                else None
                            )
                            updated_at = (
                                datetime.fromisoformat(meta_dict["updated_at"])
                                if meta_dict["updated_at"]
                                else None
                            )
                        except (ValueError, TypeError):
                            logger.warning(
                                f"Invalid timestamp in conversation metadata for {conv_id}"
                            )
                            created_at = updated_at = datetime.now()

                        # Set metadata
                        self.agent._conversation._conversation_metadata[conv_id] = {
                            "created_at": created_at,
                            "updated_at": updated_at,
                            "message_count": meta_dict.get("message_count", 0),
                        }

                # Log success message
                num_conversations = len(self.agent._conversation._conversations)
                logger.info(f"Restored {num_conversations} conversations for agent {self.agent_id}")

                # Count total messages
                total_msgs = sum(
                    len(msgs) for msgs in self.agent._conversation._conversations.values()
                )
                logger.info(f"Restored {total_msgs} messages across all conversations")

            except Exception as e:
                logger.error(f"Failed to restore conversation data: {e}")

        # Parse timestamps
        if "created_at" in state_data and state_data["created_at"]:
            try:
                self.created_at = datetime.fromisoformat(state_data["created_at"])
            except ValueError:
                logger.warning(f"Invalid created_at in state data: {state_data['created_at']}")

        if "initialized_at" in state_data and state_data["initialized_at"]:
            try:
                self.initialized_at = datetime.fromisoformat(state_data["initialized_at"])
            except ValueError:
                logger.warning(
                    f"Invalid initialized_at in state data: {state_data['initialized_at']}"
                )

        if "last_active_at" in state_data and state_data["last_active_at"]:
            try:
                self.last_active_at = datetime.fromisoformat(state_data["last_active_at"])
            except ValueError:
                logger.warning(
                    f"Invalid last_active_at in state data: {state_data['last_active_at']}"
                )

    def get_uptime(self) -> Optional[float]:
        """Get agent uptime in seconds.

        Returns:
            Uptime in seconds or None if not initialized
        """
        if not self.initialized_at:
            return None

        return (datetime.now() - self.initialized_at).total_seconds()

    def get_status(self) -> Dict[str, Any]:
        """Get agent status information.

        Returns:
            Dictionary of status information
        """
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "terminated_at": self.terminated_at.isoformat() if self.terminated_at else None,
            "uptime": self.get_uptime(),
            "version": self._version,
        }
