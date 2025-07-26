"""
Enterprise AI Agent - Chain of Thought Reasoning Pattern.

Self-contained Chain of Thought pattern without inheritance overhead.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.agent.prompts.reasoning.cot import COT_PROMPT_TEMPLATE
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.cot")


class ChainOfThoughtPattern:
    """
    Self-contained Chain of Thought reasoning pattern.
    
    Emphasizes step-by-step thinking without complex inheritance.
    """
    
    def __init__(self):
        """Initialize pattern."""
        self.llm = None
        self.mcp = None
        self.verbose = False
    
    def configure(self, llm: LLMProvider, mcp: ToolMCP, verbose: bool = False) -> None:
        """Configure the pattern with LLM and MCP."""
        self.llm = llm
        self.mcp = mcp
        self.verbose = verbose
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using Chain of Thought approach.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
        """
        if not self.llm:
            raise ValueError("ChainOfThoughtPattern not configured. Call configure() first.")
        
        # Append CoT instruction to the user's last message
        updated_messages = messages.copy()
        for i in reversed(range(len(updated_messages))):
            if updated_messages[i].role == "user":
                content = updated_messages[i].content or ""
                cot_instruction = COT_PROMPT_TEMPLATE.split("Problem:")[0].strip()
                updated_messages[i] = type(updated_messages[i])(
                    role="user",
                    content=f"{content}\n\n{cot_instruction}"
                )
                break
        
        # Get response
        response = await self.llm.acomplete(updated_messages)
        memory.add_message(response)
        
        return response.content
    
    async def process_stream(self, messages: List[MessageProtocol], memory: ConversationMemory) -> AsyncIterator[str]:
        """Stream the response."""
        result = await self.process(messages, memory)
        yield result