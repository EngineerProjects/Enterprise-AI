"""
MCP-specific configuration management.

This module handles configuration specific to the MCP server,
including tool execution policies, sandbox settings, and session management.
"""

from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from enterprise_ai.config import get_config
from enterprise_ai.tool.core.base import ExecutionMode


class MCPConfig(BaseModel):
    """Configuration for the Enterprise AI MCP server."""
    
    # Execution settings
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.AUTO,
        description="Default execution mode for tools"
    )
    max_tool_iterations: int = Field(
        default=5,
        description="Maximum number of tool execution rounds per session"
    )
    tool_execution_timeout: float = Field(
        default=30.0,
        description="Default timeout for tool execution in seconds"
    )
    
    # Security settings
    allowed_tools: Optional[Set[str]] = Field(
        default=None,
        description="Set of allowed tool names (None = all allowed)"
    )
    forbidden_tools: Set[str] = Field(
        default_factory=set,
        description="Set of forbidden tool names"
    )
    require_approval_for_dangerous: bool = Field(
        default=True,
        description="Whether dangerous tools require approval"
    )
    danger_threshold: int = Field(
        default=2,
        description="Danger level threshold for requiring approval"
    )
    
    # Sandbox settings
    sandbox_enabled: bool = Field(
        default=True,
        description="Whether to enable sandbox execution"
    )
    sandbox_auto_routing: bool = Field(
        default=True,
        description="Whether to automatically route dangerous tools to sandbox"
    )
    
    # Session management
    max_concurrent_sessions: int = Field(
        default=10,
        description="Maximum number of concurrent execution sessions"
    )
    session_timeout: float = Field(
        default=3600.0,
        description="Session timeout in seconds"
    )
    session_cleanup_interval: float = Field(
        default=300.0,
        description="How often to clean up expired sessions"
    )
    
    # Logging and monitoring
    verbose_logging: bool = Field(
        default=False,
        description="Whether to enable verbose execution logging"
    )
    track_tool_usage: bool = Field(
        default=True,
        description="Whether to track tool usage statistics"
    )
    
    # Agent communication
    enable_agent_communication: bool = Field(
        default=True,
        description="Whether to enable agent-to-agent communication"
    )
    agent_message_queue_size: int = Field(
        default=100,
        description="Maximum size of agent message queues"
    )

    @classmethod
    def from_config(cls) -> "MCPConfig":
        """Create MCPConfig from global configuration."""
        return cls(
            execution_mode=ExecutionMode(get_config("mcp.execution_mode", "auto")),
            max_tool_iterations=get_config("mcp.max_tool_iterations", 5),
            tool_execution_timeout=get_config("mcp.tool_execution_timeout", 30.0),
            sandbox_enabled=get_config("mcp.sandbox_enabled", True),
            verbose_logging=get_config("mcp.verbose_logging", False),
            max_concurrent_sessions=get_config("mcp.max_concurrent_sessions", 10),
            session_timeout=get_config("mcp.session_timeout", 3600.0),
        )

    def should_require_approval(self, tool_name: str, danger_level: int = 0) -> bool:
        """Determine if a tool should require approval."""
        if self.execution_mode == ExecutionMode.MANUAL:
            return True
        elif self.execution_mode == ExecutionMode.AUTO:
            return False
        elif self.execution_mode == ExecutionMode.HYBRID:
            return danger_level >= self.danger_threshold
        else:  # DISABLED
            return False

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed to execute."""
        # Check forbidden list first
        if tool_name in self.forbidden_tools:
            return False
        
        # Check allowed list (if specified)
        if self.allowed_tools is not None:
            return tool_name in self.allowed_tools
        
        return True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "MCPConfig":
        """Create MCPConfig from a dictionary."""
        return cls(**config_dict)