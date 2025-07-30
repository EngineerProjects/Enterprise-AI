"""
Enterprise AI Agent - Base Implementation.

Provides the core Agent class that orchestrates LLM reasoning and tool execution.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory, InMemoryConversation
from enterprise_ai.agent.role import AgentRole

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
        reasoning_pattern: Any,
        memory: Optional[ConversationMemory] = None,
        verbose: bool = False
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
        """
        self.name = name
        self.role = role
        self.llm = llm
        self.mcp = mcp
        self.reasoning_pattern = reasoning_pattern
        self.memory = memory or InMemoryConversation()
        self.verbose = verbose
        
        # Configure the reasoning pattern
        self.reasoning_pattern.configure(llm=llm, mcp=mcp, verbose=verbose)
        
        # Initialize with system prompt
        if role.system_prompt:
            self.memory.add_system_message(role.system_prompt)
            
        if verbose:
            logger.info(f"Agent '{name}' initialized with role '{role.name}'")
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tools from MCP."""
        return self.mcp.get_available_tools()
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if agent has access to a specific tool."""
        return tool_name in self.get_available_tools()
    
    def get_summary(self) -> str:
        """Get a summary of agent's capabilities."""
        tools = self.get_available_tools()
        return f"{self.name}: {self.role.name} | {len(tools)} tools available"
    
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