"""
Base agent implementations for Enterprise AI.

This module provides the foundational agent classes that implement
the AgentProtocol defined in types.py.
"""

import abc
import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from enterprise_ai.agent.memory import create_memory
from enterprise_ai.agent.message import (
    BaseAgentMessage,
    BroadcastMessage,
    ErrorMessage,
    NotificationMessage,
    QueryMessage,
    ResponseMessage,
    TaskAssignmentMessage,
    TaskUpdateMessage,
    create_message,
)
from enterprise_ai.agent.role import BaseAgentRole, create_role
from enterprise_ai.agent.state import ConversationState, create_agent_state
from enterprise_ai.agent.types import (
    AgentMessage,
    AgentProtocol,
    AgentRole,
    AgentState,
    Task,
    TaskStatus,
)
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol
from enterprise_ai.agent.tooling import AgentToolManager
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult

logger = get_logger("agent.base")


class BaseAgent(AgentProtocol):
    """Base implementation of an agent.

    This class provides a foundation for agent implementations with
    basic functionality for processing messages and tasks.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "Agent",
        role_type: Optional[str] = None,
        role_kwargs: Optional[Dict[str, Any]] = None,
        state_type: str = "base",
        state_kwargs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a base agent.

        Args:
            agent_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            role_type: Optional role type to assign
            role_kwargs: Optional arguments for role creation
            state_type: State implementation type
            state_kwargs: Optional arguments for state creation
        """
        self._id = agent_id or str(uuid.uuid4())
        self._name = name
        self._created_at = time.time()
        self._state = create_agent_state(
            self._id,
            state_type=state_type,
            **(state_kwargs or {}),
        )

        # Assign role if specified
        if role_type:
            self._state.role = create_role(role_type, **(role_kwargs or {}))

        logger.info(f"Initialized agent: {self._id} ({self._name})")

        # Initialize tool manager
        self._tool_manager = AgentToolManager(self._id)

    @property
    def id(self) -> str:
        """Get agent ID.

        Returns:
            Agent ID
        """
        return self._id

    @property
    def name(self) -> str:
        """Get agent name.

        Returns:
            Agent name
        """
        return self._name

    @property
    def state(self) -> AgentState:
        """Get agent state.

        Returns:
            Agent state
        """
        return self._state

    @property
    def role(self) -> Optional[AgentRole]:
        """Get agent role.

        Returns:
            Agent role or None if not assigned
        """
        try:
            return self._state.role
        except RuntimeError:
            # The state's role property raises RuntimeError if role not set
            return None

    @role.setter
    def role(self, role: AgentRole) -> None:
        """Set agent role.

        Args:
            role: Role to assign
        """
        self._state.role = role
        logger.info(f"Assigned role to agent {self._id}: {role.name}")

    # Add tool management methods
    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the agent's toolkit."""
        self._tool_manager.add_tool(tool)

    def list_tools(self) -> List[str]:
        """List all tools available to this agent."""
        return self._tool_manager.list_tools()

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters."""
        return await self._tool_manager.execute_tool(tool_name, **kwargs)

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message and optionally return a response.

        Base implementation that handles common message types and
        delegates to message-specific handlers.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Log message receipt
        message_id = getattr(message, "message_id", "unknown_id")
        is_broadcast = getattr(message, "is_broadcast", False)

        logger.debug(
            f"Agent {self._id} received message from {message.sender_id}: "
            f"type={message.message_type}, broadcast={is_broadcast}"
        )

        # Store message in conversation history if using ConversationState
        if isinstance(self._state, ConversationState):
            self._state.add_message(message, conversation_id=message.sender_id)

        # Extract metadata for possible tool execution
        metadata = getattr(message, "metadata", {}) or {}

        # Check if message is a tool execution request
        if metadata.get("request_type") == "tool_execution":
            tool_name = metadata.get("tool_name")
            tool_params = metadata.get("tool_params", {})

            if tool_name and hasattr(self, "_tool_manager"):
                # For synchronous response, execute the tool immediately
                if not metadata.get("async_execution", False):
                    try:
                        # Create asyncio event loop if needed and run tool execution
                        loop = asyncio.get_event_loop()
                        tool_result = loop.run_until_complete(
                            self._tool_manager.execute_tool(tool_name, **tool_params)
                        )

                        return ResponseMessage(
                            self._id,
                            message.sender_id,
                            tool_result.output
                            if not tool_result.error
                            else f"Error: {tool_result.error}",
                            message_id,
                            metadata={
                                "tool_name": tool_name,
                                "tool_result": tool_result.to_dict()
                                if hasattr(tool_result, "to_dict")
                                else {},
                                "success": tool_result.error is None,
                            },
                        )
                    except Exception as e:
                        return ErrorMessage(
                            self._id,
                            message.sender_id,
                            f"Tool execution failed: {str(e)}",
                            "TOOL_EXECUTION_ERROR",
                        )
                else:
                    # For async execution, return acknowledgment and execute in background
                    asyncio.create_task(
                        self._handle_async_tool_execution(
                            message.sender_id,
                            message_id,
                            tool_name,
                            tool_params,
                            metadata.get("task_id"),
                        )
                    )

                    return TaskUpdateMessage(
                        self._id,
                        message.sender_id,
                        metadata.get("task_id", "unknown"),
                        "IN_PROGRESS",
                        f"Tool execution started: {tool_name}",
                    )

        # Handle message based on type
        message_type = message.message_type.upper() if message.message_type else "UNKNOWN"

        if message_type == "TASK_ASSIGNMENT":
            return self._handle_task_assignment(message)
        elif message_type == "TASK_UPDATE":
            return self._handle_task_update(message)
        elif message_type == "QUERY":
            return self._handle_query(message)
        elif message_type == "RESPONSE":
            return self._handle_response(message)
        elif message_type == "BROADCAST":
            return self._handle_broadcast(message)
        elif message_type == "NOTIFICATION":
            return self._handle_notification(message)
        elif message_type == "ERROR":
            return self._handle_error(message)
        else:
            # Default handling for unknown message types
            return self._handle_unknown_message(message)

    async def _handle_async_tool_execution(
        self,
        sender_id: str,
        message_id: str,
        tool_name: str,
        params: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> None:
        """Handle tool execution asynchronously."""
        try:
            result = await self._tool_manager.execute_tool(tool_name, **params)

            # Create a response message with the tool result
            response = ResponseMessage(
                self._id,
                sender_id,
                result.output if not result.error else f"Error: {result.error}",
                message_id,
                metadata={
                    "tool_name": tool_name,
                    "tool_result": result.to_dict() if hasattr(result, "to_dict") else {},
                    "success": result.error is None,
                    "task_id": task_id,
                },
            )

            # Send the response
            self.send_message(
                message_type="RESPONSE",
                receiver_id=sender_id,
                content=response.content,
                metadata=response.metadata,
                reply_to=message_id,
            )

        except Exception as e:
            # Send error response
            _ = ErrorMessage(
                self._id,
                sender_id,
                f"Tool execution failed: {str(e)}",
                "TOOL_EXECUTION_ERROR",
                metadata={"task_id": task_id} if task_id else {},
            )

            self.send_message(
                message_type="ERROR",
                receiver_id=sender_id,
                content=str(e),
                metadata={"error_code": "TOOL_EXECUTION_ERROR", "task_id": task_id}
                if task_id
                else {"error_code": "TOOL_EXECUTION_ERROR"},
            )

    def _handle_task_assignment(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle task assignment message.

        Args:
            message: Task assignment message

        Returns:
            Optional response message
        """
        # Extract task information from message
        task_id = None
        metadata = getattr(message, "metadata", {})

        if metadata is not None:
            task_id = metadata.get("task_id")

        if not task_id:
            return ErrorMessage(
                self._id,
                message.sender_id,
                "Task assignment missing task_id",
            )

        # Create task from message
        task = Task(
            id=task_id,
            description=message.content or "No description provided",
            status=TaskStatus.PENDING,
            metadata=metadata if metadata is not None else {},
        )

        # Attempt to assign task
        success = self.assign_task(task)

        # Return acknowledgment
        if success:
            return TaskUpdateMessage(
                self._id,
                message.sender_id,
                task_id,
                "ACCEPTED",
                "Task accepted",
            )
        else:
            return TaskUpdateMessage(
                self._id,
                message.sender_id,
                task_id,
                "REJECTED",
                "Task rejected - agent busy or incompatible",
            )

    def _handle_task_update(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle task update message.

        Args:
            message: Task update message

        Returns:
            Optional response message
        """
        # Store task update in memory
        metadata = getattr(message, "metadata", {})

        if metadata is not None:
            task_id = metadata.get("task_id")
            status = metadata.get("status")

            if task_id and status:
                self._state.memory.add(
                    f"task_updates.{task_id}.{int(time.time())}",
                    {
                        "sender": message.sender_id,
                        "status": status,
                        "message": message.content,
                        "timestamp": getattr(message, "timestamp", None),
                    },
                )

        # No response needed by default
        return None

    def _handle_query(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle query message.

        Args:
            message: Query message

        Returns:
            Response message
        """
        # Base agent can only provide basic information
        if not message.content:
            return ErrorMessage(
                self._id,
                message.sender_id,
                "Query message has no content",
            )

        # Simple keyword-based response system
        query = message.content.lower()
        message_id = getattr(message, "message_id", str(uuid.uuid4()))

        if "status" in query:
            return ResponseMessage(
                self._id,
                message.sender_id,
                f"Agent {self._name} is {self._get_status_description()}",
                message_id,
            )
        elif "role" in query:
            role_info = "No role assigned"
            if self.role:
                role_info = f"Role: {self.role.name} - {self.role.description}"
            return ResponseMessage(
                self._id,
                message.sender_id,
                role_info,
                message_id,
            )
        elif "capability" in query or "capabilities" in query:
            capabilities = []
            if self.role:
                capabilities = self.role.capabilities
            return ResponseMessage(
                self._id,
                message.sender_id,
                f"Agent capabilities: {', '.join(capabilities) if capabilities else 'None'}",
                message_id,
            )
        else:
            # Default response for unknown queries
            return ResponseMessage(
                self._id,
                message.sender_id,
                f"Agent {self._name} cannot answer this query: {message.content}",
                message_id,
            )

    def _handle_response(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle response message.

        Args:
            message: Response message

        Returns:
            Optional acknowledgment message
        """
        # Store response in memory for later reference
        reply_to = getattr(message, "reply_to", None)
        if reply_to:
            self._state.memory.add(
                f"responses.{reply_to}",
                {
                    "sender": message.sender_id,
                    "content": message.content,
                    "timestamp": getattr(message, "timestamp", None),
                },
            )

        # No response needed for responses
        return None

    def _handle_broadcast(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle broadcast message.

        Args:
            message: Broadcast message

        Returns:
            Optional acknowledgment message
        """
        # Store broadcast in memory
        message_id = getattr(message, "message_id", str(uuid.uuid4()))

        self._state.memory.add(
            f"broadcasts.{message_id}",
            {
                "sender": message.sender_id,
                "content": message.content,
                "timestamp": getattr(message, "timestamp", None),
            },
        )

        # No response needed for broadcasts by default
        return None

    def _handle_notification(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle notification message.

        Args:
            message: Notification message

        Returns:
            Optional acknowledgment message
        """
        # Store notification in memory
        message_id = getattr(message, "message_id", str(uuid.uuid4()))

        self._state.memory.add(
            f"notifications.{message_id}",
            {
                "sender": message.sender_id,
                "content": message.content,
                "timestamp": getattr(message, "timestamp", None),
            },
        )

        # No response needed for notifications by default
        return None

    def _handle_error(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle error message.

        Args:
            message: Error message

        Returns:
            Optional acknowledgment message
        """
        # Log error message
        metadata = getattr(message, "metadata", {})
        error_code = "UNKNOWN"
        if metadata is not None:
            error_code = metadata.get("error_code", "UNKNOWN")

        logger.warning(
            f"Agent {self._id} received error from {message.sender_id}: "
            f"[{error_code}] {message.content}"
        )

        # Store error in memory
        message_id = getattr(message, "message_id", str(uuid.uuid4()))

        self._state.memory.add(
            f"errors.{message_id}",
            {
                "sender": message.sender_id,
                "error_code": error_code,
                "message": message.content,
                "timestamp": getattr(message, "timestamp", None),
            },
        )

        # No response needed for errors by default
        return None

    def _handle_unknown_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Handle unknown message type.

        Args:
            message: Message with unknown type

        Returns:
            Optional error message
        """
        logger.warning(f"Agent {self._id} received unknown message type: {message.message_type}")
        return ErrorMessage(
            self._id,
            message.sender_id,
            f"Unknown message type: {message.message_type}",
            "UNKNOWN_MESSAGE_TYPE",
        )

    def assign_task(self, task: Task) -> bool:
        """Assign a task to the agent.

        Args:
            task: Task to assign

        Returns:
            True if task was accepted, False otherwise
        """
        # Check if agent already has a task
        if self._state.current_task is not None:
            logger.info(f"Agent {self._id} rejected task {task.id}: already has a task")
            return False

        # Set task as current
        self._state.current_task = task
        logger.info(f"Agent {self._id} accepted task {task.id}")
        return True

    def process_task(self) -> TaskStatus:
        """Process the current task.

        Base implementation that simply marks the task as COMPLETED.
        Subclasses should override to provide actual task processing.

        Returns:
            Updated task status
        """
        # Check if agent has a task
        task = self._state.current_task
        if not task:
            logger.warning(f"Agent {self._id} has no task to process")
            return TaskStatus.FAILED

        # Update task status
        task.status = TaskStatus.COMPLETED
        logger.info(f"Agent {self._id} completed task {task.id}")

        return task.status

    def get_status(self) -> Dict[str, Any]:
        """Get agent status summary.

        Returns:
            Dictionary with status information
        """
        status = {
            "id": self._id,
            "name": self._name,
            "created_at": self._created_at,
            "uptime": time.time() - self._created_at,
            "task": None,
        }

        # Add task information if available
        if self._state.current_task:
            status["task"] = {
                "id": self._state.current_task.id,
                "description": self._state.current_task.description,
                "status": self._state.current_task.status.name,
            }

        # Add role information if available
        role = self.role
        if role:
            status["role"] = {
                "name": role.name,
                "description": role.description,
            }

        return status

    def _get_status_description(self) -> str:
        """Get a human-readable status description.

        Returns:
            Status description string
        """
        if self._state.current_task:
            task_status = self._state.current_task.status.name
            return f"{task_status.lower()} task {self._state.current_task.id}"
        else:
            return "idle"

    def send_message(
        self,
        message_type: str,
        receiver_id: Optional[str],
        content: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentMessage:
        """Create and send a message.

        Note: This method creates the message but doesn't actually
        deliver it. The message delivery is handled externally.

        Args:
            message_type: Type of message to send
            receiver_id: ID of the receiving agent or None for broadcast
            content: Message content
            **kwargs: Additional message parameters

        Returns:
            Created message
        """
        message = create_message(
            message_type,
            self._id,
            receiver_id,
            content,
            **kwargs,
        )

        # Log message sending
        logger.debug(
            f"Agent {self._id} sending message to {receiver_id or 'broadcast'}: type={message_type}"
        )

        return message


class LLMAgent(BaseAgent):
    """LLM-powered agent implementation.

    This class extends BaseAgent with LLM capabilities for more
    advanced reasoning and communication.
    """

    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: str = "LLM Agent",
        role_type: Optional[str] = None,
        role_kwargs: Optional[Dict[str, Any]] = None,
        state_type: str = "conversation",
        state_kwargs: Optional[Dict[str, Any]] = None,
        llm_provider: Optional[Any] = None,
    ) -> None:
        """Initialize an LLM agent.

        Args:
            agent_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            role_type: Optional role type to assign
            role_kwargs: Optional arguments for role creation
            state_type: State implementation type
            state_kwargs: Optional arguments for state creation
            llm_provider: Optional LLM provider instance
        """
        # Ensure we use conversation state for LLM agents
        if state_type != "conversation":
            logger.warning(
                f"LLMAgent requires conversation state, "
                f"overriding provided state_type: {state_type}"
            )
            state_type = "conversation"

        super().__init__(
            agent_id,
            name,
            role_type,
            role_kwargs,
            state_type,
            state_kwargs,
        )

        # LLM provider setup will need to be improved when LLM
        # integration is more fully implemented
        self._llm_provider = llm_provider

        # Store system prompt in state
        self._update_system_prompt()

    def _update_system_prompt(self) -> None:
        """Update the system prompt based on role and configuration."""
        system_prompt = [f"You are {self._name}, an AI assistant."]

        # Add role information if available
        role = self.role
        if role:
            system_prompt.append(f"Your role is: {role.name}")
            system_prompt.append(f"Role description: {role.description}")

            # Add role instructions
            system_prompt.append(role.get_instructions())

            # Add capabilities
            if role.capabilities:
                capabilities = ", ".join(role.capabilities)
                system_prompt.append(f"Your capabilities include: {capabilities}")

        # Store the combined system prompt in memory
        self._state.memory.add("system_prompt", "\n\n".join(system_prompt))

    def _get_messages_for_llm(
        self, conversation_id: str = "default", limit: int = 10
    ) -> List[MessageProtocol]:
        """Get messages formatted for LLM consumption.

        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of recent messages to include

        Returns:
            List of messages formatted for LLM
        """
        messages: List[MessageProtocol] = []

        # Add system message
        system_prompt = self._state.memory.get("system_prompt", "You are an AI assistant.")
        system_msg = Message.system_message(system_prompt)
        messages.append(cast(MessageProtocol, system_msg))

        # Get conversation history if available
        if isinstance(self._state, ConversationState):
            history = self._state.get_conversation_history(conversation_id, limit)

            # Convert agent messages to standard messages
            for msg_dict in history:
                # Create message based on role
                role = msg_dict.get("role", "user")
                content = msg_dict.get("content", "")
                name = msg_dict.get("name")

                if role == "user":
                    user_msg = Message.user_message(content)
                    messages.append(cast(MessageProtocol, user_msg))
                elif role == "assistant":
                    assistant_msg = Message.assistant_message(content)
                    messages.append(cast(MessageProtocol, assistant_msg))
                elif role == "system":
                    # Skip system messages as we already added our system prompt
                    pass
                elif role == "tool":
                    # Handle tool messages
                    if name and "tool_call_id" in msg_dict:
                        tool_msg = Message.tool_message(content, name, msg_dict["tool_call_id"])
                        messages.append(cast(MessageProtocol, tool_msg))

        return messages

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message and optionally return a response.

        LLMAgent implementation that uses the LLM for generating responses.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Store message in conversation history if using ConversationState
        if isinstance(self._state, ConversationState):
            self._state.add_message(message, conversation_id=message.sender_id)

        # For task assignments, use the base implementation
        if message.message_type.upper() == "TASK_ASSIGNMENT":
            return self._handle_task_assignment(message)

        # If no LLM provider is available, fall back to base implementation
        if not self._llm_provider:
            logger.warning(f"LLMAgent {self._id} has no LLM provider, using base implementation")
            return super().process_message(message)

        try:
            # Create message history for LLM
            messages = self._get_messages_for_llm(conversation_id=message.sender_id, limit=10)

            # Add the incoming message
            user_msg = Message.user_message(
                f"[Message from {message.sender_id}]: {message.content}"
            )
            messages.append(cast(MessageProtocol, user_msg))

            # Get LLM response
            response = self._llm_provider.complete(messages)

            # Create agent message from LLM response
            message_id = getattr(message, "message_id", str(uuid.uuid4()))

            return ResponseMessage(
                self._id,
                message.sender_id,
                response.content or "",
                message_id,
            )
        except Exception as e:
            logger.error(f"Error using LLM to process message: {e}")
            return ErrorMessage(
                self._id,
                message.sender_id,
                f"Failed to process message: {str(e)}",
                "LLM_ERROR",
            )

    def process_task(self) -> TaskStatus:
        """Process the current task using LLM capabilities.

        Returns:
            Updated task status
        """
        task = self._state.current_task
        if not task:
            logger.warning(f"Agent {self._id} has no task to process")
            return TaskStatus.FAILED

        if not self._llm_provider:
            logger.warning(f"LLMAgent {self._id} has no LLM provider, using base implementation")
            return super().process_task()

        try:
            # Create message history for LLM
            messages = self._get_messages_for_llm(limit=5)

            # Add task as a message
            task_msg = (
                f"Task ID: {task.id}\n"
                f"Description: {task.description}\n"
                f"Please complete this task to the best of your abilities."
            )
            user_msg = Message.user_message(task_msg)
            messages.append(cast(MessageProtocol, user_msg))

            # Get LLM response
            response = self._llm_provider.complete(messages)

            # Store response in task metadata
            if not task.metadata:
                task.metadata = {}
            task.metadata["llm_response"] = response.content

            # Mark task as completed
            task.status = TaskStatus.COMPLETED
            logger.info(f"Agent {self._id} completed task {task.id}")

            return TaskStatus.COMPLETED
        except Exception as e:
            logger.error(f"Error using LLM to process task: {e}")
            task.status = TaskStatus.FAILED
            return TaskStatus.FAILED
