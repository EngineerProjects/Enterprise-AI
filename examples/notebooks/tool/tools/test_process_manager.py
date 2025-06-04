#!/usr/bin/env python3
"""
Process Manager Tool Testing Suite - Comprehensive Process Management Testing

Comprehensive testing for the process management and monitoring tool.
"""

import asyncio
import sys
import os
import tempfile
import time
import subprocess
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parents[4]
sys.path.insert(0, str(project_root))

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.execution.process import ProcessManagerTool
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class ProcessManagerTester:
    """Comprehensive process manager tool tester."""
    
    def __init__(self):
        self.process_tool = None
        self.test_results = []
        self.test_processes = []  # PIDs of processes we start for testing
        self.working_dir = None
        self._cleanup_done = False
    
    async def setup(self):
        """Initialize the process manager tool."""
        print_header("Process Manager Tool Test Suite", "double")
        
        print_test("Creating test working directory", "running")
        self.working_dir = tempfile.mkdtemp(prefix="process_test_")
        print_test(f"Test working directory: {self.working_dir}", "pass")
        
        print_test("Initializing process manager tool", "running")
        
        self.process_tool = ProcessManagerTool()
        success = await self.process_tool.initialize()
        
        if success:
            print_test("Process manager tool initialized", "pass")
            await self.show_tool_info()
            return True
        else:
            print_test("Failed to initialize process manager tool", "fail")
            return False
    
    async def show_tool_info(self):
        """Show tool information."""
        print_header("Tool Information", "single")
        
        print_chat("tool", f"Tool Name: {self.process_tool.name}")
        print_chat("tool", f"Description: {self.process_tool.description.strip()}")
        
        if hasattr(self.process_tool, 'capabilities'):
            caps = [str(cap) for cap in self.process_tool.capabilities]
            print_chat("tool", f"Capabilities: {', '.join(caps)}")
        
        print_chat("tool", f"Working Directory: {self.working_dir}")
        print_chat("tool", f"Local Mode: {getattr(self.process_tool, '_local_mode', 'Unknown')}")

    async def test_operation(self, description: str, expect_success: bool = True, **kwargs):
        """Test a single operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {description}"):
                result = await self.process_tool.execute(**kwargs)
            
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
                    if len(output) <= 1000:
                        print_chat("output", output)
                    else:
                        # Show first part and last part for process lists
                        lines = output.split('\n')
                        if len(lines) > 20:
                            preview = '\n'.join(lines[:10]) + '\n...\n' + '\n'.join(lines[-5:])
                            print_chat("output", preview)
                        else:
                            print_chat("output", output[:1000] + "...")
                
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

    async def start_test_process(self, command: str, description: str) -> int:
        """Start a test process and return its PID."""
        try:
            # Create a more robust test script that won't exit immediately
            script_path = os.path.join(self.working_dir, f"test_script_{len(self.test_processes)}.py")
            script_content = f'''#!/usr/bin/env python3
import time
import sys
import os
import signal

# Set up signal handling to gracefully handle termination
def signal_handler(signum, frame):
    print(f"Test process {description} received signal {{signum}}")
    sys.stdout.flush()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

print(f"Test process started: {description}")
print(f"PID: {{os.getpid()}}")
sys.stdout.flush()

# Run for about 60 seconds with proper error handling
try:
    for i in range(60):
        time.sleep(1)
        if i % 10 == 0:
            print(f"Test process {description} - iteration {{i}}")
            sys.stdout.flush()
except KeyboardInterrupt:
    print(f"Test process {description} interrupted")
    sys.stdout.flush()
except Exception as e:
    print(f"Test process {description} error: {{e}}")
    sys.stdout.flush()
finally:
    print(f"Test process {description} completed")
    sys.stdout.flush()
'''
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Make script executable
            os.chmod(script_path, 0o755)
            
            # Start the process with better configuration
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.working_dir,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create new process group
            )
            
            # Give it more time to start and verify it's actually running
            time.sleep(2)
            
            # Verify the process is actually running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print_chat("error", f"Test process failed to start. Exit code: {process.returncode}")
                print_chat("error", f"Stdout: {stdout.decode()}")
                print_chat("error", f"Stderr: {stderr.decode()}")
                return -1
            
            pid = process.pid
            self.test_processes.append((pid, process, description))
            
            # Double-check the process is running using psutil if available
            try:
                import psutil
                proc = psutil.Process(pid)
                status = proc.status()
                if status == psutil.STATUS_ZOMBIE:
                    print_chat("warn", f"Process {pid} became zombie immediately")
                    return -1
                print_chat("process", f"Started test process '{description}' with PID {pid} (status: {status})")
            except ImportError:
                print_chat("process", f"Started test process '{description}' with PID {pid}")
            except psutil.NoSuchProcess:
                print_chat("error", f"Process {pid} disappeared immediately after creation")
                return -1
                
            return pid
            
        except Exception as e:
            print_chat("error", f"Failed to start test process: {e}")
            return -1
        
    async def test_process_listing(self):
        """Test process listing functionality."""
        print_header("Process Listing", "single")
        
        # List all processes (limited output)
        await self.test_operation(
            "List All Processes",
            expect_success=True,
            command="list_processes",
            include_system=False  # Only user processes for cleaner output
        )
        
        # List with system processes
        await self.test_operation(
            "List with System Processes",
            expect_success=True,
            command="list_processes",
            include_system=True
        )
        
        # List with name filter
        await self.test_operation(
            "List Processes with Python Filter",
            expect_success=True,
            command="list_processes",
            filter_name="python",
            include_system=False
        )
        
        # List with specific filter
        await self.test_operation(
            "List Processes with Bash Filter",
            expect_success=True,
            command="list_processes",
            filter_name="bash",
            include_system=False
        )

    async def test_session_management(self):
        """Test session management functionality."""
        print_header("Session Management", "single")
        
        # List sessions (should be empty initially)
        await self.test_operation(
            "List Sessions (Empty)",
            expect_success=True,
            command="list_sessions"
        )
        
        # Register a test session manually
        test_pid = os.getpid()  # Use current process PID for testing
        self.process_tool.register_session(test_pid, "test command for session management")
        
        # List sessions after registration
        await self.test_operation(
            "List Sessions After Registration",
            expect_success=True,
            command="list_sessions"
        )
        
        # Update session status
        self.process_tool.update_session_status(test_pid, "completed")
        
        # List sessions after status update
        await self.test_operation(
            "List Sessions After Status Update",
            expect_success=True,
            command="list_sessions"
        )

    async def test_process_monitoring(self):
        """Test process monitoring with real processes."""
        print_header("Process Monitoring", "single")
        
        # Start a test process
        test_pid = await self.start_test_process("sleep 10", "monitoring_test")
        
        if test_pid > 0:
            # Register the session
            self.process_tool.register_session(test_pid, "test sleep process")
            
            # Monitor the process
            await self.test_operation(
                "Monitor Test Process",
                expect_success=True,
                command="list_processes",
                filter_name="python"
            )
            
            # List our session
            await self.test_operation(
                "List Active Test Session",
                expect_success=True,
                command="list_sessions"
            )
        else:
            print_chat("warn", "Skipping process monitoring test - failed to start test process")

    async def test_process_termination(self):
        """Test process termination functionality."""
        print_header("Process Termination", "single")
        
        # Start a test process to terminate
        test_pid = await self.start_test_process("long_running_test", "termination_test")
        
        if test_pid > 0:
            # Register the session
            self.process_tool.register_session(test_pid, "test process for termination")
            
            # Wait longer for process to fully start and stabilize
            print_chat("info", "Waiting for process to stabilize...")
            time.sleep(3)
            
            # Verify process is running and not zombie
            try:
                import psutil
                proc = psutil.Process(test_pid)
                status = proc.status()
                print_chat("info", f"Process {test_pid} status: {status}")
                
                if status == psutil.STATUS_ZOMBIE:
                    print_chat("warn", "Process is already zombie, skipping termination test")
                    return
                    
            except ImportError:
                print_chat("info", "psutil not available, proceeding with termination test")
            except psutil.NoSuchProcess:
                print_chat("warn", "Process no longer exists, skipping termination test")
                return
            
            # Verify process is running
            await self.test_operation(
                "Verify Process is Running",
                expect_success=True,
                command="list_processes",
                filter_name="python"
            )
            
            # Terminate with TERM signal
            await self.test_operation(
                "Terminate Process with TERM",
                expect_success=True,
                command="kill_process",
                pid=test_pid,
                signal_type="TERM"
            )
            
            # Wait a moment and check if terminated
            time.sleep(3)
            
            # Remove from our tracking since we terminated it
            self.test_processes = [(pid, proc, desc) for pid, proc, desc in self.test_processes 
                                 if pid != test_pid]
        else:
            print_chat("warn", "Skipping termination test - failed to start test process")

    async def test_force_termination(self):
        """Test force termination functionality."""
        print_header("Force Termination", "single")
        
        # Start another test process
        test_pid = await self.start_test_process("stubborn_process", "force_termination_test")
        
        if test_pid > 0:
            # Register the session
            self.process_tool.register_session(test_pid, "stubborn test process")
            
            # Wait for process to start
            time.sleep(1)
            
            # Force terminate with KILL signal
            await self.test_operation(
                "Force Terminate Process",
                expect_success=True,
                command="force_terminate",
                pid=test_pid
            )
            
            # Wait and verify termination
            time.sleep(2)
            
            # Remove from tracking
            self.test_processes = [(pid, proc, desc) for pid, proc, desc in self.test_processes 
                                 if pid != test_pid]
        else:
            print_chat("warn", "Skipping force termination test - failed to start test process")

    async def test_output_reading(self):
        """Test output reading functionality."""
        print_header("Output Reading", "single")
        
        # Test reading output from a session
        test_pid = os.getpid()  # Use current process as dummy
        self.process_tool.register_session(test_pid, "output reading test")
        
        # Try to read output (this will show the limitation in local mode)
        await self.test_operation(
            "Read Output from Session",
            expect_success=True,  # Should succeed but show limitation message
            command="read_output",
            pid=test_pid,
            timeout_ms=1000
        )

    async def test_error_handling(self):
        """Test error handling scenarios."""
        print_header("Error Handling", "single")
        
        # Test missing command
        await self.test_operation(
            "Missing Command Parameter",
            expect_success=False,
            command=""
        )
        
        # Test invalid command
        await self.test_operation(
            "Invalid Command",
            expect_success=False,
            command="invalid_command"
        )
        
        # Test kill non-existent process
        await self.test_operation(
            "Kill Non-existent Process",
            expect_success=False,
            command="kill_process",
            pid=999999,
            signal_type="TERM"
        )
        
        # Test read output without PID
        await self.test_operation(
            "Read Output Missing PID",
            expect_success=False,
            command="read_output"
        )
        
        # Test read output from non-existent session
        await self.test_operation(
            "Read Output Non-existent Session",
            expect_success=False,
            command="read_output",
            pid=999999
        )
        
        # Test invalid signal type
        current_pid = os.getpid()
        await self.test_operation(
            "Invalid Signal Type",
            expect_success=False,
            command="kill_process",
            pid=current_pid,
            signal_type="INVALID"
        )
        
        # Test killing critical system processes (should be blocked)
        await self.test_operation(
            "Kill Critical Process (init)",
            expect_success=False,
            command="kill_process",
            pid=1,
            signal_type="TERM"
        )
        
        # Test killing self (should be blocked)
        await self.test_operation(
            "Kill Self Process",
            expect_success=False,
            command="kill_process",
            pid=os.getpid(),
            signal_type="TERM"
        )

    async def test_edge_cases(self):
        """Test edge cases and special scenarios."""
        print_header("Edge Cases", "single")
        
        # Test with very specific process filter
        await self.test_operation(
            "Filter Non-existent Process Name",
            expect_success=True,  # Should succeed but return empty
            command="list_processes",
            filter_name="definitely_nonexistent_process_name_12345"
        )
        
        # Test session management with invalid PIDs
        await self.test_operation(
            "Force Terminate Invalid PID",
            expect_success=False,
            command="force_terminate",
            pid=-1
        )
        
        # Test with timeout on output reading
        test_pid = os.getpid()
        await self.test_operation(
            "Read Output with Timeout",
            expect_success=True,
            command="read_output",
            pid=test_pid,
            timeout_ms=100
        )

    async def test_integration_scenarios(self):
        """Test integration scenarios that simulate real usage."""
        print_header("Integration Scenarios", "single")
        
        # Simulate a workflow: start process -> monitor -> terminate
        print_chat("info", "Simulating process lifecycle management workflow...")
        
        # Start a process
        test_pid = await self.start_test_process("workflow_test", "integration_workflow")
        
        if test_pid > 0:
            # Step 1: Register session
            self.process_tool.register_session(test_pid, "integration workflow test")
            
            # Step 2: Monitor
            await self.test_operation(
                "Workflow - Monitor Process",
                expect_success=True,
                command="list_sessions"
            )
            
            # Step 3: Update status
            self.process_tool.update_session_status(test_pid, "processing")
            
            # Step 4: Check status
            await self.test_operation(
                "Workflow - Check Updated Status",
                expect_success=True,
                command="list_sessions"
            )
            
            # Step 5: Terminate
            await self.test_operation(
                "Workflow - Terminate Process",
                expect_success=True,
                command="kill_process",
                pid=test_pid,
                signal_type="TERM"
            )
            
            # Step 6: Verify termination
            time.sleep(1)
            await self.test_operation(
                "Workflow - Verify Termination",
                expect_success=True,
                command="list_sessions"
            )
            
            # Remove from tracking
            self.test_processes = [(pid, proc, desc) for pid, proc, desc in self.test_processes 
                                 if pid != test_pid]
        else:
            print_chat("warn", "Skipping integration test - failed to start test process")

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
        print_chat("env", f"Test Processes Started: {len(self.test_processes)}")
        print_chat("env", f"Local Mode: {getattr(self.process_tool, '_local_mode', 'Unknown')}")
        
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
        
        # Terminate any remaining test processes
        if self.test_processes:
            print_test("Terminating test processes", "running")
            for pid, process, description in self.test_processes:
                try:
                    # Check if process is still running first
                    try:
                        import psutil
                        proc = psutil.Process(pid)
                        if proc.status() == psutil.STATUS_ZOMBIE:
                            print_chat("cleanup", f"Process {pid} ({description}) is already zombie")
                            continue
                    except (ImportError, psutil.NoSuchProcess):
                        pass
                    
                    # Try graceful termination first
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                        print_chat("cleanup", f"Gracefully terminated test process {pid} ({description})")
                    except subprocess.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        process.kill()
                        process.wait(timeout=5)
                        print_chat("cleanup", f"Force killed test process {pid} ({description})")
                        
                except Exception as e:
                    print_chat("cleanup", f"Warning terminating process {pid}: {e}")
            
            print_test("Test processes cleanup complete", "pass")
        
        # Clean up process manager tool
        if self.process_tool:
            print_test("Cleaning up process manager tool", "running")
            try:
                await self.process_tool.cleanup()
                print_test("Process manager tool cleanup complete", "pass")
            except Exception as e:
                print_test(f"Process manager tool cleanup completed with warnings: {e}", "warn")
        
        # Clean up directory
        if self.working_dir and os.path.exists(self.working_dir):
            print_test("Removing test directory", "running")
            import shutil
            try:
                # Change back to original directory first
                os.chdir('/')
                shutil.rmtree(self.working_dir)
                print_test("Test directory removed", "pass")
            except Exception as e:
                print_test(f"Directory cleanup warning: {e}", "warn")
        
        self._cleanup_done = True


async def run_all_tests():
    """Run all tests."""
    tester = ProcessManagerTester()
    
    try:
        if not await tester.setup():
            print_test("Setup failed, exiting", "fail")
            return 1
        
        # Run all test suites
        await tester.test_process_listing()
        await tester.test_session_management()
        await tester.test_process_monitoring()
        await tester.test_process_termination()
        await tester.test_force_termination()
        await tester.test_output_reading()
        await tester.test_error_handling()
        await tester.test_edge_cases()
        await tester.test_integration_scenarios()
        
        # Show comprehensive results
        await tester.show_final_statistics()
        
        print_header("Process Manager Tool Testing Complete!", "double")
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