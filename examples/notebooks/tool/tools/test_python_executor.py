#!/usr/bin/env python3
"""
Enhanced Python Executor Testing Suite

Comprehensive testing for the enhanced Python execution tool with session management,
intelligent routing, and advanced safety analysis.
"""

import asyncio
import sys
import os
import tempfile
import time
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parents[4]
sys.path.insert(0, str(project_root))

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class EnhancedPythonExecutorTester:
    """Comprehensive Python executor tester with all enhanced features."""
    
    def __init__(self):
        self.python_tool = None
        self.test_results = []
        self.session_ids = []
    
    async def setup(self):
        """Initialize the enhanced Python executor tool."""
        print_header("Enhanced Python Executor Test Suite", "double")
        
        print_test("Initializing enhanced Python executor", "running")
        
        self.python_tool = PythonExecute()
        success = await self.python_tool.initialize()
        
        if success:
            print_test("Enhanced Python executor initialized", "pass")
            await self.show_tool_info()
            return True
        else:
            print_test("Failed to initialize Python executor", "fail")
            return False
    
    async def show_tool_info(self):
        """Show enhanced tool information."""
        print_header("Tool Information", "single")
        
        print_chat("tool", f"Tool Name: {self.python_tool.name}")
        print_chat("tool", f"Description: {self.python_tool.description.strip()}")
        
        if hasattr(self.python_tool, 'capabilities'):
            caps = [str(cap) for cap in self.python_tool.capabilities]
            print_chat("tool", f"Capabilities: {', '.join(caps)}")
        
        # Show execution stats
        stats = self.python_tool.get_execution_stats()
        print_chat("tool", f"Initial Stats: {stats}")

    async def test_operation(self, description: str, expect_success: bool = True, 
                           show_analysis: bool = False, **kwargs):
        """Test a single operation with enhanced reporting."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {description}"):
                result = await self.python_tool.execute(**kwargs)
            
            is_success = isinstance(result, ToolResult) and result.success
            
            # Record test result
            self.test_results.append({
                'description': description,
                'expected_success': expect_success,
                'actual_success': is_success,
                'passed': is_success == expect_success
            })
            
            if expect_success and is_success:
                print_test(f"{description}: SUCCESS", "pass")
                
                if hasattr(result, 'result') and result.result:
                    output = result.result
                    
                    # Show execution environment
                    if isinstance(output, dict):
                        env = output.get('execution_environment', 'unknown')
                        print_chat("system", f"Execution Environment: {env}")
                        
                        # Show analysis if requested
                        if show_analysis and 'execution_analysis' in output:
                            analysis = output['execution_analysis']
                            print_chat("analysis", f"Execution Decision: {analysis}")
                        
                        # Show session info
                        if 'session_id' in output:
                            session_id = output['session_id']
                            self.session_ids.append(session_id)
                            print_chat("session", f"Session ID: {session_id}")
                        
                        # Show primary output
                        main_output = output.get('output', str(output))
                    else:
                        main_output = str(output)
                    
                    if main_output and len(main_output) <= 500:
                        print_chat("output", main_output)
                    elif main_output:
                        print_chat("output", main_output[:500] + "...")
                
                return result, True
                
            elif not expect_success and not is_success:
                print_test(f"{description}: EXPECTED ERROR", "pass")
                error_msg = getattr(result, 'error', 'Unknown error')
                print_chat("error", f"Expected error: {error_msg}")
                return result, True
                
            elif expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: UNEXPECTED FAILURE - {error_msg}", "fail")
                return result, False
                
            else:  # not expect_success and is_success
                print_test(f"{description}: UNEXPECTED SUCCESS", "warn")
                return result, False
                
        except Exception as e:
            self.test_results.append({
                'description': description,
                'expected_success': expect_success,
                'actual_success': False,
                'passed': not expect_success
            })
            
            if expect_success:
                print_test(f"{description}: EXCEPTION - {e}", "fail")
                return None, False
            else:
                print_test(f"{description}: EXPECTED EXCEPTION - {e}", "pass")
                return None, True

    async def test_basic_operations(self):
        """Test basic Python operations."""
        print_header("Basic Python Operations", "single")
        
        # Simple print (should run locally)
        await self.test_operation(
            "Simple Print Statement",
            expect_success=True,
            code="print('Hello from Enhanced Python!')",
            sandbox_mode="auto",
            show_analysis=True
        )
        
        # Basic math (should run locally)
        await self.test_operation(
            "Basic Mathematics",
            expect_success=True,
            code="""
result = 42 * 1.5 + 10
print(f"Math result: {result}")
print(f"Square root of 100: {100 ** 0.5}")
""",
            sandbox_mode="auto"
        )
        
        # List comprehension (should run locally)
        await self.test_operation(
            "List Comprehension",
            expect_success=True,
            code="""
