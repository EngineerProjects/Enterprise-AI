#!/usr/bin/env python
"""
Enterprise AI WebSearch Examples (Mock Implementation)

This script demonstrates how to use the WebSearch tool conceptually:
- Basic web searching
- Using different search engines
- Fetching and analyzing web content
- Controlling search parameters
- Error handling
"""

import asyncio
import sys
import time
import random
from typing import Dict, List, Optional, Any

# Import common utilities
from notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    AsyncTimer,
    run_async
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.tool.core.result import ToolResult


class MockSearchResult:
    """Mock search result for demonstrations."""
    def __init__(self, position, url, title, description, source):
        self.position = position
        self.url = url
        self.title = title
        self.description = description
        self.source = source
        self.raw_content = None


class MockWebSearch:
    """Mock version of the WebSearch tool to demonstrate concepts."""
    
    def __init__(self):
        """Initialize the mock search tool."""
        self.name = "web_search"
        self.description = """Search the web for real-time information about any topic.
This tool returns comprehensive search results with relevant information, URLs, titles, and descriptions."""
    
    async def execute(self, **kwargs):
        """Simulate execution of a web search."""
        # Extract parameters
        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", 5)
        fetch_content = kwargs.get("fetch_content", False)
        search_engine = kwargs.get("search_engine", "auto")
        lang = kwargs.get("lang", "en")
        country = kwargs.get("country", "us")
        
        # Validate input
        if not query:
            return ToolResult(error="Query parameter is required")
        
        if search_engine not in ["auto", "google", "bing", "duckduckgo", "baidu"]:
            return ToolResult(error=f"Invalid search engine: {search_engine}")
        
        # Simulate search delay
        await asyncio.sleep(0.5 + random.random())
        
        # Generate mock results
        mock_results = self._generate_mock_results(query, num_results, search_engine)
        
        # Fetch content if requested
        if fetch_content:
            await self._add_mock_content(mock_results)
        
        # Format the output
        output = self._format_search_output(query, mock_results, search_engine, lang, country)
        
        # Return results
        return ToolResult(output=output)
    
    def _generate_mock_results(self, query, num_results, engine):
        """Generate mock search results."""
        results = []
        domains = ["example.com", "informative-site.org", "knowledgebase.net", 
                  "learning-portal.edu", "reference.io"]
        
        for i in range(num_results):
            domain = random.choice(domains)
            url = f"https://www.{domain}/article-{i+1}"
            title = f"Information about {query.title()} - Article {i+1}"
            description = f"This page contains detailed information about {query} with explanations, examples, and references."
            
            results.append(MockSearchResult(
                position=i+1,
                url=url,
                title=title,
                description=description,
                source=engine
            ))
            
        return results
    
    async def _add_mock_content(self, results):
        """Add mock content to search results."""
        for result in results:
            # Simulate content retrieval delay
            await asyncio.sleep(0.2)
            
            # Generate mock content
            content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{result.title}</title>
</head>
<body>
    <h1>{result.title}</h1>
    <p>{result.description}</p>
    <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt 
    ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation 
    ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>
    <h2>Key Points</h2>
    <ul>
        <li>Important information about the topic</li>
        <li>Relevant facts and figures</li>
        <li>Historical context and background</li>
    </ul>
