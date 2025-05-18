"""
Patches for Enterprise AI components.

This package contains patches and fixes for various components in the Enterprise AI system.
"""

# Import patches to make them available
from enterprise_ai.agent.patches.llm_agent_fix import fixed_init, initialize_mcp, fixed_execute_tool
