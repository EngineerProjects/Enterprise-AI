#!/usr/bin/env python
"""
Enterprise AI DeepResearch Examples

This script demonstrates how to use the DeepResearch tool:
- Basic multi-level research
- Exploring topics with automatic follow-up queries
- Analyzing sources and extracting insights
- Working with different research parameters
"""

import asyncio
import sys
import uuid
from typing import Dict, List, Optional, Any

# Import common utilities
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    AsyncTimer,
    run_async,
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.research.deep_research import DeepResearch, ResearchSummary


# Create an adapter that avoids inheritance problems with Pydantic
class DeepResearchAdapter:
    """An adapter for DeepResearch that avoids Pydantic validation issues."""

    def __init__(self):
        """Initialize the adapter with DeepResearch name/description/parameters."""
        # Get the class static attributes
        self.name = "deep_research"
        self.description = """Performs comprehensive research on a topic through multi-level web searches
        and content analysis. Returns a structured summary of findings with source
        attribution and relevance ratings."""
        self.parameters = getattr(DeepResearch, "parameters", {})

    async def execute(self, **kwargs):
        """Execute the research by manually creating and initializing DeepResearch."""
        try:
            # Create a minimal but working DeepResearch instance
            from enterprise_ai.tool.research.web_search import WebSearch
            from enterprise_ai.llm.simple import LLM

            # Create a DeepResearch instance without calling __init__
            deep_research = DeepResearch.__new__(DeepResearch)

            # Set required BaseTool attributes using object.__setattr__
            # to bypass Pydantic validation
            object.__setattr__(deep_research, "name", self.name)
            object.__setattr__(deep_research, "description", self.description)
            object.__setattr__(deep_research, "parameters", self.parameters)

            # Initialize WebSearch tool with a similar bypass
            web_search = WebSearch.__new__(WebSearch)
            object.__setattr__(web_search, "name", "web_search")
            object.__setattr__(web_search, "description", "Web search tool")
            object.__setattr__(web_search, "parameters", getattr(WebSearch, "parameters", {}))

            # Initialize WebSearch attributes
            object.__setattr__(web_search, "_search_engines", {})
            web_search._initialize_search_engines()

            # Set up content fetcher for WebSearch
            from enterprise_ai.tool.research.web_search import WebContentFetcher
            from enterprise_ai.config import get_config

            object.__setattr__(web_search, "content_fetcher", WebContentFetcher())

            # Set up results cache for WebSearch
            object.__setattr__(web_search, "_results_cache", {})
            object.__setattr__(web_search, "_cache_expiry", get_config("search.cache_expiry", 300))

            # Set up DeepResearch attributes
            object.__setattr__(deep_research, "search_tool", web_search)
            object.__setattr__(deep_research, "llm", LLM())

            # Now execute the research
            return await deep_research.execute(**kwargs)

        except Exception as e:
            print_error(f"DeepResearch execution error: {e}")
            import traceback

            traceback.print_exc()
            return ToolResult(error=f"Error: {str(e)}")


# ===== TEST EXAMPLES =====


async def basic_research_example():
    """Example of basic deep research functionality."""
    print_section("Basic Deep Research")

    try:
        # Create the adapter
        research_adapter = DeepResearchAdapter()

        # Perform a basic research query
        print_info("Researching 'Quantum computing applications in medicine'...")

        async with AsyncTimer("Basic research"):
            result = await research_adapter.execute(
                query="Quantum computing applications in medicine",
                max_depth=1,  # Keep it shallow for demo
                results_per_search=3,
                max_insights=10,
                time_limit_seconds=60,
            )

        if isinstance(result, ResearchSummary):
            if result.output:
                print(result.output)
                print_info(f"\nResearch depth: {result.depth_reached + 1}")
                print_info(f"Total insights: {len(result.insights)}")
                print_info(f"Sources visited: {len(result.visited_urls)}")
            if result.error:
                print_error(f"Error: {result.error}")
        else:
            print_error(f"Unexpected result type: {type(result)}")

    except Exception as e:
        print_error(f"Error in basic research example: {e}")
        import traceback

        traceback.print_exc()


async def deep_exploration_example():
    """Example of deeper exploration with multi-level research."""
    print_section("Multi-Level Deep Research")

    try:
        # Create the adapter
        research_adapter = DeepResearchAdapter()

        # Perform a deeper research query
        print_info("Researching 'Future of renewable energy storage' with multiple levels...")

        async with AsyncTimer("Multi-level research"):
            result = await research_adapter.execute(
                query="Future of renewable energy storage",
                max_depth=2,  # Deeper exploration
                results_per_search=3,
                max_insights=15,
                time_limit_seconds=90,
            )

        if isinstance(result, ResearchSummary):
            if result.output:
                print(result.output)
                print_info(f"\nResearch depth: {result.depth_reached + 1}")
                print_info(f"Total insights: {len(result.insights)}")
                print_info(f"Sources visited: {len(result.visited_urls)}")
            if result.error:
                print_error(f"Error: {result.error}")
        else:
            print_error(f"Unexpected result type: {type(result)}")

    except Exception as e:
        print_error(f"Error in deep exploration example: {e}")
        import traceback

        traceback.print_exc()


async def research_parameters_example():
    """Example of controlling research parameters."""
    print_section("Research Parameters")

    try:
        # Create the adapter
        research_adapter = DeepResearchAdapter()

        # Example with more focused parameters
        print_info("Conducting targeted research with specific parameters...")

        async with AsyncTimer("Targeted research"):
            result = await research_adapter.execute(
                query="Recent breakthroughs in natural language processing",
                max_depth=1,
                results_per_search=4,
                max_insights=5,  # Limited number of insights
                time_limit_seconds=60,
            )

        if isinstance(result, ResearchSummary):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        print_info("\nThe DeepResearch tool provides these parameters:")
        print("- max_depth: Controls the number of levels of follow-up queries (1-5)")
        print("- results_per_search: Number of search results to analyze per query (1-20)")
        print("- max_insights: Maximum number of insights to return")
        print("- time_limit_seconds: Maximum execution time in seconds")

    except Exception as e:
        print_error(f"Error in research parameters example: {e}")
        import traceback

        traceback.print_exc()


async def comparative_research_example():
    """Example of comparing research on two related topics."""
    print_section("Comparative Research")

    try:
        # Create the adapter
        research_adapter = DeepResearchAdapter()

        # Example comparing two related topics
        queries = [
            "Advantages of nuclear fusion energy",
            "Challenges of nuclear fusion implementation",
        ]

        for query in queries:
            print_info(f"\nResearching: '{query}'...")

            async with AsyncTimer(f"Research on {query}"):
                result = await research_adapter.execute(
                    query=query,
                    max_depth=1,
                    results_per_search=3,
                    max_insights=8,
                    time_limit_seconds=60,
                )

            if isinstance(result, ResearchSummary):
                if result.output:
                    print(result.output)
                if result.error:
                    print_error(f"Error: {result.error}")
            else:
                print_error(f"Unexpected result type: {type(result)}")

        print_info("\nComparative research allows you to explore multiple facets of complex topics")

    except Exception as e:
        print_error(f"Error in comparative research example: {e}")
        import traceback

        traceback.print_exc()


async def run_examples():
    """Run all deep research examples."""
    try:
        await basic_research_example()
        separator()

        await deep_exploration_example()
        separator()

        await research_parameters_example()
        separator()

        await comparative_research_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point for deep research examples."""
    print_title("Enterprise AI Deep Research Examples")
    print_info("This script demonstrates the actual DeepResearch tool functionality")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All deep research examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
