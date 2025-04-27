# Enterprise AI Sandbox Module

## Module Overview

The Sandbox module provides a secure containerized execution environment for running untrusted code within the Enterprise AI platform. It leverages Docker containers to create isolated environments with carefully controlled resource limitations, security boundaries, and execution controls.

Key capabilities of the Sandbox module include:

- Isolated execution of arbitrary code (Python, Bash, etc.)
- Resource limitations (CPU, memory) to prevent resource exhaustion
- Network access controls to restrict external connectivity
- File system isolation with controlled access to host resources
- Secure command execution with timeout controls
- Bidirectional file operations between host and container
- Automatic resource cleanup and management

The Sandbox module is a critical security component that enables agents to execute code, process data, and interact with system resources without compromising the host system. It forms the foundation for secure tool execution, agent capabilities that require code evaluation, and testing or experimentation features throughout the Enterprise AI platform.

## Key Components

### 1. DockerSandbox

The `DockerSandbox` class is the core component that interacts directly with a Docker container. It provides methods for container management, command execution, and file operations.

```python
class DockerSandbox:
    def __init__(self, config: Optional[SandboxSettings] = None,
                 volume_bindings: Optional[Dict[str, str]] = None):
        # Initialize sandbox with configuration and volume mappings

    async def create(self) -> "DockerSandbox":
        # Create and start the container

    async def run_command(self, cmd: str, timeout: Optional[int] = None) -> str:
        # Execute a command with timeout

    async def read_file(self, path: str) -> str:
        # Read file content from the container

    async def write_file(self, path: str, content: str) -> None:
        # Write content to a file in the container

    async def copy_from(self, src_path: str, dst_path: str) -> None:
        # Copy file from container to host

    async def copy_to(self, src_path: str, dst_path: str) -> None:
        # Copy file from host to container

    async def cleanup(self) -> None:
        # Clean up all sandbox resources
```

Key features:

- Asynchronous API for non-blocking operations
- Resource limitation through Docker container settings
- Secure path resolution to prevent path traversal
- Error handling with meaningful exceptions
- Context manager support (`async with`)

### 2. SandboxManager

The `SandboxManager` class manages multiple `DockerSandbox` instances, handling their lifecycle including creation, monitoring, and cleanup.

```python
class SandboxManager:
    def __init__(self, max_sandboxes: int = 10,
                 idle_timeout: int = 1800,
                 cleanup_interval: int = 300):
        # Initialize manager with limits and timeouts

    async def create_sandbox(self, config: Optional[SandboxSettings] = None,
                            volume_bindings: Optional[Dict[str, str]] = None) -> str:
        # Create a new sandbox and return its ID

    async def get_sandbox(self, sandbox_id: str) -> DockerSandbox:
        # Get a sandbox by ID

    async def delete_sandbox(self, sandbox_id: str) -> None:
        # Delete a sandbox by ID

    async def cleanup(self) -> None:
        # Clean up all managed sandboxes

    def get_stats(self) -> Dict:
        # Get manager statistics
```

Key features:

- Concurrent sandbox management
- Automatic cleanup of idle sandboxes
- Resource limiting (maximum number of sandboxes)
- Docker image caching and management
- Metrics and monitoring
- Context manager support (`async with`)

### 3. AsyncDockerizedTerminal

The `AsyncDockerizedTerminal` class provides terminal-like interaction with Docker containers, supporting interactive command execution.

```python
class AsyncDockerizedTerminal:
    def __init__(self, container: Union[str, Container],
                 working_dir: str = "/workspace",
                 env_vars: Optional[Dict[str, str]] = None,
                 default_timeout: int = 60):
        # Initialize terminal with container and configuration

    async def init(self) -> None:
        # Initialize terminal environment

    async def run_command(self, cmd: str, timeout: Optional[int] = None) -> str:
        # Run command with timeout

    async def close(self) -> None:
        # Close terminal session
```

Key features:

- Asynchronous command execution
- Reliable command output parsing
- Timeout handling
- Command sanitization to prevent shell injection
- Environment variable management
- Working directory control

### 4. SandboxClient

The `BaseSandboxClient` abstract class defines the interface for interacting with sandboxes, and `LocalSandboxClient` provides a concrete implementation.

