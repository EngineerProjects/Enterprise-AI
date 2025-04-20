#!/usr/bin/env python
"""
Enterprise AI Python Execution Examples

This script demonstrates working with the PythonExecute tool:
- Basic code execution
- Functions and advanced Python features
- Error handling
- Timeout management
"""

import asyncio
import sys
from typing import Dict, Optional, Any

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
from enterprise_ai.tool.execution import PythonExecute


async def python_basic_example() -> None:
    """Example of basic Python code execution."""
    print_section("Basic Python Code Execution")

    # Create the Python execution tool
    py_exec = PythonExecute()

    try:
        # Execute a simple print statement
        print_info("Running a simple print statement...")
        code = """
print("Hello from the Python execution tool!")
print("This is a simple example of code execution.")
        """

        async with AsyncTimer("Simple print"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Variables and expressions
        print_info("\nRunning code with variables and expressions...")
        code = """
# Define variables
x = 10
y = 20

# Perform calculations
sum_result = x + y
product = x * y
power = x ** 2

# Print results
print(f"x = {x}, y = {y}")
print(f"Sum: {sum_result}")
print(f"Product: {product}")
print(f"x squared: {power}")

# Conditional logic
if x < y:
    print("x is less than y")
else:
    print("x is greater than or equal to y")
        """

        async with AsyncTimer("Variables and expressions"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Lists and loops
        print_info("\nRunning code with lists and loops...")
        code = """
# Create a list
numbers = [1, 2, 3, 4, 5]

# Print using a loop
print("Numbers:")
for num in numbers:
    print(f"  {num} squared is {num ** 2}")

# List comprehension
squares = [n ** 2 for n in numbers]
print(f"All squares: {squares}")

# Sum and average
total = sum(numbers)
average = total / len(numbers)
print(f"Sum: {total}, Average: {average:.2f}")
        """

        async with AsyncTimer("Lists and loops"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in basic Python example: {e}")


async def python_functions_example() -> None:
    """Example of Python code with functions."""
    print_section("Python Functions")

    # Create the Python execution tool
    py_exec = PythonExecute()

    try:
        # Define and use functions
        print_info("Running code with function definitions...")
        code = """
# Define a simple function
def greet(name):
    return f"Hello, {name}!"

# Function with default parameters
def calculate_area(length, width=None):
    if width is None:
        # Square
        return length ** 2
    return length * width

# Recursive function
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Test the functions
print(greet("World"))
print(f"Area of square with side 5: {calculate_area(5)}")
print(f"Area of rectangle 4x6: {calculate_area(4, 6)}")
print(f"Factorial of 5: {factorial(5)}")
        """

        async with AsyncTimer("Function definitions"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Lambda functions and higher-order functions
        print_info("\nRunning code with lambda and higher-order functions...")
        code = """
# Lambda function
square = lambda x: x ** 2
print(f"Square of 7 using lambda: {square(7)}")

# Map function
numbers = [1, 2, 3, 4, 5]
squared = list(map(lambda x: x ** 2, numbers))
print(f"Squared numbers using map: {squared}")

# Filter function
even_numbers = list(filter(lambda x: x % 2 == 0, numbers))
print(f"Even numbers using filter: {even_numbers}")

# Higher-order function
def apply_operation(func, x, y):
    return func(x, y)

add = lambda x, y: x + y
multiply = lambda x, y: x * y

print(f"Apply add to 5, 3: {apply_operation(add, 5, 3)}")
print(f"Apply multiply to 5, 3: {apply_operation(multiply, 5, 3)}")
        """

        async with AsyncTimer("Lambda and higher-order functions"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in Python functions example: {e}")


async def python_error_handling_example() -> None:
    """Example of handling errors in Python code."""
    print_section("Python Error Handling")

    # Create the Python execution tool
    py_exec = PythonExecute()

    try:
        # Syntax error
        print_info("Running code with syntax error...")
        code = """
# This code has a syntax error
if True
    print("This will not run")
        """

        async with AsyncTimer("Syntax error"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Expected error occurred: {result.error}")
            else:
                print_warning("Code unexpectedly ran without errors")
                print(result.output)

        # Runtime error
        print_info("\nRunning code with runtime error (division by zero)...")
        code = """
# This code will cause a runtime error
x = 10
y = 0
print(f"Attempting to divide {x} by {y}...")
result = x / y
print(f"Result: {result}")  # This line will not be reached
        """

        async with AsyncTimer("Runtime error"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.error:
                print_error(f"Expected error occurred: {result.error}")
            else:
                print_warning("Code unexpectedly ran without errors")
                print(result.output)

        # Handling exceptions with try/except
        print_info("\nRunning code with try/except error handling...")
        code = """
# This code handles exceptions properly
x = 10
y = 0

try:
    print(f"Attempting to divide {x} by {y}...")
    result = x / y
    print(f"Result: {result}")  # This line will not be reached
except ZeroDivisionError:
    print("Error: Cannot divide by zero!")
    result = "undefined"

print(f"Program continues with result = {result}")

# Handling multiple exception types
values = [10, 0, "5", "abc"]

for val in values:
    try:
        num = int(val)
        result = 100 / num
        print(f"100 / {val} = {result}")
    except ZeroDivisionError:
        print(f"Cannot divide by {val}")
    except ValueError:
        print(f"Cannot convert '{val}' to an integer")
    except Exception as e:
        print(f"Unexpected error: {e}")
        """

        async with AsyncTimer("Try/except handling"):
            result = await py_exec.execute(code=code)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

    except Exception as e:
        print_error(f"Error in Python error handling example: {e}")


async def python_timeout_example() -> None:
    """Example of handling timeouts in Python code execution."""
    print_section("Python Execution Timeouts")

    # Create the Python execution tool
    py_exec = PythonExecute()

    try:
        # Code that completes quickly
        print_info("Running code that completes quickly...")
        code = """
import time

print("Starting fast execution...")
time.sleep(1)  # Sleep for 1 second
print("Completed fast execution!")
        """

        async with AsyncTimer("Fast execution"):
            result = await py_exec.execute(code=code, timeout=5)

        if isinstance(result, ToolResult):
            if result.output:
                print(result.output)
            if result.error:
                print_error(f"Error: {result.error}")

        # Code that would time out
        print_info("\nRunning code that would time out (with 2 second timeout)...")
        code = """
import time

print("Starting slow execution...")
print("This will sleep for 10 seconds, but timeout is set to 2 seconds")
time.sleep(10)  # Sleep for 10 seconds
print("This line should not be printed due to timeout!")
        """

        async with AsyncTimer("Timeout execution"):
            result = await py_exec.execute(code=code, timeout=2)

        if isinstance(result, ToolResult):
            if result.error and "timeout" in result.error.lower():
                print_success(f"Expected timeout occurred: {result.error}")
            elif result.error:
                print_error(f"Unexpected error: {result.error}")
            else:
                print_warning("Code unexpectedly completed without timing out")
                print(result.output)

        # Code with a loop that would time out
        print_info("\nRunning code with a loop that would time out...")
        code = """
print("Starting a potentially infinite loop...")
counter = 0
while True:
    counter += 1
    if counter % 1000000 == 0:
        print(f"Iteration {counter}")

    # This would allow it to exit eventually, but timeout should happen first
    if counter >= 1000000000:
        break
        """

        async with AsyncTimer("Loop timeout"):
            result = await py_exec.execute(code=code, timeout=3)

        if isinstance(result, ToolResult):
            if result.error and "timeout" in result.error.lower():
                print_success(f"Expected timeout occurred: {result.error}")
            elif result.error:
                print_error(f"Unexpected error: {result.error}")
            else:
                print_warning("Code unexpectedly completed without timing out")
                print(result.output)

    except Exception as e:
        print_error(f"Error in Python timeout example: {e}")


async def run_examples() -> None:
    """Run all Python execution examples."""
    try:
        await python_basic_example()
        separator()

        await python_functions_example()
        separator()

        await python_error_handling_example()
        separator()

        await python_timeout_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point for Python execution examples."""
    print_title("Enterprise AI Python Execution Examples")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All Python execution examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
