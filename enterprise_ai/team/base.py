"""
Enterprise AI Team - Base Implementation.

Provides the core Team class that orchestrates multiple agents working together.
Enhanced with team context management and @mention support.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import asyncio
from enterprise_ai.agent import Agent
from enterprise_ai.agent.role import AgentRole
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.schema.agent_profile import AgentProfile
from enterprise_ai.team.memory.shared import SharedMemory
from enterprise_ai.team.communication.protocol import TeamMessage, CommunicationProtocol
from enterprise_ai.team.communication.router import MessageRouter
from enterprise_ai.team.communication.context import TeamContextBuilder
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team")


class Team:
    """
    Team implementation that orchestrates multiple agents working together.
    
    A team consists of multiple agents that can collaborate to solve complex tasks.
    The team provides coordination, shared memory, and communication between agents.
    """

    def __init__(
        self, 
        name: str,
        shared_memory: Optional[SharedMemory] = None,
        communication_protocol: Optional[CommunicationProtocol] = None,
        verbose: bool = False
    ):
        """
        Initialize team with basic components.
        
        Args:
            name: Team name
            shared_memory: Shared memory for the team
            communication_protocol: Protocol for agent communication
            verbose: Enable detailed logging
        """
        self.name = name
        self.manager = None
        self.agents = {}
        self.shared_memory = shared_memory or SharedMemory()
        self.communication = communication_protocol or CommunicationProtocol()
        self.router = MessageRouter(self.communication)
        self.context_builder = TeamContextBuilder()
        self.verbose = verbose
        
        if verbose:
            logger.info(f"Team '{name}' initialized with enhanced communication")
    
    def add_agent(self, agent_or_name: Union[Agent, str], agent: Optional[Agent] = None) -> None:
        """
        Add an agent to the team.
        
        Args:
            agent_or_name: Agent instance (preferred) or agent name (legacy)
            agent: Agent instance when using legacy signature
        """
        # Handle both new and legacy signatures for backward compatibility
        if isinstance(agent_or_name, str) and agent is not None:
            # Legacy: add_agent("alice", alice_agent)
            agent_name = agent_or_name
            agent_instance = agent
        else:
            # New: add_agent(alice_agent)
            agent_instance = agent_or_name
            agent_name = self._get_agent_name(agent_instance)
        
        self.agents[agent_name] = agent_instance
        
        # Register agent with router for message handling
        self.router.register_agent(agent_name, self._create_agent_message_callback(agent_instance))
        
        if self.verbose:
            logger.info(f"Added agent '{agent_name}' to team '{self.name}'")
    
    def remove_agent(self, name: str) -> Optional[Agent]:
        """
        Remove an agent from the team.
        
        Args:
            name: Agent name
            
        Returns:
            Removed agent or None if not found
        """
        if name in self.agents:
            agent = self.agents.pop(name)
            
            # Unregister from router
            self.router.unregister_agent(name)
            
            if self.verbose:
                logger.info(f"Removed agent '{name}' from team '{self.name}'")
            return agent
        return None
    
    def set_manager(self, manager: Agent) -> None:
        """
        Set the manager agent for the team.
        
        Args:
            manager: Manager agent
        """
        self.manager = manager
        
        # Set the team reference on the manager if it has a set_team method
        if hasattr(manager, 'set_team'):
            manager.set_team(self)
        
        # Register manager with router to receive messages
        manager_name = self._get_agent_name(manager)
        self.router.register_agent(manager_name, self._create_agent_message_callback(manager))
        
        # Also register as "manager" for default routing
        self.router.register_agent("manager", self._create_agent_message_callback(manager))
            
        if self.verbose:
            logger.info(f"Set manager for team '{self.name}' and registered with router")
    
    def refresh_team_context(self) -> None:
        """Update team context for all agents with current team composition."""
        for agent_name, agent in self.agents.items():
            team_context = self.context_builder.build_team_context(agent_name, self.agents)
            self._inject_team_context_to_agent(agent, team_context)
        
        if self.verbose:
            logger.debug(f"Refreshed team context for {len(self.agents)} agents")
    
    def _inject_team_context_to_agent(self, agent: Agent, team_context: str) -> None:
        """Inject team context into an agent's system prompt."""
        if not team_context or not hasattr(agent, 'role') or not hasattr(agent.role, 'system_prompt'):
            return
            
        current_prompt = agent.role.system_prompt
        
        # Check if team context already exists and replace it
        context_marker = "# TEAM COLLABORATION CONTEXT"
        if context_marker in current_prompt:
            # Remove existing team context
            base_prompt = current_prompt.split(context_marker)[0].rstrip()
        else:
            base_prompt = current_prompt
        
        # Add new team context
        agent.role.system_prompt = f"{base_prompt}{team_context}"
    
    def _create_agent_message_callback(self, agent: Agent) -> callable:
        """Create message callback for an agent."""
        def handle_message(message: TeamMessage) -> None:
            """Handle incoming message for agent."""
            if self.verbose:
                logger.debug(f"Agent '{agent.name}' received message from '{message.sender}'")
            
            # Could extend this to automatically process mentions
            # For now, just log the message
            
        return handle_message
    
    def _get_agent_name(self, agent: Agent) -> str:
        """Extract agent name from the agent itself."""
        # Try agent.profile.name first (most reliable)
        if hasattr(agent, 'profile') and agent.profile and hasattr(agent.profile, 'name'):
            return agent.profile.name
        
        # Fallback to agent.name if it exists
        if hasattr(agent, 'name'):
            return agent.name
        
        # Last resort - use class name or generate one
        return agent.__class__.__name__.lower().replace('agent', '') or 'agent'
    
    def add_agents(self, agents: List[Agent]) -> None:
        """
        Add multiple agents to the team at once.
        
        Args:
            agents: List of agent instances
        """
        for agent in agents:
            self.add_agent(agent)
        
        if self.verbose:
            logger.info(f"Added {len(agents)} agents to team '{self.name}'")
    
    async def send_mention_message(self, sender: str, content: str) -> List[str]:
        """
        Send a message with @mention parsing and routing.
        
        Args:
            sender: Sender agent name
            content: Message content (may contain @mentions)
            
        Returns:
            List of message IDs for routed messages
        """
        return self.router.send_message_with_mentions(sender, content)
    
    def get_team_member_names(self) -> List[str]:
        """Get list of all team member names."""
        return list(self.agents.keys())
    
    def get_agent_profile(self, name: str) -> Optional[AgentProfile]:
        """Get profile for a specific agent."""
        agent = self.agents.get(name)
        return agent.profile if agent and hasattr(agent, 'profile') else None
    
    def update_agent_capacity(self, agent_name: str, workload: float, status: str = None) -> None:
        """Update an agent's capacity and refresh team context."""
        agent = self.agents.get(agent_name)
        if agent and hasattr(agent, 'profile') and agent.profile:
            agent.profile.capacity.update_workload(workload)
            if status:
                from enterprise_ai.schema.agent_profile import AgentStatus
                agent.profile.capacity.set_status(AgentStatus(status))
            
            # Refresh team context for all agents
            self.refresh_team_context()
            
            if self.verbose:
                logger.info(f"Updated capacity for agent '{agent_name}': {workload*100:.0f}%")
    
    async def process(self, user_input: str) -> str:
        """
        Process user input through the team.
        
        If a manager is set, the request is processed through the manager.
        Otherwise, the request is processed by the first agent in the team.
        
        Args:
            user_input: User message content
            
        Returns:
            Final team response
        """
        # Store the user input in shared memory
        self.shared_memory.add_user_message(user_input)
        
        if self.manager:
            # Process with manager agent
            if self.verbose:
                logger.info(f"Team '{self.name}' processing user input with manager")
                
            response = await self.manager.process(user_input)
        elif self.agents:
            # Process with first agent if no manager
            first_agent_name = next(iter(self.agents))
            if self.verbose:
                logger.info(f"Team '{self.name}' processing user input with agent '{first_agent_name}'")
                
            response = await self.agents[first_agent_name].process(user_input)
        else:
            raise ValueError(f"Team '{self.name}' has no agents")
        
        # Store the final response in shared memory
        self.shared_memory.add_assistant_message(response)
        
        return response
    
    async def delegate_task(
        self, 
        agent_name: str, 
        task: str, 
        context: Optional[List[Message]] = None
    ) -> str:
        """
        Delegate a specific task to an agent.
        
        Args:
            agent_name: Name of the agent to delegate to
            task: Task description
            context: Optional context messages
            
        Returns:
            Agent's response
            
        Raises:
            ValueError: If agent not found
        """
        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not found in team '{self.name}'")
        
        agent = self.agents[agent_name]
        
        # Add context to agent's memory if provided
        if context:
            for msg in context:
                agent.memory.add_message(msg)
        
        # Create team message for the task
        team_msg = TeamMessage(
            sender="manager" if self.manager else "team",
            recipient=agent_name,
            content=task,
            msg_type="task"
        )
        
        # Log the delegation
        if self.verbose:
            logger.info(f"Delegating task to agent '{agent_name}' in team '{self.name}'")
            logger.debug(f"Task content: {task[:100]}...")
        
        # Process the task with the agent
        task_input = self.communication.format_team_message(team_msg)
        response = await agent.process(task_input)
        
        # Add response to shared memory
        self.shared_memory.add_agent_message(agent_name, task, response)
        
        return response
    
    async def direct_collaboration(
        self,
        subtasks: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Have agents collaborate directly on subtasks without a manager.
        
        Args:
            subtasks: Dictionary mapping agent names to their subtasks
            
        Returns:
            Dictionary mapping agent names to their responses
        """
        # Create tasks for each agent
        tasks = []
        for agent_name, subtask in subtasks.items():
            if agent_name in self.agents:
                task = self.delegate_task(agent_name, subtask)
                tasks.append((agent_name, asyncio.create_task(task)))
            else:
                logger.warning(f"Agent '{agent_name}' not found in team, skipping task")
        
        # Wait for all tasks to complete
        results = {}
        for agent_name, task in tasks:
            try:
                response = await task
                results[agent_name] = response
            except Exception as e:
                logger.error(f"Error from agent '{agent_name}': {e}")
                results[agent_name] = f"Error: {e}"
        
        return results
    
    async def collaborative_solve(
        self,
        main_task: str,
        agent_sequence: List[str]
    ) -> str:
        """
        Solve a task by passing it through a sequence of agents.
        
        Args:
            main_task: The main task to solve
            agent_sequence: List of agent names to process the task in sequence
            
        Returns:
            Final response after sequential processing
        """
        current_task = main_task
        responses = []
        
        for agent_name in agent_sequence:
            if agent_name not in self.agents:
                raise ValueError(f"Agent '{agent_name}' not found in team '{self.name}'")
            
            # Process with current agent
            response = await self.delegate_task(agent_name, current_task)
            responses.append((agent_name, response))
            
            # Update task for next agent
            current_task = f"""Continue working on this task based on {agent_name}'s work:
Original task: {main_task}

{agent_name}'s response:
{response}

Continue the work and improve upon it."""
        
        # Return the final response
        if responses:
            return responses[-1][1]
        return "No agents processed the task."
    
    def reset(self) -> None:
        """Reset all agents and shared memory."""
        # Reset all agents
        if self.manager:
            self.manager.reset()
            
        for agent in self.agents.values():
            agent.reset()
        
        # Reset shared memory
        self.shared_memory.clear()
        
        if self.verbose:
            logger.info(f"Team '{self.name}' reset")
    
    def get_agents(self) -> List[str]:
        """Get list of all agent names in the team."""
        agents = list(self.agents.keys())
        if self.manager:
            agents.insert(0, "manager")
        return agents