"""
Constants for Enterprise AI package.

Simplified constants with smart defaults and no config file dependencies.
"""

import os
from pathlib import Path
from enum import Enum


# === PATH CONSTANTS ===
def get_project_root() -> Path:
    """Get the project root directory."""
    module_path = Path(__file__).resolve().parent.parent
    return module_path


PROJECT_ROOT = get_project_root()
CONFIG_DIR = PROJECT_ROOT / "config"
ENV_PREFIX = "ENTERPRISE_AI_"


# === LLM CONSTANTS (using environment with fallbacks) ===
DEFAULT_TEMPERATURE = float(os.environ.get("ENTERPRISE_AI_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.environ.get("ENTERPRISE_AI_MAX_TOKENS", "1024"))
DEFAULT_TOP_P = float(os.environ.get("ENTERPRISE_AI_TOP_P", "1.0"))
DEFAULT_TIMEOUT = float(os.environ.get("ENTERPRISE_AI_TIMEOUT", "60.0"))
DEFAULT_MAX_RETRIES = int(os.environ.get("ENTERPRISE_AI_MAX_RETRIES", "3"))

# Ollama defaults
OLLAMA_API_BASE = os.environ.get("ENTERPRISE_AI_OLLAMA_URL", "http://localhost:11434")
DEFAULT_OLLAMA_MODEL = os.environ.get("ENTERPRISE_AI_OLLAMA_MODEL", "llama3.2")


# === MODEL CAPABILITIES ===
class ModelFeature:
    """Model feature capabilities."""
    
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    CODE = "code"
    JSON_MODE = "json_mode"
    MULTI_MODAL = "multi_modal"
    THINKING = "thinking"
    REASONING = "reasoning"


# Export main constants (without tool enums that cause circular imports)
__all__ = [
    "PROJECT_ROOT", "CONFIG_DIR", "ENV_PREFIX",
    "DEFAULT_TEMPERATURE", "DEFAULT_MAX_TOKENS", "DEFAULT_TOP_P", 
    "DEFAULT_TIMEOUT", "DEFAULT_MAX_RETRIES",
    "OLLAMA_API_BASE", "DEFAULT_OLLAMA_MODEL", "ModelFeature"
]
