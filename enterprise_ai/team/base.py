"""
Enterprise AI Team - Base Implementation.

Provides the core Team class that orchestrates multiple agents working together.
"""

from typing import Dict, List, Optional, Any, Union, Tuple
import asyncio
from enterprise_ai.agent import Agent
from enterprise_ai.agent.role import AgentRole
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.team.memory.shared import SharedMemory
from enterprise_ai.team.communication.protocol import TeamMessage, CommunicationProtocol
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
        self.verbose = verbose
        
        if verbose:
            logger.info(f"Team '{name}' initialized")
    
    def add_agent(self, name: str, agent: Agent) -> None:
        """
        Add an agent to the team.
        
        Args:
            name: Agent name
            agent: Agent instance
        """
        self.agents[name] = agent
        if self.verbose:
            logger.info(f"Added agent '{name}' to team '{self.name}'")
    
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
            
        if self.verbose:
            logger.info(f"Set manager for team '{self.name}'")
    
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