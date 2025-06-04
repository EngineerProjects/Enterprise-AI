#!/usr/bin/env python3
"""
Comprehensive File Search Tool Testing Script

Tests each aspect of the code search tool individually with detailed validation.
This script tests all CodeSearchTool capabilities systematically:
- Text pattern searching across files
- Regex pattern matching
- File type filtering (*.py, *.js, etc.)
- Case-sensitive and case-insensitive search
- Context lines before and after matches
- Result limiting and performance
- Hidden file inclusion/exclusion
- Directory exclusion patterns
- Error handling and edge cases
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

# Setup project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from examples.notebooks.utils import (
    print_header, print_test, print_chat, Timer, run_async, separator
)
from enterprise_ai.tool.file.search import CodeSearchTool
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.base import ToolConfig
from enterprise_ai.tool.constants import ExecutionMode, SandboxMode


class FileSearchTester:
    """Comprehensive file search tool tester with all feature validation."""
    
    def __init__(self, use_sandbox: bool = False):
        self.search_tool = None
        self.test_dir = None
        self.use_sandbox = use_sandbox
        self.test_count = 0
        self.pass_count = 0
        self.fail_count = 0
    
    async def setup(self):
        """Initialize the file search tool and test environment."""
        print_header("File Search Tool Comprehensive Test Suite", "double")
        
        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="search_test_"))
        print_test(f"Test directory: {self.test_dir}", "pass")
        
        # Initialize CodeSearchTool with configuration
        config = ToolConfig(
            timeout=30.0,
            max_retries=2,
            sandbox_enabled=self.use_sandbox,
            execution_mode=ExecutionMode.AUTO,
            sandbox_mode=SandboxMode.NONE if not self.use_sandbox else SandboxMode.UNIFIED,
            verbose_logging=True
        )
        
        print_test("Creating CodeSearchTool instance", "running")
        self.search_tool = CodeSearchTool(config=config)
        
        # Show tool description
        print_header("Tool Description", "single")
        print_chat("tool", self.search_tool.description)
        
        # Initialize the tool
        print_test("Initializing CodeSearchTool", "running")
        success = await self.search_tool.initialize()
        
        if success:
            print_test("CodeSearchTool initialized successfully", "pass")
            print_test(f"Mode: {'Sandbox' if self.use_sandbox else 'Local'}", "pass")
            return True
        else:
            print_test("CodeSearchTool initialization failed", "fail")
            return False
    
    def create_test_files(self):
        """Create a comprehensive set of test files for searching."""
        print_test("Creating test file structure", "running")
        
        # Python files
        (self.test_dir / "main.py").write_text("""
def hello_world():
    print("Hello, World!")
    return "success"

class TestClass:
    def __init__(self):
        self.value = 42
    
    def get_value(self):
        return self.value
""")
        
        (self.test_dir / "utils.py").write_text("""
import os
import sys

def process_data(data):
    # Process the data here
    result = data.upper()
    return result

def hello_world():
    print("Another hello world function")
""")
        
        # JavaScript files
        (self.test_dir / "script.js").write_text("""
function helloWorld() {
    console.log("Hello, World!");
    return "success";
}

class TestClass {
    constructor() {
        this.value = 42;
    }
    
    getValue() {
        return this.value;
    }
}
""")
        
        # Text files
        (self.test_dir / "readme.txt").write_text("""
This is a README file.
It contains documentation about the project.
Hello World example is included.
The function hello_world() is important.
""")
        
        (self.test_dir / "data.txt").write_text("""
Line 1: Data processing
Line 2: Hello World
Line 3: More data
Line 4: Processing complete
Line 5: HELLO WORLD in caps
""")
        
        # Configuration files
        (self.test_dir / "config.json").write_text("""
{
    "name": "test_project",
    "version": "1.0.0",
    "description": "Hello World project",
    "main": "main.py"
}
""")
        
        # Create subdirectories
        subdir = self.test_dir / "subdir"
        subdir.mkdir()
        
        (subdir / "nested.py").write_text("""
# Nested Python file
def nested_function():
    print("This is a nested function")
    hello_world()
""")
        
        (subdir / "nested.txt").write_text("""
Nested text file
Contains hello world text
For testing recursive search
""")
        
        # Hidden files
        (self.test_dir / ".hidden.py").write_text("""
# Hidden Python file
def hidden_function():
    print("Hidden hello world")
