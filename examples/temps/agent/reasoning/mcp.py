"""
Model Context Protocol (MCP) reasoning framework for Enterprise AI agents.

This module implements the MCP reasoning pattern, which is specifically
designed to work with the Model Context Protocol server, enabling agents
to discover and utilize tools in a standardized, service-oriented manner.
"""

from typing import Any, Dict, List, Optional, Set, Union, cast
import asyncio
import time

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
)
from enterprise_ai.mcp.client import ToolFilterStrategy
from enterprise_ai.mcp.utils import format_tool_descriptions, get_tool_capabilities

logger = get_logger("agent.reasoning.mcp")


class MCPReasoning(ToolBasedReasoning):
    """
    Model Context Protocol reasoning framework implementation.

    This framework is specifically designed to work with the MCP server,
    providing a standardized way for agents to discover and use tools
    exposed through the Model Context Protocol.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """
        Process input using the MCP approach.

        This method checks for tool calls in the agent's responses,
        executes them through the MCP server, and manages the interaction
        between the agent and the available tools.

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

        # Check for empty messages
        if not messages:
            logger.error("No messages provided to MCP reasoning")
            return cast(
                MessageProtocol, Message.assistant_message("I need some input to work with.")
            )

        # Ensure the system prompt includes MCP instructions
        has_mcp_prompt = False
        for idx, msg in enumerate(messages):
            if msg.role == "system" and msg.content:
                # Check if system prompt already has MCP instructions
                has_mcp_prompt = "MCP" in msg.content or "Model Context Protocol" in msg.content

                if not has_mcp_prompt:
                    # Replace with MCP prompt
                    tools_description = kwargs.get("tools_description", "")

                    if not tools_description and hasattr(agent, "_tool_manager"):
                        # Get tools description from agent's tool manager
                        tool_manager = getattr(agent, "_tool_manager")
                        if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                            tools_description = tool_manager.get_formatted_tool_descriptions(
                                include_capabilities=True, include_examples=True
                            )

                    # Format MCP system prompt
                    base_prompt = msg.content or ""
                    mcp_prompt = self.format_system_prompt(
                        agent, base_prompt, tools_description=tools_description, **kwargs
                    )

                    # Update the system message
                    messages[idx] = cast(MessageProtocol, Message.system_message(mcp_prompt))

                break

        # If no system message, add one with MCP instructions
        if not any(msg.role == "system" for msg in messages):
            tools_description = kwargs.get("tools_description", "")

            if not tools_description and hasattr(agent, "_tool_manager"):
                # Get tools description from agent's tool manager
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                    tools_description = tool_manager.get_formatted_tool_descriptions(
                        include_capabilities=True, include_examples=True
                    )

            # Format MCP system prompt
            mcp_prompt = self.format_system_prompt(
                agent, "", tools_description=tools_description, **kwargs
            )

            # Add system message at the beginning
            messages.insert(0, cast(MessageProtocol, Message.system_message(mcp_prompt)))

        # Process previous tool calls if present
        updated_messages = self._process_previous_tool_calls(agent, messages, **kwargs)

        # Generate response from LLM
        try:
            # Use function calling if supported by the model
            function_calling = False
            if hasattr(llm_provider, "supports_feature"):
                function_calling = llm_provider.supports_feature("function_calling")

            # Get available tools if function calling is supported
            tools_schema = []
            if function_calling and hasattr(agent, "_tool_manager"):
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_tool_schemas"):
                    # Run in event loop to get tool schemas
                    loop = self._get_event_loop()
                    tools_schema = loop.run_until_complete(
                        tool_manager.get_tool_schemas(filter_by_capabilities=True)
                    )

                    # Add more detailed information if capabilities were requested
                    if kwargs.get("include_tool_capabilities", True) and hasattr(
                        tool_manager, "capabilities"
                    ):
                        # Log the capabilities that will be used for filtering
                        logger.debug(
                            f"Agent {agent.id} has capabilities: {tool_manager.capabilities}"
                        )

            # Add tools to kwargs if available
            sanitized_kwargs = {k: v for k, v in kwargs.items() if not str(k) == "llm_provider"}
            if tools_schema:
                sanitized_kwargs["tools"] = tools_schema

            response = llm_provider.complete(updated_messages, **sanitized_kwargs)

            # Post-process the response for better tool handling if needed
            processed_response = self._post_process_response(response)
            return cast(MessageProtocol, processed_response)
        except Exception as e:
            logger.error(f"Error in MCP reasoning for agent {agent.id}: {e}", exc_info=True)
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

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
            Updated list of messages with tool results added
        """
        # Check if agent's response needs to be processed for tool calls
        updated_messages = messages.copy()
        last_assistant_idx = None

        # Find the last assistant message
        for idx, msg in enumerate(updated_messages):
            if msg.role == "assistant":
                last_assistant_idx = idx

        # Process tool calls if the last assistant message has them
        if last_assistant_idx is not None:
            last_assistant_msg = updated_messages[last_assistant_idx]
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
                        # Execute the tool with proper error handling
                        tool_result = self._execute_tool_with_handling(
                            agent, tool_name, params, **kwargs
                        )

                        # Format result as tool response with appropriate format
                        tool_response = format_tool_response_message(
                            tool_name,
                            tool_result,
                            tool_id,
                            response_format=kwargs.get("tool_response_format", "json"),
                        )
                        updated_messages.append(tool_response)

                        logger.info(f"Added tool result for {tool_name} to conversation")
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                        # Add error response
                        error_result = ToolFailure(
                            error=f"Error executing tool: {str(e)}",
                            metadata=ToolResultMetadata(tool_name=tool_name),
                            error_code="EXECUTION_ERROR",
                            retryable=True,
                        )
                        error_response = format_tool_response_message(
                            tool_name, error_result, tool_id
                        )
                        updated_messages.append(error_response)

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
                error="Agent does not have a tool manager", error_code="NO_TOOL_MANAGER"
            )

        tool_manager = getattr(agent, "_tool_manager")

        # Validate parameters against tool schema
        if hasattr(tool_manager, "get_tool") and kwargs.get("validate_params", True):
            tool = tool_manager.get_tool(tool_name)
            if tool and hasattr(tool, "parameters"):
                is_valid, error_msg = validate_tool_parameters(tool_name, params, tool.parameters)
                if not is_valid:
                    return ToolFailure(
                        error=f"Invalid parameters: {error_msg}",
                        error_code="INVALID_PARAMETERS",
                        retryable=True,
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
                error=f"Tool execution error: {str(e)}", error_code="EXECUTION_ERROR"
            )

    def _post_process_response(self, response: MessageProtocol) -> MessageProtocol:
        """
        Post-process an LLM response for better tool handling.

        Args:
            response: LLM response message

        Returns:
            Processed response message
        """
        if not response.content:
            return response

        # Check if response contains unstructured tool calls and format them
        # For example, convert natural language tool mentions to proper function calls
        return response

    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """
        Process a task using MCP reasoning.

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

        # Get tools description
        tools_description = kwargs.get("tools_description", "")

        if not tools_description and hasattr(agent, "_tool_manager"):
            # Get tools description from agent's tool manager
            tool_manager = getattr(agent, "_tool_manager")
            if hasattr(tool_manager, "get_formatted_tool_descriptions"):
                tools_description = tool_manager.get_formatted_tool_descriptions(
                    include_capabilities=True, include_examples=True
                )

        # Get MCP system prompt
        system_prompt = self.format_system_prompt(
            agent, "", tools_description=tools_description, **kwargs
        )

        # Create messages for the task
        messages: List[Message] = []
        messages.append(Message.system_message(system_prompt))
        messages.append(Message.user_message(f"Task: {task.description}"))

        # Process with LLM in a loop until task is completed or max iterations reached
        max_iterations = kwargs.get("max_iterations", 10)
        current_iteration = 0

        # Initialize task status
        task.status = TaskStatus.IN_PROGRESS

        # Store the start time for metrics
        start_time = time.time()

        while current_iteration < max_iterations:
            current_iteration += 1

            # Update task metadata with progress
            if not task.metadata:
                task.metadata = {}
            task.metadata["current_iteration"] = current_iteration
            task.metadata["max_iterations"] = max_iterations
            task.metadata["elapsed_time"] = time.time() - start_time

            try:
                # Check if function calling is supported
                function_calling = False
                if hasattr(llm_provider, "supports_feature"):
                    function_calling = llm_provider.supports_feature("function_calling")

                # Get available tools if function calling is supported
                tools_schema = []
                if function_calling and hasattr(agent, "_tool_manager"):
                    tool_manager = getattr(agent, "_tool_manager")
                    if hasattr(tool_manager, "get_tool_schemas"):
                        # Run in event loop to get tool schemas
                        loop = self._get_event_loop()
                        tools_schema = loop.run_until_complete(
                            tool_manager.get_tool_schemas(filter_by_capabilities=True)
                        )

                # Set up completion parameters
                complete_kwargs = {**kwargs}
                if tools_schema:
                    complete_kwargs["tools"] = tools_schema

                # Get response from LLM
                response = llm_provider.complete(
                    [cast(MessageProtocol, msg) for msg in messages], **complete_kwargs
                )
                messages.append(cast(Message, response))

                # Check for task completion indication
                if self._is_task_completed(response.content or ""):
                    break

                # Check for tool calls
                tool_calls = parse_message_for_tool_calls(response)

                if not tool_calls:
                    # No tool calls, add a prompt to continue
                    messages.append(
                        Message.user_message(
                            "Continue working on this task. Consider using available tools if they would help."
                        )
                    )
                else:
                    # Process each tool call
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name", "")
                        params = tool_call.get("parameters", {})
                        tool_id = tool_call.get("id")

                        if not tool_name:
                            continue

                        # Execute tool with enhanced error handling
                        tool_result = self._execute_tool_with_handling(
                            agent, tool_name, params, **kwargs
                        )

                        # Format result as tool response
                        tool_response = format_tool_response_message(
                            tool_name,
                            tool_result,
                            tool_id,
                            response_format=kwargs.get("tool_response_format", "json"),
                        )
                        messages.append(cast(Message, tool_response))

            except Exception as e:
                logger.error(f"Error processing task for agent {agent.id}: {e}", exc_info=True)
                task.status = TaskStatus.FAILED
                task.metadata["error"] = str(e)
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
        task.metadata["execution_time"] = time.time() - start_time

        # Mark task as completed
        task.status = TaskStatus.COMPLETED

        return task.status

    def _is_task_completed(self, content: str) -> bool:
        """
        Check if task completion is indicated in the content.

        Args:
            content: Message content to check

        Returns:
            True if task completion is indicated, False otherwise
        """
        completion_indicators = [
            "task completed",
            "completed the task",
            "finished the task",
            "task is complete",
            "here is the final result",
            "in conclusion",
            "here's the solution",
            "here is the solution",
            "final answer:",
            "final response:",
        ]

        content_lower = content.lower()
        return any(indicator in content_lower for indicator in completion_indicators)

    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """
        Format the system prompt for MCP reasoning.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Get tools description
        tools_description = kwargs.get("tools_description", "")
        additional_instructions = kwargs.get("additional_mcp_instructions", "")

        # Try to use the MCP prompt template
        mcp_prompt = format_prompt(
            "system.mcp",
            tools_description=tools_description,
            additional_mcp_instructions=additional_instructions,
        )

        if not mcp_prompt:
            # Fallback to get_tool_prompt_for_reasoning
            mcp_prompt = get_tool_prompt_for_reasoning("mcp", tools_description)

        # Combine with base prompt if provided
        if base_prompt:
            base_formatted = format_prompt("system.base", additional_instructions=base_prompt)
            if base_formatted:
                return f"{base_formatted}\n\n{mcp_prompt}"

        return mcp_prompt

    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """
        Format instructions for tool usage with MCP.

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
        additional_instructions = kwargs.get("additional_mcp_instructions", "")

        instructions = format_prompt(
            "system.mcp",
            tools_description=tools_description,
            additional_mcp_instructions=additional_instructions,
        )

        # Fallback to a simple format if the template is not available
        if not instructions:
            logger.warning("MCP prompt template not found, using fallback")
            return get_tool_prompt_for_reasoning("mcp", tools_description)

        return instructions

    def handle_tool_execution(
        self, agent: AgentProtocol, tool_name: str, tool_params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """
        Handle the execution of a tool through the MCP server.

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
        format_type = kwargs.get("response_format", "json")

        if format_type == "react":
            # ReAct format (Observation: result)
            if tool_result.error:
                return f"Observation: Error executing {tool_name}: {tool_result.error}"
            else:
                # Format for readability
                if isinstance(tool_result.output, (dict, list)):
                    import json

                    try:
                        formatted_output = json.dumps(tool_result.output, indent=2)
                        return f"Observation: {formatted_output}"
                    except Exception:
                        return f"Observation: {tool_result.output}"
                else:
                    return f"Observation: {tool_result.output}"
        else:
            # Default JSON format
            if tool_result.error:
                return f"Error executing {tool_name}: {tool_result.error}"
            else:
                return f"Result from {tool_name}: {tool_result.output or 'Success'}"

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
        return "mcp"

    @property
    def description(self) -> str:
        """
        Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        return "Model Context Protocol reasoning framework for standardized tool integration."

    @property
    def requires_tools(self) -> bool:
        """
        Check if this framework requires tools to function.

        Returns:
            True if tools are required, False otherwise
        """
        return True
