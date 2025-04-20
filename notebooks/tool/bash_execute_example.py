#!/usr/bin/env python
"""
Enterprise AI Bash Execution Examples

This script demonstrates shell command execution with a simplified Bash utility:
- Basic command execution
- File operations
- Background processes
- Error handling
"""

import asyncio
import subprocess
import uuid
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
from enterprise_ai.tool.core.result import CLIResult


# Simple Bash executor utility included directly in this file
class SimpleBash:
    """A simple, reliable bash execution utility."""
    
    def __init__(self) -> None:
        """Initialize the simple bash executor."""
        pass
        
    async def execute(self, command: str, timeout: int = 10) -> CLIResult:
        """
        Execute a bash command asynchronously.
        
        Args:
            command: The bash command to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            CLIResult with command output or error
        """
        try:
            # Use asyncio.create_subprocess_shell to run the command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for the command to complete with timeout
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                
                # Decode the output
                stdout_str = stdout.decode().strip() if stdout else ""
                stderr_str = stderr.decode().strip() if stderr else ""
                
                # Create the result
                if process.returncode == 0:
                    return CLIResult(output=stdout_str)
                else:
                    return CLIResult(error=stderr_str, output=stdout_str)
                    
            except asyncio.TimeoutError:
                # Try to terminate the process
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    process.kill()
                
                return CLIResult(error=f"Command execution timed out after {timeout} seconds")
                
        except Exception as e:
            return CLIResult(error=f"Error executing command: {str(e)}")


async def bash_basic_example() -> None:
    """Example of basic Bash command execution."""
    print_section("Basic Bash Command Execution")
    
    # Create the SimpleBash utility
    bash = SimpleBash()
    
    try:
        # Execute a simple command
        print_info("Running 'ls -l /tmp'...")
        async with AsyncTimer("Simple command"):
            result = await bash.execute(command="ls -l /tmp")
        
        if isinstance(result, CLIResult):
            # Only show first 5 lines to avoid cluttering output
            output_lines = result.output.split("\n")
            for line in output_lines[:5]:
                print(line)
            if len(output_lines) > 5:
                print("... (output truncated)")
        else:
            print_error(f"Unexpected result type: {type(result)}")
        
        # Current working directory - simple command
        print_info("\nChecking current working directory...")
        async with AsyncTimer("pwd command"):
            result = await bash.execute(command="pwd")
        
        if isinstance(result, CLIResult):
            print(result.output)
        
        # Simple echo command
        print_info("\nRunning echo command...")
        async with AsyncTimer("echo command"):
            result = await bash.execute(command="echo 'Hello from Bash'")
        
        if isinstance(result, CLIResult):
            print(result.output)
            
    except Exception as e:
        print_error(f"Error in basic bash example: {e}")


async def bash_file_operations_example() -> None:
    """Example of file operations with Bash."""
    print_section("Bash File Operations")
    
    # Create the SimpleBash utility
    bash = SimpleBash()
    
    # Use UUID for truly unique filename
    unique_id = uuid.uuid4().hex
    test_file = f"/tmp/test_bash_{unique_id}.txt"
    
    try:
        # Create a file - simple command
        print_info(f"Creating a test file at {test_file}")
        async with AsyncTimer("File creation"):
            result = await bash.execute(command=f"echo 'This is a test file created by the Bash utility' > {test_file}")
        
        if isinstance(result, CLIResult) and not result.error:
            print_success("File created successfully")
        else:
            print_error(f"File creation failed: {result.error if isinstance(result, CLIResult) else 'Unknown error'}")
            return
        
        # View the file contents
        print_info("\nViewing file contents with cat...")
        async with AsyncTimer("cat command"):
            result = await bash.execute(command=f"cat {test_file}")
        
        if isinstance(result, CLIResult):
            print(result.output)
        
        # Clean up the file - simple command
        print_info("\nCleaning up...")
        async with AsyncTimer("rm command"):
            result = await bash.execute(command=f"rm -f {test_file}")
        
        if isinstance(result, CLIResult) and not result.error:
            print_success("Cleanup completed successfully")
            
    except Exception as e:
        print_error(f"Error in bash file operations example: {e}")


async def bash_background_process_example() -> None:
    """Example of working with background processes in Bash."""
    print_section("Bash Background Processes")
    
    # Create the SimpleBash utility
    bash = SimpleBash()
    
    # Use UUID for truly unique filenames
    unique_id = uuid.uuid4().hex
    output_file = f"/tmp/bg_output_{unique_id}.txt"
    
    try:
        # Create a simple file to demonstrate background processing
        print_info(f"Creating a demonstration file for background processes...")
        async with AsyncTimer("File creation"):
            # Create a simple file
            result = await bash.execute(command=f"echo 'This demonstrates background processing' > {output_file}")
        
        if isinstance(result, CLIResult) and not result.error:
            print_success(f"File created at {output_file}")
        else:
            print_error("Failed to create the demonstration file")
            return
            
        # Check the output file
        print_info("\nChecking the output file...")
        async with AsyncTimer("cat command"):
            result = await bash.execute(command=f"cat {output_file}")
        
        if isinstance(result, CLIResult):
            print(result.output)
            
        # Explain how to run background processes
        print_info("\nTo run a command in the background, append '&':")
        print("command &")
        print("\nTo redirect output and run in the background:")
        print("command > output.log 2>&1 &")
        
        # Clean up
        print_info("\nCleaning up...")
        async with AsyncTimer("rm command"):
            result = await bash.execute(command=f"rm -f {output_file}")
        
        if isinstance(result, CLIResult) and not result.error:
            print_success("Cleanup completed successfully")
            
    except Exception as e:
        print_error(f"Error in bash background process example: {e}")


async def bash_error_handling_example() -> None:
    """Example of handling errors in Bash commands."""
    print_section("Bash Error Handling")
    
    # Create the SimpleBash utility
    bash = SimpleBash()
    
    try:
        # Command that will fail - file not found
        print_info("Running command with non-existent file...")
        async with AsyncTimer("cat non-existent file"):
            result = await bash.execute(command="cat /nonexistent_file.txt")
        
        if isinstance(result, CLIResult):
            if result.error:
                print_error(f"Expected error occurred: {result.error}")
            else:
                print_warning("Command unexpectedly succeeded")
                print(result.output)
                
        # Handling errors with || operator
        print_info("\nHandling errors with || operator...")
        async with AsyncTimer("error handling"):
            result = await bash.execute(
                command="cat /nonexistent_file.txt || echo 'File not found, using default'"
            )
        
        if isinstance(result, CLIResult):
            print(result.output)
        
        # Simple example of successful command
        print_info("\nRunning a successful command...")
        async with AsyncTimer("successful command"):
            result = await bash.execute(command="echo 'This command works'")
        
        if isinstance(result, CLIResult):
            print(result.output)
            
    except Exception as e:
        print_error(f"Error in bash error handling example: {e}")


async def run_examples() -> None:
    """Run all Bash execution examples."""
    try:
        print_info("Running Bash examples with custom Bash utility")
        await bash_basic_example()
        separator()

        await bash_file_operations_example()
        separator()

        await bash_background_process_example()
        separator()

        await bash_error_handling_example()

    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main entry point for Bash execution examples."""
    print_title("Enterprise AI Bash Execution Examples")

    try:
        # Run all examples asynchronously
        run_async(run_examples())

        print_success("All Bash execution examples completed!")
    except Exception as e:
        print_error(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()