```python
class BaseSandboxClient(ABC):
    @abstractmethod
    async def create(self, config: Optional[SandboxSettings] = None,
                    volume_bindings: Optional[Dict[str, str]] = None) -> None:
        # Create sandbox

    @abstractmethod
    async def run_command(self, command: str, timeout: Optional[int] = None) -> str:
        # Execute command

    # File operation methods
    @abstractmethod
    async def copy_from(self, container_path: str, local_path: str) -> None:
        # Copy from container

    @abstractmethod
    async def copy_to(self, local_path: str, container_path: str) -> None:
        # Copy to container

    @abstractmethod
    async def read_file(self, path: str) -> str:
        # Read file

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        # Write file

    @abstractmethod
    async def cleanup(self) -> None:
        # Clean up resources
```

The `create_sandbox_client()` factory function creates the appropriate client instance:

```python
def create_sandbox_client() -> LocalSandboxClient:
    # Create and return a sandbox client instance
```

### 5. Exception Handling

Custom exceptions for sandbox-specific errors:

```python
class SandboxError(EnterpriseAIError):
    # Base exception for sandbox-related errors

class SandboxTimeoutError(SandboxError):
    # Exception for timeout errors

class SandboxResourceError(SandboxError):
    # Exception for resource-related errors
```

## Architecture Design

The Sandbox module follows several key design principles:

### 1. Layered Architecture

The module uses a layered approach to separate concerns:

1. **Docker API Layer** (lowest): Direct interaction with Docker API
1. **Sandbox Layer**: Docker container abstraction (`DockerSandbox`, `AsyncDockerizedTerminal`)
1. **Management Layer**: Multiple sandbox coordination (`SandboxManager`)
1. **Client Layer** (highest): Simplified interface for consumers (`BaseSandboxClient`, `LocalSandboxClient`)

This separation allows each layer to focus on specific responsibilities while presenting a coherent API to consumers.

### 2. Asynchronous Design

The module uses Python's `asyncio` for non-blocking operations:

```python
async def run_command(self, cmd: str, timeout: Optional[int] = None) -> str:
    # Asynchronous command execution
```

Benefits of this approach:

- Efficient resource usage during long-running operations
- Support for concurrent sandbox operations
- Non-blocking command execution with timeout control
- Simplified cleanup and resource management

### 3. Concurrency Control

The module implements concurrency control mechanisms to prevent race conditions:

```python
# Global lock for manager-wide operations
self._global_lock = asyncio.Lock()

# Per-sandbox locks for sandbox-specific operations
self._locks: Dict[str, asyncio.Lock] = {}

@asynccontextmanager
async def sandbox_operation(self, sandbox_id: str) -> AsyncGenerator[DockerSandbox, None]:
    # Context manager for sandbox operations with locking
```

These mechanisms ensure safe concurrent access to sandboxes.

### 4. Resource Management

The module implements resource management at multiple levels:

- **Container Level**: CPU, memory limits through Docker
- **Manager Level**: Maximum concurrent sandboxes
- **Operation Level**: Command timeout controls
- **Idle Management**: Automatic cleanup of idle resources

### 5. Security Boundaries

Security is implemented through multiple layers:

- Docker container isolation
- Network access controls (disabled by default)
- Command sanitization to prevent shell injection
- Path normalization to prevent path traversal
- Resource limits to prevent denial of service
- Timeout controls for all operations

## Usage Examples

### 1. Basic Sandbox Creation and Command Execution

```python
import asyncio
from enterprise_ai.sandbox import create_sandbox_client

async def run_python_code():
    # Create a sandbox client
    sandbox = create_sandbox_client()

    try:
        # Initialize the sandbox
        await sandbox.create()

        # Write Python code to a file
        code = """
print("Hello from sandbox!")
x = 5 + 7
print(f"Result: {x}")
"""
        await sandbox.write_file("script.py", code)

        # Execute the Python code
        result = await sandbox.run_command("python script.py", timeout=10)
        print(f"Execution result:\n{result}")

    finally:
        # Clean up resources
        await sandbox.cleanup()

# Run the async function
asyncio.run(run_python_code())
```

### 2. File Operations

```python
import asyncio
from enterprise_ai.sandbox import create_sandbox_client

async def file_operations():
    sandbox = create_sandbox_client()

    try:
        await sandbox.create()

        # Write a file to the sandbox
        await sandbox.write_file("data.txt", "Some content for testing")

        # Read the file back
        content = await sandbox.read_file("data.txt")
        print(f"File content: {content}")

        # Create a directory and write another file
        await sandbox.run_command("mkdir -p test_dir")
        await sandbox.write_file("test_dir/nested.txt", "Nested file content")

        # Copy file from sandbox to host
        await sandbox.copy_from("test_dir/nested.txt", "/tmp/sandbox_output.txt")

        # Copy file from host to sandbox
        await sandbox.copy_to("/path/to/local/file.txt", "imported_file.txt")

    finally:
        await sandbox.cleanup()

asyncio.run(file_operations())
```

