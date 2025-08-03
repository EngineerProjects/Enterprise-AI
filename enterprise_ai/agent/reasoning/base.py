"""
Enterprise AI Agent - Base Reasoning Pattern.

CREATED: Base class that eliminates common boilerplate across reasoning patterns
while allowing flexible implementation of specific reasoning logic.
"""

import abc
from typing import List, Optional, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.base")


class BaseReasoningPattern(abc.ABC):
    """
    Base class for reasoning patterns with common functionality.
    
    Eliminates boilerplate while allowing flexible reasoning implementations.
    Provides consistent configuration and method signatures.
    """
    
    def __init__(self):
        """Initialize the reasoning pattern."""
        self.llm: Optional[LLMProvider] = None
        self.mcp: Optional[ToolMCP] = None
        self.verbose: bool = False
    
    def configure(self, llm: LLMProvider, mcp: ToolMCP, verbose: bool = False) -> None:
        """
        Configure the pattern with LLM and MCP.
        
        Args:
            llm: LLM provider for generating responses
            mcp: Tool execution coordinator  
            verbose: Enable detailed logging
        """
        self.llm = llm
        self.mcp = mcp
        self.verbose = verbose
        
        if verbose:
            pattern_name = self.__class__.__name__
            logger.info(f"Configured {pattern_name} with {llm.__class__.__name__}")
    
    def _validate_configuration(self) -> None:
        """Validate that pattern is properly configured."""
        if not self.llm or not self.mcp:
            pattern_name = self.__class__.__name__
            raise ValueError(f"{pattern_name} not properly configured. Call configure() first.")
    
    @abc.abstractmethod
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using the specific reasoning pattern.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
        """
        pass
    
    async def process_stream(self, messages: List[MessageProtocol], memory: ConversationMemory) -> AsyncIterator[str]:
        """
        Process messages with streaming support.
        
        Default implementation falls back to non-streaming.
        Patterns can override for true streaming support.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Async iterator of response chunks
        """
        result = await self.process(messages, memory)
        yield result
    
    def get_pattern_info(self) -> dict:
        """Get information about this reasoning pattern."""
        return {
            "name": self.__class__.__name__,
            "configured": self.llm is not None and self.mcp is not None,
            "verbose": self.verbose,
            "llm_provider": self.llm.__class__.__name__ if self.llm else None,
            "available_tools": len(self.mcp.get_available_tools()) if self.mcp else 0
        }
