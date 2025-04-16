"""
Example usage of the Docker sandbox for Enterprise AI.

This example demonstrates:
1. Creating a sandbox environment
2. Running Python code in the sandbox
3. File operations (reading/writing)
4. Cleanup
"""

import asyncio
import os
import tempfile
from typing import Dict

from enterprise_ai.config.sandbox import SandboxSettings
from enterprise_ai.sandbox.client import LocalSandboxClient
from enterprise_ai.sandbox.core.exceptions import SandboxTimeoutError


async def run_sample_code(client: LocalSandboxClient) -> None:
    """Run a sample Python code in the sandbox."""

    # Write a simple Python script to the sandbox
    python_code = """
import sys
import os
import platform
import math

# Print system info
print(f"Python version: {sys.version}")
print(f"Platform: {platform.platform()}")

# Perform some calculations
result = sum(math.factorial(n) for n in range(10))
print(f"Sum of factorials 0-9: {result}")

# Create a file
with open('output.txt', 'w') as f:
    f.write(f"Hello from sandbox! Result: {result}")

print("Script completed successfully!")
"""

    await client.write_file("script.py", python_code)
    print("\n--- Sandbox File Written ---")

    # Execute the Python script
    try:
        result = await client.run_command("python script.py", timeout=10)
        print("\n--- Execution Result ---")
        print(result)
    except SandboxTimeoutError:
        print("\n--- Execution timed out ---")

    # Read the generated file
    try:
        file_content = await client.read_file("output.txt")
        print("\n--- Generated File Content ---")
        print(file_content)
    except FileNotFoundError:
        print("\n--- Output file not found ---")


async def demonstrate_file_operations(client: LocalSandboxClient) -> None:
    """Demonstrate file operations between host and container."""

    # Create a temporary file on the host
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp:
        temp.write("This is a test file from the host system.\n")
        temp.write("It will be copied to the container.\n")
        host_file_path = temp.name

    # Copy the file to the container
    await client.copy_to(host_file_path, "host_file.txt")

    # Verify the file exists and read it
    file_content = await client.read_file("host_file.txt")
    print("\n--- Host File in Container ---")
    print(file_content)

    # Clean up the temporary file
    os.unlink(host_file_path)

    # Create a file in the container and copy it to the host
    await client.write_file("container_file.txt", "This file was created in the container.\n")

    # Create a temporary directory to copy to
    with tempfile.TemporaryDirectory() as temp_dir:
        host_output_path = os.path.join(temp_dir, "output.txt")

        # Copy the file from container to host
        await client.copy_from("container_file.txt", host_output_path)

        # Read the copied file
        with open(host_output_path, 'r') as f:
            print("\n--- Container File Copied to Host ---")
            print(f.read())


async def test_network_access(client: LocalSandboxClient, network_enabled: bool) -> None:
    """Test network access based on sandbox configuration."""

    print(f"\n--- Testing Network Access (enabled={network_enabled}) ---")

    # Try to access an external URL
    result = await client.run_command("curl -s -m 5 https://example.com || echo 'Network access failed'", timeout=10)

    if "Network access failed" in result:
        print("Network access is blocked (as expected with network_enabled=False)")
    else:
        print("Network access is working (as expected with network_enabled=True)")


async def main() -> None:
    """Main function demonstrating sandbox usage."""

    print("==== Enterprise AI Docker Sandbox Example ====\n")

    # Create sandbox settings
    settings = SandboxSettings(
        image="python:3.9-slim",
        work_dir="/workspace",
        memory_limit="256m",
        cpu_limit=0.5,
        timeout=60,
        network_enabled=False  # Disable network access for security
    )

    # Initialize the sandbox client
    client = LocalSandboxClient()

    try:
        # Create the sandbox
        print("Creating sandbox environment...")
        await client.create(config=settings)

        # Install additional packages
        print("\nInstalling curl for network testing...")
        await client.run_command("apt-get update && apt-get install -y curl", timeout=60)

        # Run sample code in the sandbox
        await run_sample_code(client)

        # Demonstrate file operations
        await demonstrate_file_operations(client)

        # Test network access with current settings
        await test_network_access(client, settings.network_enabled)

        print("\n--- Sandbox Example Completed Successfully ---")

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        # Always clean up resources
        print("\nCleaning up sandbox resources...")
        await client.cleanup()
        print("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
