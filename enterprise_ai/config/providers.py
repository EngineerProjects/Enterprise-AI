"""
Provider-specific configuration utilities.
"""

from typing import Any, Dict, List, Optional, Set, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.exceptions import ConfigValueError, ConfigDependencyError
from enterprise_ai.config.utils import get_api_key_from_env
from enterprise_ai.config.constants import PROVIDER_ENV_MAPPING

# Initialize logger
logger = get_logger("config.providers")


def validate_provider_config(
    config: Dict[str, Any], provider: str, required_keys: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """Validate provider-specific configuration.

    Args:
        config: Provider configuration
        provider: Provider name
        required_keys: Set of required keys for this provider

    Returns:
        Validated configuration

    Raises:
        ConfigValueError: If required keys are missing
    """
    # Copy config to avoid modifying the original
    validated_config = config.copy()

    # Check API key
    if "api_key" not in validated_config or not validated_config["api_key"]:
        # Try to get from environment
        api_key = get_api_key_from_env(provider)
        if api_key:
            validated_config["api_key"] = api_key
        elif required_keys and "api_key" in required_keys:
            raise ConfigValueError(
                "api_key",
                None,
                f"API key for provider '{provider}' not found in config or environment",
            )

    # Check other required keys
    if required_keys:
        for key in required_keys:
            if key not in validated_config or validated_config[key] is None:
                raise ConfigValueError(
                    key,
                    None,
                    f"Required key '{key}' for provider '{provider}' not found in config",
                )

    return validated_config


def get_openai_config(config: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Get configuration for OpenAI provider.

    Args:
        config: Base configuration
        api_key: Optional API key to override config

    Returns:
        Configuration for OpenAI provider
    """
    openai_config = config.copy()

    # Override API key if provided
    if api_key:
        openai_config["api_key"] = api_key

    # Validate configuration
    required_keys = {"api_key", "model"}
    return validate_provider_config(openai_config, "openai", required_keys)


def get_anthropic_config(config: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Get configuration for Anthropic provider.

    Args:
        config: Base configuration
        api_key: Optional API key to override config

    Returns:
        Configuration for Anthropic provider
    """
    anthropic_config = config.copy()

    # Override API key if provided
    if api_key:
        anthropic_config["api_key"] = api_key

    # Validate configuration
    required_keys = {"api_key", "model"}
    return validate_provider_config(anthropic_config, "anthropic", required_keys)


def get_ollama_config(config: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """Get configuration for Ollama provider.

    Args:
        config: Base configuration
        api_key: Optional API key to override config (typically not needed)

    Returns:
        Configuration for Ollama provider
    """
    ollama_config = config.copy()

    # Set defaults if not provided
    if "base_url" not in ollama_config:
        ollama_config["base_url"] = "http://localhost:11434"

    # API key is not required for Ollama, but we'll set it if provided
    if api_key:
        ollama_config["api_key"] = api_key

    # Validate configuration
    required_keys = {"model"}
    return validate_provider_config(ollama_config, "ollama", required_keys)
