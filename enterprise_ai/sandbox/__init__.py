"""
Docker Sandbox Module

Provides secure containerized execution environment with resource limits
and isolation for running untrusted code.
"""

# Always available - settings don't require Docker
from enterprise_ai.sandbox.settings import (
    SandboxSettings,
    get_default_sandbox_settings,
    get_secure_sandbox_settings,
    get_development_sandbox_settings,
)

# Optional Docker-dependent imports
try:
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
    
    # Docker is available
    DOCKER_AVAILABLE = True
    __all__ = [
        # Settings (always available)
        "SandboxSettings",
        "get_default_sandbox_settings",
        "get_secure_sandbox_settings", 
        "get_development_sandbox_settings",
        # Docker components (when available)
        "DockerSandbox",
        "SandboxManager", 
        "BaseSandboxClient",
        "LocalSandboxClient",
        "create_sandbox_client",
        "SandboxError",
        "SandboxTimeoutError",
        "SandboxResourceError",
        "DOCKER_AVAILABLE",
    ]
    
except ImportError as e:
    # Docker not available - that's fine for settings-only usage
    DOCKER_AVAILABLE = False
    __all__ = [
        # Settings (always available)
        "SandboxSettings",
        "get_default_sandbox_settings",
        "get_secure_sandbox_settings", 
        "get_development_sandbox_settings",
        "DOCKER_AVAILABLE",
    ]
