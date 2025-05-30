"""
Team messaging for Enterprise AI.

This module provides functionality for team communication,
extending the agent messaging system for team-based interactions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.core.types import AgentMessage, AgentProtocol, MessageProtocol, ToolInteractionType
from enterprise_ai.agent.messaging.message import (
    BaseAgentMessage, 
    BroadcastMessage, 
    NotificationMessage,
    QueryMessage,
    ResponseMessage,
    ErrorMessage
)
from enterprise_ai.logger import get_logger
from enterprise_ai.team.core.types import TeamMessageType, TeamProtocol

logger = get_logger("team.architecture.messaging")


class TeamMessage(BaseAgentMessage):
    """Extended agent message with team-specific metadata.
    
    This class adds team-specific metadata to the BaseAgentMessage,
    allowing for team coordination and routing.
    """
    
    def __init__(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        message_type: str,
        content: Optional[str] = None,
        team_id: Optional[str] = None,
        team_message_type: Optional[TeamMessageType] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a team message.
        
        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            message_type: Type of message
            content: Message content
            team_id: ID of the team
            team_message_type: Team-specific message type
            **kwargs: Additional message parameters
        """
        # Extract and handle metadata carefully
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value
        
        # Add team-specific metadata
        if team_id:
            metadata_dict["team_id"] = team_id
        
        if team_message_type:
            metadata_dict["team_message_type"] = team_message_type.value
        
        super().__init__(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
            metadata=metadata_dict,
            **kwargs,
        )
    
    @property
    def team_id(self) -> Optional[str]:
        """Get the team ID.
        
        Returns:
            Team ID or None if not set
        """
        return self.metadata.get("team_id")
    
    @property
    def team_message_type(self) -> Optional[TeamMessageType]:
        """Get the team message type.
        
        Returns:
            Team message type or None if not set
        """
        if "team_message_type" in self.metadata:
            try:
                return TeamMessageType(self.metadata["team_message_type"])
            except (ValueError, TypeError):
                return None
        return None
    
    @classmethod
    def from_agent_message(
        cls,
        message: AgentMessage,
        team_id: Optional[str] = None,
        team_message_type: Optional[TeamMessageType] = None,
    ) -> "TeamMessage":
        """Create a team message from an agent message.
        
        Args:
            message: Agent message to convert
            team_id: Optional team ID to add
            team_message_type: Optional team message type to add
            
        Returns:
            Team message
        """
        if isinstance(message, TeamMessage):
            # Already a TeamMessage, just update team_id if needed
            if team_id and not message.team_id:
                message.metadata["team_id"] = team_id
            if team_message_type and not message.team_message_type:
                message.metadata["team_message_type"] = team_message_type.value
            return message
        
        # Extract original metadata
        metadata_dict: Dict[str, Any] = {}
        if hasattr(message, "metadata") and message.metadata:
            for key, value in message.metadata.items():
                metadata_dict[key] = value
        
        # Add team-specific metadata
        if team_id:
            metadata_dict["team_id"] = team_id
        
        if team_message_type:
            metadata_dict["team_message_type"] = team_message_type.value
        
        # Create new TeamMessage
        return cls(
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            message_type=message.message_type,
            content=message.content,
            name=getattr(message, "name", None),
            timestamp=getattr(message, "timestamp", datetime.now()),
            metadata=metadata_dict,
            role=message.role,
            message_id=message.message_id,
            reply_to=getattr(message, "reply_to", None),
            tool_interaction=getattr(message, "tool_interaction", None),
            tool_data=getattr(message, "tool_data", None),
        )


class TeamBroadcastMessage(TeamMessage):
    """Team-specific broadcast message."""
    
    def __init__(
        self,
        sender_id: str,
        content: str,
        team_id: str,
        **kwargs: Any,
    ) -> None:
        """Initialize a team broadcast message.
        
        Args:
            sender_id: ID of the sending agent
            content: Message content
            team_id: ID of the team
            **kwargs: Additional message parameters
        """
        super().__init__(
            sender_id=sender_id,
            receiver_id=None,  # None indicates broadcast
            message_type="BROADCAST",
            content=content,
            team_id=team_id,
            team_message_type=TeamMessageType.BROADCAST,
            **kwargs,
        )


