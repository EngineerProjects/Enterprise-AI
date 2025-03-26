"""
Constants specific to the configuration system.
"""

from pathlib import Path
from typing import Dict, Final, List

# Import from core constants only
from enterprise_ai.constants import CONFIG_DIR, DEFAULT_CONFIGS_DIR

# Configuration file constants
CONFIG_FILE_EXTENSIONS: Final[List[str]] = [".yaml", ".yml", ".toml", ".json"]
DEFAULT_CONFIG_FILENAME: Final[str] = "config"

# Paths for different config types
LLM_CONFIG_PATH: Final[str] = "llm"
AGENT_CONFIG_PATH: Final[str] = "agent"
TEAM_CONFIG_PATH: Final[str] = "team"
TOOL_CONFIG_PATH: Final[str] = "tool"

# Environment variable prefixes
ENV_PREFIX: Final[str] = "ENTERPRISE_AI_"
CONFIG_ENV_PREFIX: Final[str] = f"{ENV_PREFIX}CONFIG_"
API_KEY_ENV_PREFIX: Final[str] = f"{ENV_PREFIX}API_KEY_"

# Provider-specific environment variables
PROVIDER_ENV_MAPPING: Final[Dict[str, str]] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "cohere": "COHERE_API_KEY",
}
