"""
Simplified configuration for Enterprise AI package.

This replaces the complex app-style config system with package-friendly defaults.
Config files are optional - the package works perfectly without them.
"""

import os
from typing import Any, Dict, Optional

from enterprise_ai.defaults import (
    load_optional_config,
    get_config_value as _get_config_value
)


def get_config(key: str, default: Any = None) -> Any:
    """
    Get configuration value (backward compatibility function).
    
    This function provides backward compatibility for existing code
    while using the new package-friendly config system.
    
    Args:
        key: Configuration key (e.g., "llm.timeout")
        default: Default value if not found
        
    Returns:
        Configuration value or default
    """
    return _get_config_value(key, default)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load optional configuration (backward compatibility function).
    
    Returns empty dict if no config file found (this is normal and expected).
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        Configuration dictionary (empty if no file)
    """
    return load_optional_config()


# Maintain backward compatibility
__all__ = ["get_config", "load_config"]
