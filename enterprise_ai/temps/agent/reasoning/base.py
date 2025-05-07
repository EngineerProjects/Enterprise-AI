"""
Base reasoning framework for Enterprise AI agents.

This module defines the core interface for agent reasoning frameworks,
enabling structured decision-making and tool usage patterns.
"""

import abc
from typing import Any, Dict, List, Optional, Set, Union, cast

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
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

logger = get_logger("agent.reasoning")


class ReasoningFramework(abc.ABC):
    """Abstract base class for agent reasoning frameworks.

    A reasoning framework defines how an agent processes inputs,
    makes decisions, and uses tools to accomplish tasks.
    """

    @abc.abstractmethod
    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process input messages and generate a response.

        Args:
            agent: The agent using this reasoning framework
            messages: List of messages to process
            **kwargs: Additional framework-specific parameters

        Returns:
            Response message
        """
        pass

    @abc.abstractmethod
    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """Process a task and update its status.

        Args:
            agent: The agent using this reasoning framework
            task: Task to process
            **kwargs: Additional framework-specific parameters

        Returns:
            Updated task status
        """
        pass

    @abc.abstractmethod
    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """Format the system prompt for this reasoning framework.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional framework-specific parameters

        Returns:
            Formatted system prompt
        """
        pass

    @abc.abstractmethod
    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """Format instructions for tool usage.

        Args:
            agent: The agent using this reasoning framework
            tools: List of available tools
            **kwargs: Additional framework-specific parameters

        Returns:
            Formatted tool instructions
        """
        pass

    @abc.abstractmethod
    def handle_tool_execution(
        self, agent: AgentProtocol, tool_name: str, tool_params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """Handle the execution of a tool.

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            tool_params: Parameters for tool execution
            **kwargs: Additional framework-specific parameters

        Returns:
            Tool execution result
        """
        pass

    @abc.abstractmethod
    def supports_function_calling(self) -> bool:
        """Check if this framework supports function calling.

        Returns:
            True if function calling is supported, False otherwise
        """
        pass

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Get the name of this reasoning framework.

        Returns:
            Framework name
        """
        pass

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Get a description of this reasoning framework.

        Returns:
            Framework description
        """
        pass

    @property
    @abc.abstractmethod
    def requires_tools(self) -> bool:
        """Check if this framework requires tools to function.

        Returns:
            True if tools are required, False otherwise
        """
        pass


class ToolBasedReasoning(ReasoningFramework, abc.ABC):
    """Base class for reasoning frameworks that use tools.

    This class extends the basic reasoning framework with additional
    methods specific to tool-based reasoning.
    """

    @abc.abstractmethod
    def parse_tool_calls(self, message: MessageProtocol, **kwargs: Any) -> List[Dict[str, Any]]:
        """Parse tool calls from a message.

        Args:
            message: Message to parse for tool calls
            **kwargs: Additional framework-specific parameters

        Returns:
            List of tool calls with name and parameters
        """
        pass

    @abc.abstractmethod
    def format_tool_response(self, tool_name: str, tool_result: ToolResult, **kwargs: Any) -> str:
        """Format a tool execution result for inclusion in a message.

        Args:
            tool_name: Name of the executed tool
            tool_result: Result of tool execution
            **kwargs: Additional framework-specific parameters

        Returns:
            Formatted tool response
        """
        pass

    @property
    def requires_tools(self) -> bool:
        """Tool-based reasoning frameworks require tools."""
        return True


class BaseReasoning(ReasoningFramework):
    """Default reasoning framework with minimal functionality.

    This class provides a basic implementation for agents that don't
    need specialized reasoning patterns.
    """

    def process_input(
        self, agent: AgentProtocol, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process input with simple pass-through to LLM.

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

        # Simply pass messages to LLM provider
        try:
            return cast(MessageProtocol, llm_provider.complete(messages, **kwargs))
        except Exception as e:
            logger.error(f"Error in base reasoning for agent {agent.id}: {e}")
            return cast(
                MessageProtocol,
                Message.assistant_message(
                    f"I encountered an error processing your request: {str(e)}"
                ),
            )

    def process_task(self, agent: AgentProtocol, task: Task, **kwargs: Any) -> TaskStatus:
        """Process task with simple approach.

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
        system_prompt = format_prompt("system.base", additional_instructions="")
        if not system_prompt:
            system_prompt = f"You are {agent.name}, an AI assistant."

        # Create messages for the task
        messages = [
            Message.system_message(system_prompt),
            Message.user_message(f"Task: {task.description}"),
        ]

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
            return task.status

    def format_system_prompt(self, agent: AgentProtocol, base_prompt: str, **kwargs: Any) -> str:
        """Format a basic system prompt.

        Args:
            agent: The agent using this reasoning framework
            base_prompt: Base system prompt
            **kwargs: Additional parameters

        Returns:
            Formatted system prompt
        """
        # Use the base.prompt template
        formatted_prompt = format_prompt("system.base", additional_instructions=base_prompt)
        if formatted_prompt:
            return formatted_prompt

        # Fallback to base prompt
        return base_prompt

    def format_tool_instructions(
        self, agent: AgentProtocol, tools: List[Dict[str, Any]], **kwargs: Any
    ) -> str:
        """Format basic tool instructions.

        Args:
            agent: The agent using this reasoning framework
            tools: List of available tools
            **kwargs: Additional parameters

        Returns:
            Formatted tool instructions
        """
        return "You do not have access to any tools."

    def handle_tool_execution(
        self, agent: AgentProtocol, tool_name: str, tool_params: Dict[str, Any], **kwargs: Any
    ) -> ToolResult:
        """Handle tool execution (not supported in base reasoning).

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool to execute
            tool_params: Parameters for tool execution
            **kwargs: Additional parameters

        Returns:
            Tool execution result (error in this case)
        """
        return ToolResult(
            error="Tool execution is not supported with the base reasoning framework."
        )

    def supports_function_calling(self) -> bool:
        """Base reasoning does not support function calling.

        Returns:
            False always
        """
        return False

    @property
    def name(self) -> str:
        """Get framework name.

        Returns:
            'base'
        """
        return "base"

    @property
    def description(self) -> str:
        """Get framework description.

        Returns:
            Description string
        """
        return "Basic reasoning without specialized patterns or tool usage."

    @property
    def requires_tools(self) -> bool:
        """Base reasoning does not require tools.

        Returns:
            False always
        """
        return False


