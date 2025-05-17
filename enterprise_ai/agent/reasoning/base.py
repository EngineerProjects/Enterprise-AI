"""
Base reasoning framework for Enterprise AI agents.

This module defines the core interface for agent reasoning frameworks,
enabling structured decision-making and tool usage patterns.
"""

import abc
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.core.types import AgentProtocol, AgentMessage, Task, TaskStatus
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

    def filter_tools_by_capabilities(
        self, agent: AgentProtocol, capabilities: List[str], match_all: bool = False
    ) -> List[Dict[str, Any]]:
        """Filter tools based on capabilities.

        Args:
            agent: The agent using this reasoning framework
            capabilities: List of capabilities to filter by
            match_all: Whether all capabilities must be present

        Returns:
            List of tools matching the capability criteria
        """
        if not hasattr(agent, "_tool_manager"):
            return []

        tool_manager = getattr(agent, "_tool_manager")

        # Get all tools first
        all_tools = []
        if hasattr(tool_manager, "get_tool_schemas"):
            import asyncio

            loop = asyncio.get_event_loop()
            all_tools = loop.run_until_complete(tool_manager.get_tool_schemas())

        # If no capabilities to filter by, return all tools
        if not capabilities:
            return all_tools

        # Filter tools by capabilities
        result = []
        for tool in all_tools:
            tool_caps = []

            # Extract tool capabilities from tool info
            if hasattr(tool_manager, "get_tool_info"):
                tool_name = tool.get("function", {}).get("name")
                if tool_name:
                    tool_info = tool_manager.get_tool_info(tool_name)
                    if "capabilities" in tool_info:
                        tool_caps = tool_info["capabilities"]

            # Skip tools without capabilities
            if not tool_caps:
                continue

            # Check if tool matches capability criteria
            if match_all:
                if all(cap in tool_caps for cap in capabilities):
                    result.append(tool)
            else:
                if any(cap in tool_caps for cap in capabilities):
                    result.append(tool)

        return result

    def validate_tool_params(
        self, agent: AgentProtocol, tool_name: str, params: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """Validate tool parameters against schema.

        Args:
            agent: The agent using this reasoning framework
            tool_name: Name of the tool
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not hasattr(agent, "_tool_manager"):
            return False, "Agent has no tool manager"

        tool_manager = getattr(agent, "_tool_manager")

        # Get tool schema if available
        if hasattr(tool_manager, "get_tool"):
            tool = tool_manager.get_tool(tool_name)
            if tool and hasattr(tool, "parameters"):
                return validate_tool_parameters(tool_name, params, tool.parameters)

        return True, None  # Default to valid if we can't validate

    async def execute_tools_parallel(
        self, agent: AgentProtocol, tool_calls: List[Dict[str, Any]], **kwargs: Any
    ) -> List[Tuple[str, ToolResult]]:
        """Execute multiple tools in parallel.

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

            # Add to execution list
            executions.append(
                {"tool_name": tool_name, "parameters": params, "timeout": kwargs.get("timeout")}
            )
            tool_names.append(tool_name)

        # Execute tools in parallel if possible
        if hasattr(tool_manager, "execute_tools_parallel"):
            results = await tool_manager.execute_tools_parallel(executions)
            return results

        # Fallback: execute sequentially
        results = []
        for execution in executions:
            tool_name = execution["tool_name"]
            result = await self.handle_tool_execution(
                agent, tool_name, execution["parameters"], **kwargs
            )
            results.append((tool_name, result))

        return results

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
        # Extract LLM provider - first check if agent has one attached directly
        llm_provider = None

        # First try to get it from the agent directly
        if hasattr(agent, "_llm_provider"):
            llm_provider = getattr(agent, "_llm_provider")

        # If not found on agent, try kwargs (but remove it to avoid serialization issues)
        if not llm_provider and "llm_provider" in kwargs:
            llm_provider = kwargs.pop("llm_provider")

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
            logger.info(
                f"Using LLM provider {type(llm_provider).__name__} with model {llm_provider.model_name}"
            )

            # Don't pass all kwargs to the LLM provider, as they may include non-serializable objects
            # Only pass relevant parameters that the LLM provider might need
            llm_kwargs = {
                "temperature": kwargs.get("temperature", None),
                "max_tokens": kwargs.get("max_tokens", None),
                "top_p": kwargs.get("top_p", None),
                "timeout": kwargs.get("timeout", 300.0),  # Use 300s default timeout
            }

            # Remove None values to use provider defaults
            llm_kwargs = {k: v for k, v in llm_kwargs.items() if v is not None}

            return cast(MessageProtocol, llm_provider.complete(messages, **llm_kwargs))
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
        # Extract LLM provider - first check if agent has one attached directly
        llm_provider = None

        # First try to get it from the agent directly
        if hasattr(agent, "_llm_provider"):
            llm_provider = getattr(agent, "_llm_provider")

        # If not found on agent, try kwargs (but remove it to avoid serialization issues)
        if not llm_provider and "llm_provider" in kwargs:
            llm_provider = kwargs.pop("llm_provider")

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
            # Don't pass all kwargs to the LLM provider, as they may include non-serializable objects
            # Only pass relevant parameters that the LLM provider might need
            llm_kwargs = {
                "temperature": kwargs.get("temperature", None),
                "max_tokens": kwargs.get("max_tokens", None),
                "top_p": kwargs.get("top_p", None),
                "timeout": kwargs.get("timeout", 300.0),  # Use 300s default timeout
            }

            # Remove None values to use provider defaults
            llm_kwargs = {k: v for k, v in llm_kwargs.items() if v is not None}

            response = llm_provider.complete(
                [cast(MessageProtocol, msg) for msg in messages], **llm_kwargs
            )

            # Store response in task metadata
            if not task.metadata:
                task.metadata = {}
            task.metadata["response"] = response.content

            task.status = TaskStatus.COMPLETED
            return task.status
        except Exception as e:
            logger.error(f"Error processing task for agent {agent.id}: {e}")
            task.status = TaskStatus.FAILED
            task.metadata = task.metadata or {}
            task.metadata["error"] = str(e)
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
        # Add memory and context instructions
        memory_instructions = """
You have access to the conversation history with the user.
When asked about previous conversations or information shared by the user previously:
1. Recall information from previous messages
2. Provide specific details the user previously shared (their name, location, preferences, etc.)
3. Acknowledge the continuity of your conversation
4. Never claim you "can't remember" or that you "don't have memory" as you can access the conversation history
"""

        # Combine prompts
        enhanced_prompt = f"{base_prompt}\n\n{memory_instructions}"

        # Use the base.prompt template
        formatted_prompt = format_prompt("system.base", additional_instructions=enhanced_prompt)
        if formatted_prompt:
            return formatted_prompt

        # Fallback to base prompt with memory instructions
        return enhanced_prompt

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
        return ToolFailure(
            error="Tool execution is not supported with the base reasoning framework.",
            error_code="UNSUPPORTED_OPERATION",
            metadata=ToolResultMetadata(tool_name=tool_name),
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
