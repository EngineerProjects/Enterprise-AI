"""
Enterprise AI Agent - Base Implementation.

Provides the core Agent class that orchestrates LLM reasoning and tool execution.
"""

from typing import List, Optional, Dict, Any, AsyncIterator

from enterprise_ai.llm.base import LLMProvider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import ConversationMemory, InMemoryConversation
from enterprise_ai.schema.agent_profile import AgentProfile, AgentStatus
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
        
        # Internal profile state - auto-generated from agent properties
        self._cached_profile: Optional[AgentProfile] = None
        self._workload: float = 0.0
        self._status: AgentStatus = AgentStatus.AVAILABLE
        
        # Configure the reasoning pattern
        self.reasoning_pattern.configure(llm=llm, mcp=mcp, verbose=verbose)
        
        # Initialize with system prompt
        if role.system_prompt:
            self.memory.add_system_message(role.system_prompt)
            
        if verbose:
            logger.info(f"Agent '{name}' initialized with role '{role.name}'")
    
    def profile(self) -> AgentProfile:
        """
        Get agent profile auto-generated from current agent state.
        
        Profile is a read-only view of the agent's current configuration.
        To update profile, use agent.update_*_config() methods.
        
        Returns:
            AgentProfile with current agent information
        """
        # Always generate fresh profile from current state to ensure consistency
        return AgentProfile.create(
            name=self.name,
            role_name=self.role.name,
            role_description=self.role.description,
            available_tools=self.get_available_tools(),
            initial_workload=self._workload,
            status=self._status
        )
    
    def set_workload(self, workload: float) -> None:
        """Update agent workload."""
        if not 0.0 <= workload <= 1.0:
            raise ValueError(f"Workload must be between 0.0 and 1.0, got {workload}")
        self._workload = workload
        if self.verbose:
            logger.info(f"Agent '{self.name}' workload updated to {workload:.1%}")
    
    def set_status(self, status: AgentStatus) -> None:
        """Update agent status."""
        self._status = status
        if self.verbose:
            logger.info(f"Agent '{self.name}' status updated to {status.value}")
    
    def update_role_config(self, config: Dict[str, Any]) -> None:
        """
        Update agent role configuration at runtime.
        
        Args:
            config: Dictionary with role configuration
                   - name: Role name
                   - description: Role description  
                   - system_prompt: New system prompt
                   - capabilities: List of capabilities
        """
        # Create new role from config
        new_role = AgentRole.from_config(config)
        
        # Update agent role
        self.role = new_role
        
        # Update system prompt in memory
        messages = self.memory.get_messages()
        non_system_messages = [m for m in messages if m.role != "system"]
        self.memory.clear()
        if new_role.system_prompt:
            self.memory.add_system_message(new_role.system_prompt)
        for msg in non_system_messages:
            self.memory.add_message(msg)
            
        if self.verbose:
            logger.info(f"Agent '{self.name}' role updated to '{new_role.name}'")
    
    def update_mcp_config(self, config: Dict[str, Any]) -> None:
        """
        Update MCP configuration at runtime.
        
        Args:
            config: Dictionary with MCP configuration
                   - timeout: Request timeout
                   - tools: List of tools to enable
                   - sandbox_config: Sandbox configuration
        """
        from enterprise_ai.mcp.executor import ToolMCP
        
        # Create new MCP with updated config
        mcp_params = {
            "timeout": config.get("timeout", 30.0),
        }
        
        if "sandbox_config" in config:
            mcp_params["sandbox_config"] = config["sandbox_config"]
        if "tools" in config:
            mcp_params["tools"] = config["tools"]
            
        # Replace current MCP
        self.mcp = ToolMCP(**mcp_params)
        
        # Reconfigure reasoning pattern with new MCP
        self.reasoning_pattern.configure(llm=self.llm, mcp=self.mcp, verbose=self.verbose)
        
        if self.verbose:
            tools_count = len(self.mcp.get_available_tools())
            logger.info(f"Agent '{self.name}' MCP updated with {tools_count} tools")
    
    def update_llm_config(self, config: Dict[str, Any]) -> None:
        """
        Update LLM configuration at runtime.
        
        Args:
            config: Dictionary with LLM configuration
                   - model_name: Model name to use
                   - timeout: Request timeout
                   - other provider-specific parameters
        """
        from enterprise_ai.llm.factory import create_provider
        from enterprise_ai.defaults import get_default_llm_config
        
        # Get current provider info
        current_provider = getattr(self.llm, 'provider_name', 'ollama')
        
        # Prepare config with defaults
        llm_defaults = get_default_llm_config(current_provider)
        llm_defaults.update(config)
        llm_defaults.update({"verbose": self.verbose})
        
        # Extract required parameters
        provider = llm_defaults.pop("provider", current_provider)
        model_name = llm_defaults.pop("model_name")
        
        # Create new LLM provider
        self.llm = create_provider(provider, model_name, **llm_defaults)
        
        # Reconfigure reasoning pattern with new LLM
        self.reasoning_pattern.configure(llm=self.llm, mcp=self.mcp, verbose=self.verbose)
        
        if self.verbose:
            logger.info(f"Agent '{self.name}' LLM updated to {provider}/{model_name}")
    
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
    
    def get_profile_summary(self) -> str:
        """Get a summary including profile information."""
        profile = self.profile()
        workload = f"{profile.capacity.workload * 100:.0f}%"
        status = profile.capacity.status.value
        return f"{self.name}: {self.role.name} | {len(self.get_available_tools())} tools | Status: {status} ({workload} load)"
    
    def sync_profile_tools(self) -> List[str]:
        """Get current tools from MCP (profile is always in sync since it's auto-generated)."""
        return self.get_available_tools()
    
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