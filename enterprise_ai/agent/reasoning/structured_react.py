"""
Enhanced ReAct Pattern - Based on 2024-2025 Research

REFACTORED: Now properly uses prompts from prompts/structured_react.py
and leverages BaseReasoningPattern to eliminate boilerplate.

Implements: Think → Act → Observe → Reflect → (Continue/Terminate)
Features: Explicit observation, reflection, and termination mechanisms
"""

from typing import List, Optional, Dict, Any, AsyncIterator
from enum import Enum

from enterprise_ai.agent.config import MAX_REACT_ITERATIONS
from enterprise_ai.agent.reasoning.base import BaseReasoningPattern
from enterprise_ai.agent.prompts.structured_react import (
    STRUCTURED_REACT_SYSTEM_GUIDANCE,
    STRUCTURED_REACT_PHASE_GUIDANCE
)
from enterprise_ai.schema import Message, ToolCall
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.types import MessageProtocol
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.structured_react")


class ReActPhase(Enum):
    """Enhanced ReAct phases based on 2024-2025 research."""
    THINK = "think"
    ACT = "act" 
    OBSERVE = "observe"
    REFLECT = "reflect"
    TERMINATE = "terminate"


class EnhancedReActPattern(BaseReasoningPattern):
    """
    Enhanced ReAct pattern with explicit observation, reflection, and termination.
    
    REFACTORED: Now uses prompts from prompts module and inherits from BaseReasoningPattern.
    
    Cycle: Think → Act → Observe → Reflect → (Continue/Terminate)
    """
    
    def __init__(self):
        """Initialize the enhanced ReAct pattern."""
        super().__init__()
        self.current_phase = ReActPhase.THINK
        self.reflection_history = []
        
    async def process(self, messages: List[MessageProtocol], memory: ConversationMemory) -> str:
        """
        Process messages using the Enhanced ReAct pattern.
        
        FIXED: Now uses STRUCTURED_REACT_SYSTEM_GUIDANCE from prompts module
        instead of embedding the prompt directly.
        """
        self._validate_configuration()
            
        # FIXED: Use prompt from prompts module instead of embedding
        enhanced_guidance = Message(
            role="system",
            content=STRUCTURED_REACT_SYSTEM_GUIDANCE
        )
        
        # Add conclude tool to available tools
        tools = self._get_enhanced_tools()
        
        # Make a copy of messages and add the guidance
        updated_messages = messages.copy()
        updated_messages.append(enhanced_guidance)
        
        # Start the enhanced ReAct cycle
        iteration = 0
        current_phase = ReActPhase.THINK
        
        while iteration < MAX_REACT_ITERATIONS:
            iteration += 1
            
            if self.verbose:
                logger.info(f"Enhanced ReAct iteration {iteration}, Phase: {current_phase.value}")
            
            # Generate response with potential tool calls
            response, tool_calls = await self.llm.acomplete_with_tool_calls(
                messages=updated_messages,
                tools=tools
            )
            
            # Add response to memory
            memory.add_message(response)
            
            # Check for termination
            if self._check_for_termination(tool_calls):
                termination_result = await self._handle_termination(tool_calls, memory)
                return termination_result
            
            # If no tool calls, continue reasoning
            if not tool_calls:
                # Add to messages for next iteration
                updated_messages.append(response)
                current_phase = self._determine_next_phase(response.content, current_phase)
                continue
            
            # Process tool calls in phases
            results = await self.mcp.execute_tool_calls(tool_calls)
            
            # Add tool results to memory with phase-aware processing
            for tool_call, result in zip(tool_calls, results):
                # Determine which phase we're in based on tool usage
                if tool_call.function.name == "conclude":
                    return await self._handle_termination([tool_call], memory)
                
                # Add tool result with observation phase
                tool_msg = Message(
                    role="tool",
                    content=f"👁️ OBSERVING: {result.result if result.success else result.error}",
                    name=tool_call.function.name,
                    tool_call_id=tool_call.id
                )
                memory.add_message(tool_msg)
            
            # Update messages for next iteration
            updated_messages = memory.get_messages()
            updated_messages.append(enhanced_guidance)
            
            # Determine next phase
            current_phase = self._advance_phase(current_phase)
        
        # Max iterations reached - force conclusion
        return await self._force_conclusion(memory)
    
    def _get_enhanced_tools(self) -> List[Dict[str, Any]]:
        """Get tools including the conclude termination tool."""
        base_tools = self.mcp.get_tool_definitions()
        
        # Add conclude tool for termination
        conclude_tool = {
            "type": "function",
            "function": {
                "name": "conclude",
                "description": "Signal task completion and provide final answer with confidence assessment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "final_answer": {
                            "type": "string", 
                            "description": "The comprehensive final response to the user"
                        },
                        "confidence": {
                            "type": "number", 
                            "description": "Confidence level in the answer (0.0-1.0)"
                        },
                        "reasoning_summary": {
                            "type": "string", 
                            "description": "Brief summary of the reasoning process used"
                        },
                        "information_gaps": {
                            "type": "string",
                            "description": "Any remaining uncertainties or information gaps"
                        }
                    },
                    "required": ["final_answer", "confidence"]
                }
            }
        }
        
        return base_tools + [conclude_tool]
    
    def _check_for_termination(self, tool_calls: List[ToolCall]) -> bool:
        """Check if any tool call is a termination signal."""
        if not tool_calls:
            return False
        return any(tc.function.name == "conclude" for tc in tool_calls)
    
    async def _handle_termination(self, tool_calls: List[ToolCall], memory: ConversationMemory) -> str:
        """Handle termination and extract final answer."""
        for tool_call in tool_calls:
            if tool_call.function.name == "conclude":
                args = tool_call.function.arguments
                final_answer = args.get("final_answer", "Task completed.")
                confidence = args.get("confidence", 0.0)
                reasoning_summary = args.get("reasoning_summary", "")
                
                # Log termination details
                if self.verbose:
                    logger.info(f"Task concluded with confidence: {confidence}")
                    if reasoning_summary:
                        logger.info(f"Reasoning summary: {reasoning_summary}")
                
                # Add termination message to memory
                termination_msg = Message(
                    role="assistant",
                    content=f"🎯 CONCLUDED: {final_answer}",
                    metadata={"termination": True, "confidence": confidence}
                )
                memory.add_message(termination_msg)
                
                return final_answer
        
        return "Task completed without explicit conclusion."
    
    def _determine_next_phase(self, content: str, current_phase: ReActPhase) -> ReActPhase:
        """Determine next phase based on content and current phase."""
        content_lower = content.lower()
        
        # FIXED: Use phase guidance from prompts module
        if "🧠 thinking:" in content_lower or "think" in content_lower:
            return ReActPhase.THINK
        elif "👁️ observing:" in content_lower or "observe" in content_lower:
            return ReActPhase.OBSERVE  
        elif "🤔 reflecting:" in content_lower or "reflect" in content_lower:
            return ReActPhase.REFLECT
        else:
            return self._advance_phase(current_phase)
    
    def _advance_phase(self, current_phase: ReActPhase) -> ReActPhase:
        """Advance to next logical phase in the cycle."""
        phase_order = [ReActPhase.THINK, ReActPhase.ACT, ReActPhase.OBSERVE, ReActPhase.REFLECT]
        
        try:
            current_index = phase_order.index(current_phase)
            next_index = (current_index + 1) % len(phase_order)
            return phase_order[next_index]
        except ValueError:
            return ReActPhase.THINK
    
    async def _force_conclusion(self, memory: ConversationMemory) -> str:
        """Force conclusion when max iterations reached."""
        warning_msg = Message(
            role="system",
            content=f"Maximum iterations ({MAX_REACT_ITERATIONS}) reached. Please provide your best answer based on available information."
        )
        memory.add_message(warning_msg)
        
        # Get final response
        final_response = await self.llm.acomplete(memory.get_messages())
        memory.add_message(final_response)
        
        return final_response.content
    
    # Streaming support
    async def process_stream(self, messages: List[MessageProtocol], memory: ConversationMemory) -> AsyncIterator[str]:
        """Enhanced streaming with phase indicators."""
        # For now, use non-streaming and yield result
        # Future enhancement: true streaming with phase indicators
        result = await self.process(messages, memory)
        yield result