# Dictionary of available reasoning frameworks
# This will be populated by the registry
_reasoning_frameworks: Dict[str, ReasoningFramework] = {"base": BaseReasoning()}


def register_framework(name: str, framework: ReasoningFramework) -> None:
    """Register a reasoning framework.

    Args:
        name: Name to register under
        framework: Framework implementation

    Raises:
        ValueError: If a framework with the same name already exists
    """
    if name in _reasoning_frameworks:
        raise ValueError(f"Reasoning framework '{name}' already registered")

    _reasoning_frameworks[name] = framework
    logger.info(f"Registered reasoning framework: {name}")


def get_framework(name: str) -> ReasoningFramework:
    """Get a reasoning framework by name.

    Args:
        name: Framework name

    Returns:
        Framework implementation

    Raises:
        ValueError: If framework not found
    """
    if name not in _reasoning_frameworks:
        logger.warning(f"Reasoning framework '{name}' not found, using base")
        return _reasoning_frameworks["base"]

    return _reasoning_frameworks[name]


def list_frameworks() -> List[str]:
    """Get list of available framework names.

    Returns:
        List of framework names
    """
    return list(_reasoning_frameworks.keys())


def get_framework_descriptions() -> Dict[str, str]:
    """Get descriptions of all registered frameworks.

    Returns:
        Dictionary mapping framework names to descriptions
    """
    return {name: framework.description for name, framework in _reasoning_frameworks.items()}