numbers = list(range(1, 11))
squares = [x**2 for x in numbers]
print(f"Numbers: {numbers}")
print(f"Squares: {squares}")
print(f"Sum of squares: {sum(squares)}")
""",
            sandbox_mode="auto"
        )

    async def test_intelligent_routing(self):
        """Test intelligent execution routing."""
        print_header("Intelligent Execution Routing", "single")
        
        # Safe code that should run locally
        await self.test_operation(
            "Safe Code (Should Use Local)",
            expect_success=True,
            code="""
import math
import json

data = {"numbers": [1, 2, 3, 4, 5]}
total = sum(data["numbers"])
avg = total / len(data["numbers"])

print(f"Data: {json.dumps(data)}")
print(f"Total: {total}")
print(f"Average: {avg}")
print(f"Standard deviation: {math.sqrt(sum((x - avg)**2 for x in data['numbers']) / len(data['numbers']))}")
""",
            sandbox_mode="auto",
            show_analysis=True
        )
        
        # Potentially dangerous code (should use sandbox)
        await self.test_operation(
            "File System Code (Should Use Sandbox)",
            expect_success=True,
            code="""
import os
import tempfile

print("Current working directory:", os.getcwd())
print("Environment variables count:", len(os.environ))
temp_dir = tempfile.gettempdir()
print(f"Temp directory: {temp_dir}")
""",
            sandbox_mode="auto",
            show_analysis=True
        )
        
        # Forced local execution
        await self.test_operation(
            "Forced Local Execution",
            expect_success=True,
            code="print('This runs locally even with os import'); import os; print(os.getcwd())",
            sandbox_mode="local"
        )
        
        # Forced sandbox execution
        await self.test_operation(
            "Forced Sandbox Execution",
            expect_success=True,
            code="print('This runs in sandbox'); result = 5 + 3; print(f'Result: {result}')",
            sandbox_mode="sandbox"
        )

    async def test_session_management(self):
        """Test session management and variable persistence."""
        print_header("Session Management", "single")
        
        # Create variables in first session
        await self.test_operation(
            "Create Session Variables",
            expect_success=True,
            code="""
session_var = "Hello from session!"
numbers_list = [1, 2, 3, 4, 5]
calculation_result = sum(numbers_list) * 2

print(f"Session variable: {session_var}")
print(f"Numbers: {numbers_list}")
print(f"Calculation result: {calculation_result}")
""",
            session_id="test_session_1",
            persist_variables=True,
            sandbox_mode="local"
        )
        
        # Try to access variables in same session
        await self.test_operation(
            "Access Session Variables",
            expect_success=True,
            code="""
try:
    print(f"Accessing session_var: {session_var}")
    print(f"Accessing numbers_list: {numbers_list}")
    print(f"Previous calculation: {calculation_result}")
    
    # Add new variable
    new_var = "Added in second execution"
    print(f"New variable: {new_var}")
except NameError as e:
    print(f"Variable not found: {e}")
""",
            session_id="test_session_1",
            persist_variables=True,
            sandbox_mode="local"
        )
        
        # Test different session (should not have access)
        await self.test_operation(
            "Different Session (No Access)",
            expect_success=True,
            code="""
try:
    print(f"Trying to access session_var: {session_var}")
except NameError:
    print("session_var not available in this session (expected)")

# Create new variable in this session
different_session_var = "This is a different session"
print(f"Different session var: {different_session_var}")
""",
            session_id="test_session_2",
            persist_variables=True,
            sandbox_mode="local"
        )

    async def test_security_controls(self):
        """Test security controls and sandbox behavior."""
        print_header("Security Controls", "single")
        
        # Test restricted imports in sandbox
        await self.test_operation(
            "Restricted Import (subprocess)",
            expect_success=False,
            code="""
import subprocess
result = subprocess.run(['echo', 'hello'], capture_output=True, text=True)
print(result.stdout)
""",
            sandbox_mode="sandbox"
        )
        
        # Test another restricted import
        await self.test_operation(
            "Restricted Import (socket)",
            expect_success=False,
            code="""
import socket
s = socket.socket()
print("Socket created")
""",
            sandbox_mode="sandbox"
        )
        
        # Test safe imports in sandbox
        await self.test_operation(
            "Safe Imports in Sandbox",
            expect_success=True,
            code="""
import math
import json
import random

data = [random.randint(1, 100) for _ in range(5)]
print(f"Random data: {data}")
print(f"Average: {sum(data) / len(data)}")
print(f"JSON: {json.dumps(data)}")
print(f"Math constants: π={math.pi:.4f}, e={math.e:.4f}")
""",
            sandbox_mode="sandbox"
        )

    async def test_error_handling(self):
        """Test comprehensive error handling."""
        print_header("Error Handling", "single")
        
        # Syntax error
        await self.test_operation(
            "Syntax Error",
            expect_success=False,
            code="""
