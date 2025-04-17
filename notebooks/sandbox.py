#!/usr/bin/env python
"""
Enterprise AI Sandbox Examples

This notebook demonstrates working with the Docker sandbox for:
- Creating and managing secure execution environments
- Running code safely in isolated containers
- Managing file operations between host and container
- Testing network access controls
- Error handling for sandbox operations
"""

import os
import sys
import asyncio
import tempfile
from typing import Dict, Optional, Any

# Import common utilities
from utils import (
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
from enterprise_ai.config.sandbox import SandboxSettings
from enterprise_ai.sandbox.client import LocalSandboxClient
from enterprise_ai.sandbox.core.exceptions import SandboxTimeoutError, SandboxError

# Sandbox configuration
DEFAULT_CONFIG = SandboxSettings(
    image="python:3.9-slim",
    work_dir="/workspace",
    memory_limit="256m",
    cpu_limit=0.5,
    timeout=60,
    network_enabled=False  # Default: no network access
)

async def create_sandbox(config: Optional[SandboxSettings] = None) -> LocalSandboxClient:
    """Create and initialize a sandbox environment."""
    print_section("Creating Sandbox Environment")
    
    # Use default config if none provided
    config = config or DEFAULT_CONFIG
    
    # Print configuration
    print_info("Sandbox Configuration:")
    print(f"- Image: {config.image}")
    print(f"- Working Directory: {config.work_dir}")
    print(f"- Memory Limit: {config.memory_limit}")
    print(f"- CPU Limit: {config.cpu_limit}")
    print(f"- Timeout: {config.timeout} seconds")
    print(f"- Network Access: {'Enabled' if config.network_enabled else 'Disabled'}")
    
    # Initialize the sandbox client
    client = LocalSandboxClient()
    
    # Create the sandbox
    print_info("\nCreating and starting sandbox container...")
    async with AsyncTimer("Sandbox creation"):
        await client.create(config=config)
    
    print_success("Sandbox created successfully!")
    
    # Install basic utilities
    print_info("\nInstalling essential packages...")
    try:
        await client.run_command("apt-get update && apt-get install -y curl wget nano jq", timeout=120)
        print_success("Packages installed successfully!")
    except Exception as e:
        print_warning(f"Package installation encountered an issue: {e}")
        print_info("Continuing with basic sandbox...")
    
    return client

async def run_python_code(client: LocalSandboxClient) -> None:
    """Run Python code in the sandbox."""
    print_section("Running Python Code")
    
    # Write a Python script to analyze
    code = """
#!/usr/bin/env python3
import sys
import os
import platform
import math
import time
from datetime import datetime

# Print environment information
print("=== Environment Information ===")
print(f"Python version: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"Current directory: {os.getcwd()}")
print(f"User: {os.getenv('USER')}")
print(f"Current time: {datetime.now()}")
print()

# Perform some calculations
print("=== Sample Calculations ===")
print(f"Factorial of 10: {math.factorial(10)}")
print(f"Pi squared: {math.pi ** 2}")
print(f"Euler's number: {math.e}")
print(f"Square root of 2: {math.sqrt(2)}")
print()

# Create some files
print("=== Creating Files ===")
with open('output.txt', 'w') as f:
    f.write(f"Hello from sandbox! Generated at {datetime.now()}\\n")
    f.write(f"Python version: {sys.version}\\n")
    f.write(f"Result of calculation: {sum(math.factorial(i) for i in range(10))}\\n")
print("Created output.txt")

# Create a directory structure
os.makedirs('data/processed', exist_ok=True)
with open('data/processed/results.txt', 'w') as f:
    f.write("Sample results file\\n")
print("Created directory structure with files")

print("\\nScript execution completed successfully!")
"""
    
    # Write the script to the sandbox
    print_info("Writing Python script to sandbox...")
    await client.write_file("analysis.py", code)
    
    # Make it executable
    await client.run_command("chmod +x analysis.py")
    
    # Execute the script
    print_info("\nExecuting Python script...")
    try:
        async with AsyncTimer("Script execution"):
            result = await client.run_command("python analysis.py", timeout=30)
        
        print_success("Script executed successfully!")
        print("\nScript Output:")
        print("-" * 40)
        print(result)
        print("-" * 40)
    except SandboxTimeoutError:
        print_error("Script execution timed out!")
    except Exception as e:
        print_error(f"Error executing script: {e}")
    
    # Read the generated file
    try:
        file_content = await client.read_file("output.txt")
        print("\nContents of output.txt:")
        print("-" * 40)
        print(file_content)
        print("-" * 40)
    except Exception as e:
        print_error(f"Failed to read output file: {e}")

async def test_file_operations(client: LocalSandboxClient) -> None:
    """Test file operations between host and container."""
    print_section("File Operations")
    
    # Create a temporary file on the host
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
        temp.write("This is a test file created on the host system.\n")
        temp.write("It will be copied to the container.\n")
        temp.write(f"Created at: {os.path.getmtime(temp.name)}\n")
        host_file_path = temp.name
    
    print_info(f"Created temporary file on host: {host_file_path}")
    
    # Copy file to container
    container_path = "host_file.txt"
    print_info(f"Copying file to container as {container_path}...")
    
    try:
        await client.copy_to(host_file_path, container_path)
        print_success("File copied to container!")
        
        # Verify file exists in container
        file_content = await client.read_file(container_path)
        print("\nFile content in container:")
        print("-" * 40)
        print(file_content)
        print("-" * 40)
    except Exception as e:
        print_error(f"Failed to copy file to container: {e}")
    
    # Create a file in the container and copy it back
    container_file = "container_file.txt"
    container_content = """This file was created inside the container.
It contains some sample data that will be copied back to the host.
Container environment information:
- Created at: $(date)
- Hostname: $(hostname)
- User: $(whoami)
"""
    
    try:
        # Create file in container using shell command (with dynamic content)
        await client.run_command(f'echo "{container_content}" | envsubst > {container_file}')
        print_info(f"Created file in container: {container_file}")
        
        # Create temporary directory for output
        with tempfile.TemporaryDirectory() as temp_dir:
            host_output_path = os.path.join(temp_dir, "output.txt")
            
            # Copy from container to host
            print_info(f"Copying file from container to host: {host_output_path}")
            await client.copy_from(container_file, host_output_path)
            
            # Read the copied file
            with open(host_output_path, 'r') as f:
                print("\nFile copied from container:")
                print("-" * 40)
                print(f.read())
                print("-" * 40)
            
            print_success("File operations completed successfully!")
    except Exception as e:
        print_error(f"File operation failed: {e}")

async def test_network_access(client: LocalSandboxClient, network_enabled: bool) -> None:
    """Test network access based on sandbox configuration."""
    print_section(f"Testing Network Access (enabled={network_enabled})")
    
    # Try to access external website
    cmd = "curl -s -m 5 https://example.com -o /dev/null -w '%{http_code}' || echo 'Failed'"
    
    print_info("Testing network connectivity to example.com...")
    result = await client.run_command(cmd, timeout=10)
    
    if result == "Failed" or "Failed" in result:
        print_info("Network access is blocked (no connection to external site)")
        if network_enabled:
            print_warning("Network access should be enabled but appears to be blocked")
        else:
            print_success("Network is correctly blocked as configured")
    else:
        print_info(f"Network access successful, received status code: {result}")
        if network_enabled:
            print_success("Network access is correctly enabled as configured")
        else:
            print_warning("Network should be blocked but appears to be accessible")

async def test_resource_limits(client: LocalSandboxClient) -> None:
    """Test resource limits in the sandbox."""
    print_section("Testing Resource Limits")
    
    # Create a script that uses memory
    memory_script = """
import numpy as np
import time
import sys

# Report memory usage
def report_memory(arrays):
    total_mb = sum(arr.nbytes for arr in arrays) / (1024 * 1024)
    print(f"Currently using approximately {total_mb:.1f} MB of memory")
    sys.stdout.flush()

# Try to allocate memory in chunks until we hit the limit
arrays = []
chunk_size_mb = 10  # Allocate in 10MB chunks
max_attempts = 30   # Don't try more than this many times

print("Starting memory allocation test...")
print(f"Will attempt to allocate memory in {chunk_size_mb}MB chunks")

try:
    for i in range(max_attempts):
        # Allocate memory chunk
        arr = np.ones((chunk_size_mb * 1024 * 1024 // 8), dtype=np.float64)
        arrays.append(arr)
        
        # Touch the memory to ensure it's allocated
        arr[0] = i
        
        # Report current memory usage
        report_memory(arrays)
        
        # Short pause to allow for output
        time.sleep(0.1)
    
    print(f"Test completed without hitting memory limits after allocating {chunk_size_mb * len(arrays)} MB")
    
except MemoryError:
    print(f"Memory limit reached after allocating approximately {chunk_size_mb * len(arrays)} MB")
except Exception as e:
    print(f"Test failed with error: {type(e).__name__}: {e}")
finally:
    # Clean up
    print("Cleaning up allocated memory...")
    arrays = None
    
print("Memory test completed")
"""
    
    # First install numpy
    print_info("Installing numpy for memory test...")
    try:
        await client.run_command("pip install numpy --no-cache-dir", timeout=120)
        print_success("NumPy installed successfully")
    except Exception as e:
        print_error(f"Failed to install NumPy: {e}")
        print_warning("Skipping memory test")
        return
    
    # Write the script
    await client.write_file("memory_test.py", memory_script)
    
    # Run the memory test
    print_info("\nRunning memory test...")
    try:
        result = await client.run_command("python memory_test.py", timeout=60)
        print("\nMemory test results:")
        print("-" * 40)
        print(result)
        print("-" * 40)
    except SandboxTimeoutError:
        print_warning("Memory test timed out - this might be expected if memory limit was reached")
    except Exception as e:
        print_error(f"Memory test failed: {e}")

async def test_error_handling(client: LocalSandboxClient) -> None:
    """Test error handling in the sandbox."""
    print_section("Error Handling Test")
    
    # Test timeout error
    print_info("Testing command timeout...")
    try:
        await client.run_command("sleep 30", timeout=5)
        print_error("Timeout test failed: Command should have timed out")
    except SandboxTimeoutError:
        print_success("Timeout correctly triggered")
    except Exception as e:
        print_error(f"Unexpected error during timeout test: {type(e).__name__}: {e}")
    
    # Test file not found
    print_info("\nTesting file not found error...")
    try:
        await client.read_file("non_existent_file.txt")
        print_error("File not found test failed: Should have raised an error")
    except FileNotFoundError:
        print_success("File not found error correctly triggered")
    except Exception as e:
        print_error(f"Unexpected error type: {type(e).__name__}: {e}")
    
    # Test invalid command
    print_info("\nTesting invalid command...")
    try:
        result = await client.run_command("non_existent_command", timeout=5)
        if "not found" in result.lower() or "command not found" in result.lower():
            print_success("Invalid command correctly returned error message")
        else:
            print_warning(f"Unexpected result from invalid command: {result}")
    except Exception as e:
        print_error(f"Unexpected error during invalid command test: {type(e).__name__}: {e}")

async def run_examples() -> None:
    """Run all sandbox examples."""
    # Create a sandbox with default settings (no network)
    client = await create_sandbox()
    
    try:
        # Run Python code example
        await run_python_code(client)
        separator()
        
        # Test file operations
        await test_file_operations(client)
        separator()
        
        # Test network access (should be blocked with default settings)
        await test_network_access(client, False)
        separator()
        
        # Test resource limits
        await test_resource_limits(client)
        separator()
        
        # Test error handling
        await test_error_handling(client)
        
    except Exception as e:
        print_error(f"Error during examples: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up sandbox resources
        print_section("Cleaning Up")
        print_info("Destroying sandbox container...")
        await client.cleanup()
        print_success("Sandbox resources cleaned up successfully")
    
    # Test with network enabled
    print_section("Creating Sandbox with Network Enabled")
    network_config = SandboxSettings(
        image="python:3.9-slim",
        work_dir="/workspace",
        memory_limit="256m",
        cpu_limit=0.5,
        timeout=60,
        network_enabled=True  # Enable network access
    )
    
    try:
        network_client = await create_sandbox(network_config)
        
        # Test network access (should be enabled)
        await test_network_access(network_client, True)
        
        # Clean up network sandbox
        print_info("\nCleaning up network-enabled sandbox...")
        await network_client.cleanup()
        print_success("Network-enabled sandbox cleaned up")
    except Exception as e:
        print_error(f"Error during network sandbox test: {e}")

def main():
    """Main entry point for sandbox examples."""
    print_title("Enterprise AI Sandbox Examples")
    
    try:
        # Run all examples asynchronously
        run_async(run_examples())
        
        print_success("All sandbox examples completed!")
    except Exception as e:
        print_error(f"Error running sandbox examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()