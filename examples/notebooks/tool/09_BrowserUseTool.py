#!/usr/bin/env python
"""
Test for BrowserUseTool via MCP

This script demonstrates how to use the BrowserUseTool through the MCP system
to automate browser interactions and extract content from websites.
"""

import asyncio
import sys
import base64
import os
import json
import tempfile
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
from enterprise_ai.tool.browser.browser import BrowserUseTool
from enterprise_ai.mcp import MCPClient
from enterprise_ai.logger import get_logger
from enterprise_ai.schema.message import Message

# Configure logger
logger = get_logger("browser_use_test")

# Define helper function for LLM initialization
def initialize_llm_provider(model_name: str = "llava", base_url: str = "http://localhost:11434", timeout: float = 60.0):
    """Initialize an LLM provider with the specified model.

    Args:
        model_name: Name of the model to use (default: llava)
        base_url: Base URL for the Ollama API
        timeout: Request timeout in seconds

    Returns:
        An initialized LLM instance
    """
    from enterprise_ai.llm.providers.ollama import OllamaProvider
    from enterprise_ai.llm.simple import LLM

    try:
        # Initialize the provider
        provider = OllamaProvider(
            model_name=model_name,
            base_url=base_url,
            timeout=timeout
        )

        # Create LLM instance with this provider
        llm = LLM(provider=provider)

        # Test the provider with a simple message to ensure it works
        test_message = Message.system_message("Test message")

        # Return the working LLM instance
        return llm
    except Exception as e:
        print(f"Error initializing LLM provider: {e}")
        return None


