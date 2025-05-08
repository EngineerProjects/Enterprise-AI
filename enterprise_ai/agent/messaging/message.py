"""
Agent messaging system for Enterprise AI.

This module provides implementations of the AgentMessage protocol
defined in types.py, enabling agent-to-agent communication.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Union, ClassVar, cast

from enterprise_ai.agent.core.types import AgentMessage
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("agent.message")


class MessageType(Enum):
    """Types of agent messages."""

    TASK_ASSIGNMENT = auto()  # Assign a task to an agent
    TASK_UPDATE = auto()  # Update task status
    TASK_COMPLETE = auto()  # Task completion notification
    QUERY = auto()  # Information request
    RESPONSE = auto()  # Response to a query
    BROADCAST = auto()  # Broadcast to all agents
    NOTIFICATION = auto()  # General notification
    ERROR = auto()  # Error message


@dataclass
class BaseAgentMessage(AgentMessage):
    """Base implementation of agent-to-agent messages.

    This class provides a concrete implementation of AgentMessage with
    support for different message types and metadata.
    """

    sender_id: str
    receiver_id: Optional[str]
    message_type: str
    content: Optional[str] = None
    name: Optional[str] = None
    timestamp: Optional[datetime] = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    role: str = "agent"
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reply_to: Optional[str] = None

    @property
    def is_broadcast(self) -> bool:
        """Check if message is a broadcast (no specific receiver).

        Returns:
            True if the message is a broadcast, False otherwise
        """
        return self.receiver_id is None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation.

        Returns:
            Dictionary representation of the message
        """
        # Create the base result dictionary
        result: Dict[str, Any] = {
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type,
            "role": self.role,
            "message_id": self.message_id,
        }

        # Add timestamp with proper handling
        if self.timestamp:
            result["timestamp"] = self.timestamp.isoformat()
        else:
            result["timestamp"] = None

        # Add optional fields only if they exist
        if self.content is not None:
            result["content"] = self.content

        if self.name is not None:
            result["name"] = self.name

        if self.reply_to is not None:
            result["reply_to"] = self.reply_to

        # Handle metadata separately to avoid type errors
        if self.metadata:
            metadata_dict: Dict[str, Any] = {}
            for key, value in self.metadata.items():
                metadata_dict[key] = value

            if metadata_dict:  # Only add if not empty
                result["metadata"] = metadata_dict

        return result

    def to_message(self) -> Message:
        """Convert to a standard Message object.

        This can be useful for compatibility with LLM interfaces that
        expect standard message objects.

        Returns:
            Standard Message object
        """
        # Create a copy of metadata to avoid modifying the original
        metadata_dict: Dict[str, Any] = {}
        if self.metadata:
            for key, value in self.metadata.items():
                metadata_dict[key] = value

        # Add agent-specific metadata
        metadata_dict["agent_metadata"] = {
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type,
            "message_id": self.message_id,
            "reply_to": self.reply_to,
            "is_broadcast": self.is_broadcast,
        }

        return Message(
            role=self.role,
            content=self.content,
            name=self.name or f"agent_{self.sender_id}",
            metadata=metadata_dict,
            timestamp=self.timestamp,
        )

    @classmethod
    def from_message(
        cls,
        message: MessageProtocol,
        sender_id: str,
        receiver_id: Optional[str] = None,
        message_type: str = "NOTIFICATION",
    ) -> "BaseAgentMessage":
        """Create an agent message from a standard Message.

        Args:
            message: Standard message to convert
            sender_id: ID of the sending agent
            receiver_id: Optional ID of the receiving agent
            message_type: Type of message

        Returns:
            Agent message
        """
        # Extract agent metadata if present
        agent_metadata: Dict[str, Any] = {}
        metadata_dict: Dict[str, Any] = {}

        if message.metadata:
            if "agent_metadata" in message.metadata:
                agent_metadata = message.metadata["agent_metadata"]
                # Create a copy of metadata without agent_metadata to avoid duplication
                for key, value in message.metadata.items():
                    if key != "agent_metadata":
                        metadata_dict[key] = value
            else:
                for key, value in message.metadata.items():
                    metadata_dict[key] = value

        return cls(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=message.content,
            name=message.name,
            timestamp=message.timestamp,
            metadata=metadata_dict,
            role=message.role,
            reply_to=agent_metadata.get("message_id"),
        )

    @classmethod
    def user_message(cls, content: str, **kwargs: Any) -> MessageProtocol:
        """Create a user message.

        Args:
            content: Message content
            **kwargs: Additional message parameters

        Returns:
            User message
        """
        msg = Message.user_message(content, **kwargs)
        return cast(MessageProtocol, msg)

    @classmethod
    def system_message(cls, content: str, **kwargs: Any) -> MessageProtocol:
        """Create a system message.

        Args:
            content: Message content
            **kwargs: Additional message parameters

        Returns:
            System message
        """
        msg = Message.system_message(content, **kwargs)
        return cast(MessageProtocol, msg)

    @classmethod
    def assistant_message(cls, content: str, **kwargs: Any) -> MessageProtocol:
        """Create an assistant message.

        Args:
            content: Message content
            **kwargs: Additional message parameters

        Returns:
            Assistant message
        """
        msg = Message.assistant_message(content, **kwargs)
        return cast(MessageProtocol, msg)


