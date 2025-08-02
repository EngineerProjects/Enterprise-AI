"""
Enterprise AI Team - Message Router.

Implements routing of messages between agents in a team.
Enhanced with @mention support for direct agent communication.
"""

from typing import Dict, List, Optional, Any, Union, Callable, Tuple

from enterprise_ai.team.communication.protocol import TeamMessage, CommunicationProtocol
from enterprise_ai.team.communication.mentions import MentionParser
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.communication.router")


class MessageRouter:
    """
    Router for messages between agents in a team.
    
    This handles:
    1. Routing messages to appropriate agents
    2. Managing message delivery and acknowledgment  
    3. Providing callback hooks for message processing
    4. Parsing and routing @mention-based messages
    """
    
    def __init__(self, protocol: Optional[CommunicationProtocol] = None):
        """
        Initialize message router.
        
        Args:
            protocol: Communication protocol
        """
        self.protocol = protocol or CommunicationProtocol()
        self.mention_parser = MentionParser()
        self.agent_callbacks = {}  # Map of agent_name -> callback function
        self.message_queue = {}    # Map of agent_name -> list of pending messages
        self.delivered_messages = {}  # Map of message_id -> delivery status
    
    def register_agent(self, agent_name: str, callback: Callable[[TeamMessage], None]) -> None:
        """
        Register an agent with a callback function.
        
        Args:
            agent_name: Agent name
            callback: Function to call when a message is received
        """
        self.agent_callbacks[agent_name] = callback
        self.message_queue[agent_name] = []
        
        # Update mention parser with current agent list
        self.mention_parser.update_valid_agents(list(self.agent_callbacks.keys()))
        
        logger.info(f"Registered agent '{agent_name}' with router")
    
    def unregister_agent(self, agent_name: str) -> None:
        """
        Unregister an agent.
        
        Args:
            agent_name: Agent name
        """
        if agent_name in self.agent_callbacks:
            del self.agent_callbacks[agent_name]
            
        if agent_name in self.message_queue:
            del self.message_queue[agent_name]
        
        # Update mention parser with current agent list
        self.mention_parser.update_valid_agents(list(self.agent_callbacks.keys()))
            
        logger.info(f"Unregistered agent '{agent_name}' from router")
    
    def send_message(self, message: TeamMessage) -> str:
        """
        Send a message to its recipient.
        
        Args:
            message: Message to send
            
        Returns:
            Message ID
        """
        # Generate message ID
        message_id = f"{message.sender}_{message.recipient}_{len(self.delivered_messages)}"
        
        # Store in protocol history
        self.protocol.message_history.append(message)
        
        # Handle broadcasting
        if message.recipient == "all":
            for agent_name in self.agent_callbacks:
                if agent_name != message.sender:  # Don't send to self
                    self._queue_message(agent_name, message, message_id)
                    
            logger.info(f"Broadcast message from '{message.sender}' queued for {len(self.agent_callbacks) - 1} agents")
            return message_id
        
        # Handle direct message
        if message.recipient in self.message_queue:
            self._queue_message(message.recipient, message, message_id)
            logger.info(f"Message from '{message.sender}' to '{message.recipient}' queued")
        else:
            logger.warning(f"Recipient '{message.recipient}' not registered, message dropped")
            
        return message_id
    
    def send_message_with_mentions(self, sender: str, content: str) -> List[str]:
        """
        Send a message with @mention parsing and routing.
        
        Args:
            sender: Sender agent name
            content: Message content (may contain @mentions)
            
        Returns:
            List of message IDs for all routed messages
        """
        # Parse the message for mentions
        parsed = self.mention_parser.parse_message(content)
        
        # If no mentions, send as regular message to manager (teams should always have a manager)
        if not parsed.has_mentions:
            regular_msg = TeamMessage(
                sender=sender,
                recipient="manager",
                content=content,
                msg_type="message"
            )
            return [self.send_message(regular_msg)]
        
        # Validate mentions against registered agents
        valid_agents, invalid_agents = self.validate_mentions(parsed)
        
        # Log invalid mentions
        if invalid_agents:
            logger.warning(f"Invalid @mentions from '{sender}': {invalid_agents} - these agents don't exist in the team")
        
        # Create and send routed messages from valid mentions only
        routed_messages = self.mention_parser.create_routed_messages(sender, parsed, validate=False)  # Don't validate again
        
        # Filter messages to only include valid recipients
        valid_messages = []
        for msg in routed_messages:
            if msg.recipient == "team" or msg.recipient in self.agent_callbacks:
                valid_messages.append(msg)
            else:
                logger.warning(f"Skipping message to invalid recipient: {msg.recipient}")
        
        message_ids = [self.send_message(msg) for msg in valid_messages]
        
        logger.info(f"Routed {len(valid_messages)} mention-based messages from '{sender}'")
        if invalid_agents:
            logger.info(f"Ignored {len(invalid_agents)} invalid mentions: {invalid_agents}")
        
        return message_ids
    
    def validate_mentions(self, parsed_message) -> Tuple[List[str], List[str]]:
        """
        Validate mentioned agents against registered team members.
        
        Args:
            parsed_message: ParsedMessage object with mentions
            
        Returns:
            Tuple of (valid_agents, invalid_agents)
        """
        valid_agents = []
        invalid_agents = []
        
        for agent_name in parsed_message.mentioned_agents:
            if agent_name in self.agent_callbacks or agent_name == "manager":
                valid_agents.append(agent_name)
            else:
                invalid_agents.append(agent_name)
        
        return valid_agents, invalid_agents
    
    def _queue_message(self, agent_name: str, message: TeamMessage, message_id: str) -> None:
        """
        Queue a message for an agent.
        
        Args:
            agent_name: Agent name
            message: Message to queue
            message_id: Message ID
        """
        self.message_queue[agent_name].append(message)
        self.delivered_messages[message_id] = False
        
        # If agent has a callback, invoke it with error handling
        if agent_name in self.agent_callbacks:
            try:
                self.agent_callbacks[agent_name](message)
                self.delivered_messages[message_id] = True
                
                # Remove from queue on successful delivery
                if message in self.message_queue[agent_name]:
                    self.message_queue[agent_name].remove(message)
                    
            except Exception as e:
                logger.error(f"Error delivering message to agent '{agent_name}': {e}")
                # Keep message in queue for potential retry
                # Mark as failed but don't remove from queue
                self.delivered_messages[message_id] = False
    
    def get_pending_messages(self, agent_name: str) -> List[TeamMessage]:
        """
        Get pending messages for an agent.
        
        Args:
            agent_name: Agent name
            
        Returns:
            List of pending messages
        """
        return self.message_queue.get(agent_name, [])
    
    def acknowledge_message(self, agent_name: str, message: TeamMessage) -> None:
        """
        Acknowledge message delivery.
        
        Args:
            agent_name: Agent name
            message: Message to acknowledge
        """
        if agent_name in self.message_queue and message in self.message_queue[agent_name]:
            self.message_queue[agent_name].remove(message)
            
            # Find message ID
            for message_id, delivered in self.delivered_messages.items():
                if not delivered and message_id.endswith(f"_{agent_name}_"):
                    self.delivered_messages[message_id] = True
                    break
    
    def get_delivery_status(self) -> Dict[str, bool]:
        """
        Get delivery status of all messages.
        
        Returns:
            Dictionary mapping message IDs to delivery status
        """
        return self.delivered_messages.copy()
    
    def clear_queue(self) -> None:
        """Clear message queues for all agents."""
        for agent_name in self.message_queue:
            self.message_queue[agent_name] = []
            
        logger.info("Cleared all message queues")