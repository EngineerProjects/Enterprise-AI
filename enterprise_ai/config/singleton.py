"""
Singleton pattern implementation for configuration.
"""

import threading
from typing import Any, Dict, Optional, TypeVar, Type, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.config.loaders import load_config, merge_configs

# Initialize logger
logger = get_logger("config.singleton")

# Type variable for singleton classes
T = TypeVar("T", bound="Singleton")


class Singleton:
    """Base singleton pattern implementation.

    This class ensures that only one instance is created for each subclass.
    """

    _instances: Dict[Type, Any] = {}
    _lock = threading.RLock()

    def __new__(cls: Type[T], *args: Any, **kwargs: Any) -> T:
        """Create a new instance if none exists.

        Args:
            *args: Arguments to pass to __init__
            **kwargs: Keyword arguments to pass to __init__

        Returns:
            Singleton instance
        """
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[cls] = instance
            return cast(T, cls._instances[cls])


class ConfigSingleton(Singleton):
    """Singleton implementation for configuration.

    This class provides a centralized way to access configuration data.
    """

    _initialized: bool = False

    def __init__(
        self,
        config_file: Optional[str] = None,
        default_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the configuration singleton.

        Args:
            config_file: Configuration file to load
            default_config: Default configuration to use if file not found
        """
        # Only initialize once (singleton pattern)
        if self._initialized:
            return

        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()

        # Load configuration
        self.load_config(config_file, default_config)
        self._initialized = True

    def load_config(
        self,
        config_file: Optional[str] = None,
        default_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Load configuration from file.

        Args:
            config_file: Configuration file to load
            default_config: Default configuration to use if file not found
        """
        with self._lock:
            # Load from file
            file_config = load_config(config_file, default_config=default_config or {})

            # Store merged configuration
            self._config = file_config

    def reload(self, config_file: Optional[str] = None) -> None:
        """Reload configuration from file.

        Args:
            config_file: Configuration file to load
        """
        with self._lock:
            # Keep a copy of the current config for fallback
            old_config = self._config.copy()

            try:
                # Reload configuration
                self.load_config(config_file, default_config=old_config)
                logger.info("Configuration reloaded successfully")
            except Exception as e:
                # Restore old configuration on error
                self._config = old_config
                logger.error(f"Error reloading configuration: {e}")
                raise

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: Configuration key (supports dotted notation)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Split key into parts for nested access
        parts = key.split(".")

        # Start with the full config
        current = self._config

        # Navigate to the specified key
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]

        return current

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get a configuration section.

        Args:
            section: Section name

        Returns:
            Section as a dictionary (empty if section not found)
        """
        section_data = self.get(section, {})
        if not isinstance(section_data, dict):
            return {}
        return section_data

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key (supports dotted notation)
            value: Value to set
        """
        with self._lock:
            # Split key into parts for nested access
            parts = key.split(".")

            # Start with the full config
            current = self._config

            # Navigate to the parent of the specified key
            for part in parts[:-1]:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

            # Set the value
            current[parts[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """Get the complete configuration.

        Returns:
            Complete configuration as a dictionary
        """
        return self._config.copy()
