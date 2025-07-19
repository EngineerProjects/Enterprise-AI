"""
Enterprise AI Team - Mention Parser.

Parses @mentions from messages and enables direct agent communication.
"""

import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

from enterprise_ai.team.communication.protocol import TeamMessage
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.communication.mentions")


@dataclass
class MentionInfo:
    """Information about a parsed mention."""
    mention_text: str  # Full mention like "@alice"
    agent_name: str   # Just the name "alice"
    start_pos: int    # Position in original text
    end_pos: int      # End position in original text


@dataclass
class ParsedMessage:
    """Result of parsing a message for mentions."""
    original_content: str
    clean_content: str      # Content with mentions removed/cleaned
    mentions: List[MentionInfo]
    is_broadcast: bool      # True if contains @team
    has_mentions: bool      # True if has any mentions
    
    @property
    def mentioned_agents(self) -> List[str]:
        """Get list of mentioned agent names."""
        return [mention.agent_name for mention in self.mentions if mention.agent_name != "team"]
    
    @property
    def unique_mentions(self) -> Set[str]:
        """Get unique set of mentioned agents."""
        return set(self.mentioned_agents)


class MentionParser:
    """
    Parses @mentions from agent messages and routes them appropriately.
    
    Handles:
    - @agent_name for direct messages
    - @team for broadcast messages
    - Multiple mentions in single message
    - Validation of mentioned agents
    """
    
    # Regex pattern for @mentions - avoid matching emails by using word boundaries
    # This pattern matches @ only when it's at word boundary (not preceded by alphanumeric)
    MENTION_PATTERN = re.compile(r'(?<![a-zA-Z0-9])@([a-zA-Z0-9_]+)', re.IGNORECASE)
    
    def __init__(self, valid_agents: Optional[List[str]] = None):
        """
        Initialize mention parser.
        
        Args:
            valid_agents: List of valid agent names for validation
        """
        self._valid_agents: Set[str] = set(valid_agents or [])
    
    def update_valid_agents(self, agent_names: List[str]) -> None:
        """
        Update list of valid agent names.
        
        Args:
            agent_names: List of valid agent names
        """
        self._valid_agents = set(name.lower() for name in agent_names)
        logger.debug(f"Updated valid agents: {self._valid_agents}")
    
    def parse_message(self, content: str) -> ParsedMessage:
        """
        Parse message content for @mentions.
        
        Args:
            content: Message content to parse
            
        Returns:
            ParsedMessage with mention information
        """
        mentions = []
        is_broadcast = False
        
        # Find all @mentions in the content
        for match in self.MENTION_PATTERN.finditer(content):
            mention_text = match.group(0)  # Full "@agent_name"
            agent_name = match.group(1).lower()  # Just "agent_name"
            
            # Check for @team broadcast
            if agent_name == "team":
                is_broadcast = True
            
            mention_info = MentionInfo(
                mention_text=mention_text,
                agent_name=agent_name,
                start_pos=match.start(),
                end_pos=match.end()
            )
            mentions.append(mention_info)
        
        # Create clean content (for now, keep mentions in place)
        clean_content = content
        
        return ParsedMessage(
            original_content=content,
            clean_content=clean_content,
            mentions=mentions,
            is_broadcast=is_broadcast,
            has_mentions=bool(mentions)
        )
    
    def validate_mentions(self, parsed: ParsedMessage) -> Tuple[List[str], List[str]]:
        """
        Validate mentioned agents against known team members.
        
        Args:
            parsed: Parsed message to validate
            
        Returns:
            Tuple of (valid_agents, invalid_agents)
        """
        valid_agents = []
        invalid_agents = []
        
        for agent_name in parsed.mentioned_agents:
            if agent_name in self._valid_agents:
                valid_agents.append(agent_name)
            else:
                invalid_agents.append(agent_name)
        
        return valid_agents, invalid_agents
    
    def create_routed_messages(
        self, 
        sender: str, 
        parsed: ParsedMessage,
        validate: bool = True
    ) -> List[TeamMessage]:
        """
        Create routed team messages from parsed mentions.
        
        Args:
            sender: Name of the sending agent
            parsed: Parsed message with mentions
            validate: Whether to validate agent names
            
        Returns:
            List of TeamMessage objects for routing
        """
        messages = []
        
        # Skip if no mentions
        if not parsed.has_mentions:
            return messages
        
        # Handle broadcast (@team)
        if parsed.is_broadcast:
            broadcast_msg = TeamMessage(
                sender=sender,
                recipient="team",
                content=parsed.clean_content,
                msg_type="broadcast",
                metadata={"mentions": ["team"], "original_content": parsed.original_content}
            )
            messages.append(broadcast_msg)
        
        # Handle direct mentions
        mentioned_agents = parsed.mentioned_agents
        if validate:
            valid_agents, invalid_agents = self.validate_mentions(parsed)
            
            # Log invalid mentions
            if invalid_agents:
                logger.warning(f"Invalid mentions from {sender}: {invalid_agents}")
            
            mentioned_agents = valid_agents
        
        # Create direct messages for each mentioned agent
        for agent_name in set(mentioned_agents):  # Remove duplicates
            direct_msg = TeamMessage(
                sender=sender,
                recipient=agent_name,
                content=parsed.clean_content,
                msg_type="peer_message",
                metadata={
                    "mentions": [agent_name], 
                    "original_content": parsed.original_content,
                    "is_direct_mention": True
                }
            )
            messages.append(direct_msg)
        
        return messages
    
    def extract_message_content(self, content: str, preserve_mentions: bool = True) -> str:
        """
        Extract clean message content for processing.
        
        Args:
            content: Original message content
            preserve_mentions: Whether to keep @mentions in the content
            
        Returns:
            Cleaned content
        """
        if preserve_mentions:
            return content
        
        # Remove @mentions for cleaner processing
        return self.MENTION_PATTERN.sub('', content).strip()
    
    def format_mention_reply(self, sender: str, recipient: str, content: str) -> str:
        """
        Format a reply that includes mention context.
        
        Args:
            sender: Sender name
            recipient: Original sender to reply to
            content: Reply content
            
        Returns:
            Formatted reply with mention
        """
        return f"@{recipient} {content}"
