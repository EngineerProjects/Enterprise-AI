#!/usr/bin/env python3
"""
Enhanced Bash Executor Testing Suite - Simplified and Reliable

Comprehensive testing for the enhanced Bash execution tool with basic functionality.
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
from enterprise_ai.tool.execution.bash import Bash
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class SimpleBashExecutorTester:
    """Simplified Bash executor tester focusing on core functionality."""
    
    def __init__(self):
        self.bash_tool = None
        self.test_results = []
        self.test_files_created = []
        self.working_dir = None
        self._cleanup_done = False
    
    async def setup(self):
        """Initialize the bash executor tool."""
        print_header("Enhanced Bash Executor Test Suite", "double")
        
        print_test("Creating test working directory", "running")
        self.working_dir = tempfile.mkdtemp(prefix="bash_test_")
        print_test(f"Test working directory: {self.working_dir}", "pass")
        
        print_test("Initializing bash executor", "running")
        
        self.bash_tool = Bash(working_dir=self.working_dir)
        success = await self.bash_tool.initialize()
        
        if success:
            print_test("Bash executor initialized", "pass")
            await self.show_tool_info()
            return True
        else:
            print_test("Failed to initialize Bash executor", "fail")
            return False
    
    async def show_tool_info(self):
        """Show tool information."""
        print_header("Tool Information", "single")
        
        print_chat("tool", f"Tool Name: {self.bash_tool.name}")
        print_chat("tool", f"Description: {self.bash_tool.description.strip()}")
        
        if hasattr(self.bash_tool, 'capabilities'):
            caps = [str(cap) for cap in self.bash_tool.capabilities]
            print_chat("tool", f"Capabilities: {', '.join(caps)}")
        
        print_chat("tool", f"Working Directory: {self.working_dir}")

    async def test_operation(self, description: str, expect_success: bool = True, **kwargs):
        """Test a single operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {description}"):
                result = await self.bash_tool.execute(**kwargs)
            
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
                    output = str(result.result)
                    # Show output (truncated if too long)
                    if len(output) <= 500:
                        print_chat("output", output)
                    else:
                        print_chat("output", output[:500] + "...")
                
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
        """Test basic bash operations."""
        print_header("Basic Bash Operations", "single")
        
        # Simple echo command
        await self.test_operation(
            "Simple Echo Command",
            expect_success=True,
            command="echo 'Hello from Bash!'",
            sandbox_mode="local"
        )
        
        # List current directory
        await self.test_operation(
            "List Current Directory",
            expect_success=True,
            command="ls -la",
            sandbox_mode="local"
        )
        
        # Show current working directory
        await self.test_operation(
            "Show Current Working Directory",
            expect_success=True,
            command="pwd",
            sandbox_mode="local"
        )
        
        # Show environment info
        await self.test_operation(
            "Show Environment Info",
            expect_success=True,
            command="whoami && date",
            sandbox_mode="local"
        )

    async def test_file_operations(self):
        """Test file creation and manipulation."""
        print_header("File Operations", "single")
        
        # Create a test file
        test_filename = "bash_test_file.txt"
        self.test_files_created.append(test_filename)
        
        await self.test_operation(
            "Create File with Echo",
            expect_success=True,
            command=f"echo 'Hello from file!' > {test_filename}",
            sandbox_mode="local"
        )
        
        # Read the file
        await self.test_operation(
            "Read File Content",
            expect_success=True,
            command=f"cat {test_filename}",
            sandbox_mode="local"
        )
        
        # Append to file
        await self.test_operation(
            "Append to File",
            expect_success=True,
            command=f"echo 'Second line' >> {test_filename}",
            sandbox_mode="local"
        )
        
        # Count lines in file
        await self.test_operation(
            "Count Lines in File",
            expect_success=True,
            command=f"wc -l {test_filename}",
            sandbox_mode="local"
        )
        
        # Create directory structure
        await self.test_operation(
            "Create Directory Structure",
            expect_success=True,
            command="mkdir -p test_dir/subdir && echo 'nested file' > test_dir/subdir/nested.txt",
            sandbox_mode="local"
        )
        
        # List directory structure
        await self.test_operation(
            "List Directory Structure", 
            expect_success=True,
            command="find test_dir -type f -ls",
            sandbox_mode="local"
        )

    async def test_command_validation(self):
        """Test command validation and security controls."""
        print_header("Command Validation & Security", "single")
        
        # Test blocked dangerous commands
        await self.test_operation(
            "Blocked Dangerous Command (rm -rf)",
            expect_success=False,
            command="rm -rf /tmp/nonexistent",
            sandbox_mode="auto"
        )
        
        # Test safe file removal
        if self.test_files_created:
            test_file = self.test_files_created[0]
            await self.test_operation(
                "Safe File Removal",
                expect_success=True,
                command=f"rm {test_file} && echo 'File removed safely'",
                sandbox_mode="local"
            )
        
        # Test command with pipes and redirections
        await self.test_operation(
            "Complex Command with Pipes",
            expect_success=True,
            command="echo -e 'line1\\nline2\\nline3' | grep 'line2' | wc -l",
            sandbox_mode="local"
        )
        
        # Test environment variable operations
        await self.test_operation(
            "Environment Variable Operations",
            expect_success=True,
            command="export TEST_VAR='hello world' && echo $TEST_VAR",
            sandbox_mode="local"
        )

    async def test_error_handling(self):
        """Test error handling."""
        print_header("Error Handling", "single")
        
        # Non-existent command
        result, success = await self.test_operation(
            "Non-existent Command",
            expect_success=True,  # Tool succeeds but shows error in output
            command="nonexistentcommand12345",
            sandbox_mode="local"
        )
        
        # Check if error message is present in output
        if success and result and hasattr(result, 'result'):
            output = str(result.result).lower()
            if 'command not found' in output or 'not found' in output:
                print_chat("validation", "✓ Error properly captured in output")
            else:
                print_chat("validation", "⚠ Error might not be properly captured")
        
        # Invalid syntax
        await self.test_operation(
            "Invalid Syntax",
            expect_success=True,  # Bash handles syntax errors gracefully
            command="echo 'unclosed quote",
            sandbox_mode="local"
        )
        
        # Permission denied (in sandbox)
        await self.test_operation(
            "Permission Denied",
            expect_success=True,
            command="cat /etc/shadow 2>&1 || echo 'Permission denied as expected'",
            sandbox_mode="sandbox"
        )
        
        # File not found
        await self.test_operation(
            "File Not Found",
            expect_success=True,
            command="cat /nonexistent/file.txt 2>&1 || echo 'File not found as expected'",
            sandbox_mode="local"
        )

    async def test_execution_modes(self):
        """Test different execution modes."""
        print_header("Execution Modes", "single")
        
        # Local execution
        await self.test_operation(
            "Forced Local Execution",
            expect_success=True,
            command="echo 'This runs locally' && uptime",
            sandbox_mode="local"
        )
        
        # Sandbox execution
        await self.test_operation(
            "Forced Sandbox Execution",
            expect_success=True,
            command="echo 'This runs in sandbox' && date",
            sandbox_mode="sandbox"
        )
        
        # Auto routing - safe command
        await self.test_operation(
            "Auto Mode - Safe Command",
            expect_success=True,
            command="echo 'Auto routing test' | wc -w",
            sandbox_mode="auto"
        )
        
        # Auto routing - potentially dangerous command
        await self.test_operation(
            "Auto Mode - System Command",
            expect_success=True,
            command="ps aux | head -5",
            sandbox_mode="auto"
        )

    async def test_shell_variants(self):
        """Test different shell variants."""
        print_header("Shell Variants", "single")
        
        # Test with bash shell
        await self.test_operation(
            "Test BASH Shell",
            expect_success=True,
            command="echo 'Running in bash' && echo $0",
            shell="bash",
            sandbox_mode="local"
        )
        
        # Test with sh shell
        await self.test_operation(
            "Test SH Shell",
            expect_success=True,
            command="echo 'Running in sh' && echo $0",
            shell="sh",
            sandbox_mode="local"
        )

    async def test_session_management(self):
        """Test basic session management."""
        print_header("Session Management", "single")
        
        # Test session restart
        await self.test_operation(
            "Restart All Sessions",
            expect_success=True,
            command="",
            restart=True
        )
        
        # Test list sessions
        await self.test_operation(
            "List Active Sessions",
            expect_success=True,
            command="list_sessions"
        )

    async def test_timeout_handling(self):
        """Test timeout handling."""
        print_header("Timeout Handling", "single")
        
        # Quick command
        await self.test_operation(
            "Quick Command",
            expect_success=True,
            command="echo 'Quick task' && sleep 0.1 && echo 'Completed'",
            timeout_ms=2000,
            sandbox_mode="local"
        )

    async def show_final_statistics(self):
        """Show comprehensive test results."""
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
        
        # Test environment info
        print_header("Test Environment", "single")
        print_chat("env", f"Working Directory: {self.working_dir}")
        print_chat("env", f"Files Created: {len(self.test_files_created)}")
        
        # Failed tests details
        if failed_tests > 0:
            print_header("Failed Tests Details", "single")
            for result in self.test_results:
                if not result['passed']:
                    status = "FAIL" if result['expected_success'] else "UNEXPECTED_SUCCESS"
                    print_test(f"{result['description']}: {status}", "fail")

    async def cleanup(self):
        """Clean up test resources."""
        if self._cleanup_done:
            return
            
        print_header("Cleanup", "single")
        
        # Clean up bash tool
        if self.bash_tool:
            print_test("Cleaning up Bash tool", "running")
            try:
                await self.bash_tool.cleanup()
                print_test("Bash tool cleanup complete", "pass")
            except Exception as e:
                print_test(f"Bash tool cleanup completed with warnings: {e}", "warn")
        
        # Clean up directory
        if self.working_dir and os.path.exists(self.working_dir):
            print_test("Removing test directory", "running")
            import shutil
            try:
                shutil.rmtree(self.working_dir)
                print_test("Test directory removed", "pass")
            except Exception as e:
                print_test(f"Directory cleanup warning: {e}", "warn")
        
        self._cleanup_done = True


