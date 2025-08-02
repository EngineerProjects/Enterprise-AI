"""
Enterprise AI Team - Communication Protocol.

Implements the protocol for inter-agent communication.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime
import json

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.communication")


@dataclass
class TeamMessage:
    """Message exchanged between team agents."""
    
    sender: str
    recipient: str
    content: str
    msg_type: str = "message"  # "message", "task", "result", "broadcast", "peer_message"
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
            
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "msg_type": self.msg_type,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TeamMessage':
        """Create from dictionary."""
        # Convert timestamp string to datetime if present
        if data.get("timestamp"):
            try:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            except ValueError:
                data["timestamp"] = datetime.now()
                
        return cls(**data)
    
    @classmethod
    def create_task(cls, sender: str, recipient: str, task: str, metadata: Optional[Dict[str, Any]] = None) -> 'TeamMessage':
        """Create a task message."""
        return cls(
            sender=sender,
            recipient=recipient,
            content=task,
            msg_type="task",
            metadata=metadata or {}
        )
    
    @classmethod
    def create_result(cls, sender: str, recipient: str, result: str, metadata: Optional[Dict[str, Any]] = None) -> 'TeamMessage':
        """Create a result message."""
        return cls(
            sender=sender,
            recipient=recipient,
            content=result,
            msg_type="result",
            metadata=metadata or {}
        )
    
    @classmethod
    def create_broadcast(cls, sender: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> 'TeamMessage':
        """Create a broadcast message."""
        return cls(
            sender=sender,
            recipient="all",
            content=content,
            msg_type="broadcast",
            metadata=metadata or {}
        )
    
    @classmethod
    def create_peer_message(cls, sender: str, recipient: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> 'TeamMessage':
        """Create a peer-to-peer message."""
        return cls(
            sender=sender,
            recipient=recipient,
            content=content,
            msg_type="peer_message",
            metadata=metadata or {}
        )


class CommunicationProtocol:
    """
    Protocol for inter-agent communication.
    
    This handles:
    1. Message formatting for agent interactions
    2. Routing messages between agents
    3. Broadcasting messages to all agents
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize communication protocol.
        
        Args:
            max_history: Maximum number of messages to keep in history
        """
        self.message_history = []
        self.max_history = max_history
    
    def format_team_message(self, message: TeamMessage) -> str:
        """
        Format a team message for agent consumption.
        
        Args:
            message: Team message
            
        Returns:
            Formatted message string
        """
        # Store message in history with bounds checking
        self.message_history.append(message)
        
        # Cleanup old messages if history is too long
        if len(self.message_history) > self.max_history:
            # Keep only the most recent messages
            self.message_history = self.message_history[-self.max_history:]
            logger.debug(f"Cleaned up message history, keeping {self.max_history} recent messages")
        
        # Format based on message type
        if message.msg_type == "task":
            return f"[TASK from {message.sender}]\n{message.content}"
        elif message.msg_type == "result":
            return f"[RESULT from {message.sender}]\n{message.content}"
        elif message.msg_type == "broadcast":
            return f"[BROADCAST from {message.sender}]\n{message.content}"
        elif message.msg_type == "peer_message":
            return f"[MESSAGE from @{message.sender}]\n{message.content}"
        else:
            return f"[MESSAGE from {message.sender}]\n{message.content}"
    
    def parse_agent_response(self, agent_name: str, response: str) -> TeamMessage:
        """
        Parse an agent's response into a team message.
        
        Args:
            agent_name: Name of the agent
            response: Agent's response
            
        Returns:
            Team message
        """
        # Default to a result message to the manager
        return TeamMessage(
            sender=agent_name,
            recipient="manager",
            content=response,
            msg_type="result"
        )
    
    def get_messages_for_agent(self, agent_name: str) -> List[TeamMessage]:
        """
        Get all messages addressed to an agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            List of messages for the agent
        """
        return [
            msg for msg in self.message_history 
            if msg.recipient == agent_name or msg.recipient == "all"
        ]
    
    def get_conversation_between(self, agent1: str, agent2: str) -> List[TeamMessage]:
        """
        Get conversation between two agents.
        
        Args:
            agent1: First agent name
            agent2: Second agent name
            
        Returns:
            List of messages between the agents
        """
        return [
            msg for msg in self.message_history
            if (msg.sender == agent1 and msg.recipient == agent2) or
               (msg.sender == agent2 and msg.recipient == agent1)
        ]
    
    def clear_history(self) -> None:
        """Clear message history."""
        self.message_history = []