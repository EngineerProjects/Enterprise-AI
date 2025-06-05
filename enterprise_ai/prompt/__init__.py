"""
Enterprise AI Prompt System

Simple, clean prompt management following OpenManus approach.
"""

from enterprise_ai.prompt.manager import (
    get_system_prompt,
    get_next_step_prompt, 
    get_available_agent_types,
    PromptManager
)

# Import specific prompts for convenience
from . import cot, react, swe, browser, planning, reflection, mcp

__all__ = [
    "get_system_prompt",
    "get_next_step_prompt",
    "get_available_agent_types", 
    "PromptManager",
    "cot",
    "react", 
    "swe",
    "browser",
    "planning",
    "reflection",
    "mcp"
]
