"""
Enhanced team messaging system.

Handles internal team communication and coordination messages.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enterprise_ai.schema import Message
from enterprise_ai.team.core import TeamRole
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.messaging")


@dataclass
class TeamMessage:
    """Enhanced team message with routing and priority."""
    sender: str
    recipient: Optional[str]  # None for broadcast
    content: str
    message_type: str = "task"  # task, status, coordination, error
    priority: int = 0  # Higher = more urgent
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_broadcast(self) -> bool:
        """Check if message is broadcast to all members."""
        return self.recipient is None


class TeamMessaging:
    """Advanced team messaging system."""
    
    def __init__(self):
        self.message_history: List[TeamMessage] = []
        self.member_inboxes: Dict[str, List[TeamMessage]] = {}
        self.broadcast_messages: List[TeamMessage] = []
        
    def send_message(self, message: TeamMessage) -> str:
        """Send message to team member(s)."""
        message_id = f"{message.sender}_{len(self.message_history)}"
        self.message_history.append(message)
        
        if message.is_broadcast:
            self.broadcast_messages.append(message)
            logger.info(f"Broadcast message from {message.sender}: {message.content[:50]}...")
        else:
            # Deliver to specific recipient
            if message.recipient not in self.member_inboxes:
                self.member_inboxes[message.recipient] = []
            self.member_inboxes[message.recipient].append(message)
            logger.info(f"Message {message.sender} -> {message.recipient}: {message.content[:50]}...")
        
        return message_id
    
    def get_messages_for_member(self, member_name: str, unread_only: bool = False) -> List[TeamMessage]:
        """Get messages for specific member."""
        messages = []
        
        # Add direct messages
        direct_messages = self.member_inboxes.get(member_name, [])
        messages.extend(direct_messages)
        
        # Add broadcast messages
        messages.extend(self.broadcast_messages)
        
        # Sort by priority and timestamp
        messages.sort(key=lambda m: (-m.priority, m.timestamp))
        
        return messages
    
    def create_coordination_message(self, sender: str, task_info: Dict[str, Any]) -> TeamMessage:
        """Create coordination message for task delegation."""
        return TeamMessage(
            sender=sender,
            recipient=None,  # Broadcast
            content=f"New task coordination: {task_info.get('description', 'No description')}",
            message_type="coordination",
            priority=task_info.get('priority', 0),
            metadata={"task_info": task_info}
        )
    
    def create_status_update(self, sender: str, status: str, details: str = "") -> TeamMessage:
        """Create status update message."""
        return TeamMessage(
            sender=sender,
            recipient=None,  # Broadcast
            content=f"Status update: {status}. {details}",
            message_type="status",
            priority=1,
            metadata={"status": status, "details": details}
        )
    
    def create_task_assignment(self, sender: str, recipient: str, task_description: str) -> TeamMessage:
        """Create task assignment message."""
        return TeamMessage(
            sender=sender,
            recipient=recipient,
            content=f"Task assignment: {task_description}",
            message_type="task",
            priority=2,
            metadata={"task_description": task_description}
        )
    
    def get_recent_messages(self, limit: int = 10) -> List[TeamMessage]:
        """Get recent team messages."""
        return sorted(self.message_history, key=lambda m: m.timestamp, reverse=True)[:limit]
    
    def clear_member_inbox(self, member_name: str) -> int:
        """Clear member's inbox and return count of cleared messages."""
        if member_name in self.member_inboxes:
            count = len(self.member_inboxes[member_name])
            self.member_inboxes[member_name] = []
            return count
        return 0
