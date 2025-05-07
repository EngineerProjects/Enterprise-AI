"""
Hierarchical team implementation for Enterprise AI.

This module provides a hierarchical team class that extends BaseTeam
with support for nested subteams, creating organizational structures
with hierarchical tool sharing and delegation.
"""

import asyncio
import time
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
from enterprise_ai.team.types import (
    TeamProtocol,
    TeamToolAccessInfo,
    ToolSharingPolicy,
    ToolRoutingStrategy,
)
from enterprise_ai.team.tool_sharing import (
    HierarchicalToolSharingPolicy,
    SimpleToolRoutingStrategy,
    TeamToolRegistry,
)
from enterprise_ai.tool.core.base import BaseTool
from enterprise_ai.tool.core.result import ToolResult, ToolFailure

logger = get_logger("team.hierarchical")


class HierarchicalTeamToolRoutingStrategy(ToolRoutingStrategy):
    """
    Tool routing strategy for hierarchical teams.

    This strategy routes tool requests through the team hierarchy,
    checking parent and child teams for tool capabilities.
    """

    def __init__(
        self,
        team_hierarchy: Dict[str, List[str]],  # team_id -> list of subteam_ids
        tool_providers: Dict[str, List[str]],  # tool_name -> list of team_ids
        parent_team_map: Dict[str, str],  # team_id -> parent_team_id
    ):
        """
        Initialize a hierarchical tool routing strategy.

        Args:
            team_hierarchy: Mapping of team IDs to lists of subteam IDs
            tool_providers: Mapping of tool names to lists of team IDs
            parent_team_map: Mapping of team IDs to parent team IDs
        """
        self._team_hierarchy = team_hierarchy
        self._tool_providers = tool_providers
        self._parent_team_map = parent_team_map
        self._agent_to_team_map: Dict[str, str] = {}  # agent_id -> team_id
        self._team_tools: Dict[
            str, Dict[str, List[str]]
        ] = {}  # team_id -> {tool_name -> [agent_ids]}

    def register_agent(self, agent_id: str, team_id: str) -> None:
        """
        Register an agent with a team.

        Args:
            agent_id: ID of the agent
            team_id: ID of the team the agent belongs to
        """
        self._agent_to_team_map[agent_id] = team_id

    def register_tool(self, tool_name: str, team_id: str, agent_id: str) -> None:
        """
        Register a tool with a team and agent.

        Args:
            tool_name: Name of the tool
            team_id: ID of the team
            agent_id: ID of the agent that provides the tool
        """
        # Update tool providers
        if tool_name not in self._tool_providers:
            self._tool_providers[tool_name] = []

        if team_id not in self._tool_providers[tool_name]:
            self._tool_providers[tool_name].append(team_id)

        # Update team tools
        if team_id not in self._team_tools:
            self._team_tools[team_id] = {}

        if tool_name not in self._team_tools[team_id]:
            self._team_tools[team_id][tool_name] = []

        if agent_id not in self._team_tools[team_id][tool_name]:
            self._team_tools[team_id][tool_name].append(agent_id)

    def get_agent_for_tool(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get the agent ID that should handle a specific tool request.

        This method looks through the team hierarchy to find the best agent
        to handle a tool request, considering:
        1. Agents in the same team as the requester
        2. Agents in parent teams (higher in hierarchy)
        3. Agents in subteams (lower in hierarchy)

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the agent that should handle the request, or None if no suitable agent
        """
        # First, check if the requester can handle the tool themselves
        requester_team_id = self._agent_to_team_map.get(requester_id)
        if requester_team_id and requester_team_id in self._team_tools:
            if tool_name in self._team_tools[requester_team_id]:
                if requester_id in self._team_tools[requester_team_id][tool_name]:
                    return requester_id

        # Next, look in the same team as the requester
        if requester_team_id and requester_team_id in self._team_tools:
            if tool_name in self._team_tools[requester_team_id]:
                agents = self._team_tools[requester_team_id][tool_name]
                if agents:
                    return agents[0]  # Return the first available agent

        # Then, look in parent teams
        current_team_id = requester_team_id
        while current_team_id and current_team_id in self._parent_team_map:
            parent_team_id = self._parent_team_map[current_team_id]

            if parent_team_id in self._team_tools and tool_name in self._team_tools[parent_team_id]:
                agents = self._team_tools[parent_team_id][tool_name]
                if agents:
                    return agents[0]  # Return the first available agent

            current_team_id = parent_team_id

        # Finally, look in subteams
        if requester_team_id and requester_team_id in self._team_hierarchy:
            for subteam_id in self._team_hierarchy[requester_team_id]:
                if subteam_id in self._team_tools and tool_name in self._team_tools[subteam_id]:
                    agents = self._team_tools[subteam_id][tool_name]
                    if agents:
                        return agents[0]  # Return the first available agent

                # Recursively check subteam's subteams
                subteam_agent = self._check_subteams_recursive(subteam_id, tool_name, visited=set())
                if subteam_agent:
                    return subteam_agent

        # No suitable agent found
        return None

    def _check_subteams_recursive(
        self, team_id: str, tool_name: str, visited: Set[str]
    ) -> Optional[str]:
        """
        Recursively check subteams for a tool provider.

        Args:
            team_id: ID of the team to check
            tool_name: Name of the tool to find
            visited: Set of already visited team IDs

        Returns:
            ID of an agent that can provide the tool, or None if not found
        """
        # Avoid cycles
        if team_id in visited:
            return None
        visited.add(team_id)

        # Check if this team has the tool
        if team_id in self._team_tools and tool_name in self._team_tools[team_id]:
            agents = self._team_tools[team_id][tool_name]
            if agents:
                return agents[0]  # Return the first available agent

        # Check subteams
        if team_id in self._team_hierarchy:
            for subteam_id in self._team_hierarchy[team_id]:
                agent = self._check_subteams_recursive(subteam_id, tool_name, visited)
                if agent:
                    return agent

        return None

    def get_fallback_agent(self, tool_name: str, requester_id: str) -> Optional[str]:
        """
        Get a fallback agent if primary agent is unavailable.

        Args:
            tool_name: Name of the requested tool
            requester_id: ID of the agent making the request

        Returns:
            ID of the fallback agent, or None if no fallback available
        """
        # Get the primary agent
        primary_agent = self.get_agent_for_tool(tool_name, requester_id)

        # If no primary agent, no fallback either
        if not primary_agent:
            return None

        # Find the team of the primary agent
        primary_team_id = self._agent_to_team_map.get(primary_agent)
        if not primary_team_id:
            return None

        # Look for another agent in the same team
        if primary_team_id in self._team_tools and tool_name in self._team_tools[primary_team_id]:
            agents = [
                agent_id
                for agent_id in self._team_tools[primary_team_id][tool_name]
                if agent_id != primary_agent
            ]
            if agents:
                return agents[0]  # Return the first available agent

        # Look in parent teams
        current_team_id = primary_team_id
        while current_team_id and current_team_id in self._parent_team_map:
            parent_team_id = self._parent_team_map[current_team_id]

            if parent_team_id in self._team_tools and tool_name in self._team_tools[parent_team_id]:
                agents = self._team_tools[parent_team_id][tool_name]
                if agents:
                    return agents[0]  # Return the first available agent

            current_team_id = parent_team_id

        # No fallback found
        return None

    def prioritize_agents_for_tool(self, tool_name: str) -> List[str]:
        """
        Get prioritized list of agents that can handle a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            List of agent IDs in priority order
        """
        agents = []

        # Collect agents from all teams that provide this tool
        for team_id, tools in self._team_tools.items():
            if tool_name in tools:
                agents.extend(tools[tool_name])

        return agents


class HierarchicalTeam(BaseTeam):
    """Hierarchical team with support for nested subteams.

    This class extends BaseTeam to support organizational hierarchies
    with teams containing other teams, enabling complex organizational
    structures with delegation across multiple levels and hierarchical
    tool sharing.
    """

    def __init__(
        self,
        team_id: Optional[str] = None,
        name: str = "Hierarchical Team",
        manager: Optional[AgentProtocol] = None,
    ) -> None:
        """Initialize a hierarchical team.

        Args:
            team_id: Optional unique identifier (generated if not provided)
            name: Human-readable name
            manager: Team manager agent
        """
        super().__init__(team_id, name, manager)
        self._subteams: Dict[str, TeamProtocol] = {}

        # Initialize hierarchical tool sharing policy
        manager_ids = {self._manager.id} if self._manager else set()
        self._tool_sharing_policy = HierarchicalToolSharingPolicy(manager_ids=manager_ids)

        # Initialize hierarchical tool routing strategy
        self._hierarchical_routing_strategy = HierarchicalTeamToolRoutingStrategy(
            team_hierarchy={},
            tool_providers={},
            parent_team_map={},
        )

        # Use the hierarchical strategy as the main routing strategy
        self._tool_routing_strategy = cast(
            SimpleToolRoutingStrategy, self._hierarchical_routing_strategy
        )

        logger.info(f"Initialized hierarchical team: {self._id} ({self._name})")

    @property
    def subteams(self) -> Dict[str, TeamProtocol]:
        """Get subteams.

        Returns:
            Dictionary of subteams
        """
        return self._subteams.copy()

    def add_subteam(self, team: TeamProtocol) -> bool:
        """Add a subteam to the team.

        Args:
            team: Team to add as subteam

        Returns:
            True if team was added, False if already a subteam
        """
        if team.id in self._subteams:
            logger.warning(f"Team {team.id} is already a subteam of {self._id}")
            return False

        self._subteams[team.id] = team

        # Update hierarchical routing strategy
        if hasattr(self, "_hierarchical_routing_strategy"):
            # Update team hierarchy
            team_hierarchy = getattr(self._hierarchical_routing_strategy, "_team_hierarchy", {})
            if self._id not in team_hierarchy:
                team_hierarchy[self._id] = []

            if team.id not in team_hierarchy[self._id]:
                team_hierarchy[self._id].append(team.id)

            # Update parent team map
            parent_team_map = getattr(self._hierarchical_routing_strategy, "_parent_team_map", {})
            parent_team_map[team.id] = self._id

            # Register agents
            if hasattr(team, "_manager") and team._manager:
                self._hierarchical_routing_strategy.register_agent(team._manager.id, team.id)

            for agent_id in team.members:
                self._hierarchical_routing_strategy.register_agent(agent_id, team.id)

        logger.info(f"Added team {team.id} ({team.name}) as subteam of {self._id}")
        return True

    def remove_subteam(self, team_id: str) -> bool:
        """Remove a subteam from the team.

        Args:
            team_id: ID of team to remove

        Returns:
            True if team was removed, False if not a subteam
        """
        if team_id not in self._subteams:
            logger.warning(f"Team {team_id} is not a subteam of {self._id}")
            return False

        # Get the subteam before removing it
        subteam = self._subteams[team_id]  # noqa: F841

        # Remove from subteams
        del self._subteams[team_id]

        # Update hierarchical routing strategy
        if hasattr(self, "_hierarchical_routing_strategy"):
            # Update team hierarchy
            team_hierarchy = getattr(self._hierarchical_routing_strategy, "_team_hierarchy", {})
            if self._id in team_hierarchy and team_id in team_hierarchy[self._id]:
                team_hierarchy[self._id].remove(team_id)

            # Update parent team map
            parent_team_map = getattr(self._hierarchical_routing_strategy, "_parent_team_map", {})
            if team_id in parent_team_map:
                del parent_team_map[team_id]

        logger.info(f"Removed team {team_id} from subteams of {self._id}")
        return True

    def get_subteam(self, team_id: str) -> Optional[TeamProtocol]:
        """Get a subteam by ID.

        Args:
            team_id: ID of the team to get

        Returns:
            Team or None if not found
        """
        return self._subteams.get(team_id)

    def get_all_members(self) -> Dict[str, AgentProtocol]:
        """Get all members including those in subteams.

        Returns:
            Dictionary of all members
        """
        all_members = super().members.copy()

        # Add members from subteams with prefixed keys
        for team_id, team in self._subteams.items():
            team_members = team.members
            # Prefix the agent IDs to avoid collisions
            for agent_id, agent in team_members.items():
                prefixed_id = f"{team_id}.{agent_id}"
                all_members[prefixed_id] = agent

        return all_members

    def get_member_path(self, agent_id: str) -> Optional[List[str]]:
        """
        Get the path to an agent in the team hierarchy.

        Args:
            agent_id: ID of the agent

        Returns:
            List of team IDs forming a path to the agent, or None if not found
        """
        # Check if agent is in this team
        if agent_id in self._members:
            return [self._id]

        if self._manager and agent_id == self._manager.id:
            return [self._id]

        # Check subteams
        for team_id, team in self._subteams.items():
            # Check if agent is in this subteam
            if agent_id in team.members:
                return [self._id, team_id]

            if hasattr(team, "manager") and team.manager.id == agent_id:
                return [self._id, team_id]

            # Recursively check deeper subteams
            if hasattr(team, "get_member_path"):
                subpath = cast(Optional[List[str]], team.get_member_path(agent_id))
                if subpath is not None:
                    return [self._id] + subpath

        return None

    def assign_task(
        self, task: Task, agent_id: Optional[str] = None, team_id: Optional[str] = None
    ) -> bool:
        """Assign a task to a team member, subteam, or let manager decide.

        Args:
            task: Task to assign
            agent_id: Optional ID of agent to assign task to
            team_id: Optional ID of subteam to assign task to

        Returns:
            True if task was assigned, False otherwise
        """
        # Check if the task requires specific tool capabilities
        if task.metadata and "required_tool" in task.metadata:
            required_tool = task.metadata["required_tool"]

            # Check if any agent in this team can handle it
            capable_agents = self.find_agents_by_tool_capability(required_tool)
            if capable_agents:
                for agent_id in capable_agents:
                    if agent_id in self._members:
                        success = self._members[agent_id].assign_task(task)
                        if success:
                            logger.info(
                                f"Assigned task {task.id} to agent {agent_id} "
                                f"based on tool capability"
                            )
                            return True

                # If manager is capable, assign to them
                if self._manager and self._manager.id in capable_agents:
                    success = self._manager.assign_task(task)
                    if success:
                        logger.info(f"Assigned task {task.id} to manager based on tool capability")
                        return True

            # Check if any subteam has an agent with this capability
            for subteam_id, subteam in self._subteams.items():
                if hasattr(subteam, "find_agents_by_tool_capability"):
                    subteam_agents = subteam.find_agents_by_tool_capability(required_tool)
                    if subteam_agents:
                        success = subteam.assign_task(task)
                        if success:
                            logger.info(
                                f"Assigned task {task.id} to subteam {subteam_id} "
                                f"based on tool capability"
                            )
                            return True

        # Case 1: Assign to a subteam
        if team_id:
            if team_id not in self._subteams:
                logger.warning(f"Subteam {team_id} not found in team {self._id}")
                return False

            success = self._subteams[team_id].assign_task(task)
            if success:
                logger.info(f"Assigned task {task.id} to subteam {team_id} in team {self._id}")
            return success

        # Case 2: Assign to a member of this team
        if agent_id:
            return super().assign_task(task, agent_id)

        # Case 3: Let manager decide
        return super().assign_task(task)

    def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process a message sent to the team.

        Args:
            message: Message to process

        Returns:
            Optional response message
        """
        # Extract metadata
        metadata = getattr(message, "metadata", {}) or {}

        # Special handling for tool-related messages
        if metadata.get("message_type") == "tool_request":
            tool_name = metadata.get("tool_name")
            tool_params = metadata.get("tool_params", {})

            if tool_name:
                # Try to route within this team first
                success, agent_id = self.route_tool_request(
                    tool_name, tool_params, message.sender_id
                )

                if success and agent_id:
                    # Forward the message to the target agent
                    if self._manager and agent_id == self._manager.id:
                        return self._manager.process_message(message)

                    if agent_id in self._members:
                        return self._members[agent_id].process_message(message)

                # If not found in this team, try subteams
                for subteam_id, subteam in self._subteams.items():
                    if hasattr(subteam, "route_tool_request"):
                        subteam_success, subteam_agent_id = subteam.route_tool_request(
                            tool_name, tool_params, message.sender_id
                        )

                        if subteam_success and subteam_agent_id:
                            # Forward to the subteam
                            subteam_metadata = metadata.copy()
                            subteam_metadata["target_team"] = subteam_id

                            # Create a new message with updated metadata
                            forward_message = create_message(
                                message.message_type,
                                message.sender_id,
                                message.receiver_id,
                                message.content,
                                metadata=subteam_metadata,
                            )

                            return subteam.process_message(forward_message)

                # If we couldn't route, return an error
                return ErrorMessage(
                    self._id,
                    message.sender_id,
                    f"No agent available to handle tool {tool_name} in the team hierarchy",
                    "TOOL_UNAVAILABLE",
                )

        # Check if message targets a specific subteam
        target_team_id = metadata.get("target_team")
        if target_team_id and target_team_id in self._subteams:
            logger.debug(f"Routing message to subteam {target_team_id}")
            return self._subteams[target_team_id].process_message(message)

        return super().process_message(message)

    def broadcast_message(
        self, message_type: str, content: str, sender_id: str, include_subteams: bool = True
    ) -> List[AgentMessage]:
        """Broadcast a message to all team members and optionally subteams.

        Args:
            message_type: Type of message
            content: Message content
            sender_id: ID of sender
            include_subteams: Whether to include subteams in broadcast

        Returns:
            List of response messages
        """
        responses = super().broadcast_message(message_type, content, sender_id)

        # Broadcast to subteams if requested
        if include_subteams:
            for team_id, team in self._subteams.items():
                # Create subteam-specific broadcast metadata
                subteam_responses = team.broadcast_message(message_type, content, sender_id)
                responses.extend(subteam_responses)

        return responses

    def get_status(self) -> Dict[str, Any]:
        """Get team status summary including subteams.

        Returns:
            Dictionary with status information
        """
        status = super().get_status()

        # Add subteam information
        status["subteams"] = [
            {
                "id": team.id,
                "name": team.name,
                "member_count": len(team.members),
            }
            for team in self._subteams.values()
        ]

        # Add hierarchical tool information
        status["tools"]["hierarchical"] = {
            "subteam_tools": {
                team_id: list(team.get_available_tools())
                for team_id, team in self._subteams.items()
                if hasattr(team, "get_available_tools")
            }
        }

        return status

    # Tool-related methods

    def get_available_tools(self) -> Dict[str, List[str]]:
        """
        Get all tools available across the team and subteams.

        Returns:
            A dictionary mapping agent IDs to lists of available tool names
        """
        # Get tools from this team
        tools = super().get_available_tools()

        # Add tools from subteams with prefixed agent IDs
        for team_id, team in self._subteams.items():
            if hasattr(team, "get_available_tools"):
                subteam_tools = team.get_available_tools()

                for agent_id, agent_tools in subteam_tools.items():
                    prefixed_id = f"{team_id}.{agent_id}"
                    tools[prefixed_id] = agent_tools

        return tools

    def route_tool_request(
        self, tool_name: str, parameters: Dict[str, Any], requester_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Route a tool request to the appropriate agent across the team hierarchy.

        Args:
            tool_name: Name of the requested tool
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool

        Returns:
            A tuple of (success, agent_id) where agent_id is the agent
            that will handle the request if successful
        """
        # First try routing within this team
        success, agent_id = super().route_tool_request(tool_name, parameters, requester_id)

        # If successful, return the result
        if success and agent_id:
            return True, agent_id

        # Otherwise, try to find an agent in the hierarchy using our routing strategy
        if hasattr(self, "_hierarchical_routing_strategy"):
            hierarchical_agent = self._hierarchical_routing_strategy.get_agent_for_tool(
                tool_name, requester_id
            )

            if hierarchical_agent:
                # Find which team this agent belongs to
                agent_team_id = None

                # Check if it's the manager
                if self._manager and self._manager.id == hierarchical_agent:
                    return True, hierarchical_agent

                # Check if it's in this team
                if hierarchical_agent in self._members:
                    return True, hierarchical_agent

                # Check if it's in a subteam
                for team_id, team in self._subteams.items():
                    if hierarchical_agent in team.members:
                        agent_team_id = team_id
                        break

                    # Check for manager
                    if hasattr(team, "manager") and team.manager.id == hierarchical_agent:
                        agent_team_id = team_id
                        break

                # If we found the team, we can route through it
                if agent_team_id:
                    return True, hierarchical_agent

        # Try each subteam in turn
        for team_id, team in self._subteams.items():
            if hasattr(team, "route_tool_request"):
                subteam_success, subteam_agent_id = team.route_tool_request(
                    tool_name, parameters, requester_id
                )

                if subteam_success and subteam_agent_id:
                    return True, f"{team_id}.{subteam_agent_id}"

        return False, None

    async def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], requester_id: str
    ) -> ToolResult:
        """
        Execute a tool using the appropriate team member across the hierarchy.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool execution
            requester_id: ID of the agent requesting the tool execution

        Returns:
            Result of the tool execution
        """
        # First try executing through this team
        try:
            result = await super().execute_tool(tool_name, parameters, requester_id)
            if not result.error:
                return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} in team: {str(e)}")

        # If that fails, try finding the tool in the hierarchy
        success, agent_id = self.route_tool_request(tool_name, parameters, requester_id)

        if success and agent_id:
            # Check if this is a prefixed ID (team.agent)
            if "." in agent_id:
                team_id, actual_agent_id = agent_id.split(".", 1)

                # Find the subteam
                subteam = self._subteams.get(team_id)
                if subteam and hasattr(subteam, "execute_tool"):
                    try:
                        return await subteam.execute_tool(tool_name, parameters, requester_id)
                    except Exception as e:
                        logger.error(
                            f"Error executing tool {tool_name} in subteam {team_id}: {str(e)}"
                        )
            else:
                # Regular agent ID
                agent = None

                # Check if it's the manager
                if self._manager and self._manager.id == agent_id:
                    agent = self._manager
                else:
                    # Check if it's a team member
                    agent = self._members.get(agent_id)

                if agent:
                    # Execute through the agent
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
                            },
                        )

                        # Send the message and wait for response
                        response = agent.process_message(message)

                        if response:
                            # Extract tool result from response
                            metadata = getattr(response, "metadata", {}) or {}

                            if "tool_result" in metadata:
                                tool_result = metadata["tool_result"]

                                # Convert dictionary result to ToolResult object
                                if isinstance(tool_result, dict):
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

        # If we reach here, we couldn't execute the tool
        return ToolFailure(error=f"No agent in the team hierarchy can execute tool {tool_name}")

    def find_agents_by_tool_capability(self, tool_name: str) -> List[str]:
        """
        Find agents that have capability to use a specific tool across the hierarchy.

        Args:
            tool_name: Name of the tool to search for

        Returns:
            List of agent IDs that can use the specified tool
        """
        # Get agents from this team
        agents = super().find_agents_by_tool_capability(tool_name)

        # Add agents from subteams
        for team_id, team in self._subteams.items():
            if hasattr(team, "find_agents_by_tool_capability"):
                subteam_agents = team.find_agents_by_tool_capability(tool_name)

                # Prefix agent IDs to avoid collisions
                agents.extend([f"{team_id}.{agent_id}" for agent_id in subteam_agents])

        return agents

    def register_team_tool(self, tool: BaseTool, owner_id: str) -> bool:
        """
        Register a tool with the team, updating hierarchical routing.

        Args:
            tool: Tool to register
            owner_id: ID of the agent that owns the tool

        Returns:
            True if registration was successful, False otherwise
        """
        # Register with this team
        success = super().register_team_tool(tool, owner_id)

        if success and hasattr(self, "_hierarchical_routing_strategy"):
            # Update hierarchical routing
            self._hierarchical_routing_strategy.register_tool(tool.name, self._id, owner_id)

            # Notify subteams about the new tool
            notification = NotificationMessage(
                self._id,
                None,  # Broadcast to all members
                f"New tool registered in parent team: {tool.name}",
                metadata={
                    "notification_type": "tool_registration",
                    "tool_name": tool.name,
                    "owner_id": owner_id,
                    "parent_team_id": self._id,
                    "description": tool.description,
                },
            )

            for team_id, team in self._subteams.items():
                if hasattr(team, "process_message"):
                    team.process_message(notification)

        return success

    def propagate_tool_sharing(
        self, tool_name: str, owner_id: str, target_id: Optional[str] = None
    ) -> bool:
        """
        Propagate tool sharing through the team hierarchy.

        Args:
            tool_name: Name of the tool to share
            owner_id: ID of the agent that owns the tool
            target_id: ID of the target agent, or None for team-wide sharing

        Returns:
            True if sharing was propagated successfully, False otherwise
        """
        # Share within this team
        success = self.share_tool(tool_name, owner_id, target_id)

        # If sharing with all team members, propagate to subteams
        if success and target_id is None:
            for team_id, team in self._subteams.items():
                if hasattr(team, "process_message"):
                    notification = NotificationMessage(
                        self._id,
                        team_id,
                        f"Sharing tool {tool_name} with all members",
                        metadata={
                            "notification_type": "tool_sharing",
                            "tool_name": tool_name,
                            "owner_id": owner_id,
                            "parent_team_id": self._id,
                            "propagate": True,
                        },
                    )

                    team.process_message(notification)

        return success