""")
        
        # Create test directory to exclude
        excluded_dir = self.test_dir / "excluded"
        excluded_dir.mkdir()
        (excluded_dir / "excluded.py").write_text("""
def excluded_function():
    print("This should not be found")
    hello_world()
""")
        
        print_test("Test file structure created", "pass")
    
    async def run_test(self, test_name: str, expected_success: bool = True, **kwargs) -> tuple[ToolResult, bool]:
        """Run a single test and validate results."""
        self.test_count += 1
        print_test(f"Test #{self.test_count}: {test_name}", "running")
        
        # Always include path as the test directory
        kwargs['path'] = str(self.test_dir)
        
        try:
            with Timer(f"Execution time"):
                result = await self.search_tool.execute(**kwargs)
            
            success = isinstance(result, ToolResult) and result.success
            
            if success == expected_success:
                self.pass_count += 1
                print_test(f"✓ {test_name}", "pass")
                
                # Show result if it's a string and not too long
                if hasattr(result, 'result') and isinstance(result.result, str):
                    output = result.result
                    if len(output) <= 400:
                        print_chat("tool", output)
                    else:
                        # Show first part and count matches
                        lines = output.split('\n')
                        preview = '\n'.join(lines[:10])
                        print_chat("tool", f"{preview}\n... [{len(lines)} total lines]")
                
                return result, True
            else:
                self.fail_count += 1
                expected_str = "SUCCESS" if expected_success else "FAILURE"
                actual_str = "SUCCESS" if success else "FAILURE"
                print_test(f"✗ {test_name}: Expected {expected_str}, got {actual_str}", "fail")
                
                if hasattr(result, 'error') and result.error:
                    print_chat("tool", f"Error: {result.error}")
                
                return result, False
                
        except Exception as e:
            self.fail_count += 1
            print_test(f"✗ {test_name}: Exception - {e}", "fail")
            return None, False
    
    async def test_basic_text_search(self):
        """Test basic text pattern searching."""
        print_header("Basic Text Search Tests", "single")
        
        # Test 1: Simple text search
        await self.run_test(
            "Search for 'hello_world'",
            pattern="hello_world"
        )
        
        # Test 2: Case-sensitive search
        await self.run_test(
            "Case-sensitive search for 'Hello'",
            pattern="Hello",
            ignore_case=False
        )
        
        # Test 3: Case-insensitive search
        await self.run_test(
            "Case-insensitive search for 'HELLO'",
            pattern="HELLO",
            ignore_case=True
        )
        
        # Test 4: Search for non-existent pattern
        await self.run_test(
            "Search for non-existent pattern",
            pattern="nonexistent_pattern_xyz123"
        )
        
        # Test 5: Search for common word
        await self.run_test(
            "Search for common word 'function'",
            pattern="function"
        )
    
    async def test_regex_patterns(self):
        """Test regex pattern matching."""
        print_header("Regex Pattern Tests", "single")
        
        # Test 1: Simple regex pattern
        await self.run_test(
            "Regex: function definitions",
            pattern=r"def \w+\(",
            use_regex=True
        )
        
        # Test 2: Class definitions
        await self.run_test(
            "Regex: class definitions",
            pattern=r"class \w+",
            use_regex=True
        )
        
        # Test 3: String literals
        await self.run_test(
            "Regex: string literals",
            pattern=r'"[^"]*"',
            use_regex=True
        )
        
        # Test 4: Numbers
        await self.run_test(
            "Regex: numbers",
            pattern=r"\b\d+\b",
            use_regex=True
        )
        
        # Test 5: Invalid regex (should fail gracefully)
        await self.run_test(
            "Invalid regex pattern",
            pattern=r"[invalid regex",
            use_regex=True,
            expected_success=False
        )
    
    async def test_file_filtering(self):
        """Test file type filtering."""
        print_header("File Filtering Tests", "single")
        
        # Test 1: Python files only
        await self.run_test(
            "Search in Python files only",
            pattern="hello_world",
            file_pattern="*.py"
        )
        
        # Test 2: JavaScript files only
        await self.run_test(
            "Search in JavaScript files only",
            pattern="helloWorld",
            file_pattern="*.js"
        )
        
        # Test 3: Text files only
        await self.run_test(
            "Search in text files only",
            pattern="Hello World",
            file_pattern="*.txt"
        )
        
        # Test 4: JSON files only
        await self.run_test(
            "Search in JSON files only",
            pattern="test_project",
            file_pattern="*.json"
        )
        
        # Test 5: Multiple file extensions
        await self.run_test(
            "Search in Python and JavaScript files",
            pattern="value",
            file_pattern="*.{py,js}"
        )
    
    async def test_context_lines(self):
        """Test context lines feature."""
        print_header("Context Lines Tests", "single")
        
        # Test 1: No context lines
        await self.run_test(
            "Search with no context",
            pattern="def hello_world",
            context_lines=0
        )
        
        # Test 2: 2 context lines
        await self.run_test(
            "Search with 2 context lines",
            pattern="def hello_world",
            context_lines=2
        )
        
        # Test 3: 5 context lines
        await self.run_test(
            "Search with 5 context lines",
            pattern="class TestClass",
            context_lines=5
        )
        
        # Test 4: Large context (more than file length)
        await self.run_test(
            "Search with excessive context lines",
            pattern="value = 42",
            context_lines=100
        )
    
    async def test_result_limiting(self):
        """Test result limiting features."""
        print_header("Result Limiting Tests", "single")
        
        # Test 1: Limit to 1 result
        await self.run_test(
            "Limit to 1 result",
            pattern="hello",
            max_results=1,
            ignore_case=True
        )
        
        # Test 2: Limit to 3 results
        await self.run_test(
            "Limit to 3 results",
            pattern="hello",
            max_results=3,
            ignore_case=True
        )
        
        # Test 3: No limit (find all)
        await self.run_test(
            "No result limit",
            pattern="hello",
            ignore_case=True
        )
        
        # Test 4: Limit larger than available results
        await self.run_test(
            "Limit larger than available",
            pattern="nested_function",
            max_results=100
        )
    
    async def test_hidden_files(self):
        """Test hidden file inclusion/exclusion."""
        print_header("Hidden Files Tests", "single")
        
        # Test 1: Exclude hidden files (default)
        await self.run_test(
            "Search excluding hidden files",
            pattern="hidden_function",
            include_hidden=False
        )
        
        # Test 2: Include hidden files
        await self.run_test(
            "Search including hidden files",
            pattern="hidden_function",
            include_hidden=True
        )
        
        # Test 3: Search for pattern only in hidden files
        await self.run_test(
            "Search in hidden files only",
            pattern="Hidden hello world",
            include_hidden=True
        )
    
    async def test_directory_exclusion(self):
        """Test directory exclusion patterns."""
        print_header("Directory Exclusion Tests", "single")
        
        # Test 1: No exclusions
        await self.run_test(
            "Search with no exclusions",
            pattern="hello_world",
            exclude_dirs=[]
        )
        
        # Test 2: Exclude subdirectory
        await self.run_test(
            "Search excluding 'subdir'",
            pattern="nested_function",
            exclude_dirs=["subdir"]
        )
        
        # Test 3: Exclude multiple directories
        await self.run_test(
            "Search excluding multiple directories",
            pattern="hello_world",
            exclude_dirs=["subdir", "excluded"]
        )
        
        # Test 4: Exclude non-existent directory
        await self.run_test(
            "Search excluding non-existent directory",
            pattern="hello_world",
            exclude_dirs=["nonexistent"]
        )
    
    async def test_search_performance(self):
        """Test search performance and timeout."""
        print_header("Performance and Timeout Tests", "single")
        
        # Test 1: Search with short timeout
        await self.run_test(
            "Search with short timeout",
            pattern="hello",
            timeout_ms=5000  # 5 seconds
        )
        
        # Test 2: Search with very short timeout (might timeout)
        await self.run_test(
            "Search with very short timeout",
            pattern=".*",  # Match everything
            use_regex=True,
            timeout_ms=10,  # 10ms - very short
            expected_success=False  # Might fail due to timeout
        )
        
        # Test 3: Complex regex with timeout
        await self.run_test(
            "Complex regex with reasonable timeout",
            pattern=r"\b[a-zA-Z]+\(\)",  # Function calls
            use_regex=True,
            timeout_ms=10000  # 10 seconds
        )
    
    async def test_edge_cases(self):
        """Test edge cases and error conditions."""
        print_header("Edge Cases and Error Handling Tests", "single")
        
        # Test 1: Empty pattern
        await self.run_test(
            "Search with empty pattern",
            pattern="",
            expected_success=False
        )
        
        # Test 2: Search in non-existent directory
        await self.run_test(
            "Search in non-existent directory",
            pattern="hello",
            path=str(self.test_dir / "nonexistent"),
            expected_success=False
        )
        
        # Test 3: Search in file instead of directory
        test_file = self.test_dir / "main.py"
        await self.run_test(
            "Search in file instead of directory",
            pattern="hello",
            path=str(test_file),
            expected_success=False
        )
        
        # Test 4: Very large max_results
        await self.run_test(
            "Search with very large max_results",
            pattern="hello",
            max_results=999999
        )
        
        # Test 5: Negative values
        await self.run_test(
            "Search with negative context_lines",
            pattern="hello",
            context_lines=-1,
            expected_success=False
        )
    
    async def test_comprehensive_search(self):
        """Test comprehensive search combining multiple features."""
        print_header("Comprehensive Search Tests", "single")
        
        # Test 1: Complex search with all features
        await self.run_test(
            "Complex search: Python files, regex, context, limit",
            pattern=r"def \w+",
            file_pattern="*.py",
            use_regex=True,
            context_lines=2,
            max_results=5,
            ignore_case=False,
            include_hidden=True
        )
        
        # Test 2: Case-insensitive text search with exclusions
        await self.run_test(
            "Case-insensitive with exclusions",
            pattern="hello world",
            ignore_case=True,
            exclude_dirs=["excluded"],
            context_lines=1
        )
        
        # Test 3: Search in specific file types with context
        await self.run_test(
            "Text files with context and limits",
            pattern="data",
            file_pattern="*.txt",
            context_lines=3,
            max_results=10,
            ignore_case=True
        )
    
    def print_summary(self):
        """Print test summary."""
        print_header("Test Summary", "double")
        
        print_test(f"Total Tests: {self.test_count}", "pass")
        print_test(f"Passed: {self.pass_count}", "pass")
        print_test(f"Failed: {self.fail_count}", "fail" if self.fail_count > 0 else "pass")
        
        success_rate = (self.pass_count / max(1, self.test_count)) * 100
        print_test(f"Success Rate: {success_rate:.1f}%", 
                  "pass" if success_rate >= 90 else "warn" if success_rate >= 70 else "fail")
        
        if self.fail_count == 0:
            print_chat("system", "🎉 All tests passed! CodeSearchTool is working perfectly.")
        elif success_rate >= 90:
            print_chat("system", "✅ Most tests passed. Minor issues detected.")
        else:
            print_chat("system", "⚠️ Some tests failed. Please review the implementation.")
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.search_tool:
            print_test("Cleaning up CodeSearchTool", "running")
            await self.search_tool.cleanup()
            print_test("CodeSearchTool cleanup complete", "pass")
        
        if self.test_dir and self.test_dir.exists():
            print_test(f"Removing test directory: {self.test_dir}", "running")
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print_test("Test directory cleanup complete", "pass")


async def main():
    """Run comprehensive file search tests."""
    test_sandbox = False  # Set to True to also test sandbox mode
    
    for mode_name, use_sandbox in [("Local Mode", False)] + ([("Sandbox Mode", True)] if test_sandbox else []):
        print_header(f"Testing in {mode_name}", "double")
        
        tester = FileSearchTester(use_sandbox=use_sandbox)
        
        try:
            # Setup
            if not await tester.setup():
                print_test("Setup failed, skipping this mode", "fail")
                continue
            
            # Create test files
            tester.create_test_files()
            
            # Run all test suites
            await tester.test_basic_text_search()
            await tester.test_regex_patterns()
            await tester.test_file_filtering()
            await tester.test_context_lines()
            await tester.test_result_limiting()
            await tester.test_hidden_files()
            await tester.test_directory_exclusion()
            await tester.test_search_performance()
            await tester.test_edge_cases()
            await tester.test_comprehensive_search()
            
            # Print summary for this mode
            tester.print_summary()
            
        except KeyboardInterrupt:
            print_test("Tests interrupted by user", "warn")
            break
        except Exception as e:
            print_test(f"Unexpected error in {mode_name}: {e}", "fail")
        finally:
            await tester.cleanup()
        
        separator("═", 80)
    
    print_header("All File Search Tests Complete!", "double")
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)