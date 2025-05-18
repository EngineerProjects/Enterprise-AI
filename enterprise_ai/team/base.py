"""
Base team implementation for Enterprise AI.

This module provides the foundational team class that implements
the TeamProtocol defined in types.py, with support for tool sharing
and delegation between team members.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from enterprise_ai.agent.messaging.message import (
    BaseAgentMessage,
    BroadcastMessage,
    ErrorMessage,
    NotificationMessage,
    create_message,
)
from enterprise_ai.agent.core.types import AgentProtocol, AgentMessage, Task, TaskStatus
from enterprise_ai.logger import get_logger
from enterprise_ai.team.types import (
    TeamProtocol,
    ToolSharingPolicy,
    ToolRoutingStrategy,
    TeamToolAccessInfo,
)
from enterprise_ai.team.tool_sharing import (
    DefaultToolSharingPolicy,
    SimpleToolRoutingStrategy,
    TeamToolRegistry,
    execute_tool_with_registry,
)
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult, ToolFailure

logger = get_logger("team.base")


class BaseTeam(TeamProtocol):
    """Base implementation of a team.

    This class provides a foundation for team implementations with
    basic functionality for organizing agents and handling tasks,
    along with tool sharing capabilities.
    """

    def __init__(
        self,
        team_id: Optional[str] = None,
        name: str = "Team",
        manager: Optional[AgentProtocol] = None,
    ) -> None:
        """Initialize a base team.

        Args:
            team_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            manager: Team manager agent
        """
        self._id = team_id or str(uuid.uuid4())
        self._name = name
        self._manager = manager
        self._members: Dict[str, AgentProtocol] = {}
        self._member_roles: Dict[str, str] = {}  # Maps agent_id to role
        self._created_at = time.time()

        # Initialize tool sharing components
        self._tool_registry = TeamToolRegistry()
        self._tool_sharing_policy = DefaultToolSharingPolicy()
        self._tool_routing_strategy = SimpleToolRoutingStrategy({})

        logger.info(f"Initialized team: {self._id} ({self._name})")

    @property
    def id(self) -> str:
        """Get team ID.

        Returns:
            Team ID
        """
        return self._id

    @property
    def name(self) -> str:
        """Get team name.

        Returns:
            Team name
        """
        return self._name

    @property
    def manager(self) -> AgentProtocol:
        """Get team manager agent.

        Returns:
            Manager agent

        Raises:
            RuntimeError: If no manager is assigned
        """
        if not self._manager:
            raise RuntimeError(f"Team {self._id} has no manager assigned")
        return self._manager

    @manager.setter
    def manager(self, agent: AgentProtocol) -> None:
        """Set team manager.

        Args:
            agent: Agent to assign as manager
        """
        self._manager = agent
        logger.info(f"Assigned manager to team {self._id}: {agent.id} ({agent.name})")

    @property
    def members(self) -> Dict[str, AgentProtocol]:
        """Get team members (excluding manager).

        Returns:
            Dictionary of member agents
        """
        return self._members.copy()

    def add_member(self, agent: AgentProtocol, role: Optional[str] = None) -> bool:
        """Add a member to the team.

        Args:
            agent: Agent to add
            role: Optional role for the agent

        Returns:
            True if agent was added, False if already a member
        """
        if agent.id in self._members:
            logger.warning(f"Agent {agent.id} is already a member of team {self._id}")
            return False

        self._members[agent.id] = agent

        if role:
            self._member_roles[agent.id] = role
            logger.info(
                f"Added agent {agent.id} ({agent.name}) to team {self._id} with role {role}"
            )
        else:
            logger.info(f"Added agent {agent.id} ({agent.name}) to team {self._id}")

        return True

    def remove_member(self, agent_id: str) -> bool:
        """Remove a member from the team.

        Args:
            agent_id: ID of agent to remove

        Returns:
            True if agent was removed, False if not a member
        """
        if agent_id not in self._members:
            logger.warning(f"Agent {agent_id} is not a member of team {self._id}")
            return False

        del self._members[agent_id]
        if agent_id in self._member_roles:
            del self._member_roles[agent_id]

        logger.info(f"Removed agent {agent_id} from team {self._id}")
        return True

    def get_member(self, agent_id: str) -> Optional[AgentProtocol]:
        """Get a team member by ID.

        Args:
            agent_id: ID of the agent to get

        Returns:
            Agent or None if not found
        """
        return self._members.get(agent_id)

    def get_member_role(self, agent_id: str) -> Optional[str]:
        """Get the role of a team member.

        Args:
            agent_id: ID of the agent

        Returns:
            Role or None if not found
        """
        return self._member_roles.get(agent_id)

    def set_member_role(self, agent_id: str, role: str) -> bool:
        """Set the role of a team member.

        Args:
            agent_id: ID of the agent
            role: Role to assign

        Returns:
            True if role was set, False if agent not a member
        """
        if agent_id not in self._members:
            logger.warning(f"Agent {agent_id} is not a member of team {self._id}")
            return False

        self._member_roles[agent_id] = role
        logger.info(f"Set role {role} for agent {agent_id} in team {self._id}")
        return True

    def get_members_by_role(self, role: str) -> Dict[str, AgentProtocol]:
        """Get team members with a specific role.

        Args:
            role: Role to filter by

        Returns:
            Dictionary of matching members
        """
        return {
            agent_id: agent
            for agent_id, agent in self._members.items()
            if self._member_roles.get(agent_id) == role
        }

    def assign_task(self, task: Task, agent_id: Optional[str] = None) -> bool:
        """Assign a task to a team member or let manager decide.

        Args:
            task: Task to assign
            agent_id: Optional ID of agent to assign task to

        Returns:
            True if task was assigned, False otherwise
        """
        if agent_id:
            # Direct assignment to specific agent
            if agent_id not in self._members:
                logger.warning(f"Agent {agent_id} is not a member of team {self._id}")
                return False

            success = self._members[agent_id].assign_task(task)
            if success:
                logger.info(f"Assigned task {task.id} to agent {agent_id} in team {self._id}")
            return success

        # Check if the task has a required tool capability
        if task.metadata and "required_tool" in task.metadata:
            required_tool = task.metadata["required_tool"]
            capable_agents = self.find_agents_by_tool_capability(required_tool)

            for capable_agent_id in capable_agents:
                if capable_agent_id in self._members:
                    success = self._members[capable_agent_id].assign_task(task)
                    if success:
                        logger.info(
                            f"Assigned task {task.id} to agent {capable_agent_id} "
                            f"based on tool capability"
                        )
                        return True

        # Let manager decide task assignment
        if self._manager:
            # For now, we simply assign to manager
            # A more sophisticated implementation would have the manager
            # decide which team member to assign the task to
            success = self._manager.assign_task(task)
            if success:
                logger.info(f"Assigned task {task.id} to manager of team {self._id}")
            return success

        logger.warning(f"Cannot assign task {task.id}: team {self._id} has no manager")
        return False

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message sent to the team.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Extract metadata
        metadata = getattr(message, "metadata", {}) or {}

        # Check for tool-related messages
        if metadata.get("message_type") == "tool_request":
            tool_name = metadata.get("tool_name")
            tool_params = metadata.get("tool_params", {})

            if tool_name:
                success, target_agent_id = self.route_tool_request(
                    tool_name, tool_params, message.sender_id
                )

                if success and target_agent_id:
                    # Forward the message to the target agent
                    agent = self._members.get(target_agent_id)
                    if agent:
                        return agent.process_message(message)

                    # Special case for manager
                    if self._manager and target_agent_id == self._manager.id:
                        return self._manager.process_message(message)

                # If we couldn't route, return an error
                return ErrorMessage(
                    self._id,
                    message.sender_id,
                    f"No agent available to handle tool {tool_name}",
                    "TOOL_UNAVAILABLE",
                )

        # Check if message targets a specific member
        target_agent_id = metadata.get("target_agent")
        if target_agent_id:
            if target_agent_id in self._members:
                logger.debug(f"Routing message to team member {target_agent_id}")
                return self._members[target_agent_id].process_message(message)
            else:
                logger.warning(f"Target agent {target_agent_id} not found in team {self._id}")
                return ErrorMessage(
                    self._id,
                    message.sender_id,
                    f"Agent {target_agent_id} not found in team {self._id}",
                    "AGENT_NOT_FOUND",
                )

        # Default to routing to manager
        if self._manager:
            logger.debug(f"Routing message to team manager {self._manager.id}")
            return self._manager.process_message(message)

        logger.warning(f"Cannot process message: team {self._id} has no manager")
        return ErrorMessage(
            self._id,
            message.sender_id,
            f"Team {self._id} has no manager to process message",
            "NO_MANAGER",
        )

    def broadcast_message(
        self, message_type: str, content: str, sender_id: str
    ) -> List[AgentMessage]:
        """Broadcast a message to all team members.

        Args:
            message_type: Type of message
            content: Message content
            sender_id: ID of sender

        Returns:
            List of response messages
        """
        responses: List[AgentMessage] = []

        # Create broadcast message
        broadcast = BroadcastMessage(
            sender_id=sender_id,
            content=content,
            metadata={"team_id": self._id, "broadcast_type": message_type},
        )

        # Send to manager
        if self._manager:
            manager_response = self._manager.process_message(broadcast)
            if manager_response:
                responses.append(manager_response)

        # Send to all members
        for agent_id, agent in self._members.items():
            member_response = agent.process_message(broadcast)
            if member_response:
                responses.append(member_response)

        logger.info(f"Broadcast message to team {self._id}: {len(responses)} responses")
        return responses

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary.

        Returns:
            Dictionary with status information
        """
        status = {
            "id": self._id,
            "name": self._name,
            "created_at": self._created_at,
            "uptime": time.time() - self._created_at,
            "member_count": len(self._members),
            "has_manager": self._manager is not None,
        }

        if self._manager:
            status["manager"] = {
                "id": self._manager.id,
                "name": self._manager.name,
            }

        status["members"] = [
            {
                "id": agent.id,
                "name": agent.name,
                "role": self._member_roles.get(agent.id, "member"),
            }
            for agent in self._members.values()
        ]

        # Add tool-related information
        status["tools"] = {
            "total_tools": len(self._tool_registry._tool_owners),
            "tools_by_agent": self.get_available_tools(),
        }

        return status

    # Tool-related methods

    def get_available_tools(self) -> Dict[str, List[str]]:
        """
        Get all tools available across the team.

        Returns:
            A dictionary mapping agent IDs to lists of available tool names
        """
        return self._tool_registry.available_tools

    def route_tool_request(
        self, tool_name: str, parameters: Dict[str, Any], requester_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Route a tool request to the appropriate agent.

        Args:
            tool_name: Name of the requested tool
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool

        Returns:
            A tuple of (success, agent_id) where agent_id is the agent
            that will handle the request if successful
        """
        # Use the routing strategy to find the appropriate agent
        agent_id = self._tool_routing_strategy.get_agent_for_tool(tool_name, requester_id)

        if not agent_id:
            logger.warning(f"No agent found for tool {tool_name} requested by {requester_id}")
            return False, None

        # Verify that the agent exists in the team
        if agent_id == self._manager.id if self._manager else False:
            return True, agent_id

        if agent_id in self._members:
            return True, agent_id

        logger.warning(f"Agent {agent_id} not found in team {self._id}")
        return False, None

    async def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], requester_id: str
    ) -> ToolResult:
        """
        Execute a tool using the appropriate team member.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool execution

        Returns:
            Result of the tool execution
        """
        # First try to execute directly through the registry
        try:
            return await execute_tool_with_registry(
                self._tool_registry, tool_name, parameters, requester_id
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} directly: {str(e)}")

        # If direct execution fails, try routing to an agent
        success, agent_id = self.route_tool_request(tool_name, parameters, requester_id)

        if not success or not agent_id:
            return ToolFailure(error=f"No agent available to execute tool {tool_name}")

        # Get the agent
        agent = (
            self._manager
            if self._manager and agent_id == self._manager.id
            else self._members.get(agent_id)
        )

        if not agent:
            return ToolFailure(error=f"Agent {agent_id} not found in team {self._id}")

        # Execute the tool through the agent
        try:
            # Create a message to the agent with a request to execute the tool
            message = create_message(
                "NOTIFICATION",
                requester_id,
                agent_id,
                f"Request to execute tool {tool_name}",
                metadata={
                    "message_type": "tool_execution",
                    "tool_name": tool_name,
                    "tool_params": parameters,
                    "request_id": str(uuid.uuid4()),
                },
            )

            # Send the message and wait for response
            response = agent.process_message(message)

            if not response:
                return ToolFailure(error=f"No response from agent {agent_id} for tool {tool_name}")

            # Extract tool result from response
            metadata = getattr(response, "metadata", {}) or {}

            if "tool_result" in metadata:
                tool_result = metadata["tool_result"]

                # Convert dictionary result to ToolResult object
                if isinstance(tool_result, dict):
                    if "error" in tool_result and tool_result["error"]:
                        return ToolFailure(error=tool_result["error"])

                    return ToolResult(
                        output=tool_result.get("output"),
                        error=tool_result.get("error"),
                        base64_image=tool_result.get("base64_image"),
                        system=tool_result.get("system"),
                    )

            # If no structured result, use content as output
            return ToolResult(output=response.content)

        except Exception as e:
            logger.error(f"Error executing tool {tool_name} through agent: {str(e)}")
            return ToolFailure(error=f"Tool execution failed: {str(e)}")

    def share_tool(self, tool_name: str, owner_id: str, target_id: Optional[str] = None) -> bool:
        """
        Share a tool with another team member or the whole team.

        Args:
            tool_name: Name of the tool to share
            owner_id: ID of the agent that owns the tool
            target_id: ID of the target agent, or None for team-wide sharing

        Returns:
            True if sharing was successful, False otherwise
        """
        # Check if the owner can share the tool
        if not self._tool_sharing_policy.can_share_tool(owner_id, tool_name):
            logger.warning(f"Agent {owner_id} not allowed to share tool {tool_name}")
            return False

        # Share with a specific agent
        if target_id:
            # Verify the target agent exists
            if target_id not in self._members and (
                not self._manager or target_id != self._manager.id
            ):
                logger.warning(f"Target agent {target_id} not found in team {self._id}")
                return False

            # Check if the target can access the tool
            if not self._tool_sharing_policy.can_access_tool(target_id, tool_name, owner_id):
                logger.warning(f"Agent {target_id} not allowed to access tool {tool_name}")
                return False

            # Share the tool
            return self._tool_registry.share_tool(tool_name, owner_id, target_id)

        # Share with all team members
        success = True

        # Share with manager
        if self._manager and self._manager.id != owner_id:
            if self._tool_sharing_policy.can_access_tool(self._manager.id, tool_name, owner_id):
                success = success and self._tool_registry.share_tool(
                    tool_name, owner_id, self._manager.id
                )

        # Share with team members
        for member_id in self._members:
            if member_id != owner_id:
                if self._tool_sharing_policy.can_access_tool(member_id, tool_name, owner_id):
                    result = self._tool_registry.share_tool(tool_name, owner_id, member_id)
                    success = success and result

        return success

    def revoke_tool_access(
        self, tool_name: str, owner_id: str, target_id: Optional[str] = None
    ) -> bool:
        """
        Revoke tool access from a team member or the whole team.

        Args:
            tool_name: Name of the tool to revoke access to
            owner_id: ID of the agent that owns the tool
            target_id: ID of the target agent, or None for team-wide revocation

        Returns:
            True if revocation was successful, False otherwise
        """
        # Revoke from a specific agent
        if target_id:
            return self._tool_registry.revoke_access(tool_name, owner_id, target_id)

        # Revoke from all team members
        success = True

        # Revoke from manager
        if self._manager and self._manager.id != owner_id:
            success = success and self._tool_registry.revoke_access(
                tool_name, owner_id, self._manager.id
            )

        # Revoke from team members
        for member_id in self._members:
            if member_id != owner_id:
                result = self._tool_registry.revoke_access(tool_name, owner_id, member_id)
                success = success and result

        return success

    def find_agents_by_tool_capability(self, tool_name: str) -> List[str]:
        """
        Find agents that have capability to use a specific tool.

        Args:
            tool_name: Name of the tool to search for

        Returns:
            List of agent IDs that can use the specified tool
        """
        return self._tool_registry.get_agents_with_tool(tool_name)

    def get_tool_access_info(self) -> TeamToolAccessInfo:
        """
        Get information about tool access within the team.

        Returns:
            TeamToolAccessInfo with details about tool access
        """
        return self._tool_registry

    def register_team_tool(self, tool: BaseTool, owner_id: str) -> bool:
        """
        Register a tool with the team.

        Args:
            tool: Tool to register
            owner_id: ID of the agent that owns the tool

        Returns:
            True if registration was successful, False otherwise
        """
        # Verify the owner exists
        if owner_id not in self._members and (not self._manager or owner_id != self._manager.id):
            logger.warning(f"Owner agent {owner_id} not found in team {self._id}")
            return False

        # Register the tool
        success = self._tool_registry.register_tool(tool, owner_id)

        if success:
            # Update the routing strategy
            tool_map = getattr(self._tool_routing_strategy, "_tool_map", {})
            if not tool_map:
                tool_map = {}

            if tool.name not in tool_map:
                tool_map[tool.name] = []

            if owner_id not in tool_map[tool.name]:
                tool_map[tool.name].append(owner_id)

            # If the strategy has an update method, use it
            if hasattr(self._tool_routing_strategy, "update_tool_mapping"):
                self._tool_routing_strategy.update_tool_mapping(tool.name, tool_map[tool.name])

            # Notify team members about the new tool
            notification = NotificationMessage(  # noqa: F841
                self._id,
                None,  # Broadcast to all members
                f"New tool registered: {tool.name}",
                metadata={
                    "notification_type": "tool_registration",
                    "tool_name": tool.name,
                    "owner_id": owner_id,
                    "description": tool.description,
                },
            )

            self.broadcast_message("NOTIFICATION", f"New tool registered: {tool.name}", self._id)

        return success

    def unregister_team_tool(self, tool_name: str, owner_id: str) -> bool:
        """
        Unregister a tool from the team.

        Args:
            tool_name: Name of the tool to unregister
            owner_id: ID of the agent that owns the tool

        Returns:
            True if unregistration was successful, False otherwise
        """
        # Unregister the tool
        success = self._tool_registry.unregister_tool(tool_name, owner_id)

        if success:
            # Update the routing strategy
            tool_map = getattr(self._tool_routing_strategy, "_tool_map", {})
            if tool_map and tool_name in tool_map:
                if owner_id in tool_map[tool_name]:
                    tool_map[tool_name].remove(owner_id)

                # If the strategy has an update method, use it
                if hasattr(self._tool_routing_strategy, "update_tool_mapping"):
                    self._tool_routing_strategy.update_tool_mapping(tool_name, tool_map[tool_name])

            # Notify team members about the tool removal
            self.broadcast_message("NOTIFICATION", f"Tool unregistered: {tool_name}", self._id)

        return success

    async def execute_tool_with_fallback(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        requester_id: str,
        max_attempts: int = 3,
    ) -> ToolResult:
        """
        Execute a tool with fallback mechanism.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool execution
            max_attempts: Maximum number of attempts before failing

        Returns:
            Result of the tool execution
        """
        # First attempt - direct execution
        result = await self.execute_tool(tool_name, parameters, requester_id)

        # If successful, return the result
        if not result.error:
            return result

        # Otherwise, try fallbacks
        attempts = 1
        tried_agents = set()

        while attempts < max_attempts:
            # Get the agent that handled the previous attempt
            success, previous_agent_id = self.route_tool_request(
                tool_name, parameters, requester_id
            )

            if success and previous_agent_id:
                tried_agents.add(previous_agent_id)

            # Get a fallback agent
            agent_id = self._tool_routing_strategy.get_fallback_agent(tool_name, requester_id)

            # If no fallback or we've already tried this agent, break
            if not agent_id or agent_id in tried_agents:
                break

            # Try executing with the fallback agent
            result = await self.execute_tool(tool_name, parameters, requester_id)

            # If successful, return the result
            if not result.error:
                return result

            # Otherwise, continue with more fallbacks
            attempts += 1
            tried_agents.add(agent_id)

        # If all attempts failed, return the last error
        return result

    async def execute_multi_tool_task(
        self,
        tool_sequence: List[Tuple[str, Dict[str, Any]]],
        requester_id: str,
    ) -> List[ToolResult]:
        """
        Execute a sequence of tool operations.

        Args:
            tool_sequence: List of (tool_name, parameters) tuples
            requester_id: ID of the agent requesting the tool executions

        Returns:
            List of tool execution results
        """
        results = []

        for tool_name, parameters in tool_sequence:
            result = await self.execute_tool_with_fallback(tool_name, parameters, requester_id)
            results.append(result)

            # If a tool fails and it's not the last one, consider stopping
            if result.error and len(results) < len(tool_sequence):
                logger.warning(f"Tool {tool_name} failed in sequence, continuing execution")

        return results
