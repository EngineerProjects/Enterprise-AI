"""
Enterprise AI Agent - Software Engineering Reasoning Pattern.

REFACTORED: Eliminated code duplication by properly leveraging ReAct parent class.
Now uses composition instead of reimplementing tool execution logic.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.prompts.swe import SWE_SYSTEM_GUIDANCE, SWE_TOOL_GUIDANCE
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.swe")


class SoftwareEngineeringPattern(ReActPattern):
    """
    Software Engineering pattern that extends ReAct for code tasks.
    
    REFACTORED: Now properly leverages parent ReAct functionality instead of
    duplicating tool execution logic. Focuses only on SWE-specific guidance.
    """
    
    def _prepare_swe_messages(self, messages: List[MessageProtocol]) -> List[MessageProtocol]:
        """
        Prepare messages with SWE-specific guidance.
        
        This is the core difference from ReAct - specialized guidance for code tasks.
        """
        updated_messages = messages.copy()
        
        # Find the last user message and append SWE guidance
        for i in reversed(range(len(updated_messages))):
            if updated_messages[i].role == "user":
                content = updated_messages[i].content or ""
                
                # Extract task guidance from SWE prompts
                swe_instruction = "\n".join(SWE_SYSTEM_GUIDANCE.split("\n")[1:])
                enhanced_content = f"{content}\n\n{swe_instruction}\n{SWE_TOOL_GUIDANCE}"
                
                # Create new message with enhanced content
                updated_messages[i] = type(updated_messages[i])(
                    role="user",
                    content=enhanced_content
                )
                break
        
        return updated_messages
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using Software Engineering pattern.
        
        REFACTORED: Now delegates to parent ReAct after adding SWE guidance,
        eliminating 80+ lines of duplicated tool execution logic.
        """
        if not self.llm or not self.mcp:
            raise ValueError("SoftwareEngineeringPattern not properly configured. Call configure() first.")
        
        # Prepare messages with SWE-specific guidance
        swe_enhanced_messages = self._prepare_swe_messages(messages)
        
        # FIXED: Delegate to parent ReAct logic instead of reimplementing
        # This eliminates all the duplicated tool execution code
        return await super().process(swe_enhanced_messages, memory)
    
    async def process_stream(self, messages: List[MessageProtocol], memory: ConversationMemory) -> AsyncIterator[str]:
        """
        Stream responses using Software Engineering pattern.
        
        REFACTORED: Now delegates to parent ReAct streaming after adding SWE guidance.
        """
        if not self.llm or not self.mcp:
            raise ValueError("SoftwareEngineeringPattern not properly configured. Call configure() first.")
        
        # Prepare messages with SWE-specific guidance
        swe_enhanced_messages = self._prepare_swe_messages(messages)
        
        # FIXED: Delegate to parent ReAct streaming logic
        async for chunk in super().process_stream(swe_enhanced_messages, memory):
            yield chunk
