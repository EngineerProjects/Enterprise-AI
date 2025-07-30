"""
Enhanced User-Friendly Sandbox Configuration for Enterprise AI MCP.

Provides intuitive sandbox configuration with tool groups and Docker validation.
"""

import docker
from typing import Dict, List, Optional, Set, Literal, Union
from dataclasses import dataclass
from pathlib import Path

from enterprise_ai.logger import get_optimized_logger
from enterprise_ai.sandbox.settings import SandboxSettings

logger = get_optimized_logger("mcp.enhanced_sandbox")

# Define tool groups for easy categorization
ToolGroup = Literal["execution", "file", "network", "research", "browser", "all"]

# Tool group definitions
TOOL_GROUPS: Dict[ToolGroup, Set[str]] = {
    "execution": {
        "bash", "python_execute", "process_manager"
    },
    "file": {
        "file_editor", "file_system", "code_search"
    },
    "network": {
        "web_search", "deep_research"
    },
    "research": {
        "web_search", "deep_research", "browser"
    },
    "browser": {
        "browser"
    },
    "all": {
        # Will be populated dynamically with all discovered tools
    }
}


@dataclass
class EnhancedSandboxConfig:
    """
    User-friendly sandbox configuration with tool groups and Docker validation.
    
    Examples:
        # Default: Everything runs locally
        config = EnhancedSandboxConfig()
        
        # Sandbox execution tools with Python image
        config = EnhancedSandboxConfig(
            enabled=True,
            docker_image="python:3.12-slim",
            tool_groups=["execution"]
        )
        
        # Sandbox file and execution tools with custom image
        config = EnhancedSandboxConfig(
            enabled=True,
            docker_image="ubuntu:22.04",
            tool_groups=["execution", "file"],
            memory_limit="1g",
            timeout=60
        )
    """
    
    # Basic configuration
    enabled: bool = False
    docker_image: Optional[str] = None
    
    # Tool routing configuration
    tool_groups: Optional[List[ToolGroup]] = None  # Groups to sandbox
    specific_tools: Optional[List[str]] = None     # Specific tools to sandbox
    exclude_tools: Optional[List[str]] = None      # Tools to never sandbox
    
    # Resource limits
    memory_limit: str = "512m"
    cpu_limit: float = 0.5
    timeout: int = 60
    network_enabled: bool = False
    
    # Docker validation
    validate_docker: bool = True
    work_dir: str = "/workspace"
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        if self.enabled:
            # Default to execution group if no groups specified
            if not self.tool_groups and not self.specific_tools:
                self.tool_groups = ["execution"]
                logger.info("No tool groups specified, defaulting to 'execution' group")
            
            # Default Docker image if not specified
            if not self.docker_image:
                self.docker_image = "python:3.12-slim"
                logger.info(f"No Docker image specified, defaulting to '{self.docker_image}'")
            
            # Validate Docker setup if requested
            if self.validate_docker:
                self._validate_docker_setup()
    
    def _validate_docker_setup(self) -> None:
        """Validate Docker is available and image exists."""
        try:
            # Check if Docker is available
            client = docker.from_env()
            
            # Check if Docker daemon is running
            client.ping()
            logger.info("✅ Docker daemon is running")
            
            # Check if the specified image exists locally or can be pulled
            if self.docker_image:
                self._validate_docker_image(client, self.docker_image)
                
        except docker.errors.DockerException as e:
            logger.error(f"❌ Docker validation failed: {e}")
            raise ValueError(
                f"Docker validation failed: {e}. "
                "Please ensure Docker is installed and running, or set validate_docker=False"
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error during Docker validation: {e}")
            raise ValueError(f"Docker setup validation failed: {e}")
    
    def _validate_docker_image(self, client: docker.DockerClient, image_name: str) -> None:
        """Validate that Docker image exists or can be pulled."""
        try:
            # Try to find the image locally
            client.images.get(image_name)
            logger.info(f"✅ Docker image '{image_name}' found locally")
        except docker.errors.ImageNotFound:
            logger.info(f"🔍 Image '{image_name}' not found locally, checking if it can be pulled...")
            
            try:
                # Try to pull the image to validate it exists
                # Note: We don't actually pull it here, just check if it's pullable
                registry_data = client.api.inspect_distribution(image_name)
                if registry_data:
                    logger.info(f"✅ Docker image '{image_name}' is available for pulling")
                else:
                    raise ValueError(f"Image '{image_name}' not found in registry")
            except Exception as e:
                logger.error(f"❌ Cannot validate image '{image_name}': {e}")
                raise ValueError(
                    f"Docker image '{image_name}' is not available locally or in registry. "
                    f"Please pull it first: docker pull {image_name}"
                )
    
    def get_sandboxed_tools(self, all_available_tools: Set[str]) -> Set[str]:
        """
        Get the set of tools that should be sandboxed based on configuration.
        
        Args:
            all_available_tools: Set of all available tool names
            
        Returns:
            Set of tool names that should run in sandbox
        """
        if not self.enabled:
            return set()
        
        sandboxed_tools = set()
        
        # Add tools from specified groups
        if self.tool_groups:
            for group in self.tool_groups:
                if group == "all":
                    # Special case: sandbox all tools except excluded ones
                    sandboxed_tools.update(all_available_tools)
                elif group in TOOL_GROUPS:
                    sandboxed_tools.update(TOOL_GROUPS[group])
                else:
                    logger.warning(f"Unknown tool group: {group}")
        
        # Add specific tools
        if self.specific_tools:
            sandboxed_tools.update(self.specific_tools)
        
        # Remove excluded tools
        if self.exclude_tools:
            sandboxed_tools.difference_update(self.exclude_tools)
        
        # Only return tools that actually exist
        existing_sandboxed_tools = sandboxed_tools.intersection(all_available_tools)
        
        if sandboxed_tools != existing_sandboxed_tools:
            missing_tools = sandboxed_tools - existing_sandboxed_tools
            logger.warning(f"Some configured sandbox tools don't exist: {missing_tools}")
        
        return existing_sandboxed_tools
    
    def to_sandbox_settings(self) -> SandboxSettings:
        """Convert to SandboxSettings for backward compatibility."""
        return SandboxSettings(
            image=self.docker_image or "python:3.12-slim",
            work_dir=self.work_dir,
            memory_limit=self.memory_limit,
            cpu_limit=self.cpu_limit,
            timeout=self.timeout,
            network_enabled=self.network_enabled
        )
    
    def get_summary(self) -> str:
        """Get a human-readable summary of the sandbox configuration."""
        if not self.enabled:
            return "🏠 Sandbox: Disabled (all tools run locally)"
        
        parts = [f"🐳 Sandbox: Enabled with '{self.docker_image}'"]
        
        if self.tool_groups:
            parts.append(f"📦 Groups: {', '.join(self.tool_groups)}")
        
        if self.specific_tools:
            parts.append(f"🔧 Specific tools: {', '.join(self.specific_tools)}")
        
        if self.exclude_tools:
            parts.append(f"🚫 Excluded: {', '.join(self.exclude_tools)}")
        
        parts.append(f"💾 Resources: {self.memory_limit} RAM, {self.cpu_limit} CPU")
        parts.append(f"⏱️ Timeout: {self.timeout}s")
        
        if self.network_enabled:
            parts.append("🌐 Network: Enabled")
        else:
            parts.append("🔒 Network: Disabled")
        
        return " | ".join(parts)


# Convenience functions for common configurations
def create_local_config() -> EnhancedSandboxConfig:
    """Create configuration for local execution (no sandbox)."""
    return EnhancedSandboxConfig(enabled=False)


def create_execution_sandbox(
    docker_image: str = "python:3.12-slim",
    memory_limit: str = "512m",
    timeout: int = 60,
    validate_docker: bool = True
) -> EnhancedSandboxConfig:
    """
    Create sandbox configuration for execution tools (bash, python, process).
    
    Args:
        docker_image: Docker image to use
        memory_limit: Memory limit for container
        timeout: Execution timeout in seconds
        validate_docker: Whether to validate Docker setup
        
    Returns:
        EnhancedSandboxConfig for execution tools
    """
    return EnhancedSandboxConfig(
        enabled=True,
        docker_image=docker_image,
        tool_groups=["execution"],
        memory_limit=memory_limit,
        timeout=timeout,
        network_enabled=False,
        validate_docker=validate_docker
    )


def create_file_sandbox(
    docker_image: str = "python:3.12-slim",
    memory_limit: str = "256m",
    timeout: int = 30,
    validate_docker: bool = True
) -> EnhancedSandboxConfig:
    """
    Create sandbox configuration for file tools.
    
    Args:
        docker_image: Docker image to use
        memory_limit: Memory limit for container
        timeout: Execution timeout in seconds
        validate_docker: Whether to validate Docker setup
        
    Returns:
        EnhancedSandboxConfig for file tools
    """
    return EnhancedSandboxConfig(
        enabled=True,
        docker_image=docker_image,
        tool_groups=["file"],
        memory_limit=memory_limit,
        timeout=timeout,
        network_enabled=False,
        validate_docker=validate_docker
    )


def create_full_sandbox(
    docker_image: str = "ubuntu:22.04",
    memory_limit: str = "1g",
    cpu_limit: float = 1.0,
    timeout: int = 120,
    network_enabled: bool = False,
    validate_docker: bool = True
) -> EnhancedSandboxConfig:
    """
    Create sandbox configuration for all tools.
    
    Args:
        docker_image: Docker image to use
        memory_limit: Memory limit for container
        cpu_limit: CPU limit for container
        timeout: Execution timeout in seconds
        network_enabled: Whether to enable network access
        validate_docker: Whether to validate Docker setup
        
    Returns:
        EnhancedSandboxConfig for all tools
    """
    return EnhancedSandboxConfig(
        enabled=True,
        docker_image=docker_image,
        tool_groups=["all"],
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        timeout=timeout,
        network_enabled=network_enabled,
        validate_docker=validate_docker
    )


def create_custom_sandbox(
    docker_image: str,
    specific_tools: List[str],
    exclude_tools: Optional[List[str]] = None,
    memory_limit: str = "512m",
    cpu_limit: float = 0.5,
    timeout: int = 60,
    network_enabled: bool = False,
    validate_docker: bool = True
) -> EnhancedSandboxConfig:
    """
    Create custom sandbox configuration with specific tools.
    
    Args:
        docker_image: Docker image to use
        specific_tools: List of specific tools to sandbox
        exclude_tools: List of tools to exclude from sandbox
        memory_limit: Memory limit for container
        cpu_limit: CPU limit for container
        timeout: Execution timeout in seconds
        network_enabled: Whether to enable network access
        validate_docker: Whether to validate Docker setup
        
    Returns:
        Custom EnhancedSandboxConfig
    """
    return EnhancedSandboxConfig(
        enabled=True,
        docker_image=docker_image,
        specific_tools=specific_tools,
        exclude_tools=exclude_tools,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        timeout=timeout,
        network_enabled=network_enabled,
        validate_docker=validate_docker
    )


# Export commonly used configurations
COMMON_CONFIGS = {
    "local": create_local_config,
    "execution": create_execution_sandbox,
    "file": create_file_sandbox,
    "full": create_full_sandbox,
    "custom": create_custom_sandbox,
}


def get_config_by_name(name: str, **kwargs) -> EnhancedSandboxConfig:
    """
    Get a predefined configuration by name.
    
    Args:
        name: Configuration name ("local", "execution", "file", "full", "custom")
        **kwargs: Additional arguments to pass to the configuration function
        
    Returns:
        EnhancedSandboxConfig instance
        
    Example:
        config = get_config_by_name("execution", docker_image="python:3.11-slim")
    """
    if name not in COMMON_CONFIGS:
        available = ", ".join(COMMON_CONFIGS.keys())
        raise ValueError(f"Unknown config name '{name}'. Available: {available}")
    
    return COMMON_CONFIGS[name](**kwargs)
