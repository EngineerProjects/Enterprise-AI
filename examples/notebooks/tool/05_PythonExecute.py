#!/usr/bin/env python
"""
Test for PythonExecute Tool via MCP

This script demonstrates how to use the PythonExecute tool through the MCP system
to execute Python code in a controlled environment.
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
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.mcp import (
    MCPClient,
    get_mcp_server
)
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("python_execute_test")


async def test_python_execute():
    """Test the PythonExecute tool using the MCP system."""
    print_title("TESTING PYTHON EXECUTE TOOL VIA MCP")

    # Create a test session
    session_id = "python-execute-test"
    client = None

    try:
        client = MCPClient(session_id, create_if_not_exists=True)
        print_success(f"Created MCP session: {session_id}")

        # Create tool with configuration
        print_section("Tool Creation and Configuration")

        config = ToolConfig(
            timeout=10.0,  # Longer timeout for more complex examples
            max_retries=1,
            cache_results=True,
        )

        # Create and register the PythonExecute tool
        python_execute = PythonExecute(
            name="python_execute",
            description="Executes Python code in an isolated environment with output capture.",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum execution time in seconds.",
                        "default": 5,
                    },
                },
                "required": ["code"],
            },
            config=config
        )

        client.session.register_tool(python_execute)
        print_success(f"Created and registered PythonExecute tool with configuration")

        # Discover available tools
        print_section("Tool Discovery")
        tools = client.discover_tools()
        print_info(f"Found {len(tools)} tools in session")

        if tools:
            for i, tool in enumerate(tools, 1):
                if "function" in tool and "name" in tool["function"]:
                    print_info(f"  {i}. {tool['function']['name']}")

        # Get detailed tool info
        tool_info = client.get_tool_info(python_execute.name)
        print_info(f"\nTool info for {python_execute.name}:")
        print_info(f"  Description: {tool_info.get('description', 'N/A')}")
        print_info(f"  State: {tool_info.get('state', 'N/A')}")

        separator()

        # Test 1: Basic code execution - Hello World
        print_section("Test 1: Basic Code Execution - Hello World")
        code = """
print("Hello, World!")
print("This is a test of the PythonExecute tool.")
print("Current execution is isolated and safe.")
"""
        with Timer("Execution"):
            result = await client.execute_tool(
                python_execute.name,
                code=code
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 2: Mathematical calculations
        print_section("Test 2: Mathematical Calculations")
        code = """
import math

def calculate_area(radius):
    return math.pi * radius**2

def calculate_volume(radius):
    return (4/3) * math.pi * radius**3

# Calculate for a sphere with radius 5
radius = 5
area = calculate_area(radius)
volume = calculate_volume(radius)

print(f"For a sphere with radius {radius}:")
print(f"Surface area: {area:.2f} square units")
print(f"Volume: {volume:.2f} cubic units")

# Calculate factorial
print(f"Factorial of 10: {math.factorial(10)}")

# Calculate some exponents
for i in range(1, 6):
    print(f"2^{i} = {2**i}")
"""
        with Timer("Execution"):
            result = await client.execute_tool(
                python_execute.name,
                code=code
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 3: Error handling - Syntax error
        print_section("Test 3: Error Handling - Syntax Error")
        code = """
# This code has a deliberate syntax error
print("Starting execution")

if True
    print("This will cause a syntax error")

print("This will never be reached")
"""
        with Timer("Execution"):
            result = await client.execute_tool(
                python_execute.name,
                code=code
            )

        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected): {result.error}")

        separator()

        # Test 4: Error handling - Runtime error
        print_section("Test 4: Error Handling - Runtime Error")
        code = """
# This code has a deliberate runtime error
print("Starting execution")

# Define a list with 3 elements
my_list = [1, 2, 3]

# Try to access an index that doesn't exist
print(f"Attempting to access index 10: {my_list[10]}")

print("This will never be reached")
"""
        with Timer("Execution"):
            result = await client.execute_tool(
                python_execute.name,
                code=code
            )

        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected): {result.error}")

        separator()

        # Test 5: Data manipulation
        print_section("Test 5: Data Manipulation")
        code = """
# Create a class to represent a person
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def __str__(self):
        return f"{self.name} ({self.age})"

# Create a list of people
people = [
    Person("Alice", 28),
    Person("Bob", 35),
    Person("Charlie", 22),
    Person("Diana", 41),
    Person("Eve", 19)
]

# Find the average age
avg_age = sum(person.age for person in people) / len(people)
print(f"Average age: {avg_age:.1f}")

# Find the oldest person
oldest = max(people, key=lambda person: person.age)
print(f"Oldest person: {oldest}")

# Find the youngest person
youngest = min(people, key=lambda person: person.age)
print(f"Youngest person: {youngest}")

# Filter for people over 30
over_30 = [person for person in people if person.age > 30]
print("People over 30:")
for person in over_30:
    print(f"- {person}")
"""
        with Timer("Execution"):
            result = await client.execute_tool(
                python_execute.name,
                code=code
            )

        if hasattr(result, 'output') and result.output is not None:
            print_success(f"Output:")
            print_info(result.output)
        if hasattr(result, 'error') and result.error is not None:
            print_error(f"Error: {result.error}")

        separator()

        # Test 6: Timeout handling
        print_section("Test 6: Timeout Handling")
        code = """
import time

print("Starting a long computation...")
# This should exceed the tool's timeout
for i in range(10):
    print(f"Iteration {i}")
    # Sleep for 2 seconds - should eventually timeout with default settings
    time.sleep(2)
    print(f"Finished iteration {i}")

print("This should never be reached if timeout works correctly")
"""
        with Timer("Execution"):
            result = await client.execute_tool(
                python_execute.name,
                code=code,
                timeout=3  # Set a short timeout to test timeout handling
            )

        if hasattr(result, 'output') and result.output is not None:
            print_info(f"Output: {result.output}")
        if hasattr(result, 'error') and result.error is not None:
            print_warning(f"Error (expected timeout): {result.error}")

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
    asyncio.run(test_python_execute())
