#!/usr/bin/env python
"""
Minimal Test for DeepResearch Tool via MCP

This script provides the most basic test of the DeepResearch tool
with comprehensive error handling.
"""

import asyncio
import sys
import traceback
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

# Import core components with extensive error handling
try:
    print_info("Importing core components...")
    from enterprise_ai.tool.core import ToolConfig
    from enterprise_ai.mcp import MCPClient
    from enterprise_ai.logger import get_logger
    print_success("Core components imported successfully")
except ImportError as e:
    print_error(f"Failed to import core components: {e}")
    sys.exit(1)

# Import DeepResearch tool specifically
try:
    print_info("Importing DeepResearch tool...")
    from enterprise_ai.tool.research.deep_research import DeepResearch
    print_success("DeepResearch tool imported successfully")
except ImportError as e:
    print_error(f"Failed to import DeepResearch tool: {e}")
    sys.exit(1)

# Configure logger
logger = get_logger("deep_research_test")


async def test_deep_research():
    """Test the DeepResearch tool at the most basic level."""
    print_title("MINIMAL DEEP RESEARCH TOOL TEST")

    # Create a test session
    session_id = "deep-research-test"
    client = None

    try:
        print_info("Creating MCP client...")
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Create and configure the tool
        print_section("Tool Creation")

        # Use simple config with extended timeout
        config = ToolConfig(
            timeout=300.0,  # 5 minute timeout
            max_retries=1,
            cache_results=True,
        )

        print_info("Creating DeepResearch tool instance...")
        try:
            research_tool = DeepResearch(
                name="deep_research",
                description="Research tool for deep exploration of topics.",
                config=config
            )
            print_success("Created DeepResearch tool instance")
        except Exception as e:
            print_error(f"Failed to create DeepResearch tool instance: {e}")
            traceback.print_exc()
            return

        # Initialize the tool
        print_info("Initializing DeepResearch tool...")
        try:
            init_success = await research_tool.initialize()
            if init_success:
                print_success("DeepResearch tool initialized successfully")
            else:
                print_error("Failed to initialize DeepResearch tool (returned False)")
                return
        except Exception as e:
            print_error(f"Error during DeepResearch tool initialization: {e}")
            traceback.print_exc()
            return

        # Register the tool with the session
        print_info("Registering tool with MCP session...")
        try:
            client.session.register_tool(research_tool)
            print_success("Registered DeepResearch tool with session")
        except Exception as e:
            print_error(f"Failed to register tool with session: {e}")
            traceback.print_exc()
            return

        # Verify tool is registered
        print_section("Tool Verification")
        try:
            tools = client.discover_tools()
            print_info(f"Found {len(tools)} tools in session")

            if len(tools) == 0:
                print_error("No tools found in session after registration!")
                return

            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")

            # Get detailed tool info
            tool_info = client.get_tool_info("deep_research")
            print_info(f"\nTool info for deep_research:")
            print_info(f"  Description: {tool_info.get('description', 'N/A')}")
            print_info(f"  State: {tool_info.get('state', 'N/A')}")
        except Exception as e:
            print_error(f"Error verifying tool registration: {e}")
            traceback.print_exc()
            return

        separator()

        # Extremely simple test - just execute with minimal parameters
        print_section("Basic Execution Test")
        simple_query = "Python programming language"  # An easy, common topic
        print_info(f"Executing basic research for: '{simple_query}'")

        try:
            with Timer("Execution"):
                result = await client.execute_tool(
                    "deep_research",
                    query=simple_query,
                    max_depth=1,            # Minimal depth
                    results_per_search=1,   # Just one result
                    max_insights=3,         # Few insights
                    time_limit_seconds=60   # Short timeout
                )

            # Check for various result properties
            print_success("Tool execution completed")

            if hasattr(result, 'output') and result.output is not None:
                print_success(f"Research results obtained:")
                # Show a snippet of the output
                output = result.output
                print_info(output[:500] + "..." if len(output) > 500 else output)

            if hasattr(result, 'error') and result.error is not None:
                print_error(f"Error in result: {result.error}")

            # Print all available attributes
            print_info("\nAll available result attributes:")
            for attr_name in dir(result):
                if not attr_name.startswith('_') and not callable(getattr(result, attr_name)):
                    try:
                        attr_value = getattr(result, attr_name)
                        attr_type = type(attr_value).__name__
                        attr_summary = str(attr_value)[:50] + "..." if len(str(attr_value)) > 50 else str(attr_value)
                        print_info(f"  {attr_name} ({attr_type}): {attr_summary}")
                    except Exception as e:
                        print_warning(f"  {attr_name}: Error accessing - {e}")

        except Exception as e:
            print_error(f"Error during tool execution: {e}")
            traceback.print_exc()
            return

        print_success("Test completed successfully!")

    except Exception as e:
        print_error(f"Test failed with unexpected error: {e}")
        traceback.print_exc()

    finally:
        # Clean up
        if client:
            try:
                print_info("Cleaning up resources...")
                await client.close()
                print_info("Session closed and resources cleaned up")
            except Exception as e:
                print_error(f"Error during cleanup: {e}")
        separator()


if __name__ == "__main__":
    try:
        asyncio.run(test_deep_research())
    except KeyboardInterrupt:
        print_warning("\nTest interrupted by user")
    except Exception as e:
        print_error(f"Unhandled exception: {e}")
        traceback.print_exc()
