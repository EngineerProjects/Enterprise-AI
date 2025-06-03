#!/usr/bin/env python3
"""
Simple WebSearch Tool Testing Script

Tests each aspect of the websearch tool individually with configurable LLM support.
"""

import asyncio
import sys
import os
from pathlib import Path

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.research.web_search import WebSearch
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class WebSearchTester:
    """Simple websearch tool tester with LLM configuration support."""
    
    def __init__(self):
        self.websearch = None
    
    async def show_current_config(self):
        """Show current configuration."""
        print_header("Current Configuration", "single")
        
        # LLM Configuration
        provider = get_config("llm.default_provider", "not configured")
        model = get_config("llm.default_model", "not configured")
        print_test(f"LLM Provider: {provider}", "pass")
        print_test(f"LLM Model: {model}", "pass")
        
        # Search Configuration
        default_engine = get_config("search.engine", "auto")
        rate_limit = get_config("search.rate_limit", 2)
        cache_expiry = get_config("search.cache_expiry", 300)
        print_test(f"Default Search Engine: {default_engine}", "pass")
        print_test(f"Rate Limit: {rate_limit} req/sec", "pass")
        print_test(f"Cache Expiry: {cache_expiry}s", "pass")

    async def show_tool_description(self):
        """Show the websearch tool description and capabilities."""
        print_header("WebSearch Tool Description", "double")
        
        if self.websearch:
            print_chat("tool", f"Tool Name: {self.websearch.name}")
            print_chat("tool", f"Description: {self.websearch.description.strip()}")
            
            # Show capabilities
            if hasattr(self.websearch, 'capabilities'):
                caps = [str(cap) for cap in self.websearch.capabilities]
                print_chat("tool", f"Capabilities: {', '.join(caps)}")
            
            # Show parameters
            print_chat("tool", "Available Parameters:")
            for param_name, param_info in self.websearch.parameters.get("properties", {}).items():
                required = param_name in self.websearch.parameters.get("required", [])
                param_type = param_info.get("type", "unknown")
                description = param_info.get("description", "No description")
                req_text = " (required)" if required else " (optional)"
                print_chat("tool", f"  • {param_name} ({param_type}){req_text}: {description}")

    async def setup(self, llm_provider=None, llm_model=None):
        """Initialize websearch tool with optional LLM configuration."""
        print_header("WebSearch Tool Test Suite", "double")
        
        # Show current config first
        await self.show_current_config()
        
        print_test("Setting up websearch tool", "running")
        
        # Create websearch with optional LLM override
        kwargs = {}
        if llm_provider:
            kwargs['llm_provider'] = llm_provider
            print_test(f"Using LLM Provider Override: {llm_provider}", "pass")
        if llm_model:
            kwargs['llm_model'] = llm_model
            print_test(f"Using LLM Model Override: {llm_model}", "pass")
        
        self.websearch = WebSearch(**kwargs)
        success = await self.websearch.initialize()
        
        if success:
            print_test("WebSearch tool initialized", "pass")
            await self.show_tool_description()
            return True
        else:
            print_test("WebSearch tool initialization failed", "fail")
            return False
    
    async def test_search(self, description: str, show_full_output: bool = False, **kwargs):
        """Test a single websearch query."""
        query = kwargs.get('query', 'unknown query')
        print_test(f"Testing: {description} - '{query}'", "running")
        
        try:
            with Timer(f"Search: {query}"):
                result = await self.websearch.execute(**kwargs)
            
            if isinstance(result, ToolResult) and result.success:
                print_test(f"{description}: SUCCESS", "pass")
                
                # Show result info
                if hasattr(result, 'results') and result.results:
                    print_chat("tool", f"Found {len(result.results)} results")
                    
                    # Show first result details
                    first_result = result.results[0]
                    print_chat("tool", f"First result: {first_result.title}")
                    print_chat("tool", f"URL: {first_result.url}")
                    
                    if first_result.description:
                        desc = first_result.description
                        print_chat("tool", f"Description: {desc}")
                
                # Show metadata if available
                if hasattr(result, 'search_metadata') and result.search_metadata:
                    meta = result.search_metadata
                    print_chat("tool", f"Metadata: {meta.total_results} results, {meta.time_taken:.2f}s, engines: {', '.join(meta.engines_tried)}")
                
                # Show full output if requested or if short
                if hasattr(result, 'result') and result.result:
                    output = str(result.result)
                    if show_full_output or len(output) <= 500:
                        print_chat("tool", output)
                    elif len(output) > 500:
                        print_chat("tool", output[:500] + "...")
                
                return result, True
            else:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: FAILED - {error_msg}", "fail")
                return result, False
                
        except Exception as e:
            print_test(f"{description}: EXCEPTION - {e}", "fail")
            return None, False
    
    async def run_basic_search_tests(self):
        """Test basic search functionality."""
        print_header("Basic Search Tests", "single")
        
        tests = [
            ("Simple Query", {"query": "Python programming"}),
            ("Limited Results", {"query": "machine learning", "num_results": 3}),
            ("Language Specific", {"query": "programmation Python", "lang": "fr", "num_results": 3}),
            ("Country Specific", {"query": "weather today", "country": "us", "num_results": 3}),
        ]
        
        for description, kwargs in tests:
            result, success = await self.test_search(description, **kwargs)
            if not success and "Simple Query" in description:
                print_test("Basic search failed, check search engine configuration", "warn")
                return False
        
        return True
    
    async def run_search_engine_tests(self):
        """Test different search engines."""
        print_header("Search Engine Tests", "single")
        
        tests = [
            ("Auto Engine", {"query": "artificial intelligence", "search_engine": "auto", "num_results": 2}),
            ("DuckDuckGo", {"query": "artificial intelligence", "search_engine": "duckduckgo", "num_results": 2}),
            ("Google", {"query": "artificial intelligence", "search_engine": "google", "num_results": 2}),
            ("Bing", {"query": "artificial intelligence", "search_engine": "bing", "num_results": 2}),
        ]
        
        for description, kwargs in tests:
            await self.test_search(description, **kwargs)
    
    async def run_content_fetching_tests(self):
        """Test content fetching functionality."""
        print_header("Content Fetching Tests", "single")
        
        tests = [
            ("Search with Content", {"query": "Enterprise AI multi-agent", "num_results": 2, "fetch_content": True}),
            ("Search without Content", {"query": "Enterprise AI multi-agent", "num_results": 2, "fetch_content": False}),
        ]
        
        for description, kwargs in tests:
            result, success = await self.test_search(description, show_full_output=True, **kwargs)
            
            if success and hasattr(result, 'results'):
                has_content = any(r.raw_content for r in result.results)
                expected_content = kwargs.get('fetch_content', False)
                
                if expected_content and has_content:
                    print_test("Content fetching: SUCCESS", "pass")
                elif not expected_content and not has_content:
                    print_test("No content fetching: SUCCESS", "pass")
                elif expected_content and not has_content:
                    print_test("Content fetching: FAILED (no content retrieved)", "warn")
                else:
                    print_test("Content fetching: UNEXPECTED", "warn")
    
    async def run_error_handling_tests(self):
        """Test error handling and edge cases."""
        print_header("Error Handling Tests", "single")
        
        tests = [
            ("Empty Query", {"query": ""}),
            ("Invalid Engine", {"query": "test", "search_engine": "invalid_engine"}),
            ("Zero Results", {"query": "test", "num_results": 0}),
            ("Large Results", {"query": "test", "num_results": 100}),
        ]
        
        for description, kwargs in tests:
            result, success = await self.test_search(description, **kwargs)
            # These tests are expected to fail or return empty results
            if description == "Empty Query" and not success:
                print_test("Empty query handling: CORRECT", "pass")
            elif description == "Invalid Engine" and not success:
                print_test("Invalid engine handling: CORRECT", "pass")
    
    async def run_performance_tests(self):
        """Test performance and caching."""
        print_header("Performance Tests", "single")
        
        # Test same query twice to check caching
        query = "Enterprise AI framework testing"
        
        print_test("Testing caching behavior", "running")
        
        # First search
        result1, success1 = await self.test_search("First Search (no cache)", query=query, num_results=3)
        
        # Second search (should use cache if enabled)
        result2, success2 = await self.test_search("Second Search (cached)", query=query, num_results=3)
        
        if success1 and success2:
            print_test("Caching test completed", "pass")
        else:
            print_test("Caching test incomplete", "warn")
    
    async def cleanup(self):
        """Clean up websearch resources."""
        print_header("Cleanup", "single")
        
        if self.websearch:
            print_test("Cleaning up websearch", "running")
            await self.websearch.cleanup()
            print_test("WebSearch cleanup complete", "pass")


async def main():
    """Run all websearch tests with comprehensive coverage."""
    tester = WebSearchTester()
    
    # Setup with default configuration
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run core test suites
        await tester.run_basic_search_tests()
        await tester.run_search_engine_tests()
        await tester.run_content_fetching_tests()
        await tester.run_error_handling_tests()
        await tester.run_performance_tests()
        
        print_header("All WebSearch Tests Complete!", "double")
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
    except Exception as e:
        print_test(f"Unexpected error: {e}", "fail")
    finally:
        await tester.cleanup()
    
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)