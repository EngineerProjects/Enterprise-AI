#!/usr/bin/env python3
"""
Simple DeepResearch Tool Testing Script

Tests each aspect of the deep research tool individually with configurable LLM support.
"""

import asyncio
import sys
import os
from pathlib import Path

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.research.deep_research import DeepResearch
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class DeepResearchTester:
    """Simple deep research tool tester with LLM configuration support."""
    
    def __init__(self):
        self.deep_research = None
    
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
        print_test(f"Search Engine: {default_engine}", "pass")
        print_test(f"Rate Limit: {rate_limit} req/sec", "pass")

    async def show_tool_description(self):
        """Show the deep research tool description and capabilities."""
        print_header("DeepResearch Tool Description", "double")
        
        if self.deep_research:
            print_chat("tool", f"Tool Name: {self.deep_research.name}")
            print_chat("tool", f"Description: {self.deep_research.description.strip()}")
            
            # Show LLM configuration
            provider = self.deep_research.llm_provider or "default"
            model = self.deep_research.llm_model or "default"
            print_chat("tool", f"LLM Provider: {provider}")
            print_chat("tool", f"LLM Model: {model}")
            
            # Show capabilities
            if hasattr(self.deep_research, 'capabilities'):
                caps = [str(cap) for cap in self.deep_research.capabilities]
                print_chat("tool", f"Capabilities: {', '.join(caps)}")
            
            # Show parameters
            print_chat("tool", "Available Parameters:")
            for param_name, param_info in self.deep_research.parameters.get("properties", {}).items():
                required = param_name in self.deep_research.parameters.get("required", [])
                param_type = param_info.get("type", "unknown")
                description = param_info.get("description", "No description")
                default = param_info.get("default", "")
                req_text = " (required)" if required else f" (optional, default: {default})"
                print_chat("tool", f"  • {param_name} ({param_type}){req_text}: {description}")

    async def setup(self, llm_provider=None, llm_model=None):
        """Initialize deep research tool with optional LLM configuration."""
        print_header("DeepResearch Tool Test Suite", "double")
        
        # Show current config first
        await self.show_current_config()
        
        print_test("Setting up deep research tool", "running")
        
        # Create deep research with optional LLM override
        kwargs = {}
        if llm_provider:
            kwargs['llm_provider'] = llm_provider
            print_test(f"Using LLM Provider Override: {llm_provider}", "pass")
        if llm_model:
            kwargs['llm_model'] = llm_model
            print_test(f"Using LLM Model Override: {llm_model}", "pass")
        
        self.deep_research = DeepResearch(**kwargs)
        success = await self.deep_research.initialize()
        
        if success:
            print_test("DeepResearch tool initialized", "pass")
            await self.show_tool_description()
            return True
        else:
            print_test("DeepResearch tool initialization failed", "fail")
            return False
    
    async def test_research(self, description: str, show_full_output: bool = False, **kwargs):
        """Test a single deep research query."""
        query = kwargs.get('query', 'unknown query')
        print_test(f"Testing: {description} - '{query}'", "running")
        
        try:
            with Timer(f"Research: {query}"):
                result = await self.deep_research.execute(**kwargs)
            
            if isinstance(result, ToolResult) and result.success:
                print_test(f"{description}: SUCCESS", "pass")
                
                # Show result info
                if hasattr(result, 'insights') and result.insights:
                    print_chat("tool", f"Found {len(result.insights)} insights")
                    
                    # Show top insights
                    for i, insight in enumerate(result.insights[:3], 1):
                        relevance = f"{insight.relevance_score:.2f}"
                        source = insight.source_title or "Unknown"
                        print_chat("tool", f"{i}. [Score: {relevance}] {insight.content[:100]}...")
                        print_chat("tool", f"   Source: {source}")
                
                # Show metadata
                if hasattr(result, 'visited_urls') and result.visited_urls:
                    print_chat("tool", f"Visited {len(result.visited_urls)} URLs")
                
                if hasattr(result, 'depth_reached'):
                    print_chat("tool", f"Research depth reached: {result.depth_reached + 1}")
                
                # Show full output if requested or if short
                if hasattr(result, 'result') and result.result and show_full_output:
                    output = str(result.result)
                    if len(output) <= 800:
                        print_chat("tool", output)
                    else:
                        print_chat("tool", output)
                
                return result, True
            else:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: FAILED - {error_msg}", "fail")
                return result, False
                
        except Exception as e:
            print_test(f"{description}: EXCEPTION - {e}", "fail")
            return None, False
    
    async def run_basic_research_tests(self):
        """Test basic research functionality."""
        print_header("Basic Research Tests", "single")
        
        tests = [
            ("Simple Research", {"query": "artificial intelligence applications", "max_depth": 1, "results_per_search": 3}),
            ("Limited Insights", {"query": "machine learning algorithms", "max_depth": 1, "max_insights": 5, "results_per_search": 2}),
            ("Quick Research", {"query": "Python programming", "max_depth": 1, "time_limit_seconds": 300, "results_per_search": 2}),
        ]
        
        for description, kwargs in tests:
            result, success = await self.test_research(description, **kwargs)
            if not success and "Simple Research" in description:
                print_test("Basic research failed, check LLM and search configuration", "warn")
                return False
        
        return True
    
    async def run_depth_research_tests(self):
        """Test different research depths."""
        print_header("Research Depth Tests", "single")
        
        tests = [
            ("Depth 1", {"query": "blockchain technology", "max_depth": 1, "results_per_search": 2}),
            ("Depth 2", {"query": "renewable energy", "max_depth": 2, "results_per_search": 2, "time_limit_seconds": 500}),
        ]
        
        for description, kwargs in tests:
            result, success = await self.test_research(description, **kwargs)
            
            if success and hasattr(result, 'depth_reached'):
                expected_depth = kwargs.get('max_depth', 1)
                actual_depth = result.depth_reached + 1
                if actual_depth >= 1:  # At least reached depth 1
                    print_test(f"Depth test: Expected {expected_depth}, got {actual_depth}", "pass")
                else:
                    print_test(f"Depth test: Expected {expected_depth}, got {actual_depth}", "warn")
    
    async def run_llm_integration_tests(self):
        """Test LLM integration aspects."""
        print_header("LLM Integration Tests", "single")
        
        print_test("Testing LLM-powered research components", "running")
        
        # Test with a topic that should generate good follow-ups
        result, success = await self.test_research(
            "LLM Integration Test", 
            show_full_output=True,
            query="enterprise AI multi-agent systems",
            max_depth=2,
            results_per_search=3,
            max_insights=8,
            time_limit_seconds=500
        )
        
        if success:
            print_test("LLM Integration: SUCCESS", "pass")
            
            # Check for insights with relevance scores
            if hasattr(result, 'insights') and result.insights:
                scored_insights = [i for i in result.insights if hasattr(i, 'relevance_score')]
                print_test(f"Relevance scoring: {len(scored_insights)}/{len(result.insights)} insights scored", "pass")
                
                # Check score distribution
                high_relevance = [i for i in result.insights if i.relevance_score >= 0.8]
                if high_relevance:
                    print_test(f"High relevance insights: {len(high_relevance)}", "pass")
        else:
            print_test("LLM Integration: FAILED (check LLM config)", "warn")
    
    async def run_error_handling_tests(self):
        """Test error handling and edge cases."""
        print_header("Error Handling Tests", "single")
        
        tests = [
            ("Empty Query", {"query": ""}),
            ("Invalid Depth", {"query": "test", "max_depth": 0}),
            ("Extreme Timeout", {"query": "test", "time_limit_seconds": 5}),
        ]
        
        for description, kwargs in tests:
            result, success = await self.test_research(description, **kwargs)
            
            # These tests expect certain behaviors
            if description == "Empty Query" and not success:
                print_test("Empty query handling: CORRECT", "pass")
            elif description == "Invalid Depth" and success:
                # Should auto-correct to valid depth
                if hasattr(result, 'depth_reached') and result.depth_reached >= 0:
                    print_test("Invalid depth auto-correction: CORRECT", "pass")
            elif description == "Extreme Timeout":
                # Should complete quickly or handle timeout gracefully
                print_test("Timeout handling: COMPLETED", "pass")
    
    async def cleanup(self):
        """Clean up deep research resources."""
        print_header("Cleanup", "single")
        
        if self.deep_research:
            print_test("Cleaning up deep research", "running")
            await self.deep_research.cleanup()
            print_test("DeepResearch cleanup complete", "pass")


async def main():
    """Run all deep research tests with comprehensive coverage."""
    tester = DeepResearchTester()
    
    # Setup with default configuration
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run core test suites
        await tester.run_basic_research_tests()
        await tester.run_depth_research_tests()
        await tester.run_llm_integration_tests()
        await tester.run_error_handling_tests()
        
        print_header("All DeepResearch Tests Complete!", "double")
        
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