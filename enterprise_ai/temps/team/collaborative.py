"""
Collaborative team implementation for Enterprise AI.

This module provides a specialized team class that focuses on collaborative
problem-solving with dynamic tool sharing and coordination among agents.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.agent.message import (
    BroadcastMessage,
    ErrorMessage,
    NotificationMessage,
    create_message,
)
from enterprise_ai.logger import get_logger
from enterprise_ai.team.base import BaseTeam
from enterprise_ai.team.hierarchical import HierarchicalTeam
from enterprise_ai.team.types import (
    CollaborativeTeamProtocol,
    ToolSharingPolicy,
    ToolRoutingStrategy,
    TeamToolAccessInfo,
)
from enterprise_ai.team.tool_sharing import (
    DefaultToolSharingPolicy,
    CapabilityBasedToolRoutingStrategy,
    SimpleToolRoutingStrategy,
    TeamToolRegistry,
    ToolPoolManager,
    execute_tool_with_registry,
)
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult, ToolFailure

logger = get_logger("team.collaborative")


class CollaborativeToolSharingPolicy(ToolSharingPolicy):
    """
    Tool sharing policy optimized for collaborative teams.

    This policy encourages flexible tool sharing based on task needs,
    with minimal restrictions to enable collaborative problem-solving.
    """

    def __init__(
        self,
        restricted_tools: Optional[Set[str]] = None,
        private_tools: Optional[Dict[str, Set[str]]] = None,
    ):
        """
        Initialize a collaborative tool sharing policy.

        Args:
            restricted_tools: Optional set of tool names that cannot be shared
            private_tools: Optional mapping of agent IDs to sets of tools
                          that should remain private
        """
        self._allow_sharing = True
        self._restricted_tools = restricted_tools or set()
        self._private_tools = private_tools or {}
        self._task_based_exemptions: Dict[str, Set[str]] = {}  # task_id -> set of exempt tool names

    @property
    def allow_sharing(self) -> bool:
        """Whether tool sharing is enabled at all."""
        return self._allow_sharing

    def can_share_tool(self, agent_id: str, tool_name: str) -> bool:
        """
        Check if an agent can share a specific tool.

        Args:
            agent_id: ID of the agent that owns the tool
            tool_name: Name of the tool to share

        Returns:
            True if the agent can share the tool, False otherwise
        """
        # Check if tool is generally restricted
        if tool_name in self._restricted_tools:
            # Check for task-based exemptions
            for exempt_tools in self._task_based_exemptions.values():
                if tool_name in exempt_tools:
                    return True
            return False

        # Check if tool is in the agent's private tools
        if agent_id in self._private_tools and tool_name in self._private_tools[agent_id]:
            # Check for task-based exemptions
            for exempt_tools in self._task_based_exemptions.values():
                if tool_name in exempt_tools:
                    return True
            return False

        # By default, sharing is allowed
        return True

    def can_access_tool(self, agent_id: str, tool_name: str, owner_id: str) -> bool:
        """
        Check if an agent can access a tool owned by another agent.

        Args:
            agent_id: ID of the agent requesting access
            tool_name: Name of the tool to access
            owner_id: ID of the agent that owns the tool

        Returns:
            True if the agent can access the tool, False otherwise
        """
        # First check if the owner can share the tool
        if not self.can_share_tool(owner_id, tool_name):
            return False

        # In a collaborative team, we enable broad access by default
        return True

    def get_shareable_tools(self, agent_id: str) -> List[str]:
        """
        Get list of tool names that an agent can share.

        Args:
            agent_id: ID of the agent

        Returns:
            List of shareable tool names (empty list if no tools can be shared)
        """
        # This would need to be implemented with actual tool information,
        # but since we don't track tools in the policy itself, this is a placeholder
        return []

    def add_task_exemption(self, task_id: str, tool_names: List[str]) -> None:
        """
        Add a task-based exemption for restricted or private tools.

        This allows otherwise restricted tools to be shared for a specific task.

        Args:
            task_id: ID of the task
            tool_names: List of tool names to exempt for this task
        """
        if task_id not in self._task_based_exemptions:
            self._task_based_exemptions[task_id] = set()

        self._task_based_exemptions[task_id].update(tool_names)

    def remove_task_exemption(self, task_id: str) -> None:
        """
        Remove a task-based exemption.

        Args:
            task_id: ID of the task
        """
        if task_id in self._task_based_exemptions:
            del self._task_based_exemptions[task_id]


class TaskToolRequirementAnalyzer:
    """
    Analyzes tasks to determine tool requirements.

    This class helps identify which tools are needed for a task
    and which agents can provide them.
    """

    def __init__(self, tool_registry: TeamToolRegistry):
        """
        Initialize a task tool requirement analyzer.

        Args:
            tool_registry: Tool registry to use for capability lookup
        """
        self._tool_registry = tool_registry
        self._task_requirements: Dict[str, Set[str]] = {}  # task_id -> set of required tool names

    def analyze_task(self, task: Task) -> Set[str]:
        """
        Analyze a task to determine required tools.

        Args:
            task: Task to analyze

        Returns:
            Set of required tool names
        """
        required_tools = set()

        # Check task metadata for explicit tool requirements
        if task.metadata:
            # Single required tool
            if "required_tool" in task.metadata:
                required_tools.add(task.metadata["required_tool"])

            # Multiple required tools
            if "required_tools" in task.metadata and isinstance(
                task.metadata["required_tools"], (list, set)
            ):
                required_tools.update(task.metadata["required_tools"])

        # Parse task description for potential tool mentions
        description = task.description.lower()

        # Simple keyword matching for common tool types
        tool_keywords = {
            "search": {"search", "find", "look up", "research"},
            "browser": {"browse", "visit", "website", "web page"},
            "code": {"code", "program", "script", "function", "implement"},
            "file": {"file", "read", "write", "save", "open"},
            "math": {"calculate", "compute", "equation", "math"},
            "database": {"database", "query", "sql", "data store"},
            "api": {"api", "endpoint", "request", "json"},
        }

        for tool_type, keywords in tool_keywords.items():
            if any(keyword in description for keyword in keywords):
                # Add potential tool matches from registry that match this type
                for tool_name in self._tool_registry.available_tools:
                    if tool_type in tool_name.lower():
                        required_tools.add(tool_name)

        # Store requirements for this task
        self._task_requirements[task.id] = required_tools

        return required_tools

    def get_capable_agents(self, task_id: str) -> Dict[str, Set[str]]:
        """
        Get agents capable of handling tools required for a task.

        Args:
            task_id: ID of the task

        Returns:
            Dictionary mapping tool names to sets of capable agent IDs
        """
        result: Dict[str, Set[str]] = {}

        # Get required tools for this task
        required_tools = self._task_requirements.get(task_id, set())

        # For each tool, find agents that can use it
        for tool_name in required_tools:
            agents = self._tool_registry.get_agents_with_tool(tool_name)
            result[tool_name] = set(agents)

        return result

    def clear_task(self, task_id: str) -> None:
        """
        Clear analysis results for a task.

        Args:
            task_id: ID of the task
        """
        if task_id in self._task_requirements:
            del self._task_requirements[task_id]


class CollaborativeTeam(HierarchicalTeam, CollaborativeTeamProtocol):
    """
    Collaborative team with dynamic tool sharing and coordination.

    This specialized team implements dynamic tool pools, collaborative
    problem-solving, and flexible sharing of tools between agents.
    """

    def __init__(
        self,
        team_id: Optional[str] = None,
        name: str = "Collaborative Team",
        manager: Optional[AgentProtocol] = None,
    ) -> None:
        """
        Initialize a collaborative team.

        Args:
            team_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            manager: Team manager agent
        """
        super().__init__(team_id, name, manager)

        # Initialize collaborative components
        self._tool_pool_manager = ToolPoolManager(self._tool_registry)
        self._task_analyzer = TaskToolRequirementAnalyzer(self._tool_registry)

        # Use collaborative tool sharing policy
        self._tool_sharing_policy = cast(DefaultToolSharingPolicy, CollaborativeToolSharingPolicy())

        # Use capability-based routing
        self._tool_routing_strategy = cast(
            SimpleToolRoutingStrategy, CapabilityBasedToolRoutingStrategy({})
        )

        # Track task-specific tool pools
        self._task_pools: Dict[str, str] = {}  # task_id -> pool_name

        logger.info(f"Initialized collaborative team: {self._id} ({self._name})")

    def assign_task(
        self, task: Task, agent_id: Optional[str] = None, team_id: Optional[str] = None
    ) -> bool:
        """
        Assign a task with collaborative tool sharing.

        This method analyzes the task for tool requirements and creates
        a task-specific tool pool when appropriate.

        Args:
            task: Task to assign
            agent_id: Optional ID of agent to assign task to
            team_id: Optional ID of subteam to assign task to

        Returns:
            True if task was assigned, False otherwise
        """
        # First, analyze the task for tool requirements
        required_tools = self._task_analyzer.analyze_task(task)

        # If the task requires tools, create a task-specific pool
        if required_tools:
            # Create a pool name based on task ID
            pool_name = f"task_{task.id}"

            # Create the pool
            success = self._tool_pool_manager.create_pool(pool_name, list(required_tools))

            if success:
                # Track the pool for this task
                self._task_pools[task.id] = pool_name

                # Add capability-based exemptions for this task
                if isinstance(self._tool_sharing_policy, CollaborativeToolSharingPolicy):
                    self._tool_sharing_policy.add_task_exemption(task.id, list(required_tools))

                logger.info(
                    f"Created tool pool '{pool_name}' for task {task.id} "
                    f"with {len(required_tools)} tools"
                )

            # Find agents capable of handling the required tools
            capable_agents = self._task_analyzer.get_capable_agents(task.id)

            # Prioritize an agent that can handle multiple required tools
            if agent_id is None and required_tools:
                # Count how many required tools each agent can handle
                agent_capabilities: Dict[str, int] = {}

                for tool_name, agents in capable_agents.items():
                    for agent in agents:
                        if agent in agent_capabilities:
                            agent_capabilities[agent] += 1
                        else:
                            agent_capabilities[agent] = 1

                # Find the agent with the most capabilities
                if agent_capabilities:
                    max_capabilities = max(agent_capabilities.values())
                    best_agents = [
                        agent_id
                        for agent_id, count in agent_capabilities.items()
                        if count == max_capabilities
                    ]

                    # If there are multiple equally capable agents, prefer one in this team
                    for best_agent in best_agents:
                        if best_agent in self._members:
                            agent_id = best_agent
                            break

                    # If no preference, take the first one
                    if agent_id is None and best_agents:
                        agent_id = best_agents[0]

                    if agent_id:
                        logger.info(
                            f"Selected agent {agent_id} for task {task.id} "
                            f"based on tool capabilities"
                        )

            # If a specific agent is selected, grant them access to the pool
            if agent_id and pool_name in self._tool_pool_manager._pools:
                self._tool_pool_manager.grant_pool_access(pool_name, agent_id)

        # Use the parent class to actually assign the task
        return super().assign_task(task, agent_id, team_id)

    def complete_task(self, task_id: str, status: TaskStatus = TaskStatus.COMPLETED) -> bool:
        """
        Complete a task and clean up associated resources.

        Args:
            task_id: ID of the task
            status: Final status of the task

        Returns:
            True if completion was successful, False otherwise
        """
        # Clean up task-specific tool pool
        if task_id in self._task_pools:
            pool_name = self._task_pools[task_id]
            self._tool_pool_manager.delete_pool(pool_name)
            del self._task_pools[task_id]

        # Remove task exemptions
        if isinstance(self._tool_sharing_policy, CollaborativeToolSharingPolicy):
            self._tool_sharing_policy.remove_task_exemption(task_id)

        # Clean up task analysis
        self._task_analyzer.clear_task(task_id)

        logger.info(f"Completed task {task_id} with status {status.name}")
        return True

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        Process a message with collaborative tool handling.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Extract metadata
        metadata = getattr(message, "metadata", {}) or {}

        # Handle task completion notifications
        if (
            metadata.get("message_type") == "task_update"
            and "task_id" in metadata
            and "status" in metadata
        ):
            task_id = metadata["task_id"]
            status_str = metadata["status"]

            # Check if the task is being marked as completed
            if status_str in ["COMPLETED", "FAILED"]:
                status = TaskStatus.COMPLETED if status_str == "COMPLETED" else TaskStatus.FAILED
                self.complete_task(task_id, status)

        # Handle collaborative tool requests
        if metadata.get("message_type") == "collaborative_tool_request":
            tool_name = metadata.get("tool_name")
            tool_params = metadata.get("tool_params", {})
            task_id = metadata.get("task_id")

            if tool_name and task_id:
                # Check if there's a pool for this task
                pool_name = self._task_pools.get(task_id)

                if pool_name and tool_name in self._tool_pool_manager.get_pool_tools(pool_name):
                    # Grant the requester access to the pool if needed
                    if message.sender_id not in self._tool_pool_manager.get_pool_access(pool_name):
                        self._tool_pool_manager.grant_pool_access(pool_name, message.sender_id)

                        logger.info(
                            f"Granted access to pool '{pool_name}' for agent {message.sender_id}"
                        )

                    # Route the tool request
                    success, agent_id = self.route_tool_request(
                        tool_name, tool_params, message.sender_id
                    )

                    if success and agent_id:
                        # Create a tool request message
                        request_message = create_message(
                            "NOTIFICATION",
                            message.sender_id,
                            agent_id,
                            f"Collaborative request to execute tool {tool_name}",
                            metadata={
                                "message_type": "tool_request",
                                "tool_name": tool_name,
                                "tool_params": tool_params,
                                "task_id": task_id,
                                "collaborative": True,
                            },
                        )

                        # Forward to the appropriate agent
                        if self._manager and agent_id == self._manager.id:
                            return self._manager.process_message(request_message)

                        if agent_id in self._members:
                            return self._members[agent_id].process_message(request_message)

                        # Handle subteam agents
                        if "." in agent_id:
                            team_id, actual_agent_id = agent_id.split(".", 1)

                            subteam = self._subteams.get(team_id)
                            if subteam:
                                # Update metadata to target the specific agent
                                request_metadata = getattr(request_message, "metadata", {}) or {}
                                request_metadata["target_agent"] = actual_agent_id

                                # Create a new message with updated metadata
                                forward_message = create_message(
                                    request_message.message_type,
                                    request_message.sender_id,
                                    team_id,  # Send to the subteam
                                    request_message.content,
                                    metadata=request_metadata,
                                )

                                return subteam.process_message(forward_message)

                # If we couldn't handle the request, return an error
                return ErrorMessage(
                    self._id,
                    message.sender_id,
                    f"Could not find tool {tool_name} in collaborative pool for task {task_id}",
                    "TOOL_NOT_IN_POOL",
                )

        # Use parent implementation for other messages
        return super().process_message(message)

    # Tool pool methods

    def create_tool_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Create a named pool of tools for collaborative use.

        Args:
            pool_name: Name of the tool pool
            tool_names: Names of tools to include in the pool

        Returns:
            True if pool creation was successful, False otherwise
        """
        return self._tool_pool_manager.create_pool(pool_name, tool_names)

    def get_pool_tools(self, pool_name: str) -> List[str]:
        """
        Get the tools in a specific pool.

        Args:
            pool_name: Name of the tool pool

        Returns:
            List of tool names in the pool
        """
        return self._tool_pool_manager.get_pool_tools(pool_name)

    def add_tools_to_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Add tools to an existing pool.

        Args:
            pool_name: Name of the tool pool
            tool_names: Names of tools to add

        Returns:
            True if tools were added successfully, False otherwise
        """
        return self._tool_pool_manager.add_tools_to_pool(pool_name, tool_names)

    def remove_tools_from_pool(self, pool_name: str, tool_names: List[str]) -> bool:
        """
        Remove tools from an existing pool.

        Args:
            pool_name: Name of the tool pool
            tool_names: Names of tools to remove

        Returns:
            True if tools were removed successfully, False otherwise
        """
        return self._tool_pool_manager.remove_tools_from_pool(pool_name, tool_names)

    def grant_pool_access(self, pool_name: str, agent_id: str) -> bool:
        """
        Grant an agent access to a tool pool.

        Args:
            pool_name: Name of the tool pool
            agent_id: ID of the agent to grant access

        Returns:
            True if access was granted successfully, False otherwise
        """
        success = self._tool_pool_manager.grant_pool_access(pool_name, agent_id)

        if success:
            # Notify the agent about access
            agent = None

            # Check if it's the manager
            if self._manager and self._manager.id == agent_id:
                agent = self._manager
            else:
                # Check if it's a team member
                agent = self._members.get(agent_id)

            if agent:
                notification = NotificationMessage(
                    self._id,
                    agent_id,
                    f"You have been granted access to tool pool '{pool_name}'",
                    metadata={
                        "notification_type": "pool_access",
                        "pool_name": pool_name,
                        "tools": self._tool_pool_manager.get_pool_tools(pool_name),
                    },
                )

                agent.process_message(notification)

        return success

    def revoke_pool_access(self, pool_name: str, agent_id: str) -> bool:
        """
        Revoke an agent's access to a tool pool.

        Args:
            pool_name: Name of the tool pool
            agent_id: ID of the agent to revoke access

        Returns:
            True if access was revoked successfully, False otherwise
        """
        success = self._tool_pool_manager.revoke_pool_access(pool_name, agent_id)

        if success:
            # Notify the agent about revocation
            agent = None

            # Check if it's the manager
            if self._manager and self._manager.id == agent_id:
                agent = self._manager
            else:
                # Check if it's a team member
                agent = self._members.get(agent_id)

            if agent:
                notification = NotificationMessage(
                    self._id,
                    agent_id,
                    f"Your access to tool pool '{pool_name}' has been revoked",
                    metadata={
                        "notification_type": "pool_access_revoked",
                        "pool_name": pool_name,
                    },
                )

                agent.process_message(notification)

        return success

    def get_agent_pools(self, agent_id: str) -> List[str]:
        """
        Get the tool pools an agent has access to.

        Args:
            agent_id: ID of the agent

        Returns:
            List of pool names the agent has access to
        """
        return self._tool_pool_manager.get_agent_pools(agent_id)

    # Advanced collaborative methods

    async def execute_collaborative_task(
        self,
        task_id: str,
        tool_sequence: List[Tuple[str, Dict[str, Any]]],
        coordinator_id: str,
    ) -> List[ToolResult]:
        """
        Execute a collaborative task using a sequence of tools.

        This method distributes tool operations across team members
        based on capability and availability.

        Args:
            task_id: ID of the task
            tool_sequence: List of (tool_name, parameters) tuples
            coordinator_id: ID of the agent coordinating the task

        Returns:
            List of tool execution results
        """
        results: List[ToolResult] = []

        # Check if there's a pool for this task
        pool_name = self._task_pools.get(task_id)

        if not pool_name:
            # Create a temporary pool for this task
            pool_name = f"task_{task_id}"
            self.create_tool_pool(pool_name, [tool[0] for tool in tool_sequence])
            self._task_pools[task_id] = pool_name

        # Grant the coordinator access to the pool
        self.grant_pool_access(pool_name, coordinator_id)

        # Execute each tool in the sequence
        for i, (tool_name, parameters) in enumerate(tool_sequence):
            # Ensure the tool is in the pool
            if tool_name not in self.get_pool_tools(pool_name):
                self.add_tools_to_pool(pool_name, [tool_name])

            # Find the best agent for this tool
            agents = self._tool_registry.get_agents_with_tool(tool_name)

            if not agents:
                results.append(ToolFailure(error=f"No agent can execute tool {tool_name}"))
                continue

            # Use the routing strategy to find the best agent
            target_agent_id = self._tool_routing_strategy.get_agent_for_tool(
                tool_name, coordinator_id
            )

            # If no specific agent, use the first available
            if not target_agent_id and agents:
                target_agent_id = agents[0]

            # Execute the tool
            if target_agent_id:
                # Create a collaborative tool request message
                request_message = create_message(
                    "NOTIFICATION",
                    coordinator_id,
                    target_agent_id,
                    f"Collaborative request to execute tool {tool_name} (step {i + 1}/{len(tool_sequence)})",
                    metadata={
                        "message_type": "tool_request",
                        "tool_name": tool_name,
                        "tool_params": parameters,
                        "task_id": task_id,
                        "collaborative": True,
                        "step": i + 1,
                        "total_steps": len(tool_sequence),
                    },
                )

                # Send to the agent through the appropriate channel
                agent = None

                # Check if it's the manager
                if self._manager and self._manager.id == target_agent_id:
                    agent = self._manager
                else:
                    # Check if it's a team member
                    agent = self._members.get(target_agent_id)

                if agent:
                    response = agent.process_message(request_message)

                    if response:
                        # Extract tool result from response
                        metadata = getattr(response, "metadata", {}) or {}

                        if "tool_result" in metadata:
                            tool_result = metadata["tool_result"]

                            # Convert dictionary result to ToolResult object
                            if isinstance(tool_result, dict):
                                result = ToolResult(
                                    output=tool_result.get("output"),
                                    error=tool_result.get("error"),
                                    base64_image=tool_result.get("base64_image"),
                                    system=tool_result.get("system"),
                                )

                                results.append(result)
                                continue

                        # If no structured result, use content as output
                        results.append(ToolResult(output=response.content))
                        continue

            # If we reach here, execution failed
            results.append(ToolFailure(error=f"Failed to execute tool {tool_name}"))

        return results

    def get_tool_sharing_policy(self) -> ToolSharingPolicy:
        """
        Get the tool sharing policy for this team.

        Returns:
            Tool sharing policy
        """
        return self._tool_sharing_policy

    def set_tool_sharing_policy(self, policy: ToolSharingPolicy) -> None:
        """
        Set the tool sharing policy for this team.

        Args:
            policy: New tool sharing policy
        """
        self._tool_sharing_policy = cast(DefaultToolSharingPolicy, policy)

    def get_tool_routing_strategy(self) -> ToolRoutingStrategy:
        """
        Get the tool routing strategy for this team.

        Returns:
            Tool routing strategy
        """
        return self._tool_routing_strategy

    def set_tool_routing_strategy(self, strategy: ToolRoutingStrategy) -> None:
        """
        Set the tool routing strategy for this team.

        Args:
            strategy: New tool routing strategy
        """
        self._tool_routing_strategy = cast(SimpleToolRoutingStrategy, strategy)

    async def execute_tool_with_fallback(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        requester_id: str,
        max_attempts: int = 3,
    ) -> ToolResult:
        """
        Execute a tool with collaborative fallback mechanism.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool execution
            max_attempts: Maximum number of attempts before failing

        Returns:
            Result of the tool execution
        """
        # Try primary execution
        result = await super().execute_tool_with_fallback(
            tool_name, parameters, requester_id, max_attempts
        )

        # If successful, return the result
        if not result.error:
            return result

        # If all attempts failed, try collaborative execution
        # Broadcast a request for help
        help_request = BroadcastMessage(  # noqa: F841
            self._id,
            f"Collaborative help needed for tool {tool_name}",
            metadata={
                "broadcast_type": "collaborative_help",
                "tool_name": tool_name,
                "tool_params": parameters,
                "requester_id": requester_id,
            },
        )

        responses = self.broadcast_message(
            "BROADCAST", f"Collaborative help needed for tool {tool_name}", self._id
        )

        # Check if any agent offered to help
        for response in responses:
            metadata = getattr(response, "metadata", {}) or {}

            if metadata.get("response_type") == "collaborative_help_offer":
                helper_id = response.sender_id

                # Create a direct request to the helper
                help_message = create_message(
                    "NOTIFICATION",
                    requester_id,
                    helper_id,
                    f"Direct request to execute tool {tool_name}",
                    metadata={
                        "message_type": "tool_request",
                        "tool_name": tool_name,
                        "tool_params": parameters,
                        "collaborative": True,
                    },
                )

                # Forward to the helper
                helper_agent = None

                # Check if it's the manager
                if self._manager and self._manager.id == helper_id:
                    helper_agent = self._manager
                else:
                    # Check if it's a team member
                    helper_agent = self._members.get(helper_id)

                if helper_agent:
                    helper_response = helper_agent.process_message(help_message)

                    if helper_response:
                        # Extract tool result from response
                        helper_metadata = getattr(helper_response, "metadata", {}) or {}

                        if "tool_result" in helper_metadata:
                            tool_result = helper_metadata["tool_result"]

                            # Convert dictionary result to ToolResult object
                            if isinstance(tool_result, dict):
                                return ToolResult(
                                    output=tool_result.get("output"),
                                    error=tool_result.get("error"),
                                    base64_image=tool_result.get("base64_image"),
                                    system=tool_result.get("system"),
                                )

                        # If no structured result, use content as output
                        return ToolResult(output=helper_response.content)

        # If we've exhausted all options, return the original error
        return result

    async def execute_multi_tool_task(
        self,
        tool_sequence: List[Tuple[str, Dict[str, Any]]],
        requester_id: str,
    ) -> List[ToolResult]:
        """
        Execute a sequence of tool operations with collaborative optimization.

        Args:
            tool_sequence: List of (tool_name, parameters) tuples
            requester_id: ID of the agent requesting the tool executions

        Returns:
            List of tool execution results
        """
        # Create a temporary task ID for this operation
        task_id = f"multi_tool_{uuid.uuid4()}"

        # Execute as a collaborative task
        return await self.execute_collaborative_task(task_id, tool_sequence, requester_id)

    def get_status(self) -> Dict[str, Any]:
        """
        Get team status summary including collaborative features.

        Returns:
            Dictionary with status information
        """
        status = super().get_status()

        # Add collaborative information
        status["collaborative"] = {
            "tool_pools": {
                pool_name: {
                    "tools": self._tool_pool_manager.get_pool_tools(pool_name),
                    "agents": self._tool_pool_manager.get_pool_access(pool_name),
                }
                for pool_name in self._tool_pool_manager._pools
            },
            "task_pools": self._task_pools,
        }

        return status