class TaskAssignmentMessage(BaseAgentMessage):
    """Message for assigning tasks to agents."""

    def __init__(
        self,
        sender_id: str,
        receiver_id: str,
        task_id: str,
        task_description: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a task assignment message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            task_id: ID of the task being assigned
            task_description: Description of the task
            **kwargs: Additional message parameters
        """
        # Extract and handle metadata carefully
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value

        metadata_dict["task_id"] = task_id

        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="TASK_ASSIGNMENT",
            content=task_description,
            metadata=metadata_dict,
            **kwargs,
        )


class TaskUpdateMessage(BaseAgentMessage):
    """Message for updating task status."""

    def __init__(
        self,
        sender_id: str,
        receiver_id: str,
        task_id: str,
        status: str,
        status_message: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a task update message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            task_id: ID of the task being updated
            status: New status of the task
            status_message: Status description
            **kwargs: Additional message parameters
        """
        # Extract and handle metadata carefully
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value

        metadata_dict["task_id"] = task_id
        metadata_dict["status"] = status

        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="TASK_UPDATE",
            content=status_message,
            metadata=metadata_dict,
            **kwargs,
        )


class QueryMessage(BaseAgentMessage):
    """Message for requesting information from other agents."""

    def __init__(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        query: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a query message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            query: Query content
            **kwargs: Additional message parameters
        """
        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="QUERY",
            content=query,
            **kwargs,
        )


class ResponseMessage(BaseAgentMessage):
    """Message for responding to queries."""

    def __init__(
        self,
        sender_id: str,
        receiver_id: str,
        response: str,
        query_id: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a response message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            response: Response content
            query_id: ID of the query being responded to
            **kwargs: Additional message parameters
        """
        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="RESPONSE",
            content=response,
            reply_to=query_id,
            **kwargs,
        )


class BroadcastMessage(BaseAgentMessage):
    """Message for broadcasting to all agents."""

    def __init__(
        self,
        sender_id: str,
        content: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a broadcast message.

        Args:
            sender_id: ID of the sending agent
            content: Message content
            **kwargs: Additional message parameters
        """
        super().__init__(
            sender_id=sender_id,
            receiver_id=None,  # None indicates broadcast
            message_type="BROADCAST",
            content=content,
            **kwargs,
        )


class NotificationMessage(BaseAgentMessage):
    """Message for general notifications."""

    def __init__(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        content: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a notification message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            content: Notification content
            **kwargs: Additional message parameters
        """
        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="NOTIFICATION",
            content=content,
            **kwargs,
        )


class ErrorMessage(BaseAgentMessage):
    """Message for error notifications."""

    def __init__(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        error_message: str,
        error_code: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize an error message.

        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            error_message: Error description
            error_code: Optional error code
            **kwargs: Additional message parameters
        """
        # Extract and handle metadata carefully
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value

        if error_code:
            metadata_dict["error_code"] = error_code

        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="ERROR",
            content=error_message,
            metadata=metadata_dict,
            **kwargs,
        )


# Factory function to create messages
def create_message(
    message_type: str,
    sender_id: str,
    receiver_id: Optional[str] = None,
    content: Optional[str] = None,
    **kwargs: Any,
) -> AgentMessage:
    """Create a message by type.

    Args:
        message_type: Type of message to create
        sender_id: ID of the sending agent
        receiver_id: ID of the receiving agent or None for broadcast
        content: Message content
        **kwargs: Additional message parameters

    Returns:
        AgentMessage implementation

    Raises:
        ValueError: If an unknown message type is specified
    """
    message_type_upper = message_type.upper()

    if message_type_upper == "TASK_ASSIGNMENT":
        if "task_id" not in kwargs or ("task_description" not in kwargs and not content):
            raise ValueError("Task assignment requires task_id and task_description")
        return TaskAssignmentMessage(
            sender_id,
            receiver_id or "",  # Task assignments require a receiver
            kwargs["task_id"],
            kwargs.get("task_description", content or ""),
            **{k: v for k, v in kwargs.items() if k not in ["task_id", "task_description"]},
        )

    elif message_type_upper == "TASK_UPDATE":
        if "task_id" not in kwargs or "status" not in kwargs:
            raise ValueError("Task update requires task_id and status")
        return TaskUpdateMessage(
            sender_id,
            receiver_id or "",  # Task updates require a receiver
            kwargs["task_id"],
            kwargs["status"],
            kwargs.get("status_message", content or ""),
            **{k: v for k, v in kwargs.items() if k not in ["task_id", "status", "status_message"]},
        )

    elif message_type_upper == "QUERY":
        if not content:
            raise ValueError("Query requires content")
        return QueryMessage(sender_id, receiver_id, content, **kwargs)

    elif message_type_upper == "RESPONSE":
        if not content or "query_id" not in kwargs:
            raise ValueError("Response requires content and query_id")
        return ResponseMessage(
            sender_id,
            receiver_id or "",  # Responses require a receiver
            content,
            kwargs["query_id"],
            **{k: v for k, v in kwargs.items() if k != "query_id"},
        )

    elif message_type_upper == "BROADCAST":
        if not content:
            raise ValueError("Broadcast requires content")
        return BroadcastMessage(sender_id, content, **kwargs)

    elif message_type_upper == "NOTIFICATION":
        if not content:
            raise ValueError("Notification requires content")
        return NotificationMessage(sender_id, receiver_id, content, **kwargs)

    elif message_type_upper == "ERROR":
        if not content:
            raise ValueError("Error requires content")
        return ErrorMessage(
            sender_id,
            receiver_id,
            content,
            kwargs.get("error_code"),
            **{k: v for k, v in kwargs.items() if k != "error_code"},
        )

    else:
        return BaseAgentMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
            **kwargs,
        )
