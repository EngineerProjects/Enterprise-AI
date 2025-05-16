"""
Core agent implementation for Enterprise AI.

This module provides the foundational agent classes with delegation
to specialized manager components for different responsibilities.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.architecture.conversation import ConversationManager, ConversationManagerConfig
from enterprise_ai.agent.architecture.errors import AgentError, AgentErrorCode, ErrorManager
from enterprise_ai.agent.architecture.execution import ExecutionManager, ExecutionManagerConfig
from enterprise_ai.agent.architecture.introspection import IntrospectionManager, IntrospectionManagerConfig
from enterprise_ai.agent.architecture.lifecycle import AgentLifecycleManager, AgentState
from enterprise_ai.agent.architecture.reasoning_manager import ReasoningManager, ReasoningManagerConfig
from enterprise_ai.agent.architecture.tools_manager import AgentToolsManager
from enterprise_ai.agent.architecture.utils import generate_id, safe_serialize, timer, run_async
from enterprise_ai.config import get_config
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("agent.base")


class BaseAgent:
    """Base agent implementation.

    This class provides a foundation for all agent types with common
    functionality and delegation to specialized manager components.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        role_type: Optional[str] = None,
        role_kwargs: Optional[Dict[str, Any]] = None,
        state_type: Optional[str] = None,
        state_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """Initialize the agent.

        Args:
            agent_id: Optional unique identifier
            name: Optional human-readable name
            role_type: Optional role type to assign
            role_kwargs: Optional arguments for role creation
            state_type: Optional state implementation type
            state_kwargs: Optional arguments for state creation
            **kwargs: Additional agent-specific parameters
        """
        # Basic agent properties
        self.id = agent_id or generate_id("agent-")
        self.name = name or f"Agent-{self.id[-4:]}"
        
        # Create error manager
        self._error_manager = ErrorManager(self.id)
        
        # Initialize lifecycle manager
        self._lifecycle = AgentLifecycleManager(self)
        
        # Initialize state
        state_kwargs = state_kwargs or {}
        state_dir = state_kwargs.get("state_dir") or get_config("agent.state_directory")
        if state_dir:
            state_kwargs["state_dir"] = state_dir
        
        # Create other managers
        self._conversation = ConversationManager(self)
        self._execution = ExecutionManager(self, error_manager=self._error_manager)
        self._introspection = IntrospectionManager(self)
        
        # Role will be set by subclasses as needed
        self._role = None
        
        logger.info(f"Initialized agent {self.id} ({self.name})")

    @property
    def state(self) -> AgentState:
        """Get the current agent state.

        Returns:
            Current agent state
        """
        return self._lifecycle.state

    def process_message(
        self, message: Union[str, MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a message and generate a response.

        Args:
            message: Input message or string
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        # This is a basic implementation - specialized agents override this
        if isinstance(message, str):
            input_message = Message.user_message(message)
        else:
            input_message = message
        
        # Create simple response
        response = Message.assistant_message(
            f"Hello, I am {self.name}. I've received your message, but I don't have advanced processing capabilities."
        )
        
        return cast(MessageProtocol, response)

    async def aprocess_message(
        self, message: Union[str, MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a message asynchronously.

        Args:
            message: Input message or string
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        return self.process_message(message, **kwargs)

    def process_conversation(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a conversation and generate a response.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        # Process the last message in the conversation
        if messages:
            return self.process_message(messages[-1], **kwargs)
        
        # Empty conversation
        return cast(
            MessageProtocol,
            Message.assistant_message(
                f"Hello, I am {self.name}. How can I assist you today?"
            )
        )

    async def aprocess_conversation(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a conversation asynchronously.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        return self.process_conversation(messages, **kwargs)

    def assign_task(self, task: Any) -> bool:
        """Assign a task to the agent.

        Args:
            task: Task to assign

        Returns:
            True if task assigned successfully, False otherwise
        """
        # Basic implementation - specialized agents override this
        logger.info(f"Task assigned to agent {self.id}: {task}")
        return False

    def process_task(self) -> Any:
        """Process the current task.

        Returns:
            Task status
        """
        # Basic implementation - specialized agents override this
        logger.info(f"Processing task for agent {self.id}")
        return None

    async def aprocess_task(self) -> Any:
        """Process the current task asynchronously.

        Returns:
            Task status
        """
        return self.process_task()

    def get_status(self) -> Dict[str, Any]:
        """Get agent status summary.

        Returns:
            Dictionary of status information
        """
        return self._lifecycle.get_status()

    def save_state(self) -> bool:
        """Save agent state.

        Returns:
            True if state saved successfully, False otherwise
        """
        return self._lifecycle.save_state()

    def load_state(self) -> bool:
        """Load agent state.

        Returns:
            True if state loaded successfully, False otherwise
        """
        return self._lifecycle.load_state()

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the agent.

        Args:
            **kwargs: Initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        return await self._lifecycle.initialize(kwargs)

    async def terminate(self) -> bool:
        """Terminate the agent and clean up resources.

        Returns:
            True if termination succeeded, False otherwise
        """
        return await self._lifecycle.terminate()

    def __del__(self) -> None:
        """Clean up resources when object is destroyed."""
        # Don't try to await coroutines in __del__, it's not reliable
        # Instead, just log that the agent is being destroyed
        logger.debug(f"Agent {self.id} is being destroyed")
        # The proper way to clean up is to explicitly call terminate() before the agent is no longer needed


class LLMAgent(BaseAgent):
    """Agent implementation using a Large Language Model.

    This class extends the base agent with the ability to use
    LLMs for reasoning and processing inputs.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        role_type: Optional[str] = None,
        role_kwargs: Optional[Dict[str, Any]] = None,
        state_type: Optional[str] = None,
        state_kwargs: Optional[Dict[str, Any]] = None,
        llm_provider: Optional[Any] = None,
        reasoning_framework: str = "base",
        use_tools: bool = False,
        enable_mcp: bool = False,
        tool_categories: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        """Initialize the LLM agent.

        Args:
            agent_id: Optional unique identifier
            name: Optional human-readable name
            role_type: Optional role type to assign
            role_kwargs: Optional arguments for role creation
            state_type: Optional state implementation type
            state_kwargs: Optional arguments for state creation
            llm_provider: LLM provider to use
            reasoning_framework: Name of the reasoning framework to use
            use_tools: Whether to enable tool usage
            enable_mcp: Whether to enable MCP for tool discovery
            tool_categories: Optional categories of tools to include
            tool_names: Optional specific tool names to include
            **kwargs: Additional agent-specific parameters
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            role_type=role_type,
            role_kwargs=role_kwargs,
            state_type=state_type,
            state_kwargs=state_kwargs,
            **kwargs,
        )
        
        # Set up LLM provider
        self._llm_provider = llm_provider
        
        # Initialize tools manager if tools are enabled
        if use_tools:
            self._tools = AgentToolsManager(self)
            
            # Store MCP config for later initialization rather than trying to initialize now
            # This avoids the coroutine handling issue with run_async
            self._mcp_config = {
                "enable": enable_mcp,
                "categories": tool_categories,
                "names": tool_names
            }
        else:
            self._tools = None
            self._mcp_config = None
        
        # Create reasoning manager with specified framework
        self._reasoning = ReasoningManager(
            self,
            config=ReasoningManagerConfig(default_framework=reasoning_framework)
        )
        
        logger.info(f"Initialized LLM agent {self.id} with framework {reasoning_framework}")
        
    async def initialize_mcp(self) -> bool:
        """Initialize MCP when it's actually needed."""
        if self._tools and hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:
            await self._tools.enable_mcp(
                tool_categories=self._mcp_config["categories"],
                tool_names=self._mcp_config["names"]
            )
            # Clear the config to avoid re-initialization
            self._mcp_config = None
            return True
        return False

    async def aprocess_message(
        self, message: Union[str, MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a message asynchronously using the LLM and reasoning framework.

        Args:
            message: Input message or string
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        # Convert string to message if needed
        if isinstance(message, str):
            input_message = Message.user_message(message)
        else:
            input_message = message
        
        # Initialize MCP if needed before processing
        if hasattr(self, "_tools") and self._tools and hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:
            await self.initialize_mcp()
        
        # Record message in conversation history
        conversation_id = kwargs.get("conversation_id", "default")
        self._conversation.add_message(input_message, conversation_id=conversation_id)
        
        # Get full conversation history
        messages = self._conversation.get_messages(conversation_id=conversation_id)
        
        # Ensure timeout is set to minimum required timeout
        if "timeout" not in kwargs and hasattr(self, "_llm_provider") and self._llm_provider:
            # Get provider timeout
            provider_timeout = getattr(self._llm_provider, "_timeout", 60.0)
            
            # For CPU-constrained environments, use a significantly higher timeout
            if provider_timeout < 300.0:
                provider_timeout = 300.0
                
            kwargs["timeout"] = provider_timeout
            logger.debug(f"Using timeout: {provider_timeout}s for LLM request")
        
        # Process using execution manager
        response = await self._execution.process_message(messages, **kwargs)
        
        # Record response in conversation history
        self._conversation.add_message(response, conversation_id=conversation_id)
        
        return response

    async def process_conversation(
        self, messages: List[MessageProtocol], **kwargs: Any
    ) -> MessageProtocol:
        """Process a conversation using the LLM and reasoning framework.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters for processing

        Returns:
            Response message
        """
        # Initialize MCP if needed before processing
        if hasattr(self, "_tools") and self._tools and hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:
            await self.initialize_mcp()
        
        # Record messages in conversation history
        conversation_id = kwargs.get("conversation_id", "default")
        for message in messages:
            self._conversation.add_message(message, conversation_id=conversation_id)
        
        # Ensure timeout is set to minimum required timeout
        if "timeout" not in kwargs and hasattr(self, "_llm_provider") and self._llm_provider:
            # Get provider timeout
            provider_timeout = getattr(self._llm_provider, "_timeout", 60.0)
            
            # For CPU-constrained environments, use a significantly higher timeout
            if provider_timeout < 300.0:
                provider_timeout = 300.0
                
            kwargs["timeout"] = provider_timeout
            logger.debug(f"Using timeout: {provider_timeout}s for LLM request")
        
        # Process using execution manager
        response = await self._execution.process_message(messages, **kwargs)
        
        # Record response in conversation history
        self._conversation.add_message(response, conversation_id=conversation_id)
        
        return response

    async def assign_task(self, task: Any) -> bool:
        """Assign a task to the agent.

        Args:
            task: Task to assign

        Returns:
            True if task assigned successfully, False otherwise
        """
        # Store task in lifecycle manager
        if hasattr(self._lifecycle, "current_task"):
            self._lifecycle.current_task = task
        
        logger.info(f"Task assigned to agent {self.id}: {task}")
        return True

    async def process_task(self) -> Any:
        """Process the current task.

        Returns:
            Task status
        """
        # Initialize MCP if needed before processing
        if hasattr(self, "_tools") and self._tools and hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:
            await self.initialize_mcp()
            
        # Get current task from lifecycle manager
        task = None
        if hasattr(self._lifecycle, "current_task"):
            task = self._lifecycle.current_task
        
        if not task:
            logger.warning(f"No task assigned to agent {self.id}")
            return None
        
        # Ensure timeout is properly set
        kwargs = {}
        if hasattr(self, "_llm_provider") and self._llm_provider:
            # Get provider timeout
            provider_timeout = getattr(self._llm_provider, "_timeout", 60.0)
            
            # For CPU-constrained environments, use a significantly higher timeout
            if provider_timeout < 300.0:
                provider_timeout = 300.0
                
            kwargs["timeout"] = provider_timeout
            logger.debug(f"Using timeout: {provider_timeout}s for task processing")
        
        # Process using execution manager
        result = await self._execution.process_task(task, **kwargs)
        
        logger.info(f"Task processed for agent {self.id}: {result}")
        return result

    def get_capabilities(self) -> Dict[str, Any]:
        """Get agent capabilities.

        Returns:
            Dictionary of capabilities
        """
        return self._introspection.get_agent_capabilities()

    def get_tools_description(self) -> str:
        """Get a description of available tools.

        Returns:
            String describing available tools
        """
        if not self._tools:
            return "No tools available."
        
        return self._tools.get_formatted_tool_descriptions()

    async def set_reasoning_framework(self, framework_name: str) -> bool:
        """Set the reasoning framework.

        Args:
            framework_name: Name of the framework to use

        Returns:
            True if framework set successfully, False otherwise
        """
        return self._reasoning.set_framework(framework_name)

    def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics.

        Returns:
            Dictionary of metrics
        """
        return self._introspection.get_performance_metrics()

    # Following are the delegate methods for backward compatibility
    
    # --- Tooling methods ---
    
    async def execute_tool(
        self, tool_name: str, **kwargs: Any
    ) -> Any:
        """Execute a tool.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Parameters for the tool

        Returns:
            Tool execution result
        """
        if not self._tools:
            raise AgentError(
                "Tools not enabled for this agent",
                error_code=AgentErrorCode.INVALID_CONFIGURATION
            )
        
        # Check if we need to initialize MCP
        if hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:
            await self.initialize_mcp()
        
        return await self._tools.execute_tool(tool_name, **kwargs)
    
    # --- Conversation methods ---
    
    def add_message(
        self, message: Union[str, MessageProtocol], conversation_id: str = "default"
    ) -> None:
        """Add a message to a conversation.

        Args:
            message: Message to add
            conversation_id: ID of conversation
        """
        self._conversation.add_message(message, conversation_id=conversation_id)
    
    def get_messages(
        self, conversation_id: str = "default", limit: Optional[int] = None
    ) -> List[MessageProtocol]:
        """Get messages from a conversation.

        Args:
            conversation_id: ID of conversation
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages
        """
        return self._conversation.get_messages(conversation_id=conversation_id, limit=limit)
    
    def clear_conversation(self, conversation_id: str = "default") -> bool:
        """Clear a conversation.

        Args:
            conversation_id: ID of conversation to clear

        Returns:
            True if successful, False otherwise
        """
        return self._conversation.clear_conversation(conversation_id=conversation_id)
    
    # --- State methods ---
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update agent configuration.

        Args:
            config: New configuration to merge with existing config
        """
        self._lifecycle.update_config(config)
    
    def get_config(self) -> Dict[str, Any]:
        """Get agent configuration.

        Returns:
            Current configuration
        """
        return self._lifecycle.get_config()