"""
Configuration system for Enterprise AI.

This module provides a centralized way to manage configuration for all
components of the Enterprise AI framework. It handles loading configuration
from files, environment variables, and programmatic sources.
"""

from typing import Any, Dict, Optional, Union

from enterprise_ai.config.singleton import ConfigSingleton
from enterprise_ai.config.loaders import load_config, merge_configs
from enterprise_ai.config.models import (
    AppConfig,
    PathConfig,
    LogConfig,
    LLMServiceConfig,
    LLMProviderSettings,
    CacheConfig,
    RequestTimeouts,
    ModelSelectionStrategy,
    OrchestratorConfig,
    OllamaConfig,
    OpenAIConfig,
    AnthropicConfig,
)
from enterprise_ai.config.utils import (
    get_env_var,
    get_api_key_from_env,
    flatten_dict,
    unflatten_dict,
)
from enterprise_ai.config.providers import (
    validate_provider_config,
    get_openai_config,
    get_anthropic_config,
    get_ollama_config,
)
from enterprise_ai.constants import DEFAULT_CONFIG_PATH

# Create the singleton instance
_config_instance = ConfigSingleton(DEFAULT_CONFIG_PATH)

# Export public functions that use the singleton
get_config = _config_instance.get
get_section = _config_instance.get_section
set_config = _config_instance.set
reload_config = _config_instance.reload
get_all_config = _config_instance.get_all


def load_app_config(config_path: Optional[str] = None) -> AppConfig:
    """Load and validate application configuration.

    Args:
        config_path: Path to configuration file

    Returns:
        Validated AppConfig object
    """
    # Load raw configuration
    raw_config = load_config(config_path or DEFAULT_CONFIG_PATH)

    # Construct and validate AppConfig
    return AppConfig(**raw_config)


__all__ = [
    # Singleton access functions
    "get_config",
    "get_section",
    "set_config",
    "reload_config",
    "get_all_config",
    "load_app_config",
    # Configuration models
    "AppConfig",
    "PathConfig",
    "LogConfig",
    "LLMServiceConfig",
    "LLMProviderSettings",
    "CacheConfig",
    "RequestTimeouts",
    "ModelSelectionStrategy",
    "OrchestratorConfig",
    "OllamaConfig",
    "OpenAIConfig",
    "AnthropicConfig",
    # Utility functions
    "load_config",
    "merge_configs",
    "get_env_var",
    "get_api_key_from_env",
    "flatten_dict",
    "unflatten_dict",
    # Provider utilities
    "validate_provider_config",
    "get_openai_config",
    "get_anthropic_config",
    "get_ollama_config",
]
