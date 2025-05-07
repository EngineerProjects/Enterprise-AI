#!/usr/bin/env python
"""
Test for PlanningTool via MCP

This script demonstrates how to use the PlanningTool through the MCP system
to create and manage structured task plans.
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
from enterprise_ai.tool.core import (
    ToolConfig,
    ToolResult
)
from enterprise_ai.tool.planning.planning import PlanningTool
from enterprise_ai.mcp import (
    MCPClient,
    get_mcp_server
)
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("planning_test")


async def test_planning_tool():
    """Test the PlanningTool using the MCP system."""
    print_title("TESTING PLANNING TOOL VIA MCP")

    # Create a test session
    session_id = "planning-tool-test"
    client = None

    try:
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Create tool with configuration
        print_section("Tool Creation and Configuration")

        config = ToolConfig(
            timeout=10.0,
            max_retries=1,
            cache_results=True,
        )

        # Create and register the PlanningTool with explicit parameters
        planning_tool = PlanningTool(
            # Explicitly provide required parameters
            name="planning",
            description="A planning tool that allows the creation and management of structured task plans.",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "description": "The command to execute. Available commands: create, update, list, get, set_active, mark_step, delete.",
                        "enum": [
                            "create",
                            "update",
                            "list",
                            "get",
                            "set_active",
                            "mark_step",
                            "delete",
                        ],
                        "type": "string",
                    },
                    "plan_id": {
                        "description": "Unique identifier for the plan. Required for create, update, set_active, and delete commands. Optional for get and mark_step (uses active plan if not specified).",
                        "type": "string",
                    },
                    "title": {
                        "description": "Title for the plan. Required for create command, optional for update command.",
                        "type": "string",
                    },
                    "steps": {
                        "description": "List of plan steps. Required for create command, optional for update command.",
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "step_index": {
                        "description": "Index of the step to update (0-based). Required for mark_step command.",
                        "type": "integer",
                    },
                    "step_status": {
                        "description": "Status to set for a step. Used with mark_step command.",
                        "enum": ["not_started", "in_progress", "completed", "blocked"],
                        "type": "string",
                    },
                    "step_notes": {
                        "description": "Additional notes for a step. Optional for mark_step command.",
                        "type": "string",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            config=config
        )

        client.session.register_tool(planning_tool)
        print_success(f"Created and registered PlanningTool with configuration")

        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")

        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")

        # Get detailed tool info
        tool_info = client.get_tool_info(planning_tool.name)
        print_info(f"\nTool info for {planning_tool.name}:")
        print_info(f"  Description: {tool_info.get('description', 'N/A')}")
        print_info(f"  State: {tool_info.get('state', 'N/A')}")

        separator()

        # Test 1: Create a plan
        print_section("Test 1: Create a Plan")
        plan_id = "test-plan-1"
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="create",
                plan_id=plan_id,
                title="Test Project Plan",
                steps=[
                    "Define project requirements",
                    "Create initial design",
                    "Implement core features",
                    "Test functionality",
                    "Deploy to production"
                ]
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Plan created:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 2: Update step status
        print_section("Test 2: Update Step Status")
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="mark_step",
                plan_id=plan_id,
                step_index=0,
                step_status="completed",
                step_notes="Requirements document finalized on May 5"
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Step updated:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 3: Mark step as in progress
        print_section("Test 3: Mark Step as In Progress")
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="mark_step",
                plan_id=plan_id,
                step_index=1,
                step_status="in_progress",
                step_notes="Design work started"
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Step updated:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 4: Get plan details
        print_section("Test 4: Get Plan Details")
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="get",
                plan_id=plan_id
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Plan details:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 5: Create a second plan
        print_section("Test 5: Create a Second Plan")
        plan_id_2 = "test-plan-2"
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="create",
                plan_id=plan_id_2,
                title="Website Redesign",
                steps=[
                    "Gather user feedback",
                    "Create wireframes",
                    "Design UI components",
                    "Implement new design",
                    "User testing"
                ]
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Second plan created:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 6: List all plans
        print_section("Test 6: List All Plans")
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="list"
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"All plans:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 7: Set active plan
        print_section("Test 7: Set Active Plan")
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="set_active",
                plan_id=plan_id_2
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Active plan set:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 8: Delete plan
        print_section("Test 8: Delete Plan")
        with Timer("Execution"):
            result = await client.execute_tool(
                planning_tool.name,
                command="delete",
                plan_id=plan_id
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Plan deleted:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

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
    asyncio.run(test_planning_tool())
