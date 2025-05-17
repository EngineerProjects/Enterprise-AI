"""
Fix for LLMAgent.__init__ coroutine handling

This module provides a monkey patch for LLMAgent.__init__ to fix
the coroutine handling issue with init_mcp.
"""

from typing import Any, Dict, List, Optional
from enterprise_ai.agent.core import base

# Save the original method
original_init = base.LLMAgent.__init__


def fixed_init(
    self,
    agent_id: Optional[str] = None,
    name: Optional[str] = None,
    role_type: Optional[str] = None,
    role_kwargs: Optional[Dict[str, Any]] = None,
    state_type: Optional[str] = None,
    state_kwargs: Optional[Dict[str, Any]] = None,
    llm_provider: Optional[Any] = None,
    reasoning_framework: str = "base",
    use_tools: bool = False,
    enable_mcp: bool = False,
    tool_categories: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
    **kwargs: Any,
):
    """Fixed initialization that properly handles async MCP initialization."""
    # Call the parent class's __init__ method
    base.BaseAgent.__init__(
        self,
        agent_id=agent_id,
        name=name,
        role_type=role_type,
        role_kwargs=role_kwargs,
        state_type=state_type,
        state_kwargs=state_kwargs,
        **kwargs,
    )

    # Set up LLM provider
    self._llm_provider = llm_provider

    # Initialize tools manager if tools are enabled, but defer MCP initialization
    if use_tools:
        self._tools = base.AgentToolsManager(self)
        # Store the MCP configuration for later initialization
        # This avoids the coroutine handling issue
        self._mcp_config = {
            "enable": enable_mcp,
            "categories": tool_categories,
            "names": tool_names,
        }
    else:
        self._tools = None
        self._mcp_config = None

    # Create reasoning manager with specified framework
    self._reasoning = base.ReasoningManager(
        self, config=base.ReasoningManagerConfig(default_framework=reasoning_framework)
    )

    base.logger.info(f"Initialized LLM agent {self.id} with framework {reasoning_framework}")


# Add a method to initialize MCP when needed
async def initialize_mcp(self):
    """Initialize MCP when it's actually needed."""
    if (
        self._tools
        and hasattr(self, "_mcp_config")
        and self._mcp_config
        and self._mcp_config["enable"]
    ):
        await self._tools.enable_mcp(
            tool_categories=self._mcp_config["categories"], tool_names=self._mcp_config["names"]
        )
        # Clear the config to avoid re-initialization
        self._mcp_config = None
        return True
    return False


# Add a modified execute_tool method that ensures MCP is initialized
original_execute_tool = base.LLMAgent.execute_tool


async def fixed_execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
    """Execute a tool, ensuring MCP is initialized first."""
    # Initialize MCP if needed and not already done
    if hasattr(self, "_mcp_config") and self._mcp_config and self._mcp_config["enable"]:
        await self.initialize_mcp()

    # Call the original method
    return await original_execute_tool(self, tool_name, **kwargs)


# Apply the monkey patches
base.LLMAgent.__init__ = fixed_init
base.LLMAgent.initialize_mcp = initialize_mcp
base.LLMAgent.execute_tool = fixed_execute_tool

print("Applied LLMAgent patches to fix coroutine handling issues")
