"""
Chain of Thought (CoT) reasoning framework for Enterprise AI agents.

This module implements the Chain of Thought reasoning pattern, which
encourages agents to break down complex problems into steps and
thoroughly explain their reasoning process before reaching a conclusion.
"""

import re
import json
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Union, cast, Tuple

from enterprise_ai.agent.core.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.reasoning.base import ReasoningFramework, ToolBasedReasoning
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.tool.core.result import ToolResult, ToolFailure, ToolResultMetadata
from enterprise_ai.prompt import get_prompt, format_prompt, combine_prompts
from enterprise_ai.agent.tools.tool_integration import (
    parse_message_for_tool_calls,
    format_tool_response_message,
    get_tool_prompt_for_reasoning,
    validate_tool_parameters,
    get_tool_error_handling_prompt,
)

logger = get_logger("agent.reasoning.cot")


class ChainOfThoughtReasoning(ReasoningFramework):
    """
    Chain of Thought reasoning framework implementation.

    This framework encourages agents to clearly articulate their
    step-by-step reasoning process when solving problems, increasing
    the quality of complex reasoning and problem-solving.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using the Chain of Thought approach.

        This method prompts the LLM to use explicit reasoning when
        generating a response, breaking down the problem into steps.

        Args:
            agent: The agent using this reasoning framework
            messages: List of messages to process
            **kwargs: Additional parameters including LLM provider

        Returns:
            Response message
        """
        # Extract LLM provider and remove it from kwargs to avoid serialization issues
        llm_provider = kwargs.pop("llm_provider", None)
        if not llm_provider:
            logger.error(f"No LLM provider available for agent {agent.id}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    "I'm unable to process your request due to a configuration issue."
                ),
            )

        # Check for empty messages
        if not messages:
            logger.error("No messages provided to CoT reasoning")
            return cast(
                MessageProtocol, Message.assistant_message("I need some input to work with.")
            )

        # Ensure the system prompt includes CoT instructions
        has_cot_prompt = False
        for msg in messages:
            if msg.role == "system" and msg.content:
                # Check if system prompt already has CoT instructions
                has_cot_prompt = self._has_cot_instructions(msg.content)
                break

        if not has_cot_prompt:
            # Replace or add CoT system prompt
            cot_prompt = self._get_cot_system_prompt(agent, **kwargs)

            # Create a new message list with the CoT prompt
            new_messages: List[MessageProtocol] = []
            system_added = False

            for msg in messages:
                if msg.role == "system":
                    # Replace existing system message
                    new_messages.append(cast(MessageProtocol, Message.system_message(cot_prompt)))
                    system_added = True
                else:
                    new_messages.append(msg)

            # Add system message if none exists
            if not system_added:
                new_messages.insert(0, cast(MessageProtocol, Message.system_message(cot_prompt)))

            messages = new_messages

        # Process the last message to see if we need to add a CoT prompt
        last_msg = messages[-1]
        if last_msg.role == "user" and not self._has_explicit_cot_request(last_msg.content or ""):
            # Append a nudge to think step by step if not already present
            user_content = last_msg.content or ""
            if not user_content.endswith(("?", ".", "!")):
                user_content += "."

            cot_nudge = f"{user_content} Please think through this step by step."
            # Replace the last message with the nudged version
            messages[-1] = cast(MessageProtocol, Message.user_message(cot_nudge))

        # Generate response from LLM
        try:
            # Make sure to pass the llm_provider back for the actual LLM call
            response = llm_provider.complete(messages, **kwargs)

            # Ensure response follows CoT format
            if response.content and not self._is_cot_format(response.content):
                formatted_content = self._format_as_cot(response.content)
                response = cast(
                    MessageProtocol,
                    Message.assistant_message(formatted_content, metadata=response.metadata),
                )

            return cast(MessageProtocol, response)
        except Exception as e:
            logger.error(f"Error in CoT reasoning for agent {agent.id}: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def _has_cot_instructions(self, prompt: str) -> bool:
        """
        Check if a prompt contains Chain of Thought instructions.

        Args:
            prompt: Prompt to check

        Returns:
            True if prompt contains CoT instructions, False otherwise
        """
        cot_indicators = [
            "step by step",
            "chain of thought",
            "think through",
            "break down",
            "reasoning process",
            "think step by step",
        ]

        prompt_lower = prompt.lower()
        return any(indicator in prompt_lower for indicator in cot_indicators)

    def _has_explicit_cot_request(self, message: str) -> bool:
        """
        Check if a message explicitly requests Chain of Thought reasoning.

        Args:
            message: Message to check

        Returns:
            True if message requests CoT reasoning, False otherwise
        """
        cot_requests = [
            "step by step",
            "explain your reasoning",
            "explain your thinking",
            "break it down",
            "show your work",
            "walk me through",
        ]

        message_lower = message.lower()
        return any(request in message_lower for request in cot_requests)

    def _is_cot_format(self, content: str) -> bool:
        """
        Check if content follows Chain of Thought format.

        Args:
            content: Message content to check

        Returns:
            True if content follows CoT format, False otherwise
        """
        # Look for explicit reasoning steps
        cot_patterns = [
            r"Step\s*\d+",
            r"First,",
            r"Second,",
            r"Third,",
            r"Next,",
            r"Finally,",
            r"Let's think",
            r"Let me think",
            r"Thinking:",
            r"My reasoning:",
        ]

        for pattern in cot_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        # Check for substantial explanation (multiple paragraphs)
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) >= 2:
            return True

        return False

    def _format_as_cot(self, content: str) -> str:
        """
        Format content to follow Chain of Thought pattern.

        Args:
            content: Content to format

        Returns:
            Content formatted in CoT pattern
        """
        # If content already has CoT elements, don't reformat
        if self._is_cot_format(content):
            return content

        # For short responses, add structure
        if len(content.strip().split("\n")) <= 2:
            return f"Thinking: Let me analyze this carefully.\n\n{content}\n\nTherefore, my answer is: {content}"

        # For longer responses, add minimal structure
        return f"Let me think through this step by step:\n\n{content}"

    def _get_cot_system_prompt(self, agent: AgentProtocol, **kwargs: Any) -> str:
        """
        Get the system prompt for Chain of Thought reasoning.

        Args:
            agent: The agent using this reasoning framework
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Use the existing prompt templates
        base_prompt = kwargs.get("base_prompt", "")
        additional_instructions = kwargs.get("additional_cot_instructions", "")

        # Try to format using existing templates
        cot_prompt = format_prompt(
            "system.cot", additional_cot_instructions=additional_instructions
        )

        if not cot_prompt:
            logger.warning("Failed to load Chain of Thought prompt template")
            cot_prompt = "Please think step by step."

        # If we have a base prompt, combine them
        if base_prompt:
            base_formatted = format_prompt("system.base", additional_instructions=base_prompt)
            if base_formatted:
                return f"{base_formatted}\n\n{cot_prompt}"

        return cot_prompt

    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """
        Process a task using Chain of Thought reasoning.

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

        # Get CoT system prompt
        system_prompt = self._get_cot_system_prompt(agent, **kwargs)

        # Create messages for the task
        messages: List[Message] = []
        messages.append(Message.system_message(system_prompt))
        messages.append(
            Message.user_message(
                f"Task: {task.description}\n\nPlease think through this step by step."
            )
        )

        # Process with LLM
        try:
            response = llm_provider.complete([cast(MessageProtocol, msg) for msg in messages])

            # Store response in task metadata
            if not task.metadata:
                task.metadata = {}
            task.metadata["response"] = response.content

            task.status = TaskStatus.COMPLETED
            return task.status
        except Exception as e:
            logger.error(f"Error processing task for agent {agent.id}: {e}")
            task.status = TaskStatus.FAILED
            if not task.metadata:
                task.metadata = {}
            task.metadata["error"] = str(e)
            return task.status

    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """
        Format the system prompt for Chain of Thought reasoning.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        return self._get_cot_system_prompt(agent, base_prompt=base_prompt, **kwargs)

    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """
        Format instructions for tool usage with Chain of Thought.

        Args:
            agent: The agent using this reasoning framework
            tools: List of available tools
            **kwargs: Additional parameters

        Returns:
            Formatted tool instructions
        """
        # Pull from system.tool_cot if it exists
        instructions = format_prompt("system.tool_cot")
        if instructions:
            return instructions

        # Return a minimal prompt otherwise
        return "When appropriate, you can use the tools provided to help solve problems. Remember to always show your reasoning process first."

    def handle_tool_execution(
        self, agent: AgentProtocol, tool_name: str, tool_params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """
        Handle the execution of a tool (not focus of CoT).

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            tool_params: Parameters for tool execution
            **kwargs: Additional parameters

        Returns:
            Tool execution result
        """
        # The basic CoT implementation doesn't focus on tools
        # This is included for API compatibility
        return ToolFailure(
            error="Tool execution is not a primary focus of the CoT reasoning framework.",
            error_code="UNSUPPORTED_OPERATION",
            metadata=ToolResultMetadata(tool_name=tool_name),
        )

    def supports_function_calling(self) -> bool:
        """
        Check if this framework supports function calling.

        Returns:
            True if function calling is supported, False otherwise
        """
        return False  # Basic CoT doesn't focus on function calling

    @property
    def name(self) -> str:
        """
        Get the name of this reasoning framework.

        Returns:
            Framework name
        """
        return "cot"

    @property
    def description(self) -> str:
        """
        Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        return "Chain of Thought reasoning framework that encourages step-by-step thinking and explanation."

    @property
    def requires_tools(self) -> bool:
        """
        Check if this framework requires tools to function.

        Returns:
            True if tools are required, False otherwise
        """
        return False  # CoT can work without tools


