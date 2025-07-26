"""
Enterprise AI Team - Base Implementation.

Simplified team class with mandatory manager and automatic role assignment.
"""

from typing import Dict, List, Optional, Any
import asyncio
from enterprise_ai.agent import Agent
from enterprise_ai.team.core.enums import CollaborationMode
from enterprise_ai.team.roles.manager import ManagerRole
from enterprise_ai.team.roles.base import SpecialistRole
from enterprise_ai.team.memory.shared import SharedMemory
from enterprise_ai.team.communication.protocol import TeamMessage, CommunicationProtocol
from enterprise_ai.team.communication.router import MessageRouter
from enterprise_ai.team.communication.context import TeamContextBuilder
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team")


class Team:
    """
    Simple team with mandatory manager and automatic specialist role assignment.
    
    Clean API: create agents with Agent module, then add to team.
    """

    def __init__(
        self, 
        name: str,
        manager: Agent,
        collaboration_mode: CollaborationMode = CollaborationMode.HIERARCHICAL,
        verbose: bool = False
    ):
        """
        Initialize team with mandatory manager.
        
        Args:
            name: Team name
            manager: Manager agent (required)
            collaboration_mode: Team collaboration pattern
            verbose: Enable detailed logging
        """
        self.name = name
        self.manager = ManagerRole(manager)
        self.specialists = {}
        self.collaboration_mode = collaboration_mode
        self.shared_memory = SharedMemory()
        self.communication = CommunicationProtocol()
        self.router = MessageRouter(self.communication)
        self.context_builder = TeamContextBuilder()
        self.verbose = verbose
        
        # Register manager with router
        manager_name = self._get_agent_name(manager)
        self.router.register_agent(manager_name, self._create_agent_message_callback(manager))
        
        if verbose:
            logger.info(f"Team '{name}' created with manager '{manager_name}'")
    
    def add_member(self, agent: Agent) -> None:
        """
        Add agent as specialist (role auto-detected from agent profile).
        
        Args:
            agent: Agent to add as team specialist
        """
        agent_name = self._get_agent_name(agent)
        specialist = SpecialistRole(agent)
        self.specialists[agent_name] = specialist
        
        # Register with router
        self.router.register_agent(agent_name, self._create_agent_message_callback(agent))
        
        # Refresh team context for all agents
        self.refresh_team_context()
        
        if self.verbose:
            logger.info(f"Added specialist '{agent_name}' to team '{self.name}'")
    
    def remove_member(self, agent_name: str) -> Optional[Agent]:
        """Remove specialist from team."""
        if agent_name in self.specialists:
            specialist = self.specialists.pop(agent_name)
            self.router.unregister_agent(agent_name)
            self.refresh_team_context()
            
            if self.verbose:
                logger.info(f"Removed specialist '{agent_name}' from team '{self.name}'")
            return specialist.agent
        return None
    
    def refresh_team_context(self) -> None:
        """Update team context for all agents with current team composition."""
        all_agents = {"manager": self.manager.agent}
        all_agents.update({name: spec.agent for name, spec in self.specialists.items()})
        
        for agent_name, agent in all_agents.items():
            team_context = self.context_builder.build_team_context(agent_name, all_agents)
            self._inject_team_context_to_agent(agent, team_context)
        
        if self.verbose:
            logger.debug(f"Refreshed team context for {len(all_agents)} agents")
    
    async def process(self, user_input: str) -> str:
        """
        Process user input through the team manager.
        
        Args:
            user_input: User message content
            
        Returns:
            Final team response
        """
        # Store input in shared memory
        self.shared_memory.add_user_message(user_input)
        
        # Manager processes the request
        if self.verbose:
            logger.info(f"Team '{self.name}' processing input through manager")
            
        response = await self.manager.agent.process(user_input)
        
        # Store response in shared memory
        self.shared_memory.add_assistant_message(response)
        
        return response
    
    async def execute_task(self, task_description: str) -> str:
        """
        Execute task through team coordination.
        
        Args:
            task_description: Description of task to execute
            
        Returns:
            Task result
        """
        return await self.process(task_description)
    
    async def delegate_task(self, agent_name: str, task: str) -> str:
        """
        Delegate specific task to team member.
        
        Args:
            agent_name: Name of specialist to delegate to
            task: Task description
            
        Returns:
            Agent's response
        """
        if agent_name not in self.specialists:
            raise ValueError(f"Specialist '{agent_name}' not found in team '{self.name}'")
        
        specialist = self.specialists[agent_name]
        
        if self.verbose:
            logger.info(f"Delegating task to '{agent_name}': {task[:50]}...")
        
        result = await specialist.agent.process(task)
        self.shared_memory.add_agent_message(agent_name, task, result)
        
        return result
    
    def get_team_members(self) -> List[str]:
        """Get list of all team member names."""
        return ["manager"] + list(self.specialists.keys())
    
    def get_available_specialists(self) -> List[str]:
        """Get list of available specialists."""
        return [
            name for name, specialist in self.specialists.items() 
            if specialist.is_available
        ]
    
    def reset(self) -> None:
        """Reset all agents and shared memory."""
        self.manager.agent.reset()
        
        for specialist in self.specialists.values():
            specialist.agent.reset()
        
        self.shared_memory.clear()
        
        if self.verbose:
            logger.info(f"Team '{self.name}' reset")
    
    def _get_agent_name(self, agent: Agent) -> str:
        """Extract agent name consistently."""
        if hasattr(agent, 'profile') and agent.profile and hasattr(agent.profile, 'name'):
            return agent.profile.name
        if hasattr(agent, 'name'):
            return agent.name
        return agent.__class__.__name__.lower()
    
    def _create_agent_message_callback(self, agent: Agent) -> callable:
        """Create message callback for an agent."""
        def handle_message(message: TeamMessage) -> None:
            if self.verbose:
                logger.debug(f"Agent '{self._get_agent_name(agent)}' received message")
        return handle_message
    
    def _inject_team_context_to_agent(self, agent: Agent, team_context: str) -> None:
        """Inject team context into agent's system prompt."""
        if not team_context or not hasattr(agent, 'role') or not hasattr(agent.role, 'system_prompt'):
            return
            
        current_prompt = agent.role.system_prompt
        
        # Check if team context already exists and replace it
        context_marker = "# YOUR IDENTITY & TEAM COLLABORATION CONTEXT"
        if context_marker in current_prompt:
            base_prompt = current_prompt.split(context_marker)[0].rstrip()
        else:
            base_prompt = current_prompt
        
        # Add new team context
        agent.role.system_prompt = f"{base_prompt}{team_context}"


# Legacy compatibility functions
def add_agent(team: Team, agent: Agent) -> None:
    """Legacy function for backward compatibility."""
    team.add_member(agent)


def set_manager(team: Team, manager: Agent) -> None:
    """Legacy function - not needed since manager is mandatory in constructor."""
    logger.warning("set_manager() is deprecated - manager is now mandatory in Team constructor")
