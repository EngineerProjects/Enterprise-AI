#!/usr/bin/env python3
"""
Simple Browser Tool Testing Script

Tests each aspect of the browser tool individually with configurable LLM support.
"""

import asyncio
import sys
import os
from pathlib import Path

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.browser.browser import BrowserUseTool
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class BrowserTester:
    """Simple browser tool tester with LLM configuration support."""
    
    def __init__(self):
        self.browser = None
    
    async def show_current_config(self):
        """Show current configuration."""
        print_header("Current Configuration", "single")
        
        # LLM Configuration
        provider = get_config("llm.default_provider", "not configured")
        model = get_config("llm.default_model", "not configured")
        print_test(f"LLM Provider: {provider}", "pass")
        print_test(f"LLM Model: {model}", "pass")
        
        # Browser Configuration
        headless = get_config("browser_config.headless", "not configured")
        print_test(f"Browser Headless: {headless}", "pass")
        
        # Execution Configuration
        exec_mode = get_config("execution.mode", "not configured")
        print_test(f"Execution Mode: {exec_mode}", "pass")

    async def setup(self, llm_provider=None, llm_model=None):
        """Initialize browser tool with optional LLM configuration."""
        print_header("Browser Tool Test Suite", "double")
        
        # Show current config first
        await self.show_current_config()
        
        print_test("Setting up browser tool", "running")
        
        # Create browser with optional LLM override
        kwargs = {}
        if llm_provider:
            kwargs['llm_provider'] = llm_provider
            print_test(f"Using LLM Provider Override: {llm_provider}", "pass")
        if llm_model:
            kwargs['llm_model'] = llm_model
            print_test(f"Using LLM Model Override: {llm_model}", "pass")
        
        self.browser = BrowserUseTool(**kwargs)
        success = await self.browser.initialize()
        
        if success:
            print_test("Browser tool initialized", "pass")
            return True
        else:
            print_test("Browser tool initialization failed", "fail")
            return False
    
    async def test_action(self, action_name: str, show_full_output: bool = False, **kwargs):
        """Test a single browser action."""
        print_test(f"Testing: {action_name}", "running")
        
        try:
            with Timer(f"Action: {action_name}"):
                result = await self.browser.execute(action=action_name, **kwargs)
            
            if isinstance(result, ToolResult) and result.success:
                print_test(f"{action_name}: SUCCESS", "pass")
                
                # Show result if not too long or if specifically requested
                if hasattr(result, 'result') and result.result:
                    output = str(result.result)
                    if show_full_output or len(output) <= 200:
                        print_chat("tool", output)
                    elif len(output) > 200:
                        print_chat("tool", output[:200] + "...")
                
                return result, True
            else:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{action_name}: FAILED - {error_msg}", "fail")
                return result, False
                
        except Exception as e:
            print_test(f"{action_name}: EXCEPTION - {e}", "fail")
            return None, False
    
    async def run_navigation_tests(self):
        """Test basic navigation functionality."""
        print_header("Navigation Tests", "single")
        
        tests = [
            ("go_to_url", {"url": "https://httpbin.org/"}),
            ("get_current_state", {}),
            ("go_to_url", {"url": "https://example.com"}),
            ("refresh", {}),
            ("get_current_state", {}),
        ]
        
        for action, kwargs in tests:
            result, success = await self.test_action(action, **kwargs)
            if not success and action == "go_to_url":
                print_test("Navigation failed, stopping navigation tests", "fail")
                return False
        
        return True
    
    async def run_interaction_tests(self):
        """Test element interaction."""
        print_header("Interaction Tests", "single")
        
        # Navigate to a form page first
        await self.test_action("go_to_url", url="https://httpbin.org/forms/post")
        
        tests = [
            ("get_current_state", {}),
            ("wait", {"seconds": 2}),
            ("scroll_down", {"scroll_amount": 300}),
            ("scroll_up", {"scroll_amount": 300}),
        ]
        
        for action, kwargs in tests:
            await self.test_action(action, **kwargs)
    
    async def run_extraction_tests(self):
        """Test content extraction with LLM."""
        print_header("Content Extraction Tests", "single")
        
        # Navigate to a content-rich page
        await self.test_action("go_to_url", url="https://example.com")
        
        print_test("Testing content extraction with configured LLM", "running")
        
        # Test extraction - this will use the configured LLM
        result, success = await self.test_action(
            "extract_content", 
            show_full_output=True,  # Show full extraction result
            goal="Get the main content and purpose of this website"
        )
        
        if success:
            print_test("LLM Content Extraction: SUCCESS", "pass")
        else:
            print_test("LLM Content Extraction: FAILED (check LLM config)", "warn")
            if result and hasattr(result, 'error'):
                print_chat("tool", f"Error: {result.error}")
    
    async def run_search_tests(self):
        """Test web search functionality."""
        print_header("Web Search Tests", "single")
        
        tests = [
            ("web_search", {"query": "python programming tutorial"}),
            ("get_current_state", {}),
        ]
        
        for action, kwargs in tests:
            await self.test_action(action, **kwargs)
    
    async def cleanup(self):
        """Clean up browser resources."""
        print_header("Cleanup", "single")
        
        if self.browser:
            print_test("Cleaning up browser", "running")
            await self.browser.cleanup()
            print_test("Browser cleanup complete", "pass")


async def main():
    """Run all browser tests with LLM configuration testing."""
    tester = BrowserTester()
    
    # Setup with default configuration
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run core test suites
        await tester.run_navigation_tests()
        await tester.run_interaction_tests()
        await tester.run_extraction_tests()
        
        # Optionally test web search (uncomment if WebSearch available)
        # await tester.run_search_tests()
        
        print_header("All Tests Complete!", "double")
        
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