### 3. Error Handling

```python
import asyncio
from enterprise_ai.sandbox import create_sandbox_client, SandboxTimeoutError, SandboxError

async def error_handling():
    sandbox = create_sandbox_client()

    try:
        await sandbox.create()

        # Handle timeout error
        try:
            # This will likely timeout (infinite loop)
            await sandbox.run_command("while true; do echo 'looping'; sleep 1; done", timeout=5)
        except SandboxTimeoutError as e:
            print(f"Command timed out as expected: {e}")

        # Handle file not found
        try:
            content = await sandbox.read_file("non_existent_file.txt")
        except FileNotFoundError as e:
            print(f"File not found as expected: {e}")

        # Handle command execution error
        result = await sandbox.run_command("ls -la /nonexistent", timeout=5)
        print(f"Command result (with error): {result}")

    except SandboxError as e:
        print(f"Sandbox error: {e}")
    finally:
        await sandbox.cleanup()

asyncio.run(error_handling())
```

### 4. Resource Limitations

```python
import asyncio
from enterprise_ai.sandbox import create_sandbox_client
from enterprise_ai.config.sandbox import SandboxSettings

async def resource_limited_sandbox():
    # Create custom sandbox settings with resource limits
    settings = SandboxSettings(
        image="python:3.9-slim",
        memory_limit="256m",  # 256 MB memory limit
        cpu_limit=0.5,        # 50% of a CPU core
        timeout=30,           # 30 second default timeout
        network_enabled=False # No network access
    )

    sandbox = create_sandbox_client()

    try:
        # Create sandbox with custom settings
        await sandbox.create(config=settings)

        # Test memory limitation with a Python script
        memory_test = """
import numpy as np
try:
    # Try to allocate a large array (more than 256MB)
    large_array = np.ones((250, 1024, 1024), dtype=np.float32)
    print(f"Allocated array of shape {large_array.shape}")
except Exception as e:
    print(f"Memory allocation failed: {e}")
"""
        await sandbox.write_file("memory_test.py", memory_test)

        # This should fail due to memory limits
        result = await sandbox.run_command("python memory_test.py", timeout=10)
        print(f"Memory test result:\n{result}")

        # Test network isolation
        network_test = await sandbox.run_command("ping -c 1 google.com || echo 'Network blocked'")
        print(f"Network test result:\n{network_test}")

    finally:
        await sandbox.cleanup()

asyncio.run(resource_limited_sandbox())
```

### 5. Using SandboxManager

```python
import asyncio
from enterprise_ai.sandbox import SandboxManager
from enterprise_ai.config.sandbox import SandboxSettings

async def manage_multiple_sandboxes():
    # Create a manager with custom limits
    manager = SandboxManager(
        max_sandboxes=5,      # Maximum 5 concurrent sandboxes
        idle_timeout=300,     # 5 minutes idle timeout
        cleanup_interval=60   # Check for idle sandboxes every minute
    )

    try:
        # Create multiple sandboxes
        sandbox_ids = []
        for i in range(3):
            settings = SandboxSettings(
                image="python:3.9-slim",
                work_dir=f"/workspace/sandbox_{i}"
            )
            sandbox_id = await manager.create_sandbox(config=settings)
            sandbox_ids.append(sandbox_id)
            print(f"Created sandbox {i}: {sandbox_id}")

        # Use one of the sandboxes
        async with manager.sandbox_operation(sandbox_ids[0]) as sandbox:
            await sandbox.write_file("test.py", "print('Hello from managed sandbox!')")
            result = await sandbox.run_command("python test.py")
            print(f"Execution result: {result}")

        # Get manager statistics
        stats = manager.get_stats()
        print(f"Manager stats: {stats}")

        # Explicitly delete one sandbox
        await manager.delete_sandbox(sandbox_ids[1])
        print(f"Deleted sandbox: {sandbox_ids[1]}")

        # Let the others be cleaned up automatically during manager cleanup

    finally:
        # Clean up all resources
        await manager.cleanup()

asyncio.run(manage_multiple_sandboxes())
```

### 6. Volume Bindings

