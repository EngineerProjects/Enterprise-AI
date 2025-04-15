"""
Docker Sandbox Module

Provides secure containerized execution environment with resource limits
and isolation for running untrusted code.
"""

from enterprise_ai.sandbox.core.exceptions import (
    SandboxError,
    SandboxTimeoutError,
    SandboxResourceError,
)
from enterprise_ai.sandbox.core.sandbox import DockerSandbox
from enterprise_ai.sandbox.core.manager import SandboxManager
from enterprise_ai.sandbox.client import (
    BaseSandboxClient,
    LocalSandboxClient,
    create_sandbox_client,
)

__all__ = [
    "DockerSandbox",
    "SandboxManager",
    "BaseSandboxClient",
    "LocalSandboxClient",
    "create_sandbox_client",
    "SandboxError",
    "SandboxTimeoutError",
    "SandboxResourceError",
]
