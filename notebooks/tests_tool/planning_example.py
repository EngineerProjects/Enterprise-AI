#!/usr/bin/env python
"""
Enterprise AI Planning Tool Examples

This script demonstrates using the Planning Tool:
- Creating plans with steps
- Updating plans
- Listing and managing multiple plans
- Tracking step progress
- Setting active plans
- Error handling
"""

import asyncio
import sys
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
from enterprise_ai.tool.planning import PlanningTool

# Create a SINGLE instance of the planning tool to use throughout all examples
planning_tool = PlanningTool()

async def create_plan_example() -> None:
    """Example of creating a basic plan."""
    print_section("Creating Plans")

    try:
        # Create a simple plan
        print_info("Creating a simple plan...")
        async with AsyncTimer("Plan creation"):
            result = await planning_tool.execute(
                command="create",
                plan_id="web-app-dev",
                title="Web Application Development Plan",
                steps=[
                    "Gather requirements from stakeholders",
                    "Create UI/UX mockups",
                    "Set up development environment",
                    "Implement core frontend components",
                    "Develop backend API",
                    "Connect frontend to backend",
                    "Write unit and integration tests",
                    "Perform security audit",
                    "Deploy to staging environment",
                    "Conduct user acceptance testing",
                ]
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")
        
        # Create another plan for demonstration
        print_info("\nCreating a second plan...")
        async with AsyncTimer("Second plan creation"):
            result = await planning_tool.execute(
                command="create",
                plan_id="data-analysis",
                title="Data Analysis Project",
                steps=[
                    "Collect raw data from sources",
                    "Clean and preprocess dataset",
                    "Perform exploratory data analysis",
                    "Build statistical models",
                    "Create data visualizations",
                    "Interpret results",
                    "Prepare final report",
                ]
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in create plan example: {e}")


async def update_plan_example() -> None:
    """Example of updating an existing plan."""
    print_section("Updating Plans")

    try:
        # Update a plan's title
        print_info("Updating plan title...")
        async with AsyncTimer("Title update"):
            result = await planning_tool.execute(
                command="update",
                plan_id="web-app-dev",
                title="Web Application Development Plan v2.0"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Update a plan's steps
        print_info("\nUpdating plan steps...")
        async with AsyncTimer("Steps update"):
            result = await planning_tool.execute(
                command="update",
                plan_id="web-app-dev",
                steps=[
                    "Gather requirements from stakeholders",
                    "Create UI/UX mockups",
                    "Set up development environment",
                    "Implement core frontend components",
                    "Develop backend API",
                    "Connect frontend to backend",
                    "Write unit and integration tests",
                    "Perform security audit",
                    "Deploy to staging environment",
                    "Conduct user acceptance testing",
                    "Fix reported issues",  # New step
                    "Deploy to production",  # New step
                    "Monitor performance"  # New step
                ]
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in update plan example: {e}")


async def list_plans_example() -> None:
    """Example of listing and retrieving plans."""
    print_section("Listing and Retrieving Plans")

    try:
        # List all plans
        print_info("Listing all available plans...")
        async with AsyncTimer("Plan listing"):
            result = await planning_tool.execute(
                command="list"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Get details of a specific plan
        print_info("\nGetting details of web-app-dev plan...")
        async with AsyncTimer("Plan retrieval"):
            result = await planning_tool.execute(
                command="get",
                plan_id="web-app-dev"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in list plans example: {e}")


async def active_plan_example() -> None:
    """Example of setting and using an active plan."""
    print_section("Working with Active Plans")

    try:
        # Set a plan as active
        print_info("Setting data-analysis as the active plan...")
        async with AsyncTimer("Set active plan"):
            result = await planning_tool.execute(
                command="set_active",
                plan_id="data-analysis"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Get active plan details without specifying plan_id
        print_info("\nGetting active plan details without plan_id...")
        async with AsyncTimer("Get active plan"):
            result = await planning_tool.execute(
                command="get"
                # No plan_id - should use active plan
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in active plan example: {e}")


async def step_tracking_example() -> None:
    """Example of tracking steps within a plan."""
    print_section("Step Progress Tracking")

    try:
        # Mark a step as in-progress
        print_info("Marking first step as in-progress...")
        async with AsyncTimer("Mark step in-progress"):
            result = await planning_tool.execute(
                command="mark_step",
                plan_id="web-app-dev",
                step_index=0,
                step_status="in_progress",
                step_notes="Started requirements gathering with stakeholders"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Mark a step as completed
        print_info("\nMarking a step as completed...")
        async with AsyncTimer("Mark step completed"):
            result = await planning_tool.execute(
                command="mark_step",
                plan_id="web-app-dev",
                step_index=2,  # Set up environment
                step_status="completed",
                step_notes="Environment set up with Docker containers"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Mark a step as blocked
        print_info("\nMarking a step as blocked...")
        async with AsyncTimer("Mark step blocked"):
            result = await planning_tool.execute(
                command="mark_step",
                plan_id="web-app-dev",
                step_index=4,  # Develop backend API
                step_status="blocked",
                step_notes="Waiting for database schema approval"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # View the updated plan
        print_info("\nViewing the updated plan with progress...")
        async with AsyncTimer("Get updated plan"):
            result = await planning_tool.execute(
                command="get",
                plan_id="web-app-dev"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in step tracking example: {e}")


async def error_handling_example() -> None:
    """Example of error handling with the planning tool."""
    print_section("Error Handling")

    try:
        # Attempt to create a plan with a duplicate ID
        print_info("Attempting to create a plan with an existing ID...")
        async with AsyncTimer("Duplicate plan creation"):
            result = await planning_tool.execute(
                command="create",
                plan_id="web-app-dev",  # This ID already exists
                title="Another Web App Plan",
                steps=["Step 1", "Step 2"]
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error occurred: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        # Attempt to get a non-existent plan
        print_info("\nAttempting to get a non-existent plan...")
        async with AsyncTimer("Non-existent plan retrieval"):
            result = await planning_tool.execute(
                command="get",
                plan_id="nonexistent-plan"
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error occurred: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

        # Attempt to update a non-existent plan
        print_info("\nAttempting to update a non-existent plan...")
        async with AsyncTimer("Non-existent plan update"):
            result = await planning_tool.execute(
                command="update",
                plan_id="nonexistent-plan",
                title="Updated Title"
            )

        if isinstance(result, ToolResult):
            if result.error:
                print_warning(f"Expected error occurred: {result.error}")
            else:
                print_error("Command unexpectedly succeeded")
                print(result.output)

    except Exception as e:
        print_error(f"Error in error handling example: {e}")


async def delete_plan_example() -> None:
    """Example of deleting a plan."""
    print_section("Deleting Plans")

    try:
        # Delete a plan
        print_info("Deleting the data-analysis plan...")
        async with AsyncTimer("Plan deletion"):
            result = await planning_tool.execute(
                command="delete",
                plan_id="data-analysis"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Verify the plan was deleted by listing all plans
        print_info("\nVerifying deletion by listing all plans...")
        async with AsyncTimer("List remaining plans"):
            result = await planning_tool.execute(
                command="list"
            )

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in delete plan example: {e}")


async def run_examples() -> None:
    """Run all planning tool examples."""
    try:
        await create_plan_example()
        separator()

        await update_plan_example()
        separator()

        await list_plans_example()
        separator()

        await active_plan_example()
        separator()

        await step_tracking_example()
        separator()

        await error_handling_example()
        separator()

        await delete_plan_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point for planning tool examples."""
    print_title("Enterprise AI Planning Tool Examples")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All planning tool examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()