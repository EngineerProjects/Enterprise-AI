"""
Enterprise AI Agent - Base Implementation.

Provides the core Agent class that orchestrates LLM reasoning and tool execution.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory, InMemoryConversation
from enterprise_ai.agent.reasoning.base import ReasoningPattern
from enterprise_ai.agent.role import AgentRole
from enterprise_ai.schema.agent_profile import AgentProfile, AgentStatus
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent")


class Agent:
    """
    Base agent implementation that orchestrates reasoning and tool execution.
    
    Connects LLM, reasoning pattern, and MCP to create a coherent AI agent
    that can process tasks and use tools as needed.
    """

    def __init__(
        self, 
        name: str,
        role: AgentRole,
        llm: LLMProvider,
        mcp: ToolMCP,
        reasoning_pattern: ReasoningPattern,
        memory: Optional[ConversationMemory] = None,
        verbose: bool = False,
        create_profile: bool = True
    ):
        """
        Initialize agent with components.
        
        Args:
            name: Agent name
            role: Agent role with system prompt
            llm: LLM provider for generating responses
            mcp: Tool execution coordinator
            reasoning_pattern: Strategy for reasoning and tool usage
            memory: Conversation memory (defaults to InMemoryConversation)
            verbose: Enable detailed logging
            create_profile: Whether to create agent profile automatically
        """
        self.name = name
        self.role = role
        self.llm = llm
        self.mcp = mcp
        self.reasoning_pattern = reasoning_pattern
        self.memory = memory or InMemoryConversation()
        self.verbose = verbose
        
        # Create agent profile with automatic tool detection
        self._profile = None
        if create_profile:
            self._create_profile()
        
        # Configure the reasoning pattern
        self.reasoning_pattern.configure(llm=llm, mcp=mcp, verbose=verbose)
        
        # Initialize with system prompt
        if role.system_prompt:
            self.memory.add_system_message(role.system_prompt)
            
        if verbose:
            logger.info(f"Agent '{name}' initialized with role '{role.name}'")
    
    def _create_profile(self) -> None:
        """Create minimal agent profile with automatic tool detection."""
        try:
            # Get available tools from MCP
            available_tools = self.mcp.get_available_tools()
            
            # Create minimal profile - just the essential 4 fields
            self._profile = AgentProfile.create(
                name=self.name,
                role_name=self.role.name,
                role_description=getattr(self.role, 'description', None),
                available_tools=available_tools,
                initial_workload=0.0,
                status=AgentStatus.AVAILABLE
            )
            
            if self.verbose:
                logger.info(f"Created minimal profile for agent '{self.name}' with {len(available_tools)} tools")
        except Exception as e:
            logger.error(f"Failed to create profile for agent '{self.name}': {e}")
            self._profile = None
    
    @property
    def profile(self) -> Optional[AgentProfile]:
        """Get agent profile."""
        return self._profile
    
    def update_capacity(self, workload: Optional[float] = None, status: Optional[AgentStatus] = None) -> None:
        """
        Update agent capacity information.
        
        Args:
            workload: New workload (0.0 to 1.0)
            status: New status
        """
        if not self._profile:
            return
        
        if workload is not None:
            self._profile.capacity.update_workload(workload)
        
        if status is not None:
            self._profile.capacity.set_status(status)
        
        if self.verbose and (workload is not None or status is not None):
            logger.info(f"Updated capacity for agent '{self.name}': "
                       f"workload={self._profile.capacity.workload:.1%}, "
                       f"status={self._profile.capacity.status.value}")
    
    def refresh_tools(self) -> None:
        """Refresh available tools from current MCP state."""
        if not self._profile:
            return
        
        try:
            current_tools = self.mcp.get_available_tools()
            old_tools = set(self._profile.available_tools)
            new_tools = set(current_tools)
            
            self._profile.update_tools(current_tools)
            
            # Log changes if verbose
            if self.verbose:
                added = new_tools - old_tools
                removed = old_tools - new_tools
                
                if added:
                    logger.info(f"Agent '{self.name}' gained tools: {', '.join(added)}")
                if removed:
                    logger.info(f"Agent '{self.name}' lost tools: {', '.join(removed)}")
        except Exception as e:
            logger.error(f"Failed to refresh tools for agent '{self.name}': {e}")
    
    def get_profile_summary(self) -> str:
        """Get a summary of agent's minimal profile."""
        if not self._profile:
            return f"{self.name} ({self.role.name})"
        
        return f"{self._profile.name}: {self._profile.role.name} | {len(self._profile.available_tools)} tools | {self._profile.capacity.workload:.1%} workload"
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has access to a specific tool."""
        if not self._profile:
            return tool_name in self.mcp.get_available_tools()
        
        return self._profile.has_tool(tool_name)
    
    def matches_role(self, role_pattern: str) -> bool:
        """Check if agent role matches a pattern."""
        if not self._profile:
            return role_pattern.lower() in self.role.name.lower()
        
        return self._profile.matches_role_pattern(role_pattern)
    
    async def process(self, user_input: str) -> str:
        """
        Process user input and return response.
        
        This method adds the user input to memory and delegates
        processing to the reasoning pattern.
        
        Args:
            user_input: User message content
            
        Returns:
            Final agent response
        """
        # Add user message to memory
        self.memory.add_user_message(user_input)
        
        # Get messages from memory
        messages = self.memory.get_messages()
        
        # Let the reasoning pattern handle the interaction
        if self.verbose:
            logger.info(f"Processing input with {self.reasoning_pattern.__class__.__name__}")
            
        final_response = await self.reasoning_pattern.process(messages, self.memory)
        
        # Return the final text response
        return final_response
    
    async def process_stream(self, user_input: str) -> AsyncIterator[str]:
        """
        Process user input and stream the response.
        
        Args:
            user_input: User message content
            
        Returns:
            Async iterator of response chunks
        """
        # Add user message to memory
        self.memory.add_user_message(user_input)
        
        # Get messages from memory
        messages = self.memory.get_messages()
        
        # Let the reasoning pattern handle the streaming interaction
        if self.verbose:
            logger.info(f"Processing streaming input with {self.reasoning_pattern.__class__.__name__}")
            
        async for response_chunk in self.reasoning_pattern.process_stream(messages, self.memory):
            yield response_chunk
    
    def reset(self) -> None:
        """Reset agent state while preserving system prompt."""
        # Get system messages
        messages = self.memory.get_messages()
        system_messages = [m for m in messages if m.role == "system"]
        
        # Clear memory
        self.memory.clear()
        
        # Re-add system messages
        for msg in system_messages:
            self.memory.add_message(msg)
            
        if self.verbose:
            logger.info(f"Agent '{self.name}' state reset")