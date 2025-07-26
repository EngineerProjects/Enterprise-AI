"""
Package-friendly sandbox settings for Enterprise AI.

Provides sensible defaults with environment variable overrides.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class SandboxSettings:
    """
    Package-friendly sandbox configuration settings.
    
    All settings can be overridden via environment variables with ENTERPRISE_AI_ prefix.
    """
    
    # Docker image configuration
    image: str = "python:3.12-slim"
    work_dir: str = "/workspace"
    
    # Resource limits
    memory_limit: str = "512m"  # Memory limit (e.g., "512m", "1g")
    cpu_limit: float = 0.5      # CPU limit (0.5 = half a CPU)
    
    # Execution settings
    timeout: int = 60           # Default command timeout in seconds
    network_enabled: bool = False  # Network access allowed
    
    def __post_init__(self):
        """Apply environment variable overrides if available."""
        # Docker settings
        self.image = os.environ.get("ENTERPRISE_AI_SANDBOX_IMAGE", self.image)
        self.work_dir = os.environ.get("ENTERPRISE_AI_SANDBOX_WORKDIR", self.work_dir)
        
        # Resource limits
        self.memory_limit = os.environ.get("ENTERPRISE_AI_SANDBOX_MEMORY", self.memory_limit)
        cpu_env = os.environ.get("ENTERPRISE_AI_SANDBOX_CPU_LIMIT")
        if cpu_env:
            try:
                self.cpu_limit = float(cpu_env)
            except ValueError:
                pass  # Keep default if invalid
                
        # Execution settings
        timeout_env = os.environ.get("ENTERPRISE_AI_SANDBOX_TIMEOUT")
        if timeout_env:
            try:
                self.timeout = int(timeout_env)
            except ValueError:
                pass  # Keep default if invalid
                
        network_env = os.environ.get("ENTERPRISE_AI_SANDBOX_NETWORK", "").lower()
        if network_env in ("true", "1", "yes", "on"):
            self.network_enabled = True
        elif network_env in ("false", "0", "no", "off"):
            self.network_enabled = False
    
    @classmethod
    def create_default(cls) -> "SandboxSettings":
        """Create default sandbox settings."""
        return cls()
    
    @classmethod
    def create_secure(cls) -> "SandboxSettings":
        """Create secure sandbox settings (minimal resources, no network)."""
        return cls(
            memory_limit="256m",
            cpu_limit=0.25,
            timeout=30,
            network_enabled=False
        )
    
    @classmethod
    def create_development(cls) -> "SandboxSettings":
        """Create development sandbox settings (more resources, network enabled)."""
        return cls(
            memory_limit="1g",
            cpu_limit=1.0,
            timeout=120,
            network_enabled=True
        )


def get_env_var(name: str, default: Optional[str] = None, prefix: str = "ENTERPRISE_AI_") -> Optional[str]:
    """
    Get environment variable with prefix.
    
    Args:
        name: Environment variable name (without prefix)
        default: Default value if variable not found
        prefix: Prefix to add to variable name
        
    Returns:
        Environment variable value or default
    """
    env_name = f"{prefix}{name}"
    return os.environ.get(env_name, default)


# Convenience functions for common configurations
def get_default_sandbox_settings() -> SandboxSettings:
    """Get default sandbox settings with environment overrides."""
    return SandboxSettings.create_default()


def get_secure_sandbox_settings() -> SandboxSettings:
    """Get secure sandbox settings (minimal resources)."""
    return SandboxSettings.create_secure()


def get_development_sandbox_settings() -> SandboxSettings:
    """Get development sandbox settings (more resources)."""
    return SandboxSettings.create_development()
