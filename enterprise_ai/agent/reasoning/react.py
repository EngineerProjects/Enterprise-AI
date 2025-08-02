"""
Enterprise AI Agent - ReAct Reasoning Pattern.

Self-contained ReAct pattern without inheritance overhead.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.agent.config import MAX_REACT_ITERATIONS
from enterprise_ai.agent.prompts.react import REACT_SYSTEM_GUIDANCE, REACT_TOOL_GUIDANCE
from enterprise_ai.schema import Message, ToolCall
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.react")


class ReActPattern:
    """
    Self-contained Reasoning and Acting pattern.
    
    Alternates between thinking and tool usage without complex inheritance.
    """
    
    def __init__(self):
        """Initialize the ReAct pattern."""
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
        Process messages using the ReAct pattern.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Final text response
        """
        if not self.llm or not self.mcp:
            raise ValueError("ReActPattern not properly configured. Call configure() first.")
            
        # Add ReAct guidance to the conversation - add as a system message before processing
        # Use both REACT_SYSTEM_GUIDANCE and REACT_TOOL_GUIDANCE
        react_guidance = Message(
            role="system",
            content=f"{REACT_SYSTEM_GUIDANCE}\n\n{REACT_TOOL_GUIDANCE}"
        )
        
        # Make a copy of messages and add the guidance
        updated_messages = messages.copy()
        updated_messages.append(react_guidance)
            
        # Get tool definitions
        tools = self.mcp.get_tool_definitions()
        
        # Generate initial response with potential tool calls
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=updated_messages, 
            tools=tools
        )
        
        # Add response to memory (but not the temporary guidance message)
        memory.add_message(response)
        
        # If no tool calls, we're done
        if not tool_calls:
            return response.content
        
        # We have tool calls to process
        iteration = 0
        
        while tool_calls and iteration < MAX_REACT_ITERATIONS:
            iteration += 1
            
            if self.verbose:
                logger.info(f"ReAct iteration {iteration}: executing {len(tool_calls)} tool(s)")
            
            # Execute tools
            results = await self.mcp.execute_tool_calls(tool_calls)
            
            # Add tool results to memory
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
            
            # Get updated messages, including our guidance again
            current_messages = memory.get_messages()
            current_messages.append(react_guidance)
            
            # Get next response with potential tool calls
            response, new_tool_calls = await self.llm.acomplete_with_tool_calls(
                messages=current_messages,
                tools=tools
            )
            
            # Add response to memory
            memory.add_message(response)
            
            # Update tool calls for next iteration
            tool_calls = new_tool_calls
            
            # If we've reached max iterations but still have tool calls, add a note
            if tool_calls and iteration >= MAX_REACT_ITERATIONS:
                warning = Message(
                    role="system",
                    content=f"Maximum tool call iterations ({MAX_REACT_ITERATIONS}) reached. Finalizing response."
                )
                memory.add_message(warning)
                
                # Final response without tools
                final_response = await self.llm.acomplete(memory.get_messages())
                memory.add_message(final_response)
                return final_response.content
        
        # Get final messages - last assistant message is the final response
        messages = memory.get_messages()
        for msg in reversed(messages):
            if msg.role == "assistant":
                return msg.content
                
        # Fallback - should not reach here
        return "I apologize, but I was unable to complete the task properly."
    
    async def process_stream(self, messages: List[MessageProtocol], memory: ConversationMemory) -> AsyncIterator[str]:
        """
        Process messages using the ReAct pattern with streaming support.
        
        Args:
            messages: Current conversation messages
            memory: Conversation memory for adding new messages
            
        Returns:
            Async iterator of response chunks
        """
        if not self.llm or not self.mcp:
            raise ValueError("ReActPattern not properly configured. Call configure() first.")
            
        # Add ReAct guidance to the conversation - add as a system message before processing
        react_guidance = Message(
            role="system",
            content=f"{REACT_SYSTEM_GUIDANCE}\n\n{REACT_TOOL_GUIDANCE}"
        )
        
        # Make a copy of messages and add the guidance
        updated_messages = messages.copy()
        updated_messages.append(react_guidance)
            
        # Get tool definitions
        tools = self.mcp.get_tool_definitions()
        
        # Generate initial response with potential tool calls
        # Note: We can't stream the first response if we need to check for tool calls
        response, tool_calls = await self.llm.acomplete_with_tool_calls(
            messages=updated_messages, 
            tools=tools
        )
        
        # Add response to memory (but not the temporary guidance message)
        memory.add_message(response)
        
        # If no tool calls, we can yield the response directly
        if not tool_calls:
            yield response.content
            return
        
        # If we have tool calls, we need to process them and then stream the final response
        # We don't yield anything for intermediate steps with tool calls
        
        # Process tool calls
        iteration = 0
        
        while tool_calls and iteration < MAX_REACT_ITERATIONS:
            iteration += 1
            
            if self.verbose:
                logger.info(f"ReAct streaming iteration {iteration}: executing {len(tool_calls)} tool(s)")
            
            # Execute tools
            results = await self.mcp.execute_tool_calls(tool_calls)
            
            # Add tool results to memory
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
            
            # Get updated messages, including our guidance again
            current_messages = memory.get_messages()
            current_messages.append(react_guidance)
            
            # Get next response with potential tool calls
            response, new_tool_calls = await self.llm.acomplete_with_tool_calls(
                messages=current_messages,
                tools=tools
            )
            
            # Add response to memory
            memory.add_message(response)
            
            # Update tool calls for next iteration
            tool_calls = new_tool_calls
            
            # If no more tool calls, we can stream the final response
            if not tool_calls:
                yield response.content
                return
            
            # If we've reached max iterations but still have tool calls, add a note and stream final response
            if iteration >= MAX_REACT_ITERATIONS:
                warning = Message(
                    role="system",
                    content=f"Maximum tool call iterations ({MAX_REACT_ITERATIONS}) reached. Finalizing response."
                )
                memory.add_message(warning)
                
                # Final response with streaming
                async for chunk in self.llm.acomplete_stream(memory.get_messages()):
                    if chunk.content:
                        yield chunk.content
                
                # Save the final response to memory
                messages = memory.get_messages()
                final_content = ""
                for msg in reversed(messages):
                    if msg.role == "assistant" and not msg.metadata.get("is_partial", False):
                        final_content = msg.content
                        break
                
                # If we didn't find a final message, create one
                if not final_content:
                    final_msg = Message(
                        role="assistant",
                        content="I apologize, but I was unable to complete the task properly."
                    )
                    memory.add_message(final_msg)
                return