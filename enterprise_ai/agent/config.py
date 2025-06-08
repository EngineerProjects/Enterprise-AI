"""
Configuration system for Enterprise AI agents.
"""

from enum import Enum
from typing import Any, Dict, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field

from enterprise_ai.config import get_config
from enterprise_ai.schema import ToolCall
from enterprise_ai.tool.constants import ExecutionMode


class LLMProvider(Enum):
    """Supported LLM providers for agents."""
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclass
class AgentConfig:
    """Configuration for Enterprise AI agents."""
    
    # Core agent settings
    agent_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    
    # LLM provider configuration
    llm_provider: LLMProvider = LLMProvider.OLLAMA
    model_name: Optional[str] = None
    
    # LLM-specific settings
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    timeout: Optional[float] = None
    
    # MCP integration settings
    enable_tools: bool = True
    auto_execute_tools: bool = True
    require_tool_approval: bool = False
    session_timeout: float = 3600.0
    
    # Tool approval callback
    tool_approval_callback: Optional[Callable[[ToolCall], Awaitable[bool]]] = None
    
    # Agent behavior settings
    verbose: bool = False
    max_iterations: int = 10
    thinking_enabled: bool = False
    
    # Provider-specific configurations
    openai_config: Dict[str, Any] = field(default_factory=dict)
    ollama_config: Dict[str, Any] = field(default_factory=dict)
    mcp_config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_config(cls, **overrides: Any) -> "AgentConfig":
        """Create configuration from global config with overrides."""
        config = cls()
        
        # Load from global config
        config.llm_provider = LLMProvider(
            get_config("agent.llm_provider", "ollama")
        )
        config.model_name = get_config("agent.model_name")
        config.temperature = get_config("agent.temperature")
        config.max_tokens = get_config("agent.max_tokens")
        config.verbose = get_config("agent.verbose", False)
        config.enable_tools = get_config("agent.enable_tools", True)
        config.auto_execute_tools = get_config("agent.auto_execute_tools", True)
        config.require_tool_approval = get_config("agent.require_tool_approval", False)
        
        # Apply overrides
        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM provider-specific configuration."""
        base_config = {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "timeout": self.timeout,
            "verbose": self.verbose,
        }
        
        # Remove None values
        base_config = {k: v for k, v in base_config.items() if v is not None}
        
        if self.llm_provider == LLMProvider.OPENAI:
            base_config.update(self.openai_config)
        elif self.llm_provider == LLMProvider.OLLAMA:
            base_config.update(self.ollama_config)
        
        return base_config
    
    def get_mcp_config(self) -> Dict[str, Any]:
        """Get MCP-specific configuration."""
        # Determine execution mode based on approval requirements
        execution_mode = ExecutionMode.AUTO
        if self.require_tool_approval:
            execution_mode = ExecutionMode.MANUAL
        
        base_config = {
            "execution_mode": execution_mode,  # USE COMPUTED MODE
            "enable_tools": self.enable_tools,
            "auto_execute_tools": self.auto_execute_tools,
            "require_tool_approval": self.require_tool_approval,
            "session_timeout": self.session_timeout,
            "verbose_logging": self.verbose,
        }
        
        base_config.update(self.mcp_config)
        return base_config