"""
Enterprise AI Team - Shared Memory.

Implements shared memory for team-wide knowledge and state.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory, InMemoryConversation
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.memory")


class SharedMemory:
    """
    Shared memory for team-wide knowledge and state.
    
    This provides a central repository for:
    1. User interactions with the team
    2. Results from individual agents
    3. Shared knowledge that all agents can access
    4. Team state and metadata
    """
    
    def __init__(self):
        """Initialize shared memory."""
        self.conversation = InMemoryConversation()
        self.agent_responses = {}  # Map of agent_name -> list of (task, response) tuples
        self.knowledge_base = {}   # Shared facts and information
        self.metadata = {}         # Team metadata
    
    def add_user_message(self, content: str) -> None:
        """
        Add a user message to shared memory.
        
        Args:
            content: Message content
        """
        self.conversation.add_user_message(content)
    
    def add_assistant_message(self, content: str) -> None:
        """
        Add an assistant (team) message to shared memory.
        
        Args:
            content: Message content
        """
        self.conversation.add_assistant_message(content)
    
    def add_system_message(self, content: str) -> None:
        """
        Add a system message to shared memory.
        
        Args:
            content: Message content
        """
        self.conversation.add_system_message(content)
    
    def add_agent_message(self, agent_name: str, task: str, response: str) -> None:
        """
        Add an agent's response to a task.
        
        Args:
            agent_name: Name of the agent
            task: Task description
            response: Agent's response
        """
        # Store in agent responses
        if agent_name not in self.agent_responses:
            self.agent_responses[agent_name] = []
            
        self.agent_responses[agent_name].append((task, response, datetime.now()))
        
        # Add to conversation with agent prefix
        msg = Message(
            role="assistant",
            content=f"[{agent_name}] {response}",
            metadata={"agent": agent_name, "task": task}
        )
        
        self.conversation.add_message(msg)
    
    def get_agent_responses(self, agent_name: Optional[str] = None) -> Dict:
        """
        Get responses from specific agent or all agents.
        
        Args:
            agent_name: Optional agent name to filter responses
            
        Returns:
            Dictionary of agent responses
        """
        if agent_name:
            return {agent_name: self.agent_responses.get(agent_name, [])}
        return self.agent_responses
    
    def get_messages(self) -> List[Message]:
        """
        Get all conversation messages.
        
        Returns:
            List of messages
        """
        return self.conversation.get_messages()
    
    def add_knowledge(self, key: str, value: Any) -> None:
        """
        Add a knowledge item to the shared knowledge base.
        
        Args:
            key: Knowledge item key
            value: Knowledge item value
        """
        self.knowledge_base[key] = value
    
    def get_knowledge(self, key: Optional[str] = None) -> Any:
        """
        Get knowledge item(s) from the shared knowledge base.
        
        Args:
            key: Optional key to retrieve specific knowledge item
            
        Returns:
            Knowledge item value or entire knowledge base
        """
        if key:
            return self.knowledge_base.get(key)
        return self.knowledge_base
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set metadata item.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
    
    def get_metadata(self, key: Optional[str] = None) -> Any:
        """
        Get metadata item(s).
        
        Args:
            key: Optional key to retrieve specific metadata item
            
        Returns:
            Metadata item value or all metadata
        """
        if key:
            return self.metadata.get(key)
        return self.metadata
    
    def clear(self) -> None:
        """Clear all memory."""
        self.conversation.clear()
        self.agent_responses = {}
        self.knowledge_base = {}
        # Keep metadata for persistence