"""
Agent communication handler for MCP requests.

This module handles agent-to-agent communication and coordination
through the MCP protocol.
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from collections import defaultdict

from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol

logger = get_logger("mcp.handlers.agent")


@dataclass
class AgentMessage:
    """Represents a message between agents."""
    from_agent: str
    to_agent: str
    message_type: str
    content: Any
    timestamp: float
    message_id: str


class AgentHandler:
    """Handles agent communication requests for the MCP server."""
    
    def __init__(self, max_queue_size: int = 100):
        """Initialize the agent handler."""
        self.max_queue_size = max_queue_size
        
        # Agent message queues: agent_id -> List[AgentMessage]
        self._message_queues: Dict[str, asyncio.Queue] = defaultdict(
            lambda: asyncio.Queue(maxsize=max_queue_size)
        )
        
        # Active agents registry
        self._active_agents: Dict[str, Dict[str, Any]] = {}
        
        logger.info("AgentHandler initialized with max_queue_size=%d", max_queue_size)
    
    async def register_agent(
        self,
        agent_id: str,
        agent_info: Dict[str, Any]
    ) -> bool:
        """
        Register an agent for communication.
        
        Args:
            agent_id: Unique agent identifier
            agent_info: Agent metadata and capabilities
            
        Returns:
            True if registration successful
        """
        try:
            self._active_agents[agent_id] = {
                "info": agent_info,
                "registered_at": asyncio.get_event_loop().time(),
                "last_activity": asyncio.get_event_loop().time()
            }
            
            # Ensure message queue exists
            if agent_id not in self._message_queues:
                self._message_queues[agent_id] = asyncio.Queue(maxsize=self.max_queue_size)
            
            logger.info("Registered agent: %s", agent_id)
            return True
            
        except Exception as e:
            logger.error("Failed to register agent %s: %s", agent_id, e)
            return False
    
    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.
        
        Args:
            agent_id: Agent identifier to unregister
            
        Returns:
            True if unregistration successful
        """
        try:
            if agent_id in self._active_agents:
                del self._active_agents[agent_id]
            
            # Clear message queue
            if agent_id in self._message_queues:
                # Drain the queue
                while not self._message_queues[agent_id].empty():
                    try:
                        self._message_queues[agent_id].get_nowait()
                    except asyncio.QueueEmpty:
                        break
                del self._message_queues[agent_id]
            
            logger.info("Unregistered agent: %s", agent_id)
            return True
            
        except Exception as e:
            logger.error("Failed to unregister agent %s: %s", agent_id, e)
            return False
    
    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: Any,
        message_id: Optional[str] = None
    ) -> bool:
        """
        Send a message from one agent to another.
        
        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            message_type: Type of message
            content: Message content
            message_id: Optional message ID
            
        Returns:
            True if message sent successfully
        """
        try:
            if to_agent not in self._active_agents:
                logger.warning("Attempted to send message to unregistered agent: %s", to_agent)
                return False
            
            import time
            import uuid
            
            message = AgentMessage(
                from_agent=from_agent,
                to_agent=to_agent,
                message_type=message_type,
                content=content,
                timestamp=time.time(),
                message_id=message_id or str(uuid.uuid4())
            )
            
            # Add to recipient's queue
            queue = self._message_queues[to_agent]
            try:
                queue.put_nowait(message)
                
                # Update activity timestamp
                self._active_agents[to_agent]["last_activity"] = asyncio.get_event_loop().time()
                
                logger.debug("Message sent from %s to %s: %s", from_agent, to_agent, message_type)
                return True
                
            except asyncio.QueueFull:
                logger.warning("Message queue full for agent %s", to_agent)
                return False
            
        except Exception as e:
            logger.error("Failed to send message from %s to %s: %s", from_agent, to_agent, e)
            return False
    
    async def receive_messages(
        self,
        agent_id: str,
        timeout: Optional[float] = None
    ) -> List[AgentMessage]:
        """
        Receive messages for an agent.
        
        Args:
            agent_id: Agent ID to receive messages for
            timeout: Optional timeout for waiting for messages
            
        Returns:
            List of received messages
        """
        try:
            if agent_id not in self._active_agents:
                logger.warning("Attempted to receive messages for unregistered agent: %s", agent_id)
                return []
            
            messages = []
            queue = self._message_queues[agent_id]
            
            # Get all available messages
            while not queue.empty():
                try:
                    message = queue.get_nowait()
                    messages.append(message)
                except asyncio.QueueEmpty:
                    break
            
            # If no messages and timeout specified, wait for one
            if not messages and timeout is not None:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=timeout)
                    messages.append(message)
                except asyncio.TimeoutError:
                    pass
            
            if messages:
                # Update activity timestamp
                self._active_agents[agent_id]["last_activity"] = asyncio.get_event_loop().time()
                logger.debug("Agent %s received %d messages", agent_id, len(messages))
            
            return messages
            
        except Exception as e:
            logger.error("Failed to receive messages for agent %s: %s", agent_id, e)
            return []
    
    async def broadcast_message(
        self,
        from_agent: str,
        message_type: str,
        content: Any,
        exclude_agents: Optional[List[str]] = None
    ) -> int:
        """
        Broadcast a message to all active agents.
        
        Args:
            from_agent: Sender agent ID
            message_type: Type of message
            content: Message content
            exclude_agents: List of agent IDs to exclude from broadcast
            
        Returns:
            Number of agents that received the message
        """
        exclude_agents = exclude_agents or []
        sent_count = 0
        
        for agent_id in self._active_agents:
            if agent_id not in exclude_agents and agent_id != from_agent:
                success = await self.send_message(
                    from_agent=from_agent,
                    to_agent=agent_id,
                    message_type=message_type,
                    content=content
                )
                if success:
                    sent_count += 1
        
        logger.info("Broadcast from %s sent to %d agents", from_agent, sent_count)
        return sent_count
    
    def get_active_agents(self) -> List[str]:
        """Get list of active agent IDs."""
        return list(self._active_agents.keys())
    
    def get_agent_info(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific agent."""
        return self._active_agents.get(agent_id)
    
    def get_communication_stats(self) -> Dict[str, Any]:
        """Get communication statistics."""
        queue_sizes = {
            agent_id: queue.qsize() 
            for agent_id, queue in self._message_queues.items()
        }
        
        return {
            "active_agents": len(self._active_agents),
            "total_queues": len(self._message_queues),
            "queue_sizes": queue_sizes,
            "total_queued_messages": sum(queue_sizes.values()),
            "max_queue_size": self.max_queue_size
        }