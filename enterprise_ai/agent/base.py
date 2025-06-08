"""
Base agent interface for Enterprise AI.
"""

import abc
import time
import uuid
import asyncio
from typing import Any, Dict, List, Optional

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.schema import ToolCall, ToolResult, Message
from enterprise_ai.types import MessageProtocol

logger = get_optimized_logger("agent.base")


class BaseAgent(LLMProvider):
    """
    Base agent class that inherits from LLMProvider and adds MCP tool execution.
    
    Agents inherit ALL LLM provider methods (complete, acomplete, complete_stream, etc.)
    and add tool execution capabilities through MCP integration.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs: Any
    ):
        """Initialize the base agent."""
        # Initialize LLM provider with all kwargs
        super().__init__(**kwargs)
        
        # Agent-specific attributes
        self.agent_id = agent_id or str(uuid.uuid4())
        self.agent_name = name or f"Agent-{self.agent_id[:8]}"
        self.agent_description = description or f"Enterprise AI Agent: {self.agent_name}"
        
        # Agent execution tracking
        self._agent_start_time = time.time()
        self._conversation_count = 0
        self._tool_execution_count = 0
        self._agent_error_count = 0
        
        logger.info(f"Initialized agent: {self.agent_name} ({self.agent_id})")
    
    # Override complete to ensure proper async handling
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        """Generate completion (sync wrapper around async method)."""
        try:
            # Use asyncio.run for sync context
            return asyncio.run(self.acomplete(messages, **kwargs))
        except Exception as e:
            self._track_agent_error()
            logger.error(f"Completion failed for agent {self.agent_name}: {e}")
            raise
    
    @abc.abstractmethod
    async def chat(
        self,
        messages: List[MessageProtocol],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_iterations: int = 5,
        **kwargs: Any
    ) -> List[MessageProtocol]:
        """
        Generate completion with automatic tool execution loop.
        
        This is the main agent method that combines LLM completion with MCP tool execution.
        
        Args:
            messages: List of conversation messages
            tools: Available tools for the conversation
            max_iterations: Maximum tool execution iterations
            **kwargs: Additional parameters for LLM completion
            
        Returns:
            List of messages including tool executions and responses
        """
        pass
    
    @abc.abstractmethod
    async def execute_tools(
        self,
        tool_calls: List[ToolCall],
        session_id: Optional[str] = None,
        **kwargs: Any
    ) -> List[ToolResult]:
        """
        Execute tool calls through MCP.
        
        Args:
            tool_calls: List of tool calls to execute
            session_id: Optional session ID for tracking
            **kwargs: Additional execution context
            
        Returns:
            List of tool execution results
        """
        pass
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information including LLM provider info."""
        return {
            # Agent-specific info
            "agent_id": self.agent_id,
            "name": self.agent_name,
            "description": self.agent_description,
            "uptime_seconds": time.time() - self._agent_start_time,
            "conversation_count": self._conversation_count,
            "tool_execution_count": self._tool_execution_count,
            "error_count": self._agent_error_count,
            
            # LLM provider info
            "model_name": self.get_model_name(),
            "llm_metrics": self.get_metrics(),
            "model_info": self.get_model_info().to_dict() if hasattr(self.get_model_info(), 'to_dict') else str(self.get_model_info()),
        }
    
    def _track_agent_conversation(self) -> None:
        """Track agent conversation metrics."""
        self._conversation_count += 1
    
    def _track_agent_tool_execution(self, count: int = 1) -> None:
        """Track agent tool execution metrics."""
        self._tool_execution_count += count
    
    def _track_agent_error(self) -> None:
        """Track agent error metrics."""
        self._agent_error_count += 1