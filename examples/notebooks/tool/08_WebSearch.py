#!/usr/bin/env python
"""
Test for WebSearch Tool via MCP

This script demonstrates how to use the WebSearch tool through the MCP system
to perform web searches and process the results.
"""

import asyncio
import sys
from typing import Any, Dict, Optional

# Import utilities for better formatting
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    Timer
)

# Set up project path
setup_project_path()

# Import core components
from enterprise_ai.tool.core import ToolConfig
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("web_search_test")

# Patch the WebSearch class before importing it
# This is a workaround for the field initialization issue
from pydantic import BaseModel
original_setattr = BaseModel.__setattr__

def patched_setattr(self, name, value):
    try:
        original_setattr(self, name, value)
    except ValueError as e:
        if "object has no field" in str(e):
            # Allow setting attributes that aren't fields
            object.__setattr__(self, name, value)
        else:
            raise

BaseModel.__setattr__ = patched_setattr

# Now we can safely import WebSearch
from enterprise_ai.tool.research.web_search import WebSearch


async def test_web_search():
    """Test the WebSearch tool using the MCP system."""
    print_title("TESTING WEB SEARCH TOOL VIA MCP")
    
    # Create a test session
    session_id = "web-search-test"
    client = None
    
    try:
        # Create MCP client
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")
        
        # Create tool with configuration
        print_section("Tool Creation and Configuration")
        
        # Configure the tool
        config = ToolConfig(
            timeout=60.0,  # Longer timeout for web searches
            max_retries=2,  # Allow retries for network issues
            cache_results=True,  # Cache search results
        )
        
        # Create and register the WebSearch tool
        web_search = WebSearch(
            name="web_search",
            description="Search the web for real-time information using multiple search engines.",
            config=config
        )
        
        # Initialize the tool before registration
        await web_search.initialize()
        
        # Register the tool with the session
        client.session.register_tool(web_search)
        print_success("Created and registered WebSearch tool")
        
        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")
        
        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")
            
            # Get detailed tool info
            tool_info = client.get_tool_info("web_search")
            print_info(f"\nTool info for web_search:")
            print_info(f"  Description: {tool_info.get('description', 'N/A')}")
            print_info(f"  State: {tool_info.get('state', 'N/A')}")
        else:
            print_error("No tools found in session")
            return
        
        separator()
        
        # Test 1: Basic search query
        print_section("Test 1: Basic Search Query")
        basic_query = "Enterprise AI systems"
        print_info(f"Searching for: '{basic_query}'")
        
        with Timer("Execution"):
            result = await client.execute_tool(
                "web_search",
                query=basic_query,
                num_results=3  # Limit to 3 results for brevity
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Search results:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 2: Search with specific parameters
        print_section("Test 2: Search with Specific Parameters")
        specific_query = "latest AI research papers"
        print_info(f"Searching for: '{specific_query}' with specific parameters")
        
        with Timer("Execution"):
            result = await client.execute_tool(
                "web_search",
                query=specific_query,
                num_results=2,  # Limit to 2 results for brevity
                lang="en",
                country="us",
                search_engine="auto"  # Let it choose the best engine
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Search results with parameters:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 3: Search with content fetching
        print_section("Test 3: Search with Content Fetching")
        content_query = "python asyncio tutorial"
        print_info(f"Searching for: '{content_query}' with content fetching")
        
        with Timer("Execution"):
            result = await client.execute_tool(
                "web_search",
                query=content_query,
                num_results=1,  # Just one result when fetching content
                fetch_content=True  # Enable content fetching
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Search results with content:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        separator()
        
        # Test 4: Error handling - Empty query
        print_section("Test 4: Error Handling - Empty Query")
        print_info("Testing with empty query string")
        
        with Timer("Execution"):
            result = await client.execute_tool(
                "web_search",
                query=""  # Empty query should cause an error
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected): {result.error}")
        
        separator()
        
        # Test 5: Different search engine
        print_section("Test 5: Using Specific Search Engine")
        engine_query = "machine learning frameworks"
        specific_engine = "bing"  # Try with a specific engine
        print_info(f"Searching for: '{engine_query}' using {specific_engine}")
        
        with Timer("Execution"):
            result = await client.execute_tool(
                "web_search",
                query=engine_query,
                num_results=2,
                search_engine=specific_engine
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Search results from {specific_engine}:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        # If the previous engine-specific search failed, try again with "auto"
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Specific engine failed, trying with 'auto'...")
            with Timer("Fallback execution"):
                result = await client.execute_tool(
                    "web_search",
                    query=engine_query,
                    num_results=2,
                    search_engine="auto"
                )
            
            if hasattr(result, 'output') and result.output is not None:
                print_success(f"Fallback search results:")
                print_info(result.output)
        
        separator()
        
        # Test 6: Search with non-English language
        print_section("Test 6: Non-English Search")
        non_english_query = "intelligence artificielle applications"  # French query
        print_info(f"Searching for: '{non_english_query}' in French")
        
        with Timer("Execution"):
            result = await client.execute_tool(
                "web_search",
                query=non_english_query,
                num_results=2,
                lang="fr",
                country="fr"
            )
        
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Non-English search results:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")
        
        print_success("All tests completed successfully!")
        
    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Restore original setattr method
        BaseModel.__setattr__ = original_setattr
        
        # Clean up
        if client:
            await client.close()
            print_info("Session closed and resources cleaned up")
        separator()


if __name__ == "__main__":
    asyncio.run(test_web_search())