"""
Base configuration functionality for Enterprise AI.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from enterprise_ai.constants import DEFAULT_CONFIG_PATH, ENV_PREFIX
from enterprise_ai.exceptions import ConfigFileError

# Global config cache
_config_cache: Dict[str, Any] = {}

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
        with open(path, 'r') as f:
            config = yaml.safe_load(f) or {}
            _config_cache[path] = config
            return config
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
    env_key = ENV_PREFIX + key.upper().replace('.', '_')
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return env_value
    
    # Load config if needed
    config = load_config(config_path)
    
    # Navigate to the specified key
    parts = key.split('.')
    current = config
    
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    
    return current