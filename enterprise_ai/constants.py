"""
Constants for Enterprise AI.

This module defines global constants used throughout the Enterprise AI framework.
"""

import os
from pathlib import Path


# System paths
def get_project_root() -> Path:
    """Get the project root directory."""
    module_path = Path(__file__).resolve().parent.parent
    return module_path


PROJECT_ROOT = get_project_root()
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CONFIG_PATH = str(CONFIG_DIR / "config.yml")
ENV_PREFIX = "ENTERPRISE_AI_"

# LLM constants
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TOP_P = 1.0
DEFAULT_TIMEOUT = float(
    os.environ.get("ENTERPRISE_AI_DEFAULT_TIMEOUT", "60.0")
)  # Read from env or use default
DEFAULT_MAX_RETRIES = 3

# Ollama API
OLLAMA_API_BASE = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = os.environ.get("ENTERPRISE_AI_DEFAULT_MODEL", "llama3.2")


# Model capabilities
class ModelFeature:
    """Model feature capabilities."""

    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    CODE = "code"
    JSON_MODE = "json_mode"
    MULTI_MODAL = "multi_modal"
    THINKING = "thinking"  # NEW: Add thinking capability
    REASONING = "reasoning"  # NEW: Add reasoning capability