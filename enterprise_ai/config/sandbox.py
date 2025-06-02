"""
Sandbox configuration settings.

This module defines the configuration options for the Docker sandbox.
"""


class SandboxSettings:
    """Sandbox configuration settings.

    Attributes:
        image: Docker image to use.
        work_dir: Working directory in the container.
        memory_limit: Memory limit in bytes or format like "512m".
        cpu_limit: CPU limit as a float (e.g., 0.5 for half a CPU).
        timeout: Default command execution timeout in seconds.
        network_enabled: Whether network access is allowed.
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        work_dir: str = "/workspace",
        memory_limit: str = "512m",
        cpu_limit: float = 0.5,
        timeout: int = 60,
        network_enabled: bool = False,
    ):
        self.image = image
        self.work_dir = work_dir
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.timeout = timeout
        self.network_enabled = network_enabled
