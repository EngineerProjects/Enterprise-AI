"""
Enterprise AI Team - Manager Agent.

Implements a specialized agent that coordinates worker agents in a team.
"""

from typing import Dict, List, Optional, Any, Union
import json
import re

from enterprise_ai.agent import Agent, create_agent
from enterprise_ai.agent.role import AgentRole
from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.manager")


class ManagerAgent(Agent):
    """
    Manager agent that coordinates worker agents in a team.
    
    This extends the base Agent class with specialized capabilities for:
    1. Decomposing complex tasks into subtasks
    2. Delegating subtasks to appropriate worker agents
    3. Aggregating results from worker agents
    4. Making decisions based on worker agent outputs
    """
    
    def __init__(
        self, 
        name: str,
        role: AgentRole,
        llm: LLMProvider,
        mcp: ToolMCP,
        reasoning_pattern: str,
        team_agents: List[str],
        memory: Optional[ConversationMemory] = None,
        verbose: bool = False
    ):
        """
        Initialize manager agent with components.
        
        Args:
            name: Agent name
            role: Agent role with system prompt
            llm: LLM provider for generating responses
            mcp: Tool execution coordinator
            reasoning_pattern: Strategy for reasoning and tool usage
            team_agents: List of worker agent names
            memory: Conversation memory (defaults to InMemoryConversation)
            verbose: Enable detailed logging
        """
        super().__init__(
            name=name,
            role=role,
            llm=llm,
            mcp=mcp,
            reasoning_pattern=create_reasoning_pattern(reasoning_pattern),
            memory=memory,
            verbose=verbose
        )
        
        # Store list of worker agents
        self.team_agents = team_agents
        
        # Add team context to system prompt
        self._add_team_context()
        
        if verbose:
            logger.info(f"Manager agent '{name}' initialized with {len(team_agents)} worker agents")
    
    def _add_team_context(self) -> None:
        """Add team information to the system prompt."""
        # Get existing system messages
        messages = self.memory.get_messages()
        system_messages = [m for m in messages if m.role == "system"]
        
        if not system_messages:
            return
        
        # Add team context to first system message
        system_msg = system_messages[0]
        content = system_msg.content or ""
        
        team_context = f"""
You are a manager agent coordinating a team of specialized agents.
Your team consists of the following agents:
{', '.join(self.team_agents)}

As a manager, your responsibilities include:
1. Breaking down complex tasks into subtasks
2. Delegating subtasks to appropriate specialist agents
3. Aggregating results from specialist agents
4. Making decisions based on specialist agent outputs
5. Providing a coherent final response

When you need to delegate a task, use the format:
DELEGATE[agent_name]: task description

You can delegate multiple subtasks to different agents.
Wait for each agent to complete their subtask before proceeding.
"""
        
        # Update system message
        updated_content = f"{content}\n\n{team_context}"
        updated_msg = Message(
            role="system",
            content=updated_content
        )
        
        # Replace system message
        self.memory.clear()
        self.memory.add_message(updated_msg)
    
    async def process(self, user_input: str) -> str:
        """
        Process user input, delegating to worker agents as needed.
        
        This method overrides the base Agent.process to add delegation handling.
        
        Args:
            user_input: User message content
            
        Returns:
            Final response after worker agent collaboration
        """
        # Store the original team context
        team = getattr(self, "_team", None)
        
        # Add user message to memory
        self.memory.add_user_message(user_input)
        
        # Process with reasoning pattern
        response = await self.reasoning_pattern.process(self.memory.get_messages(), self.memory)
        
        # Check for delegation patterns in the response
        delegation_pattern = r"DELEGATE\[([^\]]+)\]:\s*(.*?)(?=DELEGATE\[|$)"
        delegations = re.findall(delegation_pattern, response, re.DOTALL)
        
        # If no delegations or no team, return the response as is
        if not delegations or not team:
            return response
        
        # Process delegations
        delegation_results = {}
        for agent_name, task in delegations:
            agent_name = agent_name.strip()
            task = task.strip()
            
            if agent_name in self.team_agents:
                try:
                    # Delegate to the worker agent
                    result = await team.delegate_task(agent_name, task)
                    delegation_results[agent_name] = result
                    
                    # Add delegation result to memory
                    self.memory.add_message(Message(
                        role="system",
                        content=f"Agent {agent_name} response:\n{result}"
                    ))
                except Exception as e:
                    logger.error(f"Error delegating to agent '{agent_name}': {e}")
                    delegation_results[agent_name] = f"Error: {e}"
            else:
                logger.warning(f"Unknown agent '{agent_name}' in delegation")
        
        # Generate final response incorporating worker agent results
        if delegation_results:
            # Add a prompt to incorporate worker results
            self.memory.add_user_message(
                "Please provide a final response incorporating the results from the worker agents."
            )
            
            # Get final response
            final_response = await self.reasoning_pattern.process(self.memory.get_messages(), self.memory)
            return final_response
        
        return response
    
    def set_team(self, team) -> None:
        """
        Set the team reference for delegating tasks.
        
        Args:
            team: Team instance
        """
        self._team = team


def create_reasoning_pattern(pattern_name: str) -> Any:
    """
    Create a reasoning pattern instance by name.
    
    Args:
        pattern_name: Name of the reasoning pattern
        
    Returns:
        Reasoning pattern instance
        
    Raises:
        ValueError: If pattern not recognized
    """
    from enterprise_ai.agent.reasoning.react import ReActPattern
    from enterprise_ai.agent.reasoning.cot import ChainOfThoughtPattern
    from enterprise_ai.agent.reasoning.swe import SoftwareEngineeringPattern
    
    pattern_name = pattern_name.lower()
    
    if pattern_name == "react":
        return ReActPattern()
    elif pattern_name == "cot":
        return ChainOfThoughtPattern()
    elif pattern_name == "swe":
        return SoftwareEngineeringPattern()
    else:
        raise ValueError(f"Unknown reasoning pattern: {pattern_name}")
