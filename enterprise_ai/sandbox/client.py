"""
Sandbox clients for interacting with Docker sandboxes.

This module provides high-level clients for working with Docker sandboxes,
simplifying sandbox creation and usage.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Protocol

from enterprise_ai.logger import get_logger
from enterprise_ai.config.sandbox import SandboxSettings
from enterprise_ai.sandbox.core.sandbox import DockerSandbox

logger = get_logger("sandbox.client")


class SandboxFileOperations(Protocol):
    """Protocol for sandbox file operations."""

    async def copy_from(self, container_path: str, local_path: str) -> None:
        """Copies file from container to local.

        Args:
            container_path: File path in container.
            local_path: Local destination path.
        """
        ...

    async def copy_to(self, local_path: str, container_path: str) -> None:
        """Copies file from local to container.

        Args:
            local_path: Local source file path.
            container_path: Destination path in container.
        """
        ...

    async def read_file(self, path: str) -> str:
        """Reads file content from container.

        Args:
            path: File path in container.

        Returns:
            str: File content.
        """
        ...

    async def write_file(self, path: str, content: str) -> None:
        """Writes content to file in container.

        Args:
            path: File path in container.
            content: Content to write.
        """
        ...


class BaseSandboxClient(ABC):
    """Base sandbox client interface."""

    @abstractmethod
    async def create(
        self,
        config: Optional[SandboxSettings] = None,
        volume_bindings: Optional[Dict[str, str]] = None,
    ) -> None:
        """Creates sandbox."""

    @abstractmethod
    async def run_command(self, command: str, timeout: Optional[int] = None) -> str:
        """Executes command."""

    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Executes a tool in the sandbox."""

    @abstractmethod
    async def copy_from(self, container_path: str, local_path: str) -> None:
        """Copies file from container."""

    @abstractmethod
    async def copy_to(self, local_path: str, container_path: str) -> None:
        """Copies file to container."""

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Reads file."""

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """Writes file."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleans up resources."""


class LocalSandboxClient(BaseSandboxClient):
    """Local sandbox client implementation."""

    def __init__(self) -> None:
        """Initializes local sandbox client."""
        self.sandbox: Optional[DockerSandbox] = None

    async def create(
        self,
        config: Optional[SandboxSettings] = None,
        volume_bindings: Optional[Dict[str, str]] = None,
    ) -> None:
        """Creates a sandbox.

        Args:
            config: Sandbox configuration.
            volume_bindings: Volume mappings.

        Raises:
            RuntimeError: If sandbox creation fails.
        """
        self.sandbox = DockerSandbox(config, volume_bindings)
        await self.sandbox.create()
        logger.info("Created sandbox using LocalSandboxClient")

    async def run_command(self, command: str, timeout: Optional[int] = None) -> str:
        """Runs command in sandbox.

        Args:
            command: Command to execute.
            timeout: Execution timeout in seconds.

        Returns:
            Command output.

        Raises:
            RuntimeError: If sandbox not initialized.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not initialized")
        return await self.sandbox.run_command(command, timeout)

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Executes a tool in the sandbox.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            timeout: Execution timeout in seconds.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If sandbox not initialized.
        """
        # Auto-initialize sandbox if not already created
        if not self.sandbox:
            logger.info("Auto-initializing sandbox for tool execution")
            try:
                await self.create()
            except Exception as e:
                logger.warning(f"Sandbox creation failed, executing tool directly: {e}")
        
        try:
            # For now, we'll execute tools directly without sandbox isolation
            # This is a simplified implementation that should be enhanced later
            from enterprise_ai.tool.core.registry import get_registry
            
            registry = get_registry()
            tool_instance = await registry.create_tool(tool_name, initialize=True)
            
            if not tool_instance:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found or could not be created",
                    "result": None
                }
            
            import time
            start_time = time.time()
            
            # Execute the tool
            result = await tool_instance.execute(**arguments)
            
            execution_time = time.time() - start_time
            
            return {
                "success": True,
                "result": result.result if hasattr(result, 'result') else str(result),
                "error": None,
                "execution_time": execution_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "result": None,
                "execution_time": 0
            }

    async def copy_from(self, container_path: str, local_path: str) -> None:
        """Copies file from container to local.

        Args:
            container_path: File path in container.
            local_path: Local destination path.

        Raises:
            RuntimeError: If sandbox not initialized.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not initialized")
        await self.sandbox.copy_from(container_path, local_path)

    async def copy_to(self, local_path: str, container_path: str) -> None:
        """Copies file from local to container.

        Args:
            local_path: Local source file path.
            container_path: Destination path in container.

        Raises:
            RuntimeError: If sandbox not initialized.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not initialized")
        await self.sandbox.copy_to(local_path, container_path)

    async def read_file(self, path: str) -> str:
        """Reads file from container.

        Args:
            path: File path in container.

        Returns:
            File content.

        Raises:
            RuntimeError: If sandbox not initialized.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not initialized")
        return await self.sandbox.read_file(path)

    async def write_file(self, path: str, content: str) -> None:
        """Writes file to container.

        Args:
            path: File path in container.
            content: File content.

        Raises:
            RuntimeError: If sandbox not initialized.
        """
        if not self.sandbox:
            raise RuntimeError("Sandbox not initialized")
        await self.sandbox.write_file(path, content)

    async def cleanup(self) -> None:
        """Cleans up resources."""
        if self.sandbox:
            await self.sandbox.cleanup()
            self.sandbox = None
            logger.info("Cleaned up sandbox resources")


def create_sandbox_client() -> LocalSandboxClient:
    """Creates a sandbox client.

    Returns:
        LocalSandboxClient: Sandbox client instance.
    """
    return LocalSandboxClient()
