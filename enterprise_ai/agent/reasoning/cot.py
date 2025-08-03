"""
Enterprise AI Agent - Chain of Thought Reasoning Pattern.

Self-contained Chain of Thought pattern without inheritance overhead.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.agent.reasoning.base import BaseReasoningPattern  # ADDED: Use base class
from enterprise_ai.agent.prompts.cot import COT_PROMPT_TEMPLATE
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.cot")


class ChainOfThoughtPattern(BaseReasoningPattern):  # FIXED: Inherit from base class
    """
    Self-contained Chain of Thought reasoning pattern.
    
    REFACTORED: Now inherits from BaseReasoningPattern to eliminate boilerplate.
    """
    
    def __init__(self):
        """Initialize pattern."""
        super().__init__()  # FIXED: Call parent constructor
    
    # REMOVED: configure() method - now inherited from base class
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using Chain of Thought approach.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
        """
        self._validate_configuration()  # FIXED: Use base class validation
        
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