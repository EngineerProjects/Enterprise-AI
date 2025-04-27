"""
Software Engineering (SWE) reasoning framework for Enterprise AI agents.

This module implements the Software Engineering reasoning pattern, which
focuses on systematic software development approaches including planning,
implementation, testing, and debugging of code.
"""

import re
from typing import Any, Dict, List, Optional, Set, Union, cast

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

logger = get_logger("agent.reasoning.swe")


class SoftwareEngineeringReasoning(ToolBasedReasoning):
    """
    Software Engineering reasoning framework implementation.

    This framework guides agents through structured software development
    processes, including requirements analysis, design, implementation,
    testing, and debugging, with a focus on code quality and systematic
    problem solving.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using the Software Engineering approach.

        This method implements a structured development process with
        methodical reasoning about software tasks and tool usage.

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
            logger.error("No messages provided to SWE reasoning")
            return cast(
                MessageProtocol, Message.assistant_message("I need some input to work with.")
            )

        # Ensure the system prompt includes SWE instructions
        has_swe_prompt = False
        for idx, msg in enumerate(messages):
            if msg.role == "system" and msg.content:
                # Check if system prompt already has SWE instructions
                has_swe_prompt = self._has_swe_instructions(msg.content)

                if not has_swe_prompt:
                    # Replace with SWE prompt
                    tools_description = kwargs.get("tools_description", "")

                    if not tools_description and hasattr(agent, "_tool_manager"):
                        # Get tools description from agent's tool manager
                        tool_manager = getattr(agent, "_tool_manager")
                        if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                            tools_description = tool_manager.get_formatted_tool_descriptions()

                    # Format SWE system prompt
                    swe_prompt = self.format_system_prompt(
                        agent, msg.content or "", tools_description=tools_description, **kwargs
                    )

                    # Update the system message
                    messages[idx] = cast(MessageProtocol, Message.system_message(swe_prompt))

                break

        # If no system message, add one with SWE instructions
        if not any(msg.role == "system" for msg in messages):
            tools_description = kwargs.get("tools_description", "")

            if not tools_description and hasattr(agent, "_tool_manager"):
                # Get tools description from agent's tool manager
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                    tools_description = tool_manager.get_formatted_tool_descriptions()

            # Format SWE system prompt
            swe_prompt = self.format_system_prompt(
                agent, "", tools_description=tools_description, **kwargs
            )

            # Add system message at the beginning
            messages.insert(0, cast(MessageProtocol, Message.system_message(swe_prompt)))

        # Check if agent's response needs to be processed for tool calls
        last_assistant_msg = None

        for msg in reversed(messages):
            if msg.role == "assistant":
                last_assistant_msg = msg
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
                    tool_id = tool_call.get("id")

                    if not tool_name:
                        continue

                    try:
                        # Execute the tool
                        tool_result = self.handle_tool_execution(agent, tool_name, params, **kwargs)

                        # Format result as tool response
                        tool_response = format_tool_response_message(
                            tool_name, tool_result, tool_id
                        )
                        messages.append(tool_response)

                        logger.info(f"Added tool result for {tool_name} to conversation")
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        # Add error response
                        error_response = format_tool_response_message(
                            tool_name, ToolResult(error=f"Error executing tool: {str(e)}"), tool_id
                        )
                        messages.append(error_response)

        # Generate response from LLM
        try:
            # Remove any provider reference that might have been added back
            sanitized_kwargs = {k: v for k, v in kwargs.items() if not str(k) == "llm_provider"}
            response = llm_provider.complete(messages, **sanitized_kwargs)
            return cast(MessageProtocol, response)
        except Exception as e:
            logger.error(f"Error in SWE reasoning for agent {agent.id}: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def _has_swe_instructions(self, prompt: str) -> bool:
        """
        Check if a prompt contains Software Engineering instructions.

        Args:
            prompt: Prompt to check

        Returns:
            True if prompt contains SWE instructions, False otherwise
        """
        swe_indicators = [
            "software engineering",
            "code quality",
            "requirements analysis",
            "design patterns",
            "implementation",
            "testing",
            "debugging",
            "refactoring",
        ]

        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in swe_indicators)

    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """
        Process a task using Software Engineering reasoning.

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

        # Determine if this is a software development task
        is_dev_task = self._is_development_task(task.description)

        # Get tools description
        tools_description = kwargs.get("tools_description", "")

        if not tools_description and hasattr(agent, "_tool_manager"):
            # Get tools description from agent's tool manager
            tool_manager = getattr(agent, "_tool_manager")
            if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                tools_description = tool_manager.get_formatted_tool_descriptions()

        # Get SWE system prompt
        system_prompt = self.format_system_prompt(
            agent, "", tools_description=tools_description, **kwargs
        )

        # Create messages for the task
        messages: List[Message] = []
        messages.append(Message.system_message(system_prompt))

        # For development tasks, add structure to the task
        if is_dev_task:
            messages.append(
                Message.user_message(
                    f"Software Development Task: {task.description}\n\n"
                    f"Please follow a systematic software engineering approach:\n"
                    f"1. Analyze requirements\n"
                    f"2. Design a solution\n"
                    f"3. Implement the code\n"
                    f"4. Test your implementation\n"
                    f"5. Refactor as needed"
                )
            )
        else:
            messages.append(Message.user_message(f"Task: {task.description}"))

        # Process with LLM in a loop until task is completed or max iterations reached
        max_iterations = kwargs.get("max_iterations", 10)
        current_iteration = 0

        while current_iteration < max_iterations:
            current_iteration += 1

            try:
                # Get response from LLM
                response = llm_provider.complete([cast(MessageProtocol, msg) for msg in messages])
                messages.append(cast(Message, response))

                # Check for tool calls
                tool_calls = parse_message_for_tool_calls(response)

                if not tool_calls:
                    # Check if task appears to be complete
                    if self._is_task_completed(response.content or "", is_dev_task):
                        break

                    # No tool calls, add a prompt to encourage tool use if this is a dev task
                    if is_dev_task and current_iteration == 1:
                        messages.append(
                            Message.user_message(
                                "Consider using appropriate development tools to help with this task. "
                                "For example, you might need to write, run, or debug code."
                            )
                        )
                    else:
                        # General follow-up for non-tool responses
                        messages.append(
                            Message.user_message(
                                "Continue working on this task. Let me know if you need any clarification."
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

                        # Format result as tool response
                        tool_response = format_tool_response_message(tool_name, tool_result)
                        tool_response_message = cast(Message, tool_response)
                        messages.append(tool_response_message)

            except Exception as e:
                logger.error(f"Error processing task for agent {agent.id}: {e}")
                task.status = TaskStatus.FAILED
                return task.status

        # Store the final response in task metadata
        if not task.metadata:
            task.metadata = {}

        # Extract the final result from messages
        final_response = ""
        for msg in reversed(messages):
            if msg.role == "assistant":
                final_response = msg.content or ""
                break

        task.metadata["response"] = final_response
        task.metadata["iterations"] = current_iteration
        task.status = TaskStatus.COMPLETED

        return task.status

    def _is_development_task(self, description: str) -> bool:
        """
        Determine if a task is related to software development.

        Args:
            description: Task description

        Returns:
            True if it's a development task, False otherwise
        """
        dev_keywords = [
            "code",
            "program",
            "develop",
            "implement",
            "function",
            "class",
            "method",
            "script",
            "algorithm",
            "debug",
            "fix",
            "refactor",
            "optimiz",
            "test",
            "software",
        ]

        description_lower = description.lower()
        return any(keyword in description_lower for keyword in dev_keywords)

    def _is_task_completed(self, content: str, is_dev_task: bool) -> bool:
        """
        Check if task completion is indicated in the content.

        Args:
            content: Message content to check
            is_dev_task: Whether this is a development task

        Returns:
            True if task completion is indicated, False otherwise
        """
        # For dev tasks, look for code and completion statements
        if is_dev_task:
            has_code = bool(re.search(r"```\w*\n[\s\S]+?\n```", content))
            completion_patterns = [
                r"finished implementing",
                r"code is complete",
                r"implementation is complete",
                r"the solution is",
                r"final implementation",
            ]
            return has_code and any(
                re.search(pattern, content, re.IGNORECASE) for pattern in completion_patterns
            )
        else:
            # For non-dev tasks, look for general completion indicators
            completion_patterns = [
                r"task completed",
                r"finished the task",
                r"solution is ready",
                r"the answer is",
                r"in conclusion",
            ]
            return any(
                re.search(pattern, content, re.IGNORECASE) for pattern in completion_patterns
            )

    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """
        Format the system prompt for Software Engineering reasoning.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Get tools description
        tools_description = kwargs.get("tools_description", "")
        additional_instructions = kwargs.get("additional_swe_instructions", "")

        # Try to use the SWE prompt template
        swe_prompt = format_prompt(
            "system.swe",
            tools_description=tools_description,
            additional_swe_instructions=additional_instructions,
        )

        if not swe_prompt:
            # Fallback to get_tool_prompt_for_reasoning
            swe_prompt = get_tool_prompt_for_reasoning("swe", tools_description)

        # Combine with base prompt if provided
        if base_prompt:
            base_formatted = format_prompt("system.base", additional_instructions=base_prompt)
            if base_formatted:
                return f"{base_formatted}\n\n{swe_prompt}"

        return swe_prompt

    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """
        Format instructions for tool usage with SWE.

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
        additional_instructions = kwargs.get("additional_swe_instructions", "")

        instructions = format_prompt(
            "system.swe",
            tools_description=tools_description,
            additional_swe_instructions=additional_instructions,
        )

        # Fallback to a simple format if the template is not available
        if not instructions:
            logger.warning("SWE prompt template not found, using fallback")
            return get_tool_prompt_for_reasoning("swe", tools_description)

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
            return f"Error using {tool_name}: {tool_result.error}"
        else:
            # For code execution results, format nicely
            if tool_name in ["execute_code", "run_code", "execute_python"]:
                return f"Execution result:\n```\n{tool_result.output or 'No output'}\n```"
            # For file operations, be concise
            elif tool_name in ["read_file", "write_file", "list_files"]:
                return f"File operation result: {tool_result.output}"
            # Default formatting
            else:
                return f"Tool {tool_name} result: {tool_result.output or 'Success'}"

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
        return "swe"

    @property
    def description(self) -> str:
        """
        Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        return "Software Engineering reasoning framework for systematic development tasks."

    @property
    def requires_tools(self) -> bool:
        """
        Check if this framework requires tools to function.

        Returns:
            True if tools are required, False otherwise
        """
        return True
