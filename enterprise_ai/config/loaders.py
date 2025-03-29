"""
Configuration file loading utilities.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import toml  # type: ignore
import yaml
from pydantic import ValidationError

from enterprise_ai.exceptions import ConfigFileError, ConfigValueError
from enterprise_ai.constants import CONFIG_DIR, DEFAULT_CONFIGS_DIR
from enterprise_ai.logger import get_logger
from enterprise_ai.constants import CONFIG_FILE_EXTENSIONS, DEFAULT_CONFIG_FILENAME

# Initialize logger
logger = get_logger("config.loaders")


def find_config_file(
    filename: Optional[str] = None,
    config_dir: Optional[Union[str, Path]] = None,
    extensions: Optional[List[str]] = None,
) -> Tuple[Optional[Path], Optional[str]]:
    """Find a configuration file with supported extensions.

    Args:
        filename: Base filename without extension (default: "config")
        config_dir: Directory to search in (default: CONFIG_DIR)
        extensions: File extensions to check (default: CONFIG_FILE_EXTENSIONS)

    Returns:
        Tuple of (file path, file extension) if found, (None, None) otherwise
    """
    filename = filename or DEFAULT_CONFIG_FILENAME
    config_dir = Path(config_dir or CONFIG_DIR)
    extensions = extensions or CONFIG_FILE_EXTENSIONS

    # First check if filename already has an extension
    file_path = Path(filename)
    if file_path.suffix in extensions:
        full_path = config_dir / file_path
        if full_path.exists():
            return full_path, file_path.suffix

    # Try all supported extensions
    for ext in extensions:
        full_path = config_dir / f"{filename}{ext}"
        if full_path.exists():
            return full_path, ext

    # If not found in config_dir, check default configs
    for ext in extensions:
        full_path = DEFAULT_CONFIGS_DIR / f"{filename}{ext}"
        if full_path.exists():
            return full_path, ext

    return None, None


def load_config_file(
    file_path: Union[str, Path], file_format: Optional[str] = None
) -> Dict[str, Any]:
    """Load a configuration file.
    Args:
        file_path: Path to the configuration file
        file_format: Format of the file (inferred from extension if None)
    Returns:
        Configuration as a dictionary
    Raises:
        ConfigFileError: If the file cannot be loaded or parsed
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise ConfigFileError(str(file_path), f"Config file not found: {file_path}")

    # Determine format from extension if not specified
    if file_format is None:
        file_format = file_path.suffix.lower()

    try:
        with open(file_path, "r") as f:
            if file_format in [".yaml", ".yml"]:
                return yaml.safe_load(f) or {}
            elif file_format == ".toml":
                return cast(Dict[str, Any], toml.load(f))
            elif file_format == ".json":
                return cast(Dict[str, Any], json.load(f))
            else:
                raise ConfigFileError(str(file_path), f"Unsupported config format: {file_format}")
    except (yaml.YAMLError, toml.TomlDecodeError, json.JSONDecodeError) as e:
        raise ConfigFileError(str(file_path), f"Error parsing config file: {e}")
    except Exception as e:
        raise ConfigFileError(str(file_path), f"Error loading config file: {e}")


def load_config(
    filename: Optional[str] = None,
    config_dir: Optional[Union[str, Path]] = None,
    default_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Load configuration from file with fallback to default.

    Args:
        filename: Base filename without extension (default: "config")
        config_dir: Directory to search in (default: CONFIG_DIR)
        default_config: Default configuration to use if file not found

    Returns:
        Configuration as a dictionary
    """
    file_path, file_ext = find_config_file(filename, config_dir)

    if file_path is None:
        logger.warning(f"Config file not found, using defaults: {filename}")
        return default_config or {}

    try:
        return load_config_file(file_path, file_ext)
    except ConfigFileError as e:
        logger.error(f"Error loading config file: {e}")
        return default_config or {}


def merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple configuration dictionaries.

    Later dictionaries override values from earlier ones.

    Args:
        *configs: Configuration dictionaries to merge

    Returns:
        Merged configuration
    """
    result: Dict[str, Any] = {}

    for config in configs:
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                result[key] = merge_configs(result[key], value)
            else:
                # Replace or add value
                result[key] = value

    return result
