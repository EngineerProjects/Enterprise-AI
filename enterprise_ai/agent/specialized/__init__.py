"""
Specialized agents for Enterprise AI.

This module provides pre-built, specialized agent types that are optimized
for specific tasks and domains, ready to be used out of the box.
"""

from .general_purpose import GeneralPurposeAgent
from .developer import DeveloperAgent
from .researcher import ResearcherAgent
from .browser_agent import BrowserAgent

__all__ = [
    "GeneralPurposeAgent",
    "DeveloperAgent", 
    "ResearcherAgent",
    "BrowserAgent",
]
