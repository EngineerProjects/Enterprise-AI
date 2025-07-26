"""
Enterprise AI Agent - Software Engineering Reasoning Pattern.

Self-contained SWE pattern based on ReAct but optimized for code tasks.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.agent.config import MAX_REACT_ITERATIONS
from enterprise_ai.agent.reasoning.react import ReActPattern
from enterprise_ai.agent.prompts.reasoning.swe import SWE_SYSTEM_GUIDANCE, SWE_TOOL_GUIDANCE
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.swe")


class SoftwareEngineeringPattern(ReActPattern):
    """
    Software Engineering pattern that extends ReAct for code tasks.
    
    Uses ReAct's tool capabilities but adds code-specific guidance.
    """
    
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using the Software Engineering pattern.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
        """
        if not self.llm or not self.mcp:
            raise ValueError("SoftwareEngineeringPattern not properly configured. Call configure() first.")
            
        # Append instruction to the user's last message using the SWE guidance from prompts
        updated_messages = messages.copy()
        for i in reversed(range(len(updated_messages))):
            if updated_messages[i].role == "user":
                # Get the original content
                content = updated_messages[i].content or ""
                # Extract the task guidance part from SWE_SYSTEM_GUIDANCE
                swe_instruction = "\n".join(SWE_SYSTEM_GUIDANCE.split("\n")[1:])
                updated_messages[i] = type(updated_messages[i])(
                    role="user",
                    content=f"{content}\n\n{swe_instruction}\n{SWE_TOOL_GUIDANCE}"
                )
                break
        
        # Get tool definitions
        tools = self.mcp.get_tool_definitions()
        
        # Generate initial response with potential tool calls
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=updated_messages, 
            tools=tools
        )
        
        # Add response to memory (using original memory/messages)
        memory.add_message(response)
        
        # Continue with ReAct pattern's tool execution logic
        if not tool_calls:
            return response.content
            
        # Process tool calls as in ReAct
        iteration = 0
        current_tool_calls = tool_calls
        
        while current_tool_calls and iteration < MAX_REACT_ITERATIONS:
            iteration += 1
            
            if self.verbose:
                logger.info(f"SWE iteration {iteration}: executing {len(current_tool_calls)} tool(s)")
            
            # Execute tools
            results = await self.mcp.execute_tool_calls(current_tool_calls)
            
            # Add tool results to memory
            for tool_call, result in zip(current_tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
            
            # Get next response with potential tool calls
            response, current_tool_calls = await self.llm.acomplete_with_tool_calls(
                messages=memory.get_messages(),
                tools=tools
            )
            
            # Add response to memory
            memory.add_message(response)
        
        # Return the final response
        messages = memory.get_messages()
        for msg in reversed(messages):
            if msg.role == "assistant":
                return msg.content
                
        # Fallback
        return "I was unable to complete the software engineering task properly."