</body>
</html>"""
            
            result.raw_content = content
    
    def _format_search_output(self, query, results, engine, lang, country):
        """Format search results into readable output."""
        output = [f"Search results for '{query}':"]
        
        for i, result in enumerate(results, 1):
            # Add title with position number
            title = result.title.strip() or "No title"
            output.append(f"\n{i}. {title}")
            
            # Add URL with proper indentation
            output.append(f"   URL: {result.url}")
            
            # Add description if available
            if result.description:
                desc = result.description.strip()
                output.append(f"   Description: {desc}")
            
            # Add content preview if available
            if result.raw_content:
                content_preview = result.raw_content.replace("\n", " ")[:100]
                output.append(f"   Content Preview: {content_preview}...")
        
        # Add metadata
        output.extend([
            "\nMetadata:",
            f"- Total results: {len(results)}",
            f"- Language: {lang}",
            f"- Country: {country}",
            f"- Engine used: {engine}",
            f"- Time taken: {0.5 + random.random():.2f} seconds"
        ])
        
        return "\n".join(output)


async def basic_search_example() -> None:
    """Example of basic web search functionality."""
    print_section("Basic Web Search")

    # Create the mock WebSearch tool
    search_tool = MockWebSearch()

    try:
        # Basic search with default parameters
        print_info("Performing a basic search for 'Enterprise AI frameworks'...")
        async with AsyncTimer("Basic search"):
            result = await search_tool.execute(
                query="Enterprise AI frameworks",
                num_results=3
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


async def search_engines_example() -> None:
    """Example of using different search engines."""
    print_section("Different Search Engines")

    # Create the mock WebSearch tool
    search_tool = MockWebSearch()

    try:
        # Try different search engines for the same query
        engines = ["google", "bing", "duckduckgo", "auto"]
        query = "Python programming language"

        for engine in engines:
            print_info(f"\nSearching with {engine.capitalize()} engine...")
            try:
                async with AsyncTimer(f"{engine.capitalize()} search"):
                    result = await search_tool.execute(
                        query=query,
                        num_results=2,
                        search_engine=engine
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


async def content_fetch_example() -> None:
    """Example of fetching and analyzing content from search results."""
    print_section("Content Fetching")

    # Create the mock WebSearch tool
    search_tool = MockWebSearch()

    try:
        # Perform a search with content fetching enabled
        print_info("Searching for 'climate change solutions' with content fetching...")
        async with AsyncTimer("Content fetch search"):
            result = await search_tool.execute(
                query="climate change solutions",
                num_results=2,
                fetch_content=True
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                print(result.output)
                print_info("\nNote: When content fetching is enabled, the WebSearch tool will:")
                print("1. Retrieve the full HTML content of each result page")
                print("2. Extract relevant text content for analysis")
                print("3. Include content previews in the results")
                print("4. Make the raw content available for further processing")

    except Exception as e:
        print_error(f"Error in content fetch example: {e}")


async def search_parameters_example() -> None:
    """Example of controlling search parameters."""
    print_section("Search Parameters")

    # Create the mock WebSearch tool
    search_tool = MockWebSearch()

    try:
        # Example with language and country parameters
        print_info("Searching in French (fr) from France (fr)...")
        async with AsyncTimer("French search"):
            result = await search_tool.execute(
                query="actualités politiques",  # "political news" in French
                num_results=3,
                lang="fr",
                country="fr"
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Error: {result.error}")
            else:
                output_lines = result.output.split("\n")
                print("\n".join(output_lines[:15]))
                if len(output_lines) > 15:
                    print("... (output truncated)")

        # Example with different result count
        print_info("\nControlling the number of search results:")
        print_info("Note: The WebSearch tool provides these parameters:")
        print("- num_results: Controls how many search results to return")
        print("- lang: Sets the language code for results (e.g., 'en', 'fr', 'de')")
        print("- country: Sets the country code for results (e.g., 'us', 'fr', 'de')")
        print("- fetch_content: Boolean to control content retrieval")
        print("- search_engine: Specify which search engine to use")

    except Exception as e:
        print_error(f"Error in search parameters example: {e}")


async def error_handling_example() -> None:
    """Example of handling search errors and edge cases."""
    print_section("Error Handling")

    # Create the mock WebSearch tool
    search_tool = MockWebSearch()

    try:
        # Empty query
        print_info("Attempting search with empty query...")
        async with AsyncTimer("Empty query"):
            result = await search_tool.execute(
                query=""
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        # Invalid search engine
        print_info("\nAttempting search with invalid search engine...")
        async with AsyncTimer("Invalid engine"):
            result = await search_tool.execute(
                query="test query",
                search_engine="invalid_engine"
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        print_info("\nNote: The WebSearch tool handles these common errors:")
        print("- Empty or invalid queries")
        print("- Invalid search engine specifications")
        print("- Connection failures (with automatic fallback to other engines)")
        print("- Rate limiting issues")
        print("- Content retrieval failures")

    except Exception as e:
        print_error(f"Error in error handling example: {e}")


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
    print_title("Enterprise AI Web Search Examples (Mock Implementation)")
    print_info("Note: This script demonstrates WebSearch concepts using a mock implementation")
    print_info("The actual WebSearch tool provides real web search results")

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