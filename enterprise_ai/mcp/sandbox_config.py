"""
Sandbox configuration for Enterprise AI tools.

Provides manual control over which tools use sandbox and how.
"""

from typing import Dict, List, Optional, Set, Literal
from dataclasses import dataclass

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.tool.core.base import SandboxMode

logger = get_optimized_logger("mcp.sandbox_config")


@dataclass
class SandboxConfig:
    """Configuration for sandbox usage."""
    enabled: bool = False
    dangerous_tools: Set[str] = None
    always_sandbox: Set[str] = None
    never_sandbox: Set[str] = None
    timeout: float = 30.0
    default_mode: SandboxMode = SandboxMode.UNIFIED
    simplified_routing: bool = True  # When True, uses only dangerous_tools for routing
    
    def __post_init__(self):
        """Initialize default sets."""
        if self.dangerous_tools is None:
            self.dangerous_tools = {
                "bash", "python_execute", "process_manager", 
                "file_editor", "filesystem"
            }
        if self.always_sandbox is None:
            self.always_sandbox = set()
        if self.never_sandbox is None:
            self.never_sandbox = {
                "web_search", "configuration", "deep_research"
            }

    def should_use_sandbox(self, tool_name: str) -> bool:
        """Determine if a tool should use sandbox."""
        if not self.enabled:
            return False
            
        # Explicit overrides
        if tool_name in self.always_sandbox:
            return True
        if tool_name in self.never_sandbox:
            return False
            
        # Check if tool is considered dangerous
        return tool_name in self.dangerous_tools


def create_sandbox_config(
    enabled: bool = False,
    dangerous_tools: Optional[List[str]] = None,
    always_sandbox: Optional[List[str]] = None,
    never_sandbox: Optional[List[str]] = None,
    timeout: float = 30.0,
    default_mode: SandboxMode = SandboxMode.UNIFIED,
    simplified_routing: bool = True
) -> SandboxConfig:
    """Create a sandbox configuration."""
    return SandboxConfig(
        enabled=enabled,
        dangerous_tools=set(dangerous_tools) if dangerous_tools else None,
        always_sandbox=set(always_sandbox) if always_sandbox else None,
        never_sandbox=set(never_sandbox) if never_sandbox else None,
        timeout=timeout,
        default_mode=default_mode,
        simplified_routing=simplified_routing
    )


# Default configurations
DEFAULT_SANDBOX_CONFIG = SandboxConfig(enabled=False)

SAFE_SANDBOX_CONFIG = create_sandbox_config(
    enabled=True,
    dangerous_tools=["bash", "python_execute", "process_manager", "file_editor"],
    never_sandbox=["web_search", "configuration", "deep_research"]
)

STRICT_SANDBOX_CONFIG = create_sandbox_config(
    enabled=True,
    dangerous_tools=["bash", "python_execute", "process_manager", "file_editor", "filesystem"],
    always_sandbox=["bash", "python_execute"],
    never_sandbox=["web_search", "configuration"]
)
