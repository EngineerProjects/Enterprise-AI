"""
Enterprise AI Agent - Chain of Thought Reasoning Pattern.

Implements the Chain of Thought pattern that emphasizes step-by-step reasoning.
"""

from typing import List, Optional, Dict, Any

from enterprise_ai.agent.reasoning.base import ReasoningPattern
from enterprise_ai.agent.prompts.reasoning.cot import COT_PROMPT_TEMPLATE
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.cot")


class ChainOfThoughtPattern(ReasoningPattern):
    """
    Chain of Thought reasoning pattern that emphasizes step-by-step thinking.
    
    This pattern encourages the LLM to:
    1. Break down complex problems into smaller steps
    2. Work through each step explicitly
    3. Reach a conclusion based on the reasoning process
    
    Generally uses fewer tools but more detailed thinking.
    """
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using the Chain of Thought pattern.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
        """
        if not self.llm:
            raise ValueError("ChainOfThoughtPattern not properly configured. Call configure() first.")
        
        # Append instruction to the user's last message
        updated_messages = messages.copy()
        for i in reversed(range(len(updated_messages))):
            if updated_messages[i].role == "user":
                # Get the original content
                content = updated_messages[i].content or ""
                # Add CoT instruction using the template from prompts
                cot_instruction = COT_PROMPT_TEMPLATE.split("Problem:")[0].strip()
                updated_messages[i] = type(updated_messages[i])(
                    role="user",
                    content=f"{content}\n\n{cot_instruction}"
                )
                break
        
        # Get response
        response = await self.llm.acomplete(updated_messages)
        
        # Add to memory but without the CoT instruction
        memory.add_message(response)
        
        return response.content