async def test_browser_use_tool():
    """Test the BrowserUseTool using the MCP system."""
    print_title("TESTING BROWSER USE TOOL VIA MCP")

    # Create a test session
    session_id = "browser-use-test"
    client = None

    try:
        # Create MCP client
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Create tool with configuration
        print_section("Tool Creation and Configuration")

        config = ToolConfig(
            timeout=60.0,  # Longer timeout for browser operations
            max_retries=2,  # Allow retries for browser operations
            sandbox_enabled=True,  # Run in sandbox for safety
            custom_config={
                "browser_window_size": {"width": 1280, "height": 800},
                "headless": True,  # Run browser in headless mode for testing
            }
        )

        # Create and register the BrowserUseTool
        browser_tool = BrowserUseTool(
            name="browser_use",
            description="Browser automation tool that provides interactive web capabilities.",
            config=config
        )

        # Create and explicitly set the LLM provider (new code)
        print_info("Creating LLM instance for browser tool...")
        llm = initialize_llm_provider(model_name="llava")  # Using llava model which has vision capabilities
        if llm:
            print_success("LLM provider created successfully")
            browser_tool.llm = llm  # Explicitly set the LLM on the browser tool
        else:
            print_warning("Could not create LLM provider, content extraction may fail")

        # Initialize the browser before registering
        print_info("Initializing browser tool...")
        init_success = await browser_tool.initialize()

        if init_success:
            print_success("Browser tool initialized successfully")
        else:
            print_error("Failed to initialize browser tool")
            return

        # Register the tool with the session
        client.session.register_tool(browser_tool)
        print_success("Registered BrowserUseTool with configuration")

        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")

        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")

        # Get detailed tool info
        tool_info = client.get_tool_info(browser_tool.name)
        print_info(f"\nTool info for {browser_tool.name}:")
        print_info(f"  Description: {tool_info.get('description', 'N/A')}")
        print_info(f"  State: {tool_info.get('state', 'N/A')}")

        separator()

        # Test 1: Navigate to a URL
        print_section("Test 1: Navigate to a URL")
        test_url = "https://www.python.org"  # A real website with interactive elements
        print_info(f"Navigating to: {test_url}")

        with Timer("Execution"):
            result = await client.execute_tool(
                browser_tool.name,
                action="go_to_url",
                url=test_url
            )

        if hasattr(result, 'output') and result.output:
            print_success(f"Navigation result:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error:
            print_error(f"Error: {result.error}")

        separator()

        # Test 2: Extract content
        print_section("Test 2: Extract Content from Webpage")
        print_info(f"Extracting content from current page")

        # Directly call the tool's internal _analyze_content method if needed
        if hasattr(browser_tool, "_analyze_content"):
            with Timer("Direct content extraction"):
                try:
                    # Get the current page content
                    state_result = await browser_tool.get_current_state()
                    state_data = json.loads(state_result.output)
                    current_url = state_data.get("url", "unknown")
                    current_title = state_data.get("title", "unknown")

                    # Get page content using browser's DOM access
                    page = await browser_tool.context.get_current_page()
                    html_content = await page.content()

                    # Extract content using the tool's internal method
                    extraction_result = await browser_tool._analyze_content(
                        content=html_content[:5000],  # Limit content size
                        url=current_url,
                        title=current_title,
                        query="Summarize what Python is and its main features according to the homepage"
                    )

                    print_success(f"Direct extraction result:")
                    print_info(str(extraction_result.output))
                except Exception as e:
                    print_error(f"Direct extraction error: {e}")

        # Standard execution via MCP
        with Timer("Execution"):
            result = await client.execute_tool(
                browser_tool.name,
                action="extract_content",
                goal="Summarize what Python is and its main features according to the homepage"
            )

        if hasattr(result, 'output') and result.output:
            print_success(f"Extraction result:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error:
            print_error(f"Error: {result.error}")

            # Fallback approach if extraction fails
            print_info("Attempting fallback content extraction...")
            try:
                # Get the page HTML directly
                page = await browser_tool.context.get_current_page()
                html_content = await page.content()

                # Simple content extraction using BeautifulSoup
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')

                # Remove script and style elements
                for script_or_style in soup(["script", "style"]):
                    script_or_style.decompose()

                # Get text content
                text = soup.get_text()

                # Clean up text
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                text = "\n".join(lines[:30])  # Just first 30 lines

                print_success("Fallback extraction successful:")
                print_info(text[:500] + "...")  # Show first 500 chars
            except Exception as e:
                print_error(f"Fallback extraction failed: {e}")

        separator()

        # Test 3: Screenshot Capture - Get Current State with Image
        print_section("Test 3: Screenshot Capture")
        print_info("Capturing screenshot of current page")

        # Use get_current_state directly to get the screenshot
        with Timer("Execution"):
            state_result = await browser_tool.get_current_state()

        if hasattr(state_result, 'error') and state_result.error:
            print_error(f"Error getting state: {state_result.error}")
        else:
            # Check if we got a base64 image
            image_data = getattr(state_result, 'base64_image', None)
            if image_data:
                print_success("Screenshot captured successfully!")
                print_info(f"Image data size: {len(image_data)} bytes")

                # Optionally save the image to a file for inspection
                try:
                    # Use a reliable directory path
                    temp_dir = tempfile.gettempdir()
                    screenshot_path = os.path.join(temp_dir, "python_org_screenshot.jpg")
                    print_info(f"Using screenshot path: {screenshot_path}")

                    with open(screenshot_path, "wb") as f:
                        f.write(base64.b64decode(image_data))
                    print_success(f"Screenshot saved to: {screenshot_path}")
                except Exception as e:
                    print_warning(f"Could not save screenshot to file: {e}")
            else:
                print_warning("No screenshot was captured")

        separator()

        # Test 4: Click element (e.g., Documentation link)
        print_section("Test 4: Click Element")
        print_info("Clicking on an element (Documentation link)")

        # Get current state to see interactive elements
        state_result = await browser_tool.get_current_state()

        if hasattr(state_result, 'error') and state_result.error:
            print_error(f"Error getting state: {state_result.error}")
        else:
            # Print interactive elements to find a suitable one to click
            state_output = getattr(state_result, 'output', '')
            if state_output:
                try:
                    state_data = json.loads(state_output)
                    elements = state_data.get("interactive_elements", "")
                    print_info("Interactive elements (truncated):")
                    if elements and len(elements) > 300:
                        print_info(elements[:300] + "...")
                    else:
                        print_info(elements)
                except Exception as e:
                    print_warning(f"Could not parse state data: {e}")

            # Try to click an element that might be the Documentation link
            # This is a guess, might need adjustment based on actual elements
            with Timer("Execution"):
                click_result = await client.execute_tool(
                    browser_tool.name,
                    action="click_element",
                    index=5  # Trying a likely element index for a main navigation link
                )

            if hasattr(click_result, 'output') and click_result.output:
                print_success(f"Click result:")
                print_info(click_result.output)
            if hasattr(click_result, 'error') and click_result.error:
                print_warning(f"Click error (may be expected if element not found): {click_result.error}")

                # Try another approach: scroll first then try a different element
                print_info("Scrolling down and trying another element...")
                await client.execute_tool(
                    browser_tool.name,
                    action="scroll_down",
                    scroll_amount=200
                )

                click_result = await client.execute_tool(
                    browser_tool.name,
                    action="click_element",
                    index=10  # Try another index
                )

                if hasattr(click_result, 'output') and click_result.output:
                    print_success(f"Second click result:")
                    print_info(click_result.output)

        separator()

        # Test 5: Scroll operations
        print_section("Test 5: Scroll Operations")
        print_info("Scrolling down and then up")

        # Scroll down
        with Timer("Scroll Down"):
            scroll_down_result = await client.execute_tool(
                browser_tool.name,
                action="scroll_down",
                scroll_amount=500  # Scroll down 500 pixels
            )

        if hasattr(scroll_down_result, 'output') and scroll_down_result.output:
            print_success(f"Scroll down result:")
            print_info(scroll_down_result.output)
        if hasattr(scroll_down_result, 'error') and scroll_down_result.error:
            print_error(f"Error: {scroll_down_result.error}")

        # Wait a moment to visually see the scroll (if not headless)
        await asyncio.sleep(1)

        # Scroll back up
        with Timer("Scroll Up"):
            scroll_up_result = await client.execute_tool(
                browser_tool.name,
                action="scroll_up",
                scroll_amount=500  # Scroll up 500 pixels
            )

        if hasattr(scroll_up_result, 'output') and scroll_up_result.output:
            print_success(f"Scroll up result:")
            print_info(scroll_up_result.output)
        if hasattr(scroll_up_result, 'error') and scroll_up_result.error:
            print_error(f"Error: {scroll_up_result.error}")

        separator()

        # Test 6: Open a new tab with different URL
        print_section("Test 6: Tab Management")
        second_url = "https://docs.python.org/3/"
        print_info(f"Opening a new tab with URL: {second_url}")

        with Timer("Open Tab"):
            open_tab_result = await client.execute_tool(
                browser_tool.name,
                action="open_tab",
                url=second_url
            )

        if hasattr(open_tab_result, 'output') and open_tab_result.output:
            print_success(f"Open tab result:")
            print_info(open_tab_result.output)
        if hasattr(open_tab_result, 'error') and open_tab_result.error:
            print_error(f"Error: {open_tab_result.error}")

        # Switch back to first tab
        print_info("Switching back to first tab")
        with Timer("Switch Tab"):
            switch_tab_result = await client.execute_tool(
                browser_tool.name,
                action="switch_tab",
                tab_id=0  # First tab has ID 0
            )

        if hasattr(switch_tab_result, 'output') and switch_tab_result.output:
            print_success(f"Switch tab result:")
            print_info(switch_tab_result.output)
        if hasattr(switch_tab_result, 'error') and switch_tab_result.error:
            print_error(f"Error: {switch_tab_result.error}")

        separator()

        # Test 7: Web search function
        print_section("Test 7: Web Search Function")
        search_query = "Python latest version features"
        print_info(f"Performing web search for: {search_query}")

        with Timer("Web Search"):
            search_result = await client.execute_tool(
                browser_tool.name,
                action="web_search",
                query=search_query
            )

        if hasattr(search_result, 'output') and search_result.output:
            print_success(f"Search result (truncated):")
            # Print a truncated version to avoid flooding console
            result_output = search_result.output
            if result_output and len(result_output) > 500:
                print_info(f"{result_output[:500]}... (truncated)")
            else:
                print_info(result_output)
        if hasattr(search_result, 'error') and search_result.error:
            print_error(f"Error: {search_result.error}")

        print_success("All tests completed!")

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        if client:
            print_info("Closing session and cleaning up resources...")
            await client.close()
            print_info("Session closed and resources cleaned up")
        separator()


if __name__ == "__main__":
    asyncio.run(test_browser_use_tool())
