"""
ReAct (Reasoning and Acting) framework for Enterprise AI agents.

This module implements the ReAct reasoning pattern, allowing agents to
alternate between reasoning about tasks and taking actions using tools.
The ReAct pattern follows a systematic approach of:
1. Thinking about the current state and what to do next
2. Acting by using tools
3. Observing the results
4. Repeating until the task is completed
"""

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.reasoning.base import ToolBasedReasoning
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.prompt import get_prompt, format_prompt, combine_prompts
from enterprise_ai.agent.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
)

logger = get_logger("agent.reasoning.react")


class ReActReasoning(ToolBasedReasoning):
    """
    ReAct reasoning framework implementation.

    This framework implements the ReAct pattern (Reasoning + Acting)
    allowing agents to systematically approach problems by thinking
    about what to do, taking actions via tools, observing results,
    and repeating until the task is completed.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using the ReAct approach.

        This method analyzes the conversation history, extracts any
        tool calls from the agent's previous responses, executes tools
        if needed, and generates the next agent response using the
        ReAct pattern.

        Args:
            agent: The agent using this reasoning framework
            messages: List of messages to process
            **kwargs: Additional parameters including LLM provider

        Returns:
            Response message
        """
        # Extract LLM provider
        llm_provider = kwargs.get("llm_provider")
        if not llm_provider:
            logger.error(f"No LLM provider available for agent {agent.id}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    "I'm unable to process your request due to a configuration issue."
                ),
            )

        # Get the last message
        if not messages:
            logger.error("No messages provided to ReAct reasoning")
            return cast(
                MessageProtocol, Message.assistant_message("I need some input to work with.")
            )

        # Check if agent's response needs to be processed for tool calls
        last_assistant_msg = None
        last_user_msg = None

        for msg in reversed(messages):
            if msg.role == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg
            elif msg.role == "user" and not last_user_msg:
                last_user_msg = msg
                break

        # Process tool calls if the last assistant message has them
        if last_assistant_msg:
            tool_calls = parse_message_for_tool_calls(last_assistant_msg)

            if tool_calls:
                logger.info(f"Found {len(tool_calls)} tool calls in agent {agent.id} response")

                # Execute tools and add results to messages
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    params = tool_call.get("parameters", {})
                    tool_id = tool_call.get("id")  # noqa: F841

                    if not tool_name:
                        continue

                    try:
                        # Execute the tool
                        tool_result = self.handle_tool_execution(agent, tool_name, params, **kwargs)

                        # Format result as observation
                        observation = f"Observation: {tool_result.output if not tool_result.error else 'Error: ' + tool_result.error}"

                        # Add observation as user message
                        tool_response = Message.user_message(observation)
                        messages.append(cast(MessageProtocol, tool_response))

                        logger.info(f"Added tool result for {tool_name} to conversation")
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        # Add error observation
                        error_msg = Message.user_message(
                            f"Observation: Error executing tool {tool_name}: {str(e)}"
                        )
                        messages.append(cast(MessageProtocol, error_msg))

        # Generate response from LLM
        try:
            response = llm_provider.complete(messages, **kwargs)

            # Ensure response follows ReAct format
            if response.content and not self._is_react_format(response.content):
                formatted_content = self._format_as_react(response.content)
                response = cast(
                    MessageProtocol,
                    Message.assistant_message(formatted_content, metadata=response.metadata),
                )

            return cast(MessageProtocol, response)
        except Exception as e:
            logger.error(f"Error in ReAct reasoning for agent {agent.id}: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def _is_react_format(self, content: str) -> bool:
        """
        Check if content follows ReAct format.

        Args:
            content: Message content to check

        Returns:
            True if content follows ReAct format, False otherwise
        """
        # Check for "Thought:", "Action:", or "Observation:" patterns
        react_patterns = [r"Thought:", r"Action:", r"Observation:", r"Answer:"]

        for pattern in react_patterns:
            if re.search(pattern, content):
                return True

        return False

    def _format_as_react(self, content: str) -> str:
        """
        Format content to follow ReAct pattern.

        Args:
            content: Content to format

        Returns:
            Content formatted in ReAct pattern
        """
        # If content already contains some ReAct elements, don't reformat
        if self._is_react_format(content):
            return content

        # Extract potential tool calls
        tool_match = re.search(r"<tool_request>(.*?)</tool_request>", content, re.DOTALL)

        if tool_match:
            # Content already has tool request, just add Thought prefix
            if not content.startswith("Thought:"):
                thought_content = content.split("<tool_request>")[0].strip()
                tool_content = content[content.find("<tool_request>") :]
                return f"Thought: {thought_content}\n\nAction: {tool_content}"

        # Regular content, format as thought
        return f"Thought: {content}\n\nI need more information to proceed or take an action."

    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """
        Process a task using ReAct reasoning.

        Args:
            agent: The agent using this reasoning framework
            task: Task to process
            **kwargs: Additional parameters

        Returns:
            Updated task status
        """
        # Extract LLM provider
        llm_provider = kwargs.get("llm_provider")
        if not llm_provider:
            logger.error(f"No LLM provider available for agent {agent.id}")
            task.status = TaskStatus.FAILED
            return task.status

        # Get system prompt
        system_prompt = self.format_system_prompt(agent, "", **kwargs)

        # Create messages for the task
        message_list: List[Message] = []
        message_list.append(Message.system_message(system_prompt))
        message_list.append(Message.user_message(f"Task: {task.description}"))

        # Process with LLM in a loop until task is completed or max iterations reached
        max_iterations = kwargs.get("max_iterations", 10)
        current_iteration = 0

        while current_iteration < max_iterations:
            current_iteration += 1

            try:
                # Get response from LLM
                response = llm_provider.complete(
                    [cast(MessageProtocol, msg) for msg in message_list]
                )
                message_list.append(cast(Message, response))

                # Check if task is completed
                if self._is_task_completed(response.content or ""):
                    # Store response in task metadata
                    if not task.metadata:
                        task.metadata = {}
                    task.metadata["response"] = response.content
                    task.metadata["iterations"] = current_iteration

                    task.status = TaskStatus.COMPLETED
                    return task.status

                # Check for tool calls
                tool_calls = parse_message_for_tool_calls(response)

                if not tool_calls:
                    # No tool calls, extract action from text
                    action_info = self._extract_action_from_text(response.content or "")
                    if action_info:
                        tool_name, params = action_info

                        # Execute tool
                        tool_result = self.handle_tool_execution(agent, tool_name, params, **kwargs)

                        # Add observation
                        observation = f"Observation: {tool_result.output if not tool_result.error else 'Error: ' + tool_result.error}"
                        message_list.append(Message.user_message(observation))
                    else:
                        # No action found, add a prompt to continue
                        message_list.append(
                            Message.user_message(
                                "I need you to take an action or provide a final answer."
                            )
                        )
                else:
                    # Process each tool call
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name", "")
                        params = tool_call.get("parameters", {})

                        if not tool_name:
                            continue

                        # Execute tool
                        tool_result = self.handle_tool_execution(agent, tool_name, params, **kwargs)

                        # Format result as observation
                        observation = f"Observation: {tool_result.output if not tool_result.error else 'Error: ' + tool_result.error}"
                        message_list.append(Message.user_message(observation))

            except Exception as e:
                logger.error(f"Error processing task for agent {agent.id}: {e}")
                task.status = TaskStatus.FAILED
                return task.status

        # If we've reached max iterations without completing the task
        if not task.metadata:
            task.metadata = {}
        task.metadata["iterations"] = current_iteration
        task.metadata["max_iterations_reached"] = True

        # Use the last response as the result
        if message_list and message_list[-1].role == "assistant":
            task.metadata["response"] = message_list[-1].content

        task.status = TaskStatus.COMPLETED  # Consider it completed even if max iterations reached
        return task.status

    def _is_task_completed(self, content: str) -> bool:
        """
        Check if task completion is indicated in the content.

        Args:
            content: Message content to check

        Returns:
            True if task completion is indicated, False otherwise
        """
        # Check for task completion indicators
        completion_patterns = [
            r"Answer:",
            r"Final Answer:",
            r"Task completed",
            r"I've completed the task",
        ]

        for pattern in completion_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _extract_action_from_text(self, content: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Extract tool action from text content.

        Args:
            content: Message content to parse

        Returns:
            Tuple of (tool_name, parameters) if action found, None otherwise
        """
        # Try to extract ReAct format action
        action_match = re.search(r"Action:\s*(\w+)\s*\((.*?)\)", content, re.DOTALL)

        if action_match:
            tool_name = action_match.group(1)
            params_text = action_match.group(2)

            # Parse parameters
            params: Dict[str, Any] = {}
            param_matches = re.findall(r"(\w+)=([^,]+)(?:,|$)", params_text)

            for key, value in param_matches:
                # Convert to appropriate types
                if value.lower() == "true":
                    params[key] = True
                elif value.lower() == "false":
                    params[key] = False
                elif value.isdigit():
                    params[key] = int(value)  # Type consistent with Dict[str, Any]
                elif value.replace(".", "", 1).isdigit():
                    params[key] = float(value)  # Type consistent with Dict[str, Any]
                else:
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    params[key] = value

            return tool_name, params

        # Try to extract JSON format action
        json_match = re.search(r"```json\s*({.*?})\s*```", content, re.DOTALL)
        if json_match:
            try:
                json_data = json.loads(json_match.group(1))
                if (
                    isinstance(json_data, dict)
                    and "tool" in json_data
                    and "parameters" in json_data
                ):
                    return json_data["tool"], json_data["parameters"]
            except json.JSONDecodeError:
                pass

        return None

    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """
        Format the system prompt for ReAct reasoning.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Get tools description
        tools_description = kwargs.get("tools_description", "")

        if not tools_description and hasattr(agent, "_tool_manager"):
            # Get tools description from agent's tool manager
            tool_manager = getattr(agent, "_tool_manager")
            if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                tools_description = tool_manager.get_formatted_tool_descriptions()

        # Use the existing prompt templates
        react_prompt = get_tool_prompt_for_reasoning("react", tools_description)

        # Combine with base prompt
        if base_prompt:
            # If we have a base prompt, format it properly and combine
            base_formatted = format_prompt("system.base", additional_instructions=base_prompt)
            if base_formatted:
                combined = combine_prompts(
                    ["system.base", "system.react"],
                    additional_instructions=base_prompt,
                    tools_description=tools_description,
                )
                if combined:
                    return combined

        # Just return the react prompt with tools if no base prompt
        return react_prompt or ""  # Ensure we never return None

    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """
        Format instructions for tool usage.

        Args:
            agent: The agent using this reasoning framework
            tools: List of available tools
            **kwargs: Additional parameters

        Returns:
            Formatted tool instructions
        """
        # Format tools description
        from enterprise_ai.mcp.utils import format_tool_descriptions

        tools_description = format_tool_descriptions(tools)

        # Use existing prompt template
        additional_instructions = kwargs.get("additional_instructions", "")

        instructions = format_prompt(
            "system.react",
            tools_description=tools_description,
            additional_react_instructions=additional_instructions,
        )

        # Fallback to a simple format if the template is not available
        if not instructions:
            logger.warning("React prompt template not found, using fallback")
            return get_tool_prompt_for_reasoning("react", tools_description)

        return instructions

    def handle_tool_execution(
        self, agent: AgentProtocol, tool_name: str, tool_params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """
        Handle the execution of a tool.

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            tool_params: Parameters for tool execution
            **kwargs: Additional parameters

        Returns:
            Tool execution result
        """
        if not hasattr(agent, "_tool_manager"):
            return ToolResult(error="Agent does not have a tool manager")

        tool_manager = getattr(agent, "_tool_manager")

        try:
            # Execute tool
            import asyncio

            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(tool_manager.execute_tool(tool_name, **tool_params))

            logger.info(f"Executed tool {tool_name} for agent {agent.id}")
            return cast(ToolResult, result)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolResult(error=f"Tool execution error: {str(e)}")

    def parse_tool_calls(self, message: MessageProtocol, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Parse tool calls from a message.

        Args:
            message: Message to parse for tool calls
            **kwargs: Additional parameters

        Returns:
            List of tool calls with name and parameters
        """
        return parse_message_for_tool_calls(message)

    def format_tool_response(self, tool_name: str, tool_result: ToolResult, **kwargs: Any) -> str:
        """
        Format a tool execution result for inclusion in a message.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            **kwargs: Additional parameters

        Returns:
            Formatted tool response
        """
        if tool_result.error:
            return f"Observation: Error: {tool_result.error}"
        else:
            return f"Observation: {tool_result.output or 'Success'}"

    def supports_function_calling(self) -> bool:
        """
        Check if this framework supports function calling.

        Returns:
            True if function calling is supported, False otherwise
        """
        return True

    @property
    def name(self) -> str:
        """
        Get the name of this reasoning framework.

        Returns:
            Framework name
        """
        return "react"

    @property
    def description(self) -> str:
        """
        Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        return "ReAct reasoning framework that combines reasoning with action taking in a systematic way."