class ToolAugmentedCoT(ChainOfThoughtReasoning, ToolBasedReasoning):
    """
    Tool-augmented Chain of Thought reasoning framework.

    This extension of CoT supports tools while maintaining the
    emphasis on step-by-step reasoning.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using the Tool-augmented Chain of Thought approach.

        This method combines CoT reasoning with tool capabilities.

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
            logger.error("No messages provided to Tool-augmented CoT reasoning")
            return cast(
                MessageProtocol, Message.assistant_message("I need some input to work with.")
            )

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
                        # Validate parameters if possible
                        is_valid, error_msg = self.validate_tool_params(agent, tool_name, params)

                        if not is_valid:
                            # Add parameter validation error
                            tool_result = ToolFailure(
                                error=f"Invalid parameters: {error_msg}",
                                error_code="INVALID_PARAMETERS",
                                retryable=True,
                                metadata=ToolResultMetadata(tool_name=tool_name),
                            )

                            tool_response = format_tool_response_message(
                                tool_name, tool_result, tool_id
                            )
                            messages.append(tool_response)
                            continue

                        # Execute the tool with timeout and retries
                        # Use the event loop to run the async method synchronously
                        loop = self._get_event_loop()
                        tool_result = loop.run_until_complete(
                            self._execute_tool_with_retries(
                                agent,
                                tool_name,
                                params,
                                timeout=kwargs.get("timeout"),
                                max_retries=kwargs.get("max_retries", 2),
                                retry_delay=kwargs.get("retry_delay", 1.0),
                            )
                        )

                        # Format result as tool response
                        tool_response = format_tool_response_message(
                            tool_name, tool_result, tool_id
                        )
                        messages.append(tool_response)

                        logger.info(f"Added tool result for {tool_name} to conversation")
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}")
                        # Add error response
                        error_result = ToolFailure(
                            error=f"Error executing tool: {str(e)}",
                            error_code="EXECUTION_ERROR",
                            metadata=ToolResultMetadata(tool_name=tool_name),
                        )

                        error_response = format_tool_response_message(
                            tool_name, error_result, tool_id
                        )
                        messages.append(error_response)

        # Ensure the system prompt includes CoT and tool instructions
        has_cot_tool_prompt = False
        for idx, msg in enumerate(messages):
            if msg.role == "system" and msg.content:
                # Check if system prompt already has CoT and tool instructions
                has_cot_tool_prompt = (
                    self._has_cot_instructions(msg.content) and "tool" in msg.content.lower()
                )

                if not has_cot_tool_prompt:
                    # Replace with combined prompt
                    tools_description = kwargs.get("tools_description", "")

                    if not tools_description and hasattr(agent, "_tool_manager"):
                        # Get tools description from agent's tool manager
                        tool_manager = getattr(agent, "_tool_manager")
                        if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                            tools_description = tool_manager.get_formatted_tool_descriptions(
                                include_capabilities=True,  # Include capability info
                                include_examples=True,  # Include usage examples
                            )

                    # Create combined prompt
                    cot_tool_prompt = self._get_cot_tool_system_prompt(
                        agent, tools_description=tools_description, **kwargs
                    )

                    # Update the system message
                    messages[idx] = cast(MessageProtocol, Message.system_message(cot_tool_prompt))

                break

        # If no system message, add one with CoT and tool instructions
        if not any(msg.role == "system" for msg in messages):
            tools_description = kwargs.get("tools_description", "")

            if not tools_description and hasattr(agent, "_tool_manager"):
                # Get tools description from agent's tool manager
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                    tools_description = tool_manager.get_formatted_tool_descriptions(
                        include_capabilities=True, include_examples=True
                    )

            # Create combined prompt
            cot_tool_prompt = self._get_cot_tool_system_prompt(
                agent, tools_description=tools_description, **kwargs
            )

            # Add system message at the beginning
            messages.insert(0, cast(MessageProtocol, Message.system_message(cot_tool_prompt)))

        # Generate response from LLM
        try:
            # Support function calling if the model supports it
            sanitized_kwargs = {k: v for k, v in kwargs.items() if k != "llm_provider"}

            # Set up function calling if model supports it
            function_calling = False
            if hasattr(llm_provider, "supports_feature"):
                function_calling = llm_provider.supports_feature("function_calling")

            if function_calling and hasattr(agent, "_tool_manager"):
                # Get available tools
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_tool_schemas"):
                    # Use async event loop
                    loop = self._get_event_loop()
                    tools_schema = loop.run_until_complete(
                        tool_manager.get_tool_schemas(filter_by_capabilities=True)
                    )
                    if tools_schema:
                        sanitized_kwargs["tools"] = tools_schema

            # Generate response
            response = llm_provider.complete(messages, **sanitized_kwargs)

            # Ensure response follows CoT format if needed
            if response.content and not self._is_cot_format(response.content):
                formatted_content = self._format_as_cot(response.content)
                response = cast(
                    MessageProtocol,
                    Message.assistant_message(formatted_content, metadata=response.metadata),
                )

            return cast(MessageProtocol, response)
        except Exception as e:
            logger.error(f"Error in Tool-augmented CoT reasoning for agent {agent.id}: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for async operations.

        Returns:
            An asyncio event loop
        """
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop exists in this thread, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def _execute_tool_with_retries(
        self,
        agent: AgentProtocol,
        tool_name: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> ToolResult:
        """Execute a tool with retry mechanism.

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            params: Parameters for the tool
            timeout: Optional timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Base delay between retries (doubles each attempt)

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

        # Try execution with retries
        attempt = 0
        last_error = None
        delay = retry_delay

        while attempt <= max_retries:
            try:
                # Add delay for retries (not on first attempt)
                if attempt > 0:
                    logger.info(f"Retrying tool {tool_name} (attempt {attempt}/{max_retries})")
                    await asyncio.sleep(delay)
                    # Exponential backoff
                    delay *= 2

                # Execute tool
                result = await tool_manager.execute_tool(tool_name, timeout=timeout, **params)

                # If successful or permanent error, return result
                if not result.error or (
                    isinstance(result, ToolFailure)
                    and hasattr(result, "retryable")
                    and not result.retryable
                ):
                    return result

                # For temporary errors, retry if attempts remain
                last_error = result.error
                attempt += 1

                # Check if we've used all retries
                if attempt > max_retries:
                    return result

            except Exception as e:
                logger.error(f"Error executing tool {tool_name}: {e}")
                last_error = str(e)
                attempt += 1

                # If out of retries, return error
                if attempt > max_retries:
                    return ToolFailure(
                        error=f"Tool execution failed after {max_retries} attempts: {last_error}",
                        error_code="MAX_RETRIES_EXCEEDED",
                        metadata=ToolResultMetadata(tool_name=tool_name),
                    )

        # We should only get here if all retries failed
        return ToolFailure(
            error=f"Tool execution failed after {max_retries} attempts: {last_error}",
            error_code="MAX_RETRIES_EXCEEDED",
            metadata=ToolResultMetadata(tool_name=tool_name),
        )

    def _get_cot_tool_system_prompt(
        self, agent: AgentProtocol, tools_description: str = "", **kwargs: Any
    ) -> str:
        """
        Get the system prompt for Tool-augmented Chain of Thought reasoning.

        Args:
            agent: The agent using this reasoning framework
            tools_description: Description of available tools
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Get base prompt
        base_prompt = kwargs.get("base_prompt", "")

        # Try using prompt templates first
        # Combine cot and tool prompts
        try:
            combined_prompt = combine_prompts(
                ["system.cot", "system.with_tools"],
                additional_cot_instructions=kwargs.get("additional_cot_instructions", ""),
                tools_description=tools_description,
            )

            if combined_prompt:
                if base_prompt:
                    base_formatted = format_prompt(
                        "system.base", additional_instructions=base_prompt
                    )
                    if base_formatted:
                        return f"{base_formatted}\n\n{combined_prompt}"
                return combined_prompt
        except Exception as e:
            logger.error(f"Error combining prompts: {e}")

        # Add error handling guidance
        error_handling = get_tool_error_handling_prompt()

        # Fallback to get_tool_prompt_for_reasoning which uses template system
        tool_prompt = get_tool_prompt_for_reasoning("cot", tools_description)
        return f"{tool_prompt}\n\n{error_handling}"

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
            return ToolFailure(
                error="Agent does not have a tool manager",
                error_code="NO_TOOL_MANAGER",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )

        tool_manager = getattr(agent, "_tool_manager")

        try:
            # Execute tool with async handling
            loop = self._get_event_loop()
            start_time = datetime.now()

            # Support timeout if provided
            timeout = kwargs.get("timeout")
            if timeout:
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            tool_manager.execute_tool(tool_name, **tool_params), timeout=timeout
                        )
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Tool {tool_name} execution timed out")
                    return ToolFailure(
                        error=f"Tool execution timed out after {timeout} seconds",
                        error_code="TIMEOUT",
                        retryable=True,
                        metadata=ToolResultMetadata(tool_name=tool_name),
                    )
            else:
                result = loop.run_until_complete(
                    tool_manager.execute_tool(tool_name, **tool_params)
                )

            # Track execution time
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Update result metadata
            if not isinstance(result, ToolResult):
                result = ToolResult(
                    output=result,
                    metadata=ToolResultMetadata(
                        tool_name=tool_name, execution_time_ms=execution_time
                    ),
                )
            elif result.metadata:
                result.metadata.tool_name = tool_name
                result.metadata.execution_time_ms = execution_time
            else:
                result.metadata = ToolResultMetadata(
                    tool_name=tool_name, execution_time_ms=execution_time
                )

            logger.info(f"Executed tool {tool_name} for agent {agent.id}")
            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return ToolFailure(
                error=f"Tool execution error: {str(e)}",
                error_code="EXECUTION_ERROR",
                metadata=ToolResultMetadata(tool_name=tool_name),
            )

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
        response_format = kwargs.get("response_format", "json")
        include_metadata = kwargs.get("include_metadata", False)

        if response_format == "markdown":
            # Format as markdown with clearly visible sections
            if tool_result.error:
                result = f"### ❌ Error using {tool_name}\n\n{tool_result.error}"

                # Add suggestions if available
                if isinstance(tool_result, ToolFailure) and tool_result.suggestions:
                    result += "\n\n**Suggestions:**\n"
                    for suggestion in tool_result.suggestions:
                        result += f"- {suggestion}\n"
            else:
                result = f"### ✅ Result from {tool_name}\n\n"

                # Format based on output type
                if isinstance(tool_result.output, (dict, list)):
                    try:
                        result += "```json\n"
                        result += json.dumps(tool_result.output, indent=2)
                        result += "\n```"
                    except:
                        result += f"{tool_result.output}"
                else:
                    result += f"{tool_result.output}"

            # Add metadata if requested
            if include_metadata and tool_result.metadata and tool_result.metadata.execution_time_ms:
                result += f"\n\n*Execution time: {tool_result.metadata.execution_time_ms:.2f}ms*"

            return result

        elif response_format == "react":
            # ReAct format for observation
            if tool_result.error:
                return f"Observation: Error executing {tool_name}: {tool_result.error}"
            else:
                # Format based on output type
                if isinstance(tool_result.output, (dict, list)):
                    try:
                        formatted_output = json.dumps(tool_result.output, indent=2)
                        return f"Observation: {formatted_output}"
                    except:
                        return f"Observation: {tool_result.output}"
                else:
                    return f"Observation: {tool_result.output}"
        else:
            # Default JSON format
            if tool_result.error:
                return f"Error executing {tool_name}: {tool_result.error}"
            else:
                return f"Result from {tool_name}: {tool_result.output or 'Success'}"

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
        return "tool_cot"

    @property
    def description(self) -> str:
        """
        Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        return "Tool-augmented Chain of Thought reasoning framework that combines step-by-step thinking with tool capabilities."

    @property
    def requires_tools(self) -> bool:
        """
        Check if this framework requires tools to function.

        Returns:
            True if tools are required, False otherwise
        """
        return True
