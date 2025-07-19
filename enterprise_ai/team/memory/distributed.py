"""
Enterprise AI Team - Distributed Memory.

Implements agent-specific memory with synchronization capabilities.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory, InMemoryConversation
from enterprise_ai.team.memory.shared import SharedMemory
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.memory.distributed")


class DistributedMemory:
    """
    Distributed memory with agent-specific contexts and synchronization.
    
    This provides:
    1. Individual memory for each agent
    2. Synchronization with shared team memory
    3. Selective sharing of context between agents
    """
    
    def __init__(
        self,
        agent_names: List[str],
        shared_memory: Optional[SharedMemory] = None
    ):
        """
        Initialize distributed memory.
        
        Args:
            agent_names: List of agent names
            shared_memory: Shared team memory
        """
        self.agent_memories = {name: InMemoryConversation() for name in agent_names}
        self.shared_memory = shared_memory or SharedMemory()
    
    def get_agent_memory(self, agent_name: str) -> Optional[ConversationMemory]:
        """
        Get memory for specific agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            Agent's memory or None if not found
        """
        return self.agent_memories.get(agent_name)
    
    def add_message_to_agent(self, agent_name: str, message: Message) -> None:
        """
        Add message to specific agent's memory.
        
        Args:
            agent_name: Agent name
            message: Message to add
            
        Raises:
            ValueError: If agent not found
        """
        if agent_name not in self.agent_memories:
            raise ValueError(f"Agent '{agent_name}' not found")
            
        self.agent_memories[agent_name].add_message(message)
    
    def sync_from_shared(self, agent_name: str, message_types: Optional[List[str]] = None) -> None:
        """
        Sync messages from shared memory to agent memory.
        
        Args:
            agent_name: Agent name
            message_types: Optional list of message roles to sync (e.g., ["user", "system"])
            
        Raises:
            ValueError: If agent not found
        """
        if agent_name not in self.agent_memories:
            raise ValueError(f"Agent '{agent_name}' not found")
            
        # Get shared messages
        shared_messages = self.shared_memory.get_messages()
        
        # Filter by message type if specified
        if message_types:
            shared_messages = [msg for msg in shared_messages if msg.role in message_types]
            
        # Add to agent memory
        agent_memory = self.agent_memories[agent_name]
        
        # Clear agent memory first
        agent_memory.clear()
        
        # Add shared messages
        for msg in shared_messages:
            agent_memory.add_message(msg)
    
    def sync_to_shared(self, agent_name: str, message_types: Optional[List[str]] = None) -> None:
        """
        Sync messages from agent memory to shared memory.
        
        Args:
            agent_name: Agent name
            message_types: Optional list of message roles to sync
            
        Raises:
            ValueError: If agent not found
        """
        if agent_name not in self.agent_memories:
            raise ValueError(f"Agent '{agent_name}' not found")
            
        # Get agent messages
        agent_memory = self.agent_memories[agent_name]
        agent_messages = agent_memory.get_messages()
        
        # Filter by message type if specified
        if message_types:
            agent_messages = [msg for msg in agent_messages if msg.role in message_types]
            
        # Add to shared memory with agent prefix
        for msg in agent_messages:
            # Skip if message is already from an agent
            if msg.metadata and "agent" in msg.metadata:
                continue
                
            # Create a copy with agent metadata
            content = msg.content
            prefixed_content = f"[{agent_name}] {content}" if msg.role != "system" else content
            
            agent_msg = Message(
                role=msg.role,
                content=prefixed_content,
                metadata={"agent": agent_name, **(msg.metadata or {})}
            )
            
            self.shared_memory.conversation.add_message(agent_msg)
    
    def broadcast_message(self, message: Message, exclude: Optional[List[str]] = None) -> None:
        """
        Broadcast message to all agent memories.
        
        Args:
            message: Message to broadcast
            exclude: Optional list of agent names to exclude
        """
        exclude = exclude or []
        
        for agent_name, memory in self.agent_memories.items():
            if agent_name not in exclude:
                memory.add_message(message)
    
    def share_context(self, from_agent: str, to_agent: str, last_n: Optional[int] = None) -> None:
        """
        Share context from one agent to another.
        
        Args:
            from_agent: Source agent name
            to_agent: Destination agent name
            last_n: Optional number of most recent messages to share
            
        Raises:
            ValueError: If agent not found
        """
        if from_agent not in self.agent_memories:
            raise ValueError(f"Agent '{from_agent}' not found")
            
        if to_agent not in self.agent_memories:
            raise ValueError(f"Agent '{to_agent}' not found")
            
        # Get source agent messages
        source_memory = self.agent_memories[from_agent]
        source_messages = source_memory.get_messages()
        
        # Take only last N messages if specified
        if last_n:
            source_messages = source_messages[-last_n:]
            
        # Add to destination agent memory with source prefix
        dest_memory = self.agent_memories[to_agent]
        
        for msg in source_messages:
            # Skip system messages
            if msg.role == "system":
                continue
                
            # Create a copy with source agent metadata
            content = msg.content
            prefixed_content = f"[{from_agent}] {content}"
            
            shared_msg = Message(
                role=msg.role,
                content=prefixed_content,
                metadata={"shared_from": from_agent, **(msg.metadata or {})}
            )
            
            dest_memory.add_message(shared_msg)
    
    def clear_agent_memory(self, agent_name: str) -> None:
        """
        Clear specific agent's memory.
        
        Args:
            agent_name: Agent name
            
        Raises:
            ValueError: If agent not found
        """
        if agent_name not in self.agent_memories:
            raise ValueError(f"Agent '{agent_name}' not found")
            
        self.agent_memories[agent_name].clear()
    
    def clear_all(self) -> None:
        """Clear all agent memories and shared memory."""
        for memory in self.agent_memories.values():
            memory.clear()
            
        self.shared_memory.clear()