```python
import asyncio
import os
import tempfile
from enterprise_ai.sandbox import create_sandbox_client
from enterprise_ai.config.sandbox import SandboxSettings

async def sandbox_with_volume_bindings():
    # Create a temporary directory to share with the sandbox
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write a file in the temporary directory
        with open(os.path.join(temp_dir, "shared_data.txt"), "w") as f:
            f.write("This file is shared between host and container")

        # Define volume bindings
        bindings = {
            temp_dir: "/shared"  # Mount temp_dir as /shared in container
        }

        # Create sandbox with volume bindings
        sandbox = create_sandbox_client()

        try:
            # Create sandbox with the specified volume bindings
            await sandbox.create(
                config=SandboxSettings(image="python:3.9-slim"),
                volume_bindings=bindings
            )

            # Verify access to the shared volume
            result = await sandbox.run_command("ls -la /shared")
            print(f"Shared directory contents:\n{result}")

            # Read the shared file
            content = await sandbox.run_command("cat /shared/shared_data.txt")
            print(f"Shared file content: {content}")

            # Write to the shared directory from the container
            await sandbox.run_command("echo 'Written from container' > /shared/container_output.txt")

            # Verify the file was created on the host
            host_file_path = os.path.join(temp_dir, "container_output.txt")
            if os.path.exists(host_file_path):
                with open(host_file_path, "r") as f:
                    print(f"File created by container: {f.read()}")

        finally:
            await sandbox.cleanup()

asyncio.run(sandbox_with_volume_bindings())
```

## Integration Points

The Sandbox module integrates with several other components of the Enterprise AI platform:

### 1. Configuration System

The Sandbox module uses the configuration system for default settings:

```python
from enterprise_ai.config.sandbox import SandboxSettings

# Create custom sandbox settings
settings = SandboxSettings(
    image="python:3.9-slim",
    memory_limit="512m",
    cpu_limit=1.0,
    timeout=60,
    network_enabled=True,
    work_dir="/workspace"
)
```

Configuration parameters can be provided programmatically or loaded from configuration files, allowing for customization of sandbox behavior throughout the platform.

### 2. Logging System

The Sandbox module integrates with the platform's logging system:

```python
from enterprise_ai.logger import get_logger
logger = get_logger("sandbox.core")

# Usage in methods
logger.info(f"Created sandbox container: {container_name}")
logger.error(f"Failed to create sandbox: {e}")
```

This integration enables:

- Consistent logging across the platform
- Diagnostic information for sandbox operations
- Error tracking and auditing
- Configurable log levels for different sandbox components

### 3. Docker API

The Sandbox module wraps the Docker API, providing a higher-level interface:

```python
import docker
from docker.models.containers import Container

# Docker client creation
self.client = docker.from_env()

# Container operations
self.container = self.client.containers.get(container["Id"])
await asyncio.to_thread(self.container.start)
```

This integration allows:

- Container lifecycle management
- Resource limitation
- Command execution
- File transfers
- Environment configuration

### 4. Agent Execution Environment

Agents can use the Sandbox module for code execution:

```python
# In an agent implementation
async def execute_code(self, code: str, language: str = "python") -> str:
    sandbox = create_sandbox_client()
    try:
        await sandbox.create()

        if language == "python":
            filename = "agent_code.py"
        elif language == "bash":
            filename = "agent_code.sh"
        else:
            raise ValueError(f"Unsupported language: {language}")

        await sandbox.write_file(filename, code)

        if language == "bash":
            await sandbox.run_command(f"chmod +x {filename}")
            command = f"./{filename}"
        else:
            command = f"python {filename}"

        result = await sandbox.run_command(command, timeout=30)
        return result
    finally:
        await sandbox.cleanup()
```

This integration enables:

- Secure code execution for agents
- Language-specific execution environments
- Isolation of agent code from the host system
- Resource control for agent operations

### 5. Tool Execution System

Tools can leverage the Sandbox for secure execution:

```python
# In a tool implementation
class CodeExecutionTool:
    def __init__(self):
        self._sandbox = None

    async def setup(self):
        self._sandbox = create_sandbox_client()
        await self._sandbox.create()

    async def execute(self, code: str, language: str) -> str:
        if not self._sandbox:
            await self.setup()

        # Write code to file
        filename = f"tool_code.{language}"
        await self._sandbox.write_file(filename, code)

        # Execute based on language
        if language == "py":
            result = await self._sandbox.run_command(f"python {filename}")
        elif language == "js":
            result = await self._sandbox.run_command(f"node {filename}")
        else:
            raise ValueError(f"Unsupported language: {language}")

        return result

    async def cleanup(self):
        if self._sandbox:
            await self._sandbox.cleanup()
            self._sandbox = None
```

This integration allows tools to:

- Execute code securely
- Support multiple programming languages
- Isolate tool execution from the host system
- Control resource usage for tool operations

## Best Practices

### Security Considerations

1. **Use network isolation** by default:

   ```python
   # Disable network access unless explicitly needed
   settings = SandboxSettings(network_enabled=False)
   ```