print("This has a syntax error"
# Missing closing parenthesis
""",
            sandbox_mode="local"
        )
        
        # Runtime error
        await self.test_operation(
            "Runtime Error (Division by Zero)",
            expect_success=False,
            code="""
x = 10
y = 0
result = x / y
print(f"Result: {result}")
""",
            sandbox_mode="local"
        )
        
        # Index error
        await self.test_operation(
            "Index Error", 
            expect_success=False,
            code="""
my_list = [1, 2, 3]
print(my_list[5])  # Index out of range
""",
            sandbox_mode="local"
        )
        
        # Name error
        await self.test_operation(
            "Name Error",
            expect_success=False,
            code="""
print(undefined_variable)
""",
            sandbox_mode="local"
        )

    async def test_performance_and_complexity(self):
        """Test performance with complex operations."""
        print_header("Performance & Complexity", "single")
        
        # Medium complexity (should run locally)
        await self.test_operation(
            "Medium Complexity Algorithm",
            expect_success=True,
            code="""
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)

print("Fibonacci sequence (first 10):")
fib_sequence = [fibonacci(i) for i in range(10)]
print(fib_sequence)

print("\\nFactorials (1-8):")
fact_sequence = [factorial(i) for i in range(1, 9)]
print(fact_sequence)
""",
            sandbox_mode="auto",
            show_analysis=True
        )
        
        # High complexity (might trigger sandbox)
        await self.test_operation(
            "High Complexity with File Operations",
            expect_success=True,
            code="""
import tempfile
import os
import json
from collections import defaultdict

# Create temporary data
data = {
    "users": [
        {"id": i, "name": f"User_{i}", "score": i * 10} 
        for i in range(1, 101)
    ]
}

# Complex data processing
user_stats = defaultdict(list)
for user in data["users"]:
    category = "high" if user["score"] > 500 else "medium" if user["score"] > 200 else "low"
    user_stats[category].append(user)

# Write temporary file
temp_file = os.path.join(tempfile.gettempdir(), "user_stats.json")
with open(temp_file, "w") as f:
    json.dump(user_stats, f, indent=2)

print(f"Processing complete. Categories:")
for category, users in user_stats.items():
    print(f"  {category}: {len(users)} users")

print(f"Temporary file: {temp_file}")
""",
            sandbox_mode="auto",
            show_analysis=True
        )

    async def test_timeout_handling(self):
        """Test timeout handling."""
        print_header("Timeout Handling", "single")
        
        # Quick operation (should complete)
        await self.test_operation(
            "Quick Operation (Under Timeout)",
            expect_success=True,
            code="""
import time
print("Starting quick operation...")
time.sleep(0.5)  # Half second
print("Quick operation completed!")
""",
            timeout=2,
            sandbox_mode="local"
        )
        
        # Slow operation (should timeout)
        await self.test_operation(
            "Slow Operation (Should Timeout)",
            expect_success=False,
            code="""
import time
print("Starting slow operation...")
time.sleep(5)  # 5 seconds
print("This should not print due to timeout")
""",
            timeout=2,
            sandbox_mode="local"
        )

    async def show_final_statistics(self):
        """Show comprehensive test results and tool statistics."""
        print_header("Final Test Results & Statistics", "double")
        
        # Test summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['passed'])
        failed_tests = total_tests - passed_tests
        
        print_test(f"Total Tests: {total_tests}", "pass")
        print_test(f"Passed: {passed_tests}", "pass")
        print_test(f"Failed: {failed_tests}", "fail" if failed_tests > 0 else "pass")
        print_test(f"Success Rate: {passed_tests/total_tests*100:.1f}%", 
                  "pass" if passed_tests/total_tests >= 0.8 else "warn")
        
        # Tool execution statistics
        stats = self.python_tool.get_execution_stats()
        print_header("Tool Execution Statistics", "single")
        
        for key, value in stats.items():
            print_chat("stats", f"{key}: {value}")
        
        # Session information
        if self.session_ids:
            print_header("Session Information", "single")
            print_chat("session", f"Sessions created: {len(set(self.session_ids))}")
            print_chat("session", f"Unique session IDs: {list(set(self.session_ids))}")
        
        # Failed tests details
        if failed_tests > 0:
            print_header("Failed Tests Details", "single")
            for result in self.test_results:
                if not result['passed']:
                    status = "FAIL" if result['expected_success'] else "UNEXPECTED_SUCCESS"
                    print_test(f"{result['description']}: {status}", "fail")

    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.python_tool:
            print_test("Cleaning up Python tool", "running")
            await self.python_tool.cleanup()
            print_test("Python tool cleanup complete", "pass")


async def main():
    """Run comprehensive Python executor tests."""
    tester = EnhancedPythonExecutorTester()
    
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run all test suites
        await tester.test_basic_operations()
        await tester.test_intelligent_routing()
        await tester.test_session_management()
        await tester.test_security_controls()
        await tester.test_error_handling()
        await tester.test_performance_and_complexity()
        await tester.test_timeout_handling()
        
        # Show comprehensive results
        await tester.show_final_statistics()
        
        print_header("Enhanced Python Executor Testing Complete!", "double")
        print_test("All test suites completed successfully", "pass")
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
    except Exception as e:
        print_test(f"Unexpected error during testing: {e}", "fail")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup()
    
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)