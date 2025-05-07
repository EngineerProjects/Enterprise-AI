#!/usr/bin/env python
"""
Test for ToolResult and ToolConfig via MCP

This script demonstrates how to create, configure, and use a tool with proper
ToolResult and ToolConfig through the Model Context Protocol (MCP) system.
"""

import asyncio
import sys
from typing import Any, Dict, Optional, Set, Union

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
from enterprise_ai.tool.core import (
    BaseTool,
    ToolConfig,
    ToolCapability,
    register_tool
)
from enterprise_ai.tool.core.result import ToolResult, ToolResultMetadata
from enterprise_ai.mcp import (
    MCPClient,
    get_mcp_server
)
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("tool_test")

# Create a simple test tool for our demonstration
@register_tool(category="test")
class SimpleTestTool(BaseTool):
    """A simple test tool for demonstrating ToolResult and ToolConfig."""

    # Define tool capabilities
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.UTILITY}

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool and return a ToolResult."""
        # Extract parameters
        message = kwargs.get("message", "Default message")
        fail = kwargs.get("fail", False)
        include_metadata = kwargs.get("metadata", False)

        # Get values from config (if they exist)
        timeout = 30.0
        simulate_delay = False
        delay_seconds = 1.0

        if hasattr(self, "config"):
            timeout = getattr(self.config, "timeout", timeout)
            custom_config = getattr(self.config, "custom_config", {})
            simulate_delay = custom_config.get("simulate_delay", simulate_delay)
            delay_seconds = custom_config.get("delay_seconds", delay_seconds)

        # Log execution details
        logger.info(f"Executing with message: {message}, fail: {fail}")
        logger.info(f"Using timeout: {timeout}s, simulate_delay: {simulate_delay}")

        # Simulate processing delay if configured
        if simulate_delay:
            logger.debug(f"Simulating delay of {delay_seconds}s")
            await asyncio.sleep(delay_seconds)

        # Simulate a failure if requested
        if fail:
            logger.warning("Simulating tool failure")
            return ToolResult(
                error=f"Tool execution failed as requested with message: {message}"
            )

        # Create a result with or without metadata
        if include_metadata:
            # Create result with metadata
            metadata = ToolResultMetadata(
                tool_name=self.name,
                tool_version="1.0.0",
                parameters=kwargs,
                tags={"test", "example", "foundation"}
            )

            result = ToolResult(
                output=f"Tool executed successfully with message: {message}",
                metadata=metadata,
                system="This is a system message for additional context"
            )
        else:
            # Create a simple result
            result = ToolResult(
                output=f"Tool executed successfully with message: {message}"
            )

        # Complete the execution if the method exists
        if hasattr(result, "complete") and callable(result.complete):
            result = result.complete()

        return result


async def test_tool_result_config():
    """Test ToolResult and ToolConfig using the MCP system."""
    print_title("TESTING TOOLRESULT AND TOOLCONFIG VIA MCP")

    # Create a test session
    session_id = "tool-result-config-test"
    client = None

    try:
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Create tool with custom configuration
        print_section("Tool Creation and Configuration")

        config = ToolConfig(
            timeout=5.0,
            max_retries=1,
            cache_results=True,
            custom_config={
                "simulate_delay": True,
                "delay_seconds": 1.0
            }
        )

        # Create the test tool with explicit name and description
        test_tool = SimpleTestTool(
            name="simple_test_tool",
            description="A simple test tool for demonstrating ToolResult and ToolConfig",
            parameters={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to include in the result"
                    },
                    "fail": {
                        "type": "boolean",
                        "description": "Whether to simulate a failure",
                        "default": False
                    },
                    "metadata": {
                        "type": "boolean",
                        "description": "Whether to include metadata in the result",
                        "default": False
                    }
                },
                "required": ["message"]
            },
            config=config
        )

        # Register the tool with our session
        client.session.register_tool(test_tool)
        print_success(f"Created and registered SimpleTestTool with custom configuration")

        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")

        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")

        # Get detailed tool info
        tool_info = client.get_tool_info(test_tool.name)
        print_info(f"\nTool info for {test_tool.name}:")
        print_info(f"  Description: {tool_info.get('description', 'N/A')}")
        print_info(f"  State: {tool_info.get('state', 'N/A')}")

        # Get configuration-related metrics
        metrics = tool_info.get('metrics', {})
        print_info(f"\nTool metrics:")
        for key, value in metrics.items():
            print_info(f"  {key}: {value}")

        separator()

        # Test 1: Basic execution with success
        print_section("Test 1: Basic Execution With Success")
        with Timer("Execution"):
            result = await client.execute_tool(
                test_tool.name,
                message="Hello from ToolResult test!"
            )

        print_info(f"Result type: {type(result).__name__}")
        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 2: Execution with failure
        print_section("Test 2: Execution With Failure")
        with Timer("Execution"):
            result = await client.execute_tool(
                test_tool.name,
                message="This should fail",
                fail=True
            )

        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected): {result.error}")

        separator()

        # Test 3: Execution with metadata
        print_section("Test 3: Execution With Metadata")
        with Timer("Execution"):
            result = await client.execute_tool(
                test_tool.name,
                message="Including metadata",
                metadata=True
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output: {result.output}")

        # Inspect ToolResult metadata if available
        if hasattr(result, 'metadata') and result.metadata is not None:
            metadata = result.metadata
            print_info(f"Metadata:")

            # Convert metadata to dictionary for easier display
            metadata_dict = {}
            for key, value in metadata.__dict__.items():
                if not key.startswith("_"):
                    metadata_dict[key] = value

            # Display metadata entries
            for key, value in metadata_dict.items():
                print_info(f"  {key}: {value}")

        print_success("All tests completed successfully!")

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        if client:
            await client.close()
            print_info("Session closed and resources cleaned up")
        separator()


if __name__ == "__main__":
    asyncio.run(test_tool_result_config())
