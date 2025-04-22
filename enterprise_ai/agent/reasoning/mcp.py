"""
Model Context Protocol (MCP) reasoning framework for Enterprise AI agents.

This module implements the MCP reasoning pattern, which is specifically
designed to work with the Model Context Protocol server, enabling agents
to discover and utilize tools in a standardized, service-oriented manner.
"""

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
                            tools_description = tool_manager.get_formatted_tool_descriptions()

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
                    tools_description = tool_manager.get_formatted_tool_descriptions()

            # Format MCP system prompt
            mcp_prompt = self.format_system_prompt(
                agent, "", tools_description=tools_description, **kwargs
            )

            # Add system message at the beginning
            messages.insert(0, cast(MessageProtocol, Message.system_message(mcp_prompt)))

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
            # Use function calling if supported by the model
            function_calling = llm_provider.supports_feature("function_calling")

            # Get available tools if function calling is supported
            tools_schema = []
            if function_calling and hasattr(agent, "_tool_manager"):
                tool_manager = getattr(agent, "_tool_manager")
                if hasattr(tool_manager, "get_tool_schemas"):
                    # Run in event loop to get tool schemas
                    import asyncio

                    loop = asyncio.get_event_loop()
                    tools_schema = loop.run_until_complete(tool_manager.get_tool_schemas())

            # Add tools to kwargs if available
            if tools_schema:
                kwargs["tools"] = tools_schema

            response = llm_provider.complete(messages, **kwargs)
            return cast(MessageProtocol, response)
        except Exception as e:
            logger.error(f"Error in MCP reasoning for agent {agent.id}: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

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
                tools_description = tool_manager.get_formatted_tool_descriptions()

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

        while current_iteration < max_iterations:
            current_iteration += 1

            try:
                # Check if function calling is supported
                function_calling = llm_provider.supports_feature("function_calling")

                # Get available tools if function calling is supported
                tools_schema = []
                if function_calling and hasattr(agent, "_tool_manager"):
                    tool_manager = getattr(agent, "_tool_manager")
                    if hasattr(tool_manager, "get_tool_schemas"):
                        # Run in event loop to get tool schemas
                        import asyncio

                        loop = asyncio.get_event_loop()
                        tools_schema = loop.run_until_complete(tool_manager.get_tool_schemas())

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

                        # Execute tool
                        tool_result = self.handle_tool_execution(agent, tool_name, params, **kwargs)

                        # Format result as tool response
                        tool_response = format_tool_response_message(
                            tool_name, tool_result, tool_id
                        )
                        messages.append(cast(Message, tool_response))

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
        from enterprise_ai.mcp.utils import format_tool_descriptions

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
