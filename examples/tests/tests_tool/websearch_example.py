#!/usr/bin/env python
"""
Enterprise AI WebSearch Examples (Real Implementation)

This script demonstrates how to use the WebSearch tool via direct object creation
and manipulation, bypassing Pydantic validation issues.
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
from enterprise_ai.mcp.client import MCPClient
from enterprise_ai.mcp.server import get_mcp_server
from enterprise_ai.tool.core.base import BaseTool

# Import WebSearch directly - we'll fix it later
from enterprise_ai.tool.research.web_search import WebSearch


# Create an adapter that avoids inheritance problems with Pydantic
class WebSearchAdapter:
    """An adapter for WebSearch that avoids Pydantic validation issues."""

    def __init__(self):
        """Initialize the adapter with WebSearch name/description/parameters."""
        # Get the class static attributes
        self.name = "web_search"
        self.description = """Search the web for real-time information about any topic.
        This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions.
        If the primary search engine fails, it automatically falls back to alternative engines."""
        self.parameters = getattr(WebSearch, "parameters", {})

    async def execute(self, **kwargs):
        """Execute the search by manually creating and initializing WebSearch."""
        try:
            # Create a minimal but working WebSearch instance
            from enterprise_ai.tool.research.web_search import WebContentFetcher
            from enterprise_ai.config import get_config

            # This is our secret trick - create a new WebSearch instance
            # but DON'T call __init__ which causes problems
            websearch = WebSearch.__new__(WebSearch)

            # Set required BaseTool attributes using object.__setattr__
            # to bypass Pydantic validation
            object.__setattr__(websearch, "name", self.name)
            object.__setattr__(websearch, "description", self.description)
            object.__setattr__(websearch, "parameters", self.parameters)

            # Initialize other needed attributes
            object.__setattr__(websearch, "_search_engines", {})
            # Call the initialization method
            websearch._initialize_search_engines()

            # Set up content fetcher
            object.__setattr__(websearch, "content_fetcher", WebContentFetcher())

            # Set up results cache
            object.__setattr__(websearch, "_results_cache", {})
            object.__setattr__(websearch, "_cache_expiry", get_config("search.cache_expiry", 300))

            # Now that our WebSearch is fully initialized, execute the search
            return await websearch.execute(**kwargs)

        except Exception as e:
            print_error(f"WebSearch execution error: {e}")
            import traceback

            traceback.print_exc()
            return ToolResult(error=f"Error: {str(e)}")


# ===== TEST EXAMPLES =====


async def run_search_example(session_id, query, **kwargs):
    """Run a search query using our adapter."""
    try:
        # Create the WebSearchAdapter
        search_adapter = WebSearchAdapter()

        # Execute search directly through adapter
        return await search_adapter.execute(query=query, **kwargs)
    except Exception as e:
        print_error(f"Search execution error: {e}")
        import traceback

        traceback.print_exc()
        return ToolResult(error=f"Error: {str(e)}")


async def basic_search_example() -> None:
    """Example of basic web search functionality."""
    print_section("Basic Web Search")

    try:
        # Create a unique session ID
        session_id = f"test-session-{uuid.uuid4()}"

        # Run a basic search
        print_info("Performing a basic search for 'Enterprise AI frameworks'...")
        async with AsyncTimer("Basic search"):
            result = await run_search_example(
                session_id=session_id, query="Enterprise AI frameworks", num_results=3
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")
        else:
            print_error(f"Unexpected result type: {type(result)}")

    except Exception as e:
        print_error(f"Error in basic search example: {e}")
        import traceback

        traceback.print_exc()


async def search_engines_example() -> None:
    """Example of using different search engines."""
    print_section("Different Search Engines")

    try:
        # Create a unique session ID
        session_id = f"test-session-{uuid.uuid4()}"

        # Try different search engines for the same query
        engines = ["google", "bing", "duckduckgo", "auto"]
        query = "Python programming language"

        for engine in engines:
            print_info(f"\nSearching with {engine.capitalize()} engine...")
            try:
                async with AsyncTimer(f"{engine.capitalize()} search"):
                    result = await run_search_example(
                        session_id=session_id, query=query, num_results=2, search_engine=engine
                    )

                if isinstance(result, ToolResult):
                    if result.error:
                        print_warning(f"Search error: {result.error}")
                    else:
                        # Just print the first part to keep output manageable
                        output_lines = result.output.split("\n")
                        print("\n".join(output_lines[:10]))
                        if len(output_lines) > 10:
                            print("... (output truncated)")
            except Exception as e:
                print_warning(f"Error with {engine} engine: {e}")

    except Exception as e:
        print_error(f"Error in search engines example: {e}")
        import traceback

        traceback.print_exc()


async def content_fetch_example() -> None:
    """Example of fetching and analyzing content from search results."""
    print_section("Content Fetching")

    try:
        # Create a unique session ID
        session_id = f"test-session-{uuid.uuid4()}"

        # Perform a search with content fetching enabled
        print_info("Searching for 'climate change solutions' with content fetching...")
        async with AsyncTimer("Content fetch search"):
            result = await run_search_example(
                session_id=session_id,
                query="climate change solutions",
                num_results=2,
                fetch_content=True,
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                print(result.output)
                print_info("\nWhen content fetching is enabled, the WebSearch tool will:")
                print("1. Retrieve the full HTML content of each result page")
                print("2. Extract relevant text content for analysis")
                print("3. Include content previews in the results")
                print("4. Make the raw content available for further processing")

    except Exception as e:
        print_error(f"Error in content fetch example: {e}")
        import traceback

        traceback.print_exc()


async def search_parameters_example() -> None:
    """Example of controlling search parameters."""
    print_section("Search Parameters")

    try:
        # Create a unique session ID
        session_id = f"test-session-{uuid.uuid4()}"

        # Example with language and country parameters
        print_info("Searching in French (fr) from France (fr)...")
        async with AsyncTimer("French search"):
            result = await run_search_example(
                session_id=session_id,
                query="actualités politiques",  # "political news" in French
                num_results=3,
                lang="fr",
                country="fr",
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                output_lines = result.output.split("\n")
                print("\n".join(output_lines[:15]))
                if len(output_lines) > 15:
                    print("... (output truncated)")

        print_info("\nThe WebSearch tool provides these parameters:")
        print("- num_results: Controls how many search results to return")
        print("- lang: Sets the language code for results (e.g., 'en', 'fr', 'de')")
        print("- country: Sets the country code for results (e.g., 'us', 'fr', 'de')")
        print("- fetch_content: Boolean to control content retrieval")
        print("- search_engine: Specify which search engine to use")

    except Exception as e:
        print_error(f"Error in search parameters example: {e}")
        import traceback

        traceback.print_exc()


async def error_handling_example() -> None:
    """Example of handling search errors and edge cases."""
    print_section("Error Handling")

    try:
        # Create a unique session ID
        session_id = f"test-session-{uuid.uuid4()}"

        # Empty query
        print_info("Attempting search with empty query...")
        async with AsyncTimer("Empty query"):
            result = await run_search_example(session_id=session_id, query="")

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        # Invalid search engine
        print_info("\nAttempting search with invalid search engine...")
        async with AsyncTimer("Invalid engine"):
            result = await run_search_example(
                session_id=session_id, query="test query", search_engine="invalid_engine"
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        print_info("\nThe WebSearch tool handles these common errors:")
        print("- Empty or invalid queries")
        print("- Invalid search engine specifications")
        print("- Connection failures (with automatic fallback to other engines)")
        print("- Rate limiting issues")
        print("- Content retrieval failures")

    except Exception as e:
        print_error(f"Error in error handling example: {e}")
        import traceback

        traceback.print_exc()


async def run_examples() -> None:
    """Run all web search examples."""
    try:
        await basic_search_example()
        separator()

        await search_engines_example()
        separator()

        await content_fetch_example()
        separator()

        await search_parameters_example()
        separator()

        await error_handling_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point for web search examples."""
    print_title("Enterprise AI Web Search Examples (Real Implementation)")
    print_info(
        "This script demonstrates the actual WebSearch tool functionality with real searches"
    )

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All web search examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
