"""
Simplified configuration for Enterprise AI package.

This replaces the complex app-style config system with package-friendly defaults.
Config files are optional - the package works perfectly without them.
"""

import os
from typing import Any, Dict, Optional

from enterprise_ai.defaults import (
    load_optional_config,
    get_config_value as get_config  # Direct import, no wrapper needed
)

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load optional configuration (backward compatibility function).
    
    Returns empty dict if no config file found (this is normal and expected).
    Note: config_path parameter is maintained for backward compatibility 
    but is currently ignored as the system auto-discovers config files.
    
    Args:
        config_path: Optional path to config file (currently ignored)
        
    Returns:
        Configuration dictionary (empty if no file)
    """
    return load_optional_config()


# Maintain backward compatibility
__all__ = ["get_config", "load_config"]