1. **Apply resource limitations** to prevent resource exhaustion:

   ```python
   # Limit memory and CPU
   settings = SandboxSettings(
       memory_limit="256m",
       cpu_limit=0.5
   )
   ```

1. **Always set timeouts** to prevent hung operations:

   ```python
   # Set a reasonable timeout for command execution
   result = await sandbox.run_command("some_command", timeout=30)
   ```

1. **Validate and sanitize all inputs** to prevent shell injection:

   ```python
   # The module automatically sanitizes commands, but be cautious with dynamic commands
   user_input = "potentially malicious input"
   safe_input = user_input.replace(";", "").replace("&&", "")
   result = await sandbox.run_command(f"echo {safe_input}")
   ```

1. **Use path validation** to prevent path traversal:

   ```python
   # The module automatically validates paths, but be cautious with dynamic paths
   user_path = "potentially/malicious/../path"
   safe_path = os.path.normpath(user_path)
   if ".." in safe_path.split("/"):
       raise ValueError("Invalid path")
   ```

### Resource Management

1. **Release resources promptly** using context managers or `finally` blocks:

   ```python
   try:
       # Use sandbox
   finally:
       await sandbox.cleanup()
   ```

1. **Set appropriate resource limits** based on workload:

   ```python
   # For data processing
   data_settings = SandboxSettings(memory_limit="1g", cpu_limit=1.0)

   # For simple code execution
   code_settings = SandboxSettings(memory_limit="256m", cpu_limit=0.5)
   ```

1. **Configure idle timeouts** to automatically free unused resources:

   ```python
   manager = SandboxManager(
       idle_timeout=600,      # 10 minutes
       cleanup_interval=60    # Check every minute
   )
   ```

1. **Limit concurrent sandboxes** to prevent resource exhaustion:

   ```python
   manager = SandboxManager(max_sandboxes=10)
   ```

### Error Handling

1. **Use specific exception handling** to provide meaningful feedback:

   ```python
   try:
       result = await sandbox.run_command("python script.py")
   except SandboxTimeoutError:
       print("Operation timed out")
   except FileNotFoundError:
       print("Script not found")
   except SandboxError as e:
       print(f"Sandbox error: {e}")
   ```

1. **Handle cleanup failures gracefully**:

   ```python
   try:
       await sandbox.cleanup()
   except Exception as e:
       logger.error(f"Cleanup failed: {e}")
       # Continue with other operations
   ```

1. **Implement retries for transient errors**:

   ```python
   async def run_with_retry(sandbox, command, max_retries=3):
       for attempt in range(max_retries):
           try:
               return await sandbox.run_command(command)
           except Exception as e:
               if attempt == max_retries - 1:
                   raise
               logger.warning(f"Retry {attempt+1}/{max_retries}: {e}")
               await asyncio.sleep(1)
   ```

### Performance Optimization

1. **Reuse sandbox instances** for multiple operations:

   ```python
   # Create once, use multiple times
   sandbox = create_sandbox_client()
   await sandbox.create()

   for task in tasks:
       result = await sandbox.run_command(task)
       # Process result

   await sandbox.cleanup()
   ```

1. **Use batched commands** where appropriate:

   ```python
   # Instead of multiple commands
   # await sandbox.run_command("mkdir -p dir1")
   # await sandbox.run_command("mkdir -p dir2")

   # Use a single command
   await sandbox.run_command("mkdir -p dir1 dir2")
   ```

1. **Optimize volume bindings** for file-heavy operations:

   ```python
   # Mount directories for bulk file operations
   bindings = {
       "/path/to/data": "/data",
       "/path/to/output": "/output"
   }
   ```

1. **Use the right Docker image** for your workload:

   ```python
   # For Python workloads
   python_settings = SandboxSettings(image="python:3.9-slim")

   # For Node.js workloads
   node_settings = SandboxSettings(image="node:16-alpine")
   ```

### Docker Configuration

1. **Use lightweight images** to improve startup time:

   ```python
   # Prefer slim or alpine variants
   settings = SandboxSettings(image="python:3.9-slim")
   ```

1. **Consider pre-pulling images** to avoid startup delays:

   ```python
   # Pull images during initialization
   await manager.ensure_image("python:3.9-slim")
   ```

1. **Configure appropriate work directories**:

   ```python
   # Set a specific working directory
   settings = SandboxSettings(work_dir="/app")
   ```

1. **Be mindful of Docker daemon settings**:

   - Ensure the Docker daemon has sufficient resources
   - Configure appropriate log rotation
   - Set up Docker daemon security options
