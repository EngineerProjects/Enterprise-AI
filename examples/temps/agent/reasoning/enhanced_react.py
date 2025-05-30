"""
Enhanced ReAct reasoning framework with improved tool execution loop.

This fixes the critical issue where tool calls are generated but not executed
in the proper conversational loop.
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.agent.reasoning.base import ToolBasedReasoning
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata
from enterprise_ai.agent.tools.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
)

logger = get_logger("agent.reasoning.react_enhanced")


class EnhancedReActReasoning(ToolBasedReasoning):
    """
    Enhanced ReAct reasoning framework with proper tool execution loop.
    
    This version ensures that:
    1. Tool calls are properly detected and parsed
    2. Tools are executed immediately when detected
    3. Tool results are fed back into the conversation
    4. The loop continues until completion or max iterations
    """

    async def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using enhanced ReAct approach with proper tool execution loop.
        """
        llm_provider = kwargs.pop("llm_provider", None)
        if not llm_provider:
            if hasattr(agent, "_llm_provider"):
                llm_provider = getattr(agent, "_llm_provider")
            else:
                logger.error(f"No LLM provider available for agent {agent.id}")
                return cast(
                    MessageProtocol,
                    Message.assistant_message(
                        "I'm unable to process your request due to a configuration issue."
                    ),
                )

        # Ensure we have proper ReAct system prompt
        working_messages = await self._ensure_react_system_prompt(agent, list(messages), **kwargs)
        
        # Run the main ReAct loop
        max_iterations = kwargs.get("max_iterations", 5)
        current_iteration = 0
        
        while current_iteration < max_iterations:
            current_iteration += 1
            logger.info(f"ReAct iteration {current_iteration}/{max_iterations} for agent {agent.id}")
            
            try:
                # Get response from LLM
                response = await self._get_llm_response(llm_provider, working_messages, **kwargs)
                working_messages.append(response)
                
                # Check if we have a final answer
                if self._is_final_answer(response.content or ""):
                    logger.info(f"ReAct completed with final answer after {current_iteration} iterations")
                    return response
                
                # Parse and execute any tool calls
                tool_executed = await self._process_tool_calls_in_response(
                    agent, response, working_messages, **kwargs
                )
                
                # If no tools were executed and no final answer, prompt for action
                if not tool_executed and not self._is_final_answer(response.content or ""):
                    prompt_msg = Message.user_message(
                        "Please either use a tool to get more information or provide your final answer."
                    )
                    working_messages.append(cast(MessageProtocol, prompt_msg))
                
            except Exception as e:
                logger.error(f"Error in ReAct iteration {current_iteration}: {e}")
                break
        
        # If we've reached max iterations, return the last response
        if working_messages and working_messages[-1].role == "assistant":
            return working_messages[-1]
        
        # Fallback response
        return cast(
            MessageProtocol,
            Message.assistant_message(
                "I've processed your request but reached the maximum number of reasoning steps. "
                "Please let me know if you need me to continue with a more specific question."
            ),
        )

    async def _ensure_react_system_prompt(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> List[MessageProtocol]:
        """Ensure the conversation has a proper ReAct system prompt."""
        
        # Get tools description
        tools_description = await self._get_tools_description(agent, **kwargs)
        
        # Check if we already have a system message with ReAct instructions
        has_react_system = False
        for i, msg in enumerate(messages):
            if msg.role == "system" and msg.content:
                if self._has_react_instructions(msg.content):
                    has_react_system = True
                else:
                    # Update existing system message with ReAct instructions
                    react_prompt = self._create_react_system_prompt(tools_description, msg.content)
                    messages[i] = cast(MessageProtocol, Message.system_message(react_prompt))
                    has_react_system = True
                break
        
        # If no system message, add one
        if not has_react_system:
            react_prompt = self._create_react_system_prompt(tools_description)
            messages.insert(0, cast(MessageProtocol, Message.system_message(react_prompt)))
        
        return messages

    async def _get_tools_description(self, agent: AgentProtocol, **kwargs: Any) -> str:
        """Get formatted tools description for the agent."""
        
        tools_description = kwargs.get("tools_description", "")
        
        if not tools_description and hasattr(agent, "_agent_tools_manager"):
            tool_manager = getattr(agent, "_agent_tools_manager")
            if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                tools_description = tool_manager.get_formatted_tool_descriptions(
                    include_capabilities=True, include_examples=True
                )
        
        return tools_description or "No tools available."

    def _create_react_system_prompt(self, tools_description: str, base_prompt: str = "") -> str:
        """Create a comprehensive ReAct system prompt."""
        
        react_instructions = f"""You are a helpful assistant that uses a Reasoning and Acting (ReAct) approach.

Follow these steps for each task:
1. Think: Analyze the problem and what you need to do
2. Act: Use tools when you need information or to perform actions  
3. Observe: Review the results from your actions
4. Repeat: Continue until you can provide a final answer

CRITICAL: Tool Usage Instructions
When you need to use a tool, use this EXACT format:

<tool_request>
{{
  "name": "tool_name",
  "parameters": {{
    "parameter1": "value1",
    "parameter2": "value2"
  }}
}}
</tool_request>

Available Tools:
{tools_description}

Response Format:
Thought: [Your reasoning about what to do next]
<tool_request>...</tool_request> [If you need to use a tool]
Observation: [Results from tool execution - will be provided automatically]
... [Repeat as needed]
Answer: [Your final answer when you have enough information]

IMPORTANT: 
- Always think step by step
- Use tools when you need information you don't have
- Provide a clear final answer when you're done
"""
        
        if base_prompt:
            return f"{base_prompt}\n\n{react_instructions}"
        else:
            return react_instructions

    def _has_react_instructions(self, prompt: str) -> bool:
        """Check if a prompt already contains ReAct instructions."""
        react_indicators = [
            "reasoning and acting", "react approach", "tool_request",
            "thought:", "action:", "observation:", "answer:"
        ]
        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in react_indicators)

    async def _get_llm_response(
        self, llm_provider: Any, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Get response from LLM with proper error handling."""
        
        try:
            # Clean kwargs to avoid serialization issues
            sanitized_kwargs = {
                k: v for k, v in kwargs.items() 
                if k not in ["llm_provider", "tools_description"] and not str(k).startswith("_")
            }
            
            response = llm_provider.complete(messages, **sanitized_kwargs)
            
            # Ensure response is in ReAct format
            if response.content and not self._is_react_format(response.content):
                response.content = self._format_as_react_thought(response.content)
            
            return cast(MessageProtocol, response)
            
        except Exception as e:
            logger.error(f"Error getting LLM response: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(f"I encountered an error: {str(e)}")
            )

    async def _process_tool_calls_in_response(
        self, agent: AgentProtocol, response: MessageProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> bool:
        """Process any tool calls found in the response and add results to messages."""
        
        if not response.content:
            return False
        
        # Extract tool calls using multiple methods
        tool_calls = parse_message_for_tool_calls(response)
        
        # If no structured tool calls, try to extract from ReAct format
        if not tool_calls:
            tool_calls = self._extract_tool_requests_from_text(response.content)
        
        if not tool_calls:
            logger.debug("No tool calls found in response")
            return False
        
        logger.info(f"Found {len(tool_calls)} tool calls to execute")
        
        # Execute each tool call
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            params = tool_call.get("parameters", {})
            
            if not tool_name:
                continue
            
            try:
                # Execute the tool
                tool_result = await self._execute_tool_safely(agent, tool_name, params, **kwargs)
                
                # Format the result as an observation
                observation = self._format_tool_result_as_observation(tool_name, tool_result)
                
                # Add observation to messages
                observation_msg = Message.user_message(observation)
                messages.append(cast(MessageProtocol, observation_msg))
                
                logger.info(f"Executed tool {tool_name} and added observation")
                
            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                # Add error observation
                error_observation = f"Observation: Error executing {tool_name}: {str(e)}"
                error_msg = Message.user_message(error_observation)
                messages.append(cast(MessageProtocol, error_msg))
        
        return len(tool_calls) > 0

    def _extract_tool_requests_from_text(self, content: str) -> List[Dict[str, Any]]:
        """Extract tool requests from text content using multiple patterns."""
        
        tool_calls = []
        
        # Pattern 1: <tool_request> JSON format
        tool_matches = re.findall(r"<tool_request>\s*({.*?})\s*</tool_request>", content, re.DOTALL)
        for match in tool_matches:
            try:
                tool_data = json.loads(match)
                if "name" in tool_data:
                    tool_calls.append({
                        "name": tool_data.get("name", ""),
                        "parameters": tool_data.get("parameters", {}),
                        "id": f"extracted-{datetime.now().timestamp()}"
                    })
            except json.JSONDecodeError:
                continue
        
        # Pattern 2: Action: tool_name(params) format
        action_matches = re.findall(r"Action:\s*(\w+)\s*\((.*?)\)", content)
        for tool_name, params_str in action_matches:
            params = {}
            # Simple parameter parsing for key=value pairs
            param_pairs = re.findall(r"(\w+)=([^,\)]+)", params_str)
            for key, value in param_pairs:
                # Clean and convert value
                value = value.strip().strip('"\'')
                if value.lower() == "true":
                    params[key] = True
                elif value.lower() == "false":
                    params[key] = False
                elif value.isdigit():
                    params[key] = int(value)
                else:
                    params[key] = value
            
            tool_calls.append({
                "name": tool_name,
                "parameters": params,
                "id": f"action-{datetime.now().timestamp()}"
            })
        
        return tool_calls

    async def _execute_tool_safely(
        self, agent: AgentProtocol, tool_name: str, params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """Execute a tool with comprehensive error handling."""
        
        if not hasattr(agent, "_agent_tools_manager"):
            return ToolFailure(
                error="Agent does not have a tool manager",
                error_code="NO_TOOL_MANAGER",
                metadata=ToolResultMetadata(tool_name=tool_name)
            )
        
        tool_manager = getattr(agent, "_agent_tools_manager")
        
        try:
            # Configure execution options
            timeout = kwargs.get("tool_timeout", 30.0)
            retry_count = kwargs.get("retry_count", 1)
            
            logger.info(f"Executing tool {tool_name} with timeout {timeout}s")
            
            # Execute the tool
            result = await tool_manager.execute_tool(
                tool_name=tool_name,
                timeout=timeout,
                retry_count=retry_count,
                **params
            )
            
            logger.info(f"Tool {tool_name} executed successfully")
            return cast(ToolResult, result)
            
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolFailure(
                error=f"Tool execution error: {str(e)}",
                error_code="EXECUTION_ERROR",
                metadata=ToolResultMetadata(tool_name=tool_name)
            )

    def _format_tool_result_as_observation(self, tool_name: str, result: ToolResult) -> str:
        """Format a tool result as a ReAct observation."""
        
        if result.error:
            return f"Observation: Error executing {tool_name}: {result.error}"
        
        # Format the output appropriately
        if isinstance(result.output, (dict, list)):
            try:
                formatted_output = json.dumps(result.output, indent=2)
                return f"Observation: Tool {tool_name} result:\n{formatted_output}"
            except (TypeError, ValueError):
                return f"Observation: Tool {tool_name} result: {str(result.output)}"
        else:
            return f"Observation: {str(result.output)}"

    def _is_final_answer(self, content: str) -> bool:
        """Check if the content contains a final answer."""
        
        final_patterns = [
            r"Answer:\s*(.+)",
            r"Final Answer:\s*(.+)", 
            r"My final answer is",
            r"The answer is",
            r"In conclusion",
            r"Therefore,?\s*the answer"
        ]
        
        for pattern in final_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

    def _is_react_format(self, content: str) -> bool:
        """Check if content is already in ReAct format."""
        
        react_patterns = [
            r"Thought:",
            r"Action:",
            r"Observation:",
            r"Answer:",
            r"<tool_request>"
        ]
        
        for pattern in react_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        return False

    def _format_as_react_thought(self, content: str) -> str:
        """Format content as a ReAct thought if it's not already formatted."""
        
        if self._is_react_format(content):
            return content
        
        return f"Thought: {content}"

    @property
    def name(self) -> str:
        return "enhanced_react"

    @property  
    def description(self) -> str:
        return "Enhanced ReAct reasoning framework with improved tool execution loop"