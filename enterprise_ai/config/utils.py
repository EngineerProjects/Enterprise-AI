"""
Utility functions for the configuration system.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TypeVar, Union, cast

from enterprise_ai.exceptions import ConfigValueError
from enterprise_ai.logger import get_logger
from enterprise_ai.config.constants import (
    ENV_PREFIX,
    CONFIG_ENV_PREFIX,
    API_KEY_ENV_PREFIX,
    PROVIDER_ENV_MAPPING,
)

# Initialize logger
logger = get_logger("config.utils")

# Type variable for generic functions
T = TypeVar("T")


def get_env_var(name: str, default: Optional[T] = None, prefix: str = ENV_PREFIX) -> Union[str, T]:
    """Get environment variable with prefix.

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
        return default  # type: ignore
    return value


def get_api_key_from_env(provider: str) -> Optional[str]:
    """Get provider API key from environment variables.

    Checks both provider-specific variables (e.g., OPENAI_API_KEY) and
    Enterprise AI variables (e.g., ENTERPRISE_AI_API_KEY_OPENAI).

    Args:
        provider: Provider name (e.g., "openai", "anthropic")

    Returns:
        API key if found, None otherwise
    """
    # First check provider-specific environment variables
    if provider.lower() in PROVIDER_ENV_MAPPING:
        env_var = PROVIDER_ENV_MAPPING[provider.lower()]
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key

    # Then check Enterprise AI environment variables
    api_key = get_env_var(provider.upper(), prefix=API_KEY_ENV_PREFIX)
    if isinstance(api_key, str):
        return api_key

    return None


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key for nested dictionaries
        sep: Separator for key levels

    Returns:
        Flattened dictionary
    """
    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict) and v:
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict[str, Any], sep: str = ".") -> Dict[str, Any]:
    """Unflatten a dictionary with keys containing separators.

    Args:
        d: Flattened dictionary
        sep: Separator used in keys

    Returns:
        Nested dictionary
    """
    result: Dict[str, Any] = {}
    for key, value in d.items():
        parts = key.split(sep)

        # Navigate to the appropriate level
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set the value
        current[parts[-1]] = value

    return result


def validate_required_keys(
    config: Dict[str, Any], required_keys: Set[str], section: Optional[str] = None
) -> List[str]:
    """Validate that all required keys are present in the configuration.

    Args:
        config: Configuration dictionary
        required_keys: Set of required keys
        section: Section name for error messages

    Returns:
        List of missing keys
    """
    flat_config = flatten_dict(config)
    flat_keys = set(flat_config.keys())
    missing_keys = required_keys - flat_keys

    section_info = f" in section {section}" if section else ""
    if missing_keys:
        missing_list = ", ".join(missing_keys)
        logger.warning(f"Missing required configuration keys{section_info}: {missing_list}")

    return list(missing_keys)