class MessagingManager:
    """Team messaging manager.
    
    This component handles all aspects of team communication, including:
    - Processing incoming messages
    - Routing messages to appropriate team members
    - Broadcasting messages to all team members
    - Managing message history
    - Implementing message filtering and prioritization
    """
    
    def __init__(self, team: "TeamProtocol"):
        """Initialize the messaging manager.
        
        Args:
            team: Team that this manager belongs to
        """
        self._team = team
        self._message_history: List[AgentMessage] = []
        self._message_index: Dict[str, AgentMessage] = {}  # Index by message_id
        self._thread_index: Dict[str, List[str]] = {}  # Index by reply_to -> list of message_ids
        
        logger.info(f"Initialized messaging manager for team {team.id}")
    
    @property
    def history_count(self) -> int:
        """Get the number of messages in the history.
        
        Returns:
            Number of messages
        """
        return len(self._message_history)
    
    def send_message(
        self,
        message: Union[str, AgentMessage, MessageProtocol],
        sender_id: Optional[str] = None,
        receiver_id: Optional[str] = None,
        message_type: str = "NOTIFICATION",
        **kwargs: Any,
    ) -> AgentMessage:
        """Send a message to a team member.
        
        Args:
            message: Message to send
            sender_id: Optional sender ID
            receiver_id: Optional receiver ID
            message_type: Type of message
            **kwargs: Additional message parameters
            
        Returns:
            Sent message
        """
        # Convert string to message if needed
        if isinstance(message, str):
            # Create a message using the appropriate parameters
            resolved_sender_id = sender_id or kwargs.get("sender_id") or self._team.id
            
            if message_type.upper() == "BROADCAST":
                msg = TeamBroadcastMessage(
                    sender_id=resolved_sender_id,
                    content=message,
                    team_id=self._team.id,
                    **{k: v for k, v in kwargs.items() if k not in ["sender_id", "team_id"]},
                )
            else:
                msg = TeamMessage(
                    sender_id=resolved_sender_id,
                    receiver_id=receiver_id,
                    message_type=message_type,
                    content=message,
                    team_id=self._team.id,
                    **{k: v for k, v in kwargs.items() if k not in ["sender_id", "team_id"]},
                )
        else:
            # Convert existing message to TeamMessage if needed
            msg = TeamMessage.from_agent_message(
                cast(AgentMessage, message),
                team_id=self._team.id,
            )
            
            # Override sender/receiver if specified
            if sender_id:
                msg.sender_id = sender_id
            if receiver_id:
                msg.receiver_id = receiver_id
        
        # Record in message history
        self._record_message(msg)
        
        logger.info(
            f"Team {self._team.id} sent message from {msg.sender_id} "
            f"to {msg.receiver_id or 'broadcast'} of type {msg.message_type}"
        )
        
        return msg
    
    def broadcast(
        self,
        message: Union[str, AgentMessage, MessageProtocol],
        sender_id: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentMessage:
        """Broadcast a message to all team members.
        
        Args:
            message: Message to broadcast
            sender_id: Optional sender ID
            **kwargs: Additional message parameters
            
        Returns:
            Broadcast message
        """
        # Determine the sender ID
        resolved_sender_id = sender_id or kwargs.get("sender_id") or self._team.id
        
        # Convert to broadcast message
        if isinstance(message, str):
            # Create a new broadcast message
            msg = TeamBroadcastMessage(
                sender_id=resolved_sender_id,
                content=message,
                team_id=self._team.id,
                team_message_type=TeamMessageType.BROADCAST,
                **{k: v for k, v in kwargs.items() if k not in ["sender_id", "team_id"]},
            )
        else:
            # Convert existing message to broadcast
            orig_message = cast(AgentMessage, message)
            
            if isinstance(orig_message, TeamBroadcastMessage):
                # Already a team broadcast message
                msg = orig_message
                # Update sender if specified
                if sender_id:
                    msg.sender_id = resolved_sender_id
            elif isinstance(orig_message, BroadcastMessage):
                # Regular broadcast message, convert to team broadcast
                msg = TeamBroadcastMessage(
                    sender_id=resolved_sender_id,
                    content=orig_message.content or "",
                    team_id=self._team.id,
                    **{k: v for k, v in kwargs.items() if k not in ["sender_id", "team_id"]},
                )
            else:
                # Other message type, convert to team broadcast
                msg = TeamBroadcastMessage(
                    sender_id=resolved_sender_id,
                    content=orig_message.content or "",
                    team_id=self._team.id,
                    **{k: v for k, v in kwargs.items() if k not in ["sender_id", "team_id"]},
                )
        
        # Record in message history
        self._record_message(msg)
        
        logger.info(f"Team {self._team.id} broadcast message from {msg.sender_id}")
        
        return msg
    
    def route_message(
        self,
        message: AgentMessage,
    ) -> Optional[AgentProtocol]:
        """Route a message to the appropriate team member.
        
        Args:
            message: Message to route
            
        Returns:
            Agent that the message was routed to, or None if not routed
        """
        if not message.receiver_id:
            logger.warning(f"Cannot route message without receiver_id: {message.message_id}")
            return None
        
        # Find the target agent
        target_agent = self._team.get_member(message.receiver_id)
        if not target_agent:
            logger.warning(
                f"Cannot route message: receiver {message.receiver_id} "
                f"is not a member of team {self._team.id}"
            )
            return None
        
        # Record in message history
        self._record_message(message)
        
        logger.info(
            f"Team {self._team.id} routed message from {message.sender_id} "
            f"to {message.receiver_id} of type {message.message_type}"
        )
        
        return target_agent
    
    def get_message_by_id(self, message_id: str) -> Optional[AgentMessage]:
        """Get a message by its ID.
        
        Args:
            message_id: ID of the message to retrieve
            
        Returns:
            Message with the specified ID, or None if not found
        """
        return self._message_index.get(message_id)
    
    def get_thread(self, root_message_id: str) -> List[AgentMessage]:
        """Get all messages in a thread.
        
        Args:
            root_message_id: ID of the root message of the thread
            
        Returns:
            List of messages in the thread
        """
        # Start with the root message
        thread_messages: List[AgentMessage] = []
        root_message = self.get_message_by_id(root_message_id)
        if root_message:
            thread_messages.append(root_message)
        
        # Add all replies
        message_ids = self._thread_index.get(root_message_id, [])
        for msg_id in message_ids:
            msg = self.get_message_by_id(msg_id)
            if msg:
                thread_messages.append(msg)
                
                # Recursively get replies to this message
                nested_ids = self._thread_index.get(msg_id, [])
                for nested_id in nested_ids:
                    nested_msg = self.get_message_by_id(nested_id)
                    if nested_msg:
                        thread_messages.append(nested_msg)
        
        return thread_messages
    
    def get_messages_by_type(self, message_type: str) -> List[AgentMessage]:
        """Get messages of a specific type.
        
        Args:
            message_type: Type of messages to retrieve
            
        Returns:
            List of messages of the specified type
        """
        return [
            msg for msg in self._message_history
            if msg.message_type == message_type
        ]
    
    def get_messages_by_sender(self, sender_id: str) -> List[AgentMessage]:
        """Get messages from a specific sender.
        
        Args:
            sender_id: ID of the sender
            
        Returns:
            List of messages from the specified sender
        """
        return [
            msg for msg in self._message_history
            if msg.sender_id == sender_id
        ]
    
    def get_messages_by_receiver(self, receiver_id: str) -> List[AgentMessage]:
        """Get messages to a specific receiver.
        
        Args:
            receiver_id: ID of the receiver
            
        Returns:
            List of messages to the specified receiver
        """
        return [
            msg for msg in self._message_history
            if msg.receiver_id == receiver_id
        ]
    
    def get_messages_by_team(self, team_id: str) -> List[AgentMessage]:
        """Get messages related to a specific team.
        
        Args:
            team_id: ID of the team
            
        Returns:
            List of messages related to the specified team
        """
        return [
            msg for msg in self._message_history
            if isinstance(msg, TeamMessage) and msg.team_id == team_id
        ]
    
    def get_message_history(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        reverse: bool = True,
    ) -> List[AgentMessage]:
        """Get message history.
        
        Args:
            limit: Maximum number of messages to retrieve
            offset: Number of messages to skip
            reverse: Whether to return messages in reverse order (newest first)
            
        Returns:
            List of messages
        """
        messages = self._message_history
        
        # Reverse if requested
        if reverse:
            messages = list(reversed(messages))
        
        # Apply offset and limit
        start = offset
        end = None if limit is None else offset + limit
        
        return messages[start:end]
    
    def clear_history(self) -> None:
        """Clear message history."""
        self._message_history = []
        self._message_index = {}
        self._thread_index = {}
        
        logger.info(f"Cleared message history for team {self._team.id}")
    
    def create_query(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        query: str,
        **kwargs: Any,
    ) -> QueryMessage:
        """Create a query message.
        
        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            query: Query content
            **kwargs: Additional message parameters
            
        Returns:
            Query message
        """
        # Create a team-specific query message
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value
        
        # Add team metadata
        metadata_dict["team_id"] = self._team.id
        metadata_dict["team_message_type"] = TeamMessageType.DIRECT.value
        
        msg = QueryMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            query=query,
            metadata=metadata_dict,
            **kwargs,
        )
        
        # Record in message history
        self._record_message(msg)
        
        return msg
    
    def create_response(
        self,
        sender_id: str,
        receiver_id: str,
        response: str,
        query_id: str,
        **kwargs: Any,
    ) -> ResponseMessage:
        """Create a response message.
        
        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent
            response: Response content
            query_id: ID of the query being responded to
            **kwargs: Additional message parameters
            
        Returns:
            Response message
        """
        # Create a team-specific response message
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value
        
        # Add team metadata
        metadata_dict["team_id"] = self._team.id
        metadata_dict["team_message_type"] = TeamMessageType.DIRECT.value
        
        msg = ResponseMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            response=response,
            query_id=query_id,
            metadata=metadata_dict,
            **kwargs,
        )
        
        # Record in message history
        self._record_message(msg)
        
        return msg
    
    def create_error(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        error_message: str,
        error_code: Optional[str] = None,
        **kwargs: Any,
    ) -> ErrorMessage:
        """Create an error message.
        
        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            error_message: Error description
            error_code: Optional error code
            **kwargs: Additional message parameters
            
        Returns:
            Error message
        """
        # Create a team-specific error message
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value
        
        # Add team metadata
        metadata_dict["team_id"] = self._team.id
        
        if receiver_id is None:
            metadata_dict["team_message_type"] = TeamMessageType.BROADCAST.value
        else:
            metadata_dict["team_message_type"] = TeamMessageType.DIRECT.value
        
        if error_code:
            metadata_dict["error_code"] = error_code
        
        msg = ErrorMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            error_message=error_message,
            metadata=metadata_dict,
            **{k: v for k, v in kwargs.items() if k != "error_code"},
        )
        
        # Record in message history
        self._record_message(msg)
        
        return msg
    
    def create_notification(
        self,
        sender_id: str,
        receiver_id: Optional[str],
        content: str,
        **kwargs: Any,
    ) -> NotificationMessage:
        """Create a notification message.
        
        Args:
            sender_id: ID of the sending agent
            receiver_id: ID of the receiving agent or None for broadcast
            content: Notification content
            **kwargs: Additional message parameters
            
        Returns:
            Notification message
        """
        # Create a team-specific notification message
        metadata_dict: Dict[str, Any] = {}
        if "metadata" in kwargs:
            for key, value in kwargs.pop("metadata").items():
                metadata_dict[key] = value
        
        # Add team metadata
        metadata_dict["team_id"] = self._team.id
        
        if receiver_id is None:
            metadata_dict["team_message_type"] = TeamMessageType.BROADCAST.value
        else:
            metadata_dict["team_message_type"] = TeamMessageType.DIRECT.value
        
        msg = NotificationMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            metadata=metadata_dict,
            **kwargs,
        )
        
        # Record in message history
        self._record_message(msg)
        
        return msg
    
    def _record_message(self, message: AgentMessage) -> None:
        """Record a message in the history.
        
        Args:
            message: Message to record
        """
        # Add to history
        self._message_history.append(message)
        
        # Index by message_id
        self._message_index[message.message_id] = message
        
        # Index by thread
        if hasattr(message, "reply_to") and message.reply_to:
            if message.reply_to not in self._thread_index:
                self._thread_index[message.reply_to] = []
            self._thread_index[message.reply_to].append(message.message_id)
