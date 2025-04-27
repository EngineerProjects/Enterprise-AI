#!/usr/bin/env python
"""
Enterprise AI Manual Browser Test

This script demonstrates a workaround method to test the browser functionality
by manually setting up the necessary components without using the standard initialization.
"""

import asyncio
import sys
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

# Import just what we need and avoid initialization problems
from enterprise_ai.tool.core.result import ToolResult


async def manual_browser_test() -> None:
    """
    A manual browser test that creates a simplified browser interaction.
    This bypasses the standard initialization to avoid class attribute issues.
    """
    print_section("Manual Browser Test")

    try:
        # Import browser modules
        from enterprise_ai.config import get_config
        from browser_use import Browser as BrowserUseBrowser
        from browser_use import BrowserConfig
        from browser_use.browser.context import BrowserContext, BrowserContextConfig
        from browser_use.dom.service import DomService

        # Create browser instance directly instead of through BrowserUseTool
        print_info("Creating browser instance directly...")

        # Get configuration values
        headless = get_config("browser_config.headless", False)
        disable_security = get_config("browser_config.disable_security", True)
        extra_args = get_config("browser_config.extra_chromium_args", [])

        # Set up browser configuration
        browser_config_kwargs = {
            "headless": False,  # headless,
            "disable_security": disable_security,
        }

        if extra_args:
            browser_config_kwargs["extra_chromium_args"] = extra_args

        # Create the browser
        browser = BrowserUseBrowser(BrowserConfig(**browser_config_kwargs))
        print_success("Browser created successfully")

        # Create browser context
        print_info("Creating browser context...")
        context = await browser.new_context(BrowserContextConfig())
        print_success("Browser context created")

        # Get current page
        print_info("Getting current page...")
        page = await context.get_current_page()
        print_success("Page retrieved")

        # Navigate to example.com
        print_info("Navigating to example.com...")
        await page.goto("https://fr.wikipedia.org/wiki/Vie_extraterrestre")
        await page.wait_for_load_state()
        print_success("Navigation successful!")

        # Get page content for verification
        content = await page.content()
        print_info(f"Page title: {await page.title()}")
        print_info(f"Content length: {len(content)} characters")

        # Try a simple DOM operation
        print_info("Checking for elements on the page...")
        h1_elements = await page.query_selector_all("h1")
        p_elements = await page.query_selector_all("p")

        print_info(f"Found {len(h1_elements)} h1 elements and {len(p_elements)} p elements")

        # Take a screenshot
        print_info("Taking a screenshot...")
        screenshot = await page.screenshot(full_page=True)
        print_success(f"Screenshot taken, size: {len(screenshot)} bytes")

        # Clean up resources
        print_info("Cleaning up browser resources...")
        await context.close()
        await browser.close()
        print_success("Browser resources cleaned up successfully")

    except Exception as e:
        print_error(f"Error in manual browser test: {e}")
        import traceback

        traceback.print_exc()


async def run_examples() -> None:
    """Run all browser examples."""
    try:
        await manual_browser_test()
    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main entry point for manual browser example."""
    print_title("Enterprise AI Manual Browser Test")
    print_info(
        "Note: This example demonstrates direct browser usage without the BrowserUseTool class"
    )
    print_info("It bypasses initialization issues by working with the browser_use library directly")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("Browser test completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
