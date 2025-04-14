"""
Utility functions for the configuration system.
"""

import os
from typing import Any, Dict, Optional

from enterprise_ai.constants import ENV_PREFIX


def get_env_var(name: str, default: Optional[Any] = None, prefix: str = ENV_PREFIX) -> Any:
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
    value = os.environ.get(env_name)
    if value is None:
        return default
    return value
