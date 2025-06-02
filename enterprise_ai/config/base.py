"""
Enhanced configuration functionality for Enterprise AI with execution defaults.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, cast

import yaml

from enterprise_ai.constants import DEFAULT_CONFIG_PATH, ENV_PREFIX
from enterprise_ai.exceptions import ConfigFileError

# Import enums from constants to avoid circular imports
try:
    from enterprise_ai.tool.constants import ExecutionMode, SandboxMode
except ImportError:
    # Fallback for backwards compatibility
    ExecutionMode = None
    SandboxMode = None

# Global config cache
_config_cache: Dict[str, Dict[str, Any]] = {}


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the config file (defaults to DEFAULT_CONFIG_PATH)

    Returns:
        Configuration dictionary

    Raises:
        ConfigFileError: If the file cannot be loaded
    """
    global _config_cache

    path = config_path or DEFAULT_CONFIG_PATH

    # Return cached config if available
    if path in _config_cache:
        return _config_cache[path]

    # Initialize with empty dict if no file exists
    if not os.path.exists(path):
        _config_cache[path] = {}
        return {}

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f) or {}
            config_dict = cast(Dict[str, Any], config)
            _config_cache[path] = config_dict
            return config_dict
    except Exception as e:
        raise ConfigFileError(f"Failed to load config from {path}: {str(e)}")


def get_config(key: str, default: Any = None, config_path: Optional[str] = None) -> Any:
    """
    Get a configuration value by key using dot notation.

    Args:
        key: Configuration key (e.g., "llm.openai.api_key")
        default: Default value if key not found
        config_path: Path to config file (optional)

    Returns:
        Configuration value or default
    """
    # First check environment variables
    env_key = ENV_PREFIX + key.upper().replace(".", "_")
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return env_value

    # Load config if needed
    config = load_config(config_path)

    # Navigate to the specified key
    parts = key.split(".")
    current: Any = config

    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]

    return current


def get_execution_config() -> Dict[str, Any]:
    """
    Get execution-related configuration with sensible defaults.
    
    Returns:
        Dictionary of execution configuration options
    """
    # Handle case where enums are not available due to circular imports
    if ExecutionMode is None or SandboxMode is None:
        return {
            "execution_mode": get_config("execution.mode", "auto"),
            "max_tool_iterations": get_config("execution.max_iterations", 5),
            "tool_execution_timeout": get_config("execution.timeout", 30.0),
            "verbose_logging": get_config("execution.verbose", False),
            "hybrid_danger_threshold": get_config("execution.hybrid_threshold", 2),
            
            "sandbox_mode": get_config("sandbox.mode", "none"),
            "enable_sandbox_routing": get_config("sandbox.routing_enabled", False),
            "sandbox_image": get_config("sandbox.image", "python:3.12-slim"),
            "sandbox_memory_limit": get_config("sandbox.memory_limit", "512m"),
            "sandbox_cpu_limit": get_config("sandbox.cpu_limit", 0.5),
            "sandbox_network_enabled": get_config("sandbox.network_enabled", False),
            
            "allowed_tools": get_config("security.allowed_tools", None),
            "forbidden_tools": get_config("security.forbidden_tools", []),
            "require_approval_for_dangerous": get_config("security.require_approval", True),
        }
    
    return {
        # Tool execution defaults
        "execution_mode": ExecutionMode(get_config("execution.mode", ExecutionMode.AUTO)),
        "max_tool_iterations": get_config("execution.max_iterations", 5),
        "tool_execution_timeout": get_config("execution.timeout", 30.0),
        "verbose_logging": get_config("execution.verbose", False),
        "hybrid_danger_threshold": get_config("execution.hybrid_threshold", 2),
        
        # Sandbox defaults
        "sandbox_mode": SandboxMode(get_config("sandbox.mode", SandboxMode.NONE)),
        "enable_sandbox_routing": get_config("sandbox.routing_enabled", False),
        "sandbox_image": get_config("sandbox.image", "python:3.12-slim"),
        "sandbox_memory_limit": get_config("sandbox.memory_limit", "512m"),
        "sandbox_cpu_limit": get_config("sandbox.cpu_limit", 0.5),
        "sandbox_network_enabled": get_config("sandbox.network_enabled", False),
        
        # Security defaults
        "allowed_tools": get_config("security.allowed_tools", None),
        "forbidden_tools": get_config("security.forbidden_tools", []),
        "require_approval_for_dangerous": get_config("security.require_approval", True),
    }


def set_execution_defaults(config_updates: Dict[str, Any]) -> None:
    """
    Update execution configuration defaults.
    
    Args:
        config_updates: Dictionary of configuration updates
    """
    # This would update the config file or environment
    # For now, we'll just log the intent
    import logging
    logger = logging.getLogger("config.base")
    
    logger.info(f"Execution config updates requested: {config_updates}")
    # In a full implementation, this would write to config file