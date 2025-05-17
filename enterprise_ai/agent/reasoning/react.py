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
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.reasoning.base import ToolBasedReasoning
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.prompt import get_prompt, format_prompt, combine_prompts
from enterprise_ai.agent.tools.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
    validate_tool_parameters,
    get_tool_error_handling_prompt,
)
from enterprise_ai.mcp.utils import format_tool_descriptions

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
        # Extract LLM provider and remove from kwargs to avoid serialization issues
        llm_provider = kwargs.pop("llm_provider", None)
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

        # Ensure system prompt includes ReAct instructions
        has_react_prompt = False
        for idx, msg in enumerate(messages):
            if msg.role == "system" and msg.content:
                # Check if system prompt already includes ReAct instructions
                has_react_prompt = self._has_react_instructions(msg.content)

                if not has_react_prompt:
                    # Get tools description
                    tools_description = kwargs.get("tools_description", "")

                    if not tools_description and hasattr(agent, "_tool_manager"):
                        # Get tools description from agent's tool manager
                        tool_manager = getattr(agent, "_tool_manager")
                        if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                            tools_description = tool_manager.get_formatted_tool_descriptions(
                                include_capabilities=True, include_examples=True
                            )

                    # Format updated ReAct system prompt with tool information
                    react_prompt = self.format_system_prompt(
                        agent, msg.content, tools_description=tools_description, **kwargs
                    )

                    # Update the system message
                    messages[idx] = cast(MessageProtocol, Message.system_message(react_prompt))

                break

        # If no system message found, add one with ReAct instructions
        if not any(msg.role == "system" for msg in messages):
            tools_description = kwargs.get("tools_description", "")

            if not tools_description and hasattr(agent, "_tool_manager"):
                # Get tools description from agent's tool manager
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                    tools_description = tool_manager.get_formatted_tool_descriptions(
                        include_capabilities=True, include_examples=True
                    )

            # Format ReAct system prompt
            react_prompt = self.format_system_prompt(
                agent, "", tools_description=tools_description, **kwargs
            )

            # Add system message at the beginning
            messages.insert(0, cast(MessageProtocol, Message.system_message(react_prompt)))

        # Process previously identified tool calls
        updated_messages = self._process_previous_tool_calls(agent, messages, **kwargs)

        # Generate response from LLM
        try:
            # Get available tools if function calling is supported
            tools_schema = []
            function_calling = False

            if hasattr(llm_provider, "supports_feature"):
                function_calling = llm_provider.supports_feature("function_calling")

            if function_calling and hasattr(agent, "_tool_manager"):
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_tool_schemas"):
                    # Run in event loop to get tool schemas
                    loop = self._get_event_loop()
                    tools_schema = loop.run_until_complete(
                        tool_manager.get_tool_schemas(filter_by_capabilities=True)
                    )

            # Remove any provider reference that might have been added back
            sanitized_kwargs = {k: v for k, v in kwargs.items() if not str(k) == "llm_provider"}

            # Add tools to kwargs if available
            if tools_schema:
                sanitized_kwargs["tools"] = tools_schema

            response = llm_provider.complete(updated_messages, **sanitized_kwargs)

            # Ensure response follows ReAct format
            if response.content and not self._is_react_format(response.content):
                formatted_content = self._format_as_react(response.content)
                response = cast(
                    MessageProtocol,
                    Message.assistant_message(formatted_content, metadata=response.metadata),
                )

            return cast(MessageProtocol, response)
        except Exception as e:
            logger.error(f"Error in ReAct reasoning for agent {agent.id}: {e}", exc_info=True)
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def _has_react_instructions(self, prompt: str) -> bool:
        """
        Check if a prompt contains ReAct instructions.

        Args:
            prompt: Prompt to check

        Returns:
            True if the prompt contains ReAct instructions
        """
        react_indicators = [
            "thinking, acting, and observing",
            "thought:",
            "action:",
            "observation:",
            "reason step by step",
            "react pattern",
            "reasoning and acting",
        ]

        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in react_indicators)

    def _process_previous_tool_calls(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> List[MessageProtocol]:
        """
        Process any tool calls in previous messages.

        Args:
            agent: The agent using this reasoning framework
            messages: List of messages to process
            **kwargs: Additional parameters

        Returns:
            Updated list of messages
        """
        # Make a copy to avoid modifying the original
        updated_messages = list(messages)

        # Check for the last assistant message
        last_assistant_msg = None
        last_user_msg = None

        for msg in reversed(updated_messages):
            if msg.role == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg
            elif msg.role == "user" and not last_user_msg:
                last_user_msg = msg
                break

        # Process tool calls if the last assistant message has them
        if last_assistant_msg:
            # First look for structured tool calls
            tool_calls = parse_message_for_tool_calls(last_assistant_msg)

            # If no structured tool calls, try to extract from ReAct format text
            if not tool_calls and last_assistant_msg.content:
                action_info = self._extract_action_from_text(last_assistant_msg.content)
                if action_info:
                    tool_name, params = action_info
                    tool_calls = [
                        {
                            "name": tool_name,
                            "parameters": params,
                            "id": f"extracted-{datetime.now().timestamp()}",
                        }
                    ]

            if tool_calls:
                logger.info(f"Found {len(tool_calls)} tool calls in agent {agent.id} response")

                # Execute tools and add results to messages
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "")
                    params = tool_call.get("parameters", {})
                    tool_id = tool_call.get("id")

                    if not tool_name:
                        continue

                    try:
                        # Execute the tool with proper error handling
                        tool_result = self._execute_tool_with_handling(
                            agent, tool_name, params, **kwargs
                        )

                        # Format result as observation for ReAct
                        if tool_result.error:
                            observation = (
                                f"Observation: Error executing {tool_name}: {tool_result.error}"
                            )
                        else:
                            # Format the output according to its type
                            if isinstance(tool_result.output, (dict, list)):
                                try:
                                    formatted_output = json.dumps(tool_result.output, indent=2)
                                    observation = f"Observation: {formatted_output}"
                                except (TypeError, ValueError):
                                    observation = f"Observation: {str(tool_result.output)}"
                            else:
                                observation = f"Observation: {str(tool_result.output)}"

                        # Add observation as user message
                        updated_messages.append(
                            cast(MessageProtocol, Message.user_message(observation))
                        )
                        logger.info(f"Added tool result for {tool_name} to conversation")
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                        # Add error observation
                        error_msg = Message.user_message(
                            f"Observation: Error executing tool {tool_name}: {str(e)}"
                        )
                        updated_messages.append(cast(MessageProtocol, error_msg))

        return updated_messages

    def _execute_tool_with_handling(
        self, agent: AgentProtocol, tool_name: str, params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """
        Execute a tool with enhanced error handling.

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            params: Parameters for tool execution
            **kwargs: Additional parameters

        Returns:
            Tool execution result
        """
        if not hasattr(agent, "_tool_manager"):
            return ToolFailure(
                error="Agent does not have a tool manager",
                error_code="NO_TOOL_MANAGER",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )

        tool_manager = getattr(agent, "_tool_manager")

        # Validate parameters against tool schema if validation is enabled
        if hasattr(tool_manager, "get_tool") and kwargs.get("validate_params", True):
            tool = tool_manager.get_tool(tool_name)
            if tool and hasattr(tool, "parameters"):
                valid_params, error_msg = validate_tool_parameters(
                    tool_name, params, tool.parameters
                )
                if not valid_params:
                    return ToolFailure(
                        error=f"Invalid parameters: {error_msg}",
                        error_code="INVALID_PARAMETERS",
                        retryable=True,
                        metadata=ToolResultMetadata(tool_name=tool_name),
                    )

        # Configure execution options
        timeout = kwargs.get("tool_timeout", None)
        retry_count = kwargs.get("retry_count", 2)
        retry_delay = kwargs.get("retry_delay", 1.0)

        try:
            # Execute tool with retry logic
            loop = self._get_event_loop()
            result = loop.run_until_complete(
                tool_manager.execute_tool(
                    tool_name=tool_name,
                    timeout=timeout,
                    retry_count=retry_count,
                    retry_delay=retry_delay,
                    **params,
                )
            )

            logger.info(f"Executed tool {tool_name} for agent {agent.id}")
            return cast(ToolResult, result)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return ToolFailure(
                error=f"Tool execution error: {str(e)}",
                error_code="EXECUTION_ERROR",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get or create an event loop.

        Returns:
            Event loop instance
        """
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists in this thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def execute_tools_parallel(
        self, agent: AgentProtocol, tool_calls: List[Dict[str, Any]], **kwargs: Any
    ) -> List[Tuple[str, ToolResult]]:
        """
        Execute multiple tools in parallel.

        Args:
            agent: The agent using this reasoning framework
            tool_calls: List of tool call specifications
            **kwargs: Additional parameters

        Returns:
            List of tuples containing (tool_name, result)
        """
        if not hasattr(agent, "_tool_manager"):
            # Return error results if no tool manager
            return [
                (
                    call["name"],
                    ToolFailure(
                        error="Agent does not have a tool manager", error_code="NO_TOOL_MANAGER"
                    ),
                )
                for call in tool_calls
            ]

        tool_manager = getattr(agent, "_tool_manager")

        # Prepare executions for parallel processing
        executions = []
        tool_names = []

        for call in tool_calls:
            tool_name = call.get("name", "")
            params = call.get("parameters", {})

            if not tool_name:
                continue

            # Validate parameters if validation is enabled
            if hasattr(tool_manager, "get_tool") and kwargs.get("validate_params", True):
                tool = tool_manager.get_tool(tool_name)
                if tool and hasattr(tool, "parameters"):
                    valid_params, _ = validate_tool_parameters(tool_name, params, tool.parameters)
                    if not valid_params:
                        continue  # Skip invalid tools

            # Configure execution
            timeout = kwargs.get("tool_timeout", None)
            executions.append({"tool_name": tool_name, "parameters": params, "timeout": timeout})
            tool_names.append(tool_name)

        # Execute tools in parallel
        if not executions:
            return []

        try:
            # Use tool manager's parallel execution if available
            if hasattr(tool_manager, "execute_tools_parallel"):
                results = await tool_manager.execute_tools_parallel(executions)
                return results

            # Fallback: create and gather tasks manually
            tasks = []
            for execution in executions:
                task = asyncio.create_task(
                    tool_manager.execute_tool(
                        execution["tool_name"],
                        timeout=execution.get("timeout"),
                        **execution["parameters"],
                    )
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            return [
                (name, self._process_parallel_result(name, result))
                for name, result in zip(tool_names, results)
            ]
        except Exception as e:
            logger.error(f"Error executing tools in parallel: {e}", exc_info=True)
            # Return error results
            return [
                (
                    name,
                    ToolFailure(
                        error=f"Parallel execution error: {str(e)}",
                        error_code="PARALLEL_EXECUTION_ERROR",
                        metadata=ToolResultMetadata(tool_name=name),
                    ),
                )
                for name in tool_names
            ]

    def _process_parallel_result(self, tool_name: str, result: Any) -> ToolResult:
        """
        Process a result from parallel execution.

        Args:
            tool_name: Name of the tool
            result: Execution result or exception

        Returns:
            Processed tool result
        """
        if isinstance(result, Exception):
            return ToolFailure(
                error=f"Execution error: {str(result)}",
                error_code="EXECUTION_ERROR",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )

        if isinstance(result, ToolResult):
            # Ensure metadata includes tool name
            if result.metadata is None:
                result.metadata = ToolResultMetadata(tool_name=tool_name)
            elif result.metadata.tool_name is None:
                result.metadata.tool_name = tool_name

            return result

        # Convert non-ToolResult to ToolResult
        return ToolResult(output=result, metadata=ToolResultMetadata(tool_name=tool_name))

    def _is_react_format(self, content: str) -> bool:
        """
        Check if content follows ReAct format.

        Args:
            content: Message content to check

        Returns:
            True if content follows ReAct format, False otherwise
        """
        # Check for "Thought:", "Action:", or "Observation:" patterns
        react_patterns = [
            r"Thought:",
            r"Action:",
            r"Observation:",
            r"Answer:",
            r"I need to",
            r"First,",
        ]

        for pattern in react_patterns:
            if re.search(pattern, content, re.IGNORECASE):
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

        # Identify if content contains a specific task or question to answer
        if re.search(r"(task|answer|solve|find|calculate|determine)", content, re.IGNORECASE):
            return f"Thought: I need to analyze this problem step by step.\n\n{content}\n\nI need more information to proceed or take an action."

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
        tools_description = kwargs.get("tools_description", "")

        if not tools_description and hasattr(agent, "_tool_manager"):
            # Get tools description from agent's tool manager
            tool_manager = getattr(agent, "_tool_manager")
            if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                tools_description = tool_manager.get_formatted_tool_descriptions(
                    include_capabilities=True, include_examples=True
                )

        system_prompt = self.format_system_prompt(
            agent, "", tools_description=tools_description, **kwargs
        )

        # Create messages for the task
        message_list: List[Message] = []
        message_list.append(Message.system_message(system_prompt))
        message_list.append(Message.user_message(f"Task: {task.description}"))

        # Mark task as in progress
        task.status = TaskStatus.IN_PROGRESS

        # Initialize task metadata
        if not task.metadata:
            task.metadata = {}

        task.metadata["start_time"] = datetime.now().isoformat()

        # Process with LLM in a loop until task is completed or max iterations reached
        max_iterations = kwargs.get("max_iterations", 10)
        current_iteration = 0

        # Track previous actions to detect loops
        previous_actions: List[str] = []
        action_counter: Dict[str, int] = {}

        # Initialize backtracking state
        backtracking = False
        backtrack_attempt = 0
        max_backtrack_attempts = kwargs.get("max_backtrack_attempts", 2)

        while current_iteration < max_iterations:
            current_iteration += 1
            task.metadata["current_iteration"] = current_iteration

            try:
                # Get available tools for function calling
                tools_schema = []
                if hasattr(agent, "_tool_manager"):
                    tool_manager = getattr(agent, "_tool_manager")
                    if hasattr(tool_manager, "get_tool_schemas"):
                        # Run in event loop to get tool schemas
                        loop = self._get_event_loop()
                        tools_schema = loop.run_until_complete(
                            tool_manager.get_tool_schemas(filter_by_capabilities=True)
                        )

                # Prepare completion parameters
                completion_kwargs = {}
                if tools_schema:
                    completion_kwargs["tools"] = tools_schema

                # Add any additional parameters from kwargs
                for key, value in kwargs.items():
                    if key != "llm_provider" and key != "tools_description":
                        completion_kwargs[key] = value

                # Get response from LLM
                response = llm_provider.complete(
                    [cast(MessageProtocol, msg) for msg in message_list], **completion_kwargs
                )

                # Ensure response follows ReAct format
                if response.content and not self._is_react_format(response.content):
                    response.content = self._format_as_react(response.content)

                message_list.append(cast(Message, response))

                # Check if task is completed
                if self._is_task_completed(response.content or ""):
                    # Extract final answer
                    final_answer = self._extract_final_answer(response.content or "")

                    # Store response in task metadata
                    task.metadata["response"] = final_answer or response.content
                    task.metadata["iterations"] = current_iteration
                    task.metadata["end_time"] = datetime.now().isoformat()

                    task.status = TaskStatus.COMPLETED
                    return task.status

                # Check for tool calls
                tool_calls = parse_message_for_tool_calls(response)

                if not tool_calls:
                    # No structured tool calls, try to extract action from text
                    action_info = self._extract_action_from_text(response.content or "")

                    if action_info:
                        tool_name, params = action_info

                        # Check if we're in a loop of the same action
                        action_key = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
                        action_counter[action_key] = action_counter.get(action_key, 0) + 1

                        # Detect action loops and apply backtracking if needed
                        if action_counter[action_key] > 2 and not backtracking:
                            backtracking = True
                            backtrack_attempt += 1

                            # Add backtracking prompt
                            message_list.append(
                                Message.user_message(
                                    "I notice you're repeating the same action. Try a different approach or tool."
                                )
                            )
                            continue

                        # Execute tool
                        tool_result = self._execute_tool_with_handling(
                            agent, tool_name, params, **kwargs
                        )

                        # Add observation
                        observation = self._format_observation(tool_name, tool_result)
                        message_list.append(Message.user_message(observation))

                        # Reset backtracking state
                        if backtracking:
                            backtracking = False
                    else:
                        # No action found, add a prompt to continue
                        if backtracking and backtrack_attempt >= max_backtrack_attempts:
                            # Too many backtrack attempts, guide more explicitly
                            message_list.append(
                                Message.user_message(
                                    "Let's try to solve this problem differently. Please provide a final answer based on what you've learned so far."
                                )
                            )
                            backtracking = False
                        else:
                            message_list.append(
                                Message.user_message(
                                    "I need you to take an action or provide a final answer."
                                )
                            )
                else:
                    # Process each tool call
                    if len(tool_calls) > 1 and kwargs.get("enable_parallel", True):
                        # Execute tools in parallel
                        loop = self._get_event_loop()
                        tool_results = loop.run_until_complete(
                            self.execute_tools_parallel(agent, tool_calls, **kwargs)
                        )

                        # Add observations for all results
                        for tool_name, result in tool_results:
                            observation = self._format_observation(tool_name, result)
                            message_list.append(Message.user_message(observation))
                    else:
                        # Process sequentially
                        for tool_call in tool_calls:
                            tool_name = tool_call.get("name", "")
                            params = tool_call.get("parameters", {})

                            if not tool_name:
                                continue

                            # Execute tool
                            tool_result = self._execute_tool_with_handling(
                                agent, tool_name, params, **kwargs
                            )

                            # Add observation
                            observation = self._format_observation(tool_name, tool_result)
                            message_list.append(Message.user_message(observation))

            except Exception as e:
                logger.error(f"Error processing task for agent {agent.id}: {e}", exc_info=True)
                task.status = TaskStatus.FAILED
                task.metadata["error"] = str(e)
                return task.status

        # If we've reached max iterations without completing the task
        if not task.metadata:
            task.metadata = {}
        task.metadata["iterations"] = current_iteration
        task.metadata["max_iterations_reached"] = True
        task.metadata["end_time"] = datetime.now().isoformat()

        # Use the last response as the result
        if message_list and message_list[-1].role == "assistant":
            task.metadata["response"] = message_list[-1].content

        task.status = TaskStatus.COMPLETED  # Consider it completed even if max iterations reached
        return task.status

    def _format_observation(self, tool_name: str, result: ToolResult) -> str:
        """
        Format a tool result as an observation.

        Args:
            tool_name: Name of the tool
            result: Tool execution result

        Returns:
            Formatted observation
        """
        if result.error:
            return f"Observation: Error executing {tool_name}: {result.error}"

        # Format output based on type
        if isinstance(result.output, (dict, list)):
            try:
                formatted_output = json.dumps(result.output, indent=2)
                return f"Observation: {formatted_output}"
            except (TypeError, ValueError):
                return f"Observation: {str(result.output)}"
        else:
            return f"Observation: {str(result.output)}"

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
            r"The answer is",
            r"Here is the answer",
        ]

        for pattern in completion_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _extract_final_answer(self, content: str) -> Optional[str]:
        """
        Extract the final answer from content.

        Args:
            content: Message content to parse

        Returns:
            Extracted final answer or None
        """
        # Try to extract content after "Answer:" or "Final Answer:"
        answer_match = re.search(r"(?:Answer:|Final Answer:)(.*?)(?:$|\n\n)", content, re.DOTALL)
        if answer_match:
            return answer_match.group(1).strip()

        # If no match, return None
        return None

    def _extract_action_from_text(self, content: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Extract tool action from text content.

        Args:
            content: Message content to parse

        Returns:
            Tuple of (tool_name, parameters) if action found, None otherwise
        """
        # First try to extract ReAct format action
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

        # Try to extract tool request format
        tool_match = re.search(r"<tool_request>(.*?)</tool_request>", content, re.DOTALL)
        if tool_match:
            tool_content = tool_match.group(1)

            # Try parsing as JSON first
            try:
                tool_data = json.loads(tool_content)
                tool_name = tool_data.get("tool", "")
                params = tool_data.get("parameters", {})
                if tool_name:
                    return tool_name, params
            except json.JSONDecodeError:
                # Try to parse with regex if JSON parsing fails
                tool_name_match = re.search(r'"tool":\s*"([^"]+)"', tool_content)
                params_match = re.search(r'"parameters":\s*({.*})', tool_content)

                if tool_name_match:
                    tool_name = tool_name_match.group(1)
                    params = {}

                    if params_match:
                        try:
                            params = json.loads(params_match.group(1))
                        except json.JSONDecodeError:
                            # Extract parameters using regex if JSON parsing fails
                            param_matches = re.findall(
                                r'"([^"]+)":\s*(("[^"]*"|[\d.]+|\{.*?\}|\[.*?\]|true|false))',
                                params_match.group(1),
                            )
                            for param_name, param_value, _ in param_matches:
                                # Convert to appropriate types
                                if param_value.lower() == "true":
                                    params[param_name] = True
                                elif param_value.lower() == "false":
                                    params[param_name] = False
                                elif param_value.isdigit():
                                    params[param_name] = int(param_value)
                                elif param_value.replace(".", "", 1).isdigit():
                                    params[param_name] = float(param_value)
                                elif param_value.startswith('"') and param_value.endswith('"'):
                                    params[param_name] = param_value[1:-1]
                                else:
                                    params[param_name] = param_value

                    return tool_name, params

        # Try to extract JSON format action
        json_match = re.search(r"```(?:json)?\s*({.*?})\s*```", content, re.DOTALL)
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

        # Try to extract looser format
        looser_action_match = re.search(
            r"(?:use|call|execute)\s+the\s+(\w+)\s+tool", content, re.IGNORECASE
        )
        if looser_action_match:
            tool_name = looser_action_match.group(1)

            # Try to find parameters
            params: Dict[str, Any] = {}

            # Look for parameter patterns like "with parameter x=y"
            param_matches = re.findall(r"parameter\s+(\w+)\s*=\s*([^,\s]+)", content)
            for key, value in param_matches:
                # Convert to appropriate types
                if value.lower() == "true":
                    params[key] = True
                elif value.lower() == "false":
                    params[key] = False
                elif value.isdigit():
                    params[key] = int(value)
                elif value.replace(".", "", 1).isdigit():
                    params[key] = float(value)
                else:
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    params[key] = value

            if tool_name:
                return tool_name, params

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
                tools_description = tool_manager.get_formatted_tool_descriptions(
                    include_capabilities=True, include_examples=True
                )

        # Use the existing prompt templates
        react_prompt = get_tool_prompt_for_reasoning("react", tools_description)

        # Add error handling guidance
        error_handling = get_tool_error_handling_prompt()

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
                    return f"{combined}\n\n{error_handling}"

        # Just return the react prompt with tools if no base prompt
        return f"{react_prompt}\n\n{error_handling}" if react_prompt else ""

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
        return self._execute_tool_with_handling(agent, tool_name, tool_params, **kwargs)

    def parse_tool_calls(self, message: MessageProtocol, **kwargs: Any) -> List[Dict[str, Any]]:
        """
        Parse tool calls from a message.

        Args:
            message: Message to parse for tool calls
            **kwargs: Additional parameters

        Returns:
            List of tool calls with name and parameters
        """
        tool_calls = parse_message_for_tool_calls(message)

        # If no structured tool calls found, try to extract from text
        if not tool_calls and hasattr(message, "content") and message.content:
            action_info = self._extract_action_from_text(message.content)
            if action_info:
                tool_name, params = action_info
                tool_calls = [
                    {
                        "name": tool_name,
                        "parameters": params,
                        "id": f"extracted-{datetime.now().timestamp()}",
                    }
                ]

        return tool_calls

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
        return self._format_observation(tool_name, tool_result)

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
