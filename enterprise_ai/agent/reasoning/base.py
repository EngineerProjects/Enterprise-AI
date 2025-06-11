"""
Enterprise AI Agent - Reasoning Pattern Base.

Defines the base interface for reasoning patterns.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol


class ReasoningPattern:
    """
    Base interface for reasoning patterns.
    
    Reasoning patterns define how an agent approaches problem-solving,
    including when and how to use tools, structure thinking, and generate responses.
    """
    
    def __init__(self):
        """Initialize reasoning pattern."""
        self.llm = None
        self.mcp = None
        self.verbose = False
    
    def configure(self, llm: LLMProvider, mcp: ToolMCP, verbose: bool = False) -> None:
        """
        Configure the reasoning pattern with required components.
        
        Args:
            llm: LLM provider for generating responses
            mcp: Tool execution coordinator
            verbose: Enable detailed logging
        """
        self.llm = llm
        self.mcp = mcp
        self.verbose = verbose
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages and generate a response using the reasoning pattern.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
            
        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Reasoning patterns must implement process()")
    
    async def process_stream(self, messages: List[MessageProtocol], memory: ConversationMemory) -> AsyncIterator[str]:
        """
        Process messages and stream the response using the reasoning pattern.
        
        This default implementation calls process() and yields the result as a single chunk.
        Subclasses should override this for proper streaming support.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Async iterator of response chunks
        """
        # Default implementation just calls the regular process method
        # and returns the result as a single chunk
        result = await self.process(messages, memory)
        yield result