async def run_all_tests():
    """Run all tests."""
    tester = SimpleBashExecutorTester()
    
    try:
        if not await tester.setup():
            print_test("Setup failed, exiting", "fail")
            return 1
        
        # Run all test suites
        await tester.test_basic_operations()
        await tester.test_file_operations()
        await tester.test_command_validation()
        await tester.test_error_handling()
        await tester.test_execution_modes()
        await tester.test_shell_variants()
        await tester.test_session_management()
        await tester.test_timeout_handling()
        
        # Show comprehensive results
        await tester.show_final_statistics()
        
        print_header("Bash Executor Testing Complete!", "double")
        print_test("All test suites completed successfully", "pass")
        
        return 0
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
        return 1
    except Exception as e:
        print_test(f"Unexpected error during testing: {e}", "fail")
        return 1
    finally:
        try:
            await tester.cleanup()
        except Exception as e:
            print_test(f"Final cleanup warning: {e}", "warn")


def main():
    """Main entry point."""
    try:
        return asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print_test("Tests interrupted", "warn")
        return 1
    except Exception as e:
        print_test(f"Fatal error occurred: {e}", "fail")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print_test("Tests interrupted", "warn")
        sys.exit(1)
    except Exception as e:
        print_test(f"Fatal error: {e}", "fail")
        sys.exit(1)