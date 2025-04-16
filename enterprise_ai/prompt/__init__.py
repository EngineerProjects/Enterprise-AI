"""
Prompt management for Enterprise AI.

This module provides functionality for loading, formatting, and managing
prompts throughout the Enterprise AI system.
"""

from enterprise_ai.prompt.base import (
    PromptTemplate,
    PromptLibrary,
    get_prompt_library,
    get_prompt,
    format_prompt,
)

__all__ = [
    "PromptTemplate",
    "PromptLibrary",
    "get_prompt_library",
    "get_prompt",
    "format_prompt",
]
