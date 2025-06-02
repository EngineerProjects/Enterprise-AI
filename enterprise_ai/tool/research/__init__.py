"""
Research tools for Enterprise AI.

This module provides tools for information gathering and research using
the unified tool system and updated LLM integration.
"""

from enterprise_ai.tool.research.web_search import WebSearch, SearchResult, SearchResponse
from enterprise_ai.tool.research.deep_research import DeepResearch, ResearchInsight, ResearchSummary

__all__ = [
    "WebSearch",
    "SearchResult", 
    "SearchResponse",
    "DeepResearch",
    "ResearchInsight",
    "ResearchSummary",
]