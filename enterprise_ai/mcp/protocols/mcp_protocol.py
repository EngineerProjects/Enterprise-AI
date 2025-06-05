"""
Model Context Protocol implementation for Enterprise AI.

This module implements the MCP protocol for communication between
agents and the tool execution engine.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import ToolCall, ToolResult
from enterprise_ai.types import MessageProtocol

logger = get_logger("mcp.protocol")


class MCPMessageType(str, Enum):
    """MCP message types."""
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_LIST = "tool_list"
    TOOL_INFO = "tool_info"
    SESSION_CREATE = "session_create"
    SESSION_CLOSE = "session_close"
    AGENT_REGISTER = "agent_register"
    AGENT_MESSAGE = "agent_message"
    STATUS_REQUEST = "status_request"
    ERROR = "error"


@dataclass
class MCPMessage:
    """Base MCP message structure."""
    message_type: MCPMessageType
    message_id: str
    timestamp: float
    data: Dict[str, Any]
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        message_type: MCPMessageType,
        data: Dict[str, Any],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> "MCPMessage":
        """Create a new MCP message."""
        return cls(
            message_type=message_type,
            message_id=message_id or str(uuid.uuid4()),
            timestamp=time.time(),
            data=data,
            session_id=session_id,
            agent_id=agent_id
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPMessage":
        """Create message from dictionary."""
        return cls(
            message_type=MCPMessageType(data["message_type"]),
            message_id=data["message_id"],
            timestamp=data["timestamp"],
            data=data["data"],
            session_id=data.get("session_id"),
            agent_id=data.get("agent_id")
        )
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> "MCPMessage":
        """Create message from JSON string."""
        return cls.from_dict(json.loads(json_str))


class MCPProtocol:
    """Model Context Protocol implementation."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the MCP protocol."""
        self.verbose = verbose
        self._message_handlers: Dict[MCPMessageType, Any] = {}
        
        logger.info("MCPProtocol initialized")
    
    def register_handler(
        self,
        message_type: MCPMessageType,
        handler: Any
    ) -> None:
        """Register a handler for a specific message type."""
        self._message_handlers[message_type] = handler
        if self.verbose:
            logger.info("Registered handler for %s", message_type)
    
    def create_tool_call_message(
        self,
        tool_calls: List[ToolCall],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> MCPMessage:
        """Create a tool call message."""
        data = {
            "tool_calls": [tc.to_dict() for tc in tool_calls]
        }
        
        return MCPMessage.create(
            message_type=MCPMessageType.TOOL_CALL,
            data=data,
            session_id=session_id,
            agent_id=agent_id
        )
    
    def create_tool_result_message(
        self,
        tool_results: List[ToolResult],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> MCPMessage:
        """Create a tool result message."""
        data = {
            "tool_results": [tr.to_dict() for tr in tool_results]
        }
        
        return MCPMessage.create(
            message_type=MCPMessageType.TOOL_RESULT,
            data=data,
            session_id=session_id,
            agent_id=agent_id
        )
    
    def create_tool_list_message(
        self,
        tools: List[Dict[str, Any]],
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> MCPMessage:
        """Create a tool list message."""
        data = {"tools": tools}
        
        return MCPMessage.create(
            message_type=MCPMessageType.TOOL_LIST,
            data=data,
            session_id=session_id,
            agent_id=agent_id
        )
    
    def create_session_create_message(
        self,
        agent_id: Optional[str] = None
    ) -> MCPMessage:
        """Create a session creation message."""
        data = {"agent_id": agent_id} if agent_id else {}
        
        return MCPMessage.create(
            message_type=MCPMessageType.SESSION_CREATE,
            data=data,
            agent_id=agent_id
        )
    
    def create_agent_register_message(
        self,
        agent_id: str,
        agent_info: Dict[str, Any]
    ) -> MCPMessage:
        """Create an agent registration message."""
        data = {
            "agent_id": agent_id,
            "agent_info": agent_info
        }
        
        return MCPMessage.create(
            message_type=MCPMessageType.AGENT_REGISTER,
            data=data,
            agent_id=agent_id
        )
    
    def create_agent_message(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        message_type_name: str = "general"
    ) -> MCPMessage:
        """Create an inter-agent message."""
        data = {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "content": content,
            "message_type_name": message_type_name
        }
        
        return MCPMessage.create(
            message_type=MCPMessageType.AGENT_MESSAGE,
            data=data,
            agent_id=from_agent
        )
    
    def create_error_message(
        self,
        error: str,
        error_code: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> MCPMessage:
        """Create an error message."""
        data = {
            "error": error,
            "error_code": error_code
        }
        
        return MCPMessage.create(
            message_type=MCPMessageType.ERROR,
            data=data,
            session_id=session_id,
            agent_id=agent_id
        )
    
    async def process_message(self, message: MCPMessage) -> Optional[MCPMessage]:
        """
        Process an incoming MCP message.
        
        Args:
            message: The message to process
            
        Returns:
            Optional response message
        """
        try:
            handler = self._message_handlers.get(message.message_type)
            if not handler:
                error_msg = f"No handler registered for message type: {message.message_type}"
                logger.warning(error_msg)
                return self.create_error_message(
                    error=error_msg,
                    error_code="NO_HANDLER",
                    session_id=message.session_id,
                    agent_id=message.agent_id
                )
            
            # Call the handler
            response = await handler(message)
            
            if self.verbose:
                logger.info("Processed %s message: %s", message.message_type, message.message_id)
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            logger.error(error_msg)
            return self.create_error_message(
                error=error_msg,
                error_code="PROCESSING_ERROR",
                session_id=message.session_id,
                agent_id=message.agent_id
            )
    
    def validate_message(self, message: MCPMessage) -> bool:
        """
        Validate an MCP message.
        
        Args:
            message: Message to validate
            
        Returns:
            True if message is valid
        """
        try:
            # Basic validation
            if not isinstance(message.message_type, MCPMessageType):
                return False
            
            if not message.message_id or not message.timestamp:
                return False
            
            if not isinstance(message.data, dict):
                return False
            
            # Type-specific validation
            if message.message_type == MCPMessageType.TOOL_CALL:
                return "tool_calls" in message.data
            elif message.message_type == MCPMessageType.TOOL_RESULT:
                return "tool_results" in message.data
            elif message.message_type == MCPMessageType.AGENT_MESSAGE:
                required_fields = ["from_agent", "to_agent", "content"]
                return all(field in message.data for field in required_fields)
            
            return True
            
        except Exception as e:
            logger.error("Message validation error: %s", e)
            return False
    
    def get_protocol_info(self) -> Dict[str, Any]:
        """Get protocol information."""
        return {
            "protocol_name": "Enterprise AI MCP",
            "version": "1.0.0",
            "supported_message_types": [mt.value for mt in MCPMessageType],
            "registered_handlers": list(self._message_handlers.keys()),
            "features": [
                "tool_execution",
                "session_management", 
                "agent_communication",
                "sandbox_integration"
            ]
        }