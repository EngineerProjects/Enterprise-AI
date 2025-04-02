"""
Constants and paths for Enterprise AI.

This module defines global constants and paths used throughout the Enterprise AI
framework, organized by functional area.
"""

import os
from pathlib import Path
from typing import Dict, List, Set, Final, Any, Optional, cast

# -----------------------------------------------------------------------------
# System Paths
# -----------------------------------------------------------------------------


def get_project_root() -> Path:
    """Get the project root directory.

    This function identifies the root path of the project regardless of how
    it's installed or where it's running from.

    Returns:
        Path to the project root directory
    """
    # First try to find the module's parent directory
    module_path = Path(__file__).resolve().parent.parent

    # Check if this looks like our project structure
    if (module_path / "enterprise_ai").exists():
        return module_path

    # Fallback for installed packages or other environments
    return Path(os.getcwd())


# Core path constants
PROJECT_ROOT: Final[Path] = get_project_root()
WORKSPACE_ROOT: Final[Path] = PROJECT_ROOT / "workspace"
LOGS_DIR: Final[Path] = WORKSPACE_ROOT / "logs"
CACHE_DIR: Final[Path] = WORKSPACE_ROOT / "cache"
CONFIG_DIR: Final[Path] = PROJECT_ROOT / "config"
DEFAULT_CONFIGS_DIR: Final[Path] = Path(__file__).parent / "default_configs"
TEMPLATES_DIR: Final[Path] = PROJECT_ROOT / "templates"

# Ensure essential directories exist
os.makedirs(WORKSPACE_ROOT, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Default configuration file paths
DEFAULT_CONFIG_PATH: Final[str] = str(CONFIG_DIR / "config.yaml")
DEFAULT_CONFIG_TOML: Final[str] = str(CONFIG_DIR / "config.toml")
DEFAULT_CONFIG_YAML: Final[str] = str(CONFIG_DIR / "config.yaml")

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
}

# -----------------------------------------------------------------------------
# LLM Constants
# -----------------------------------------------------------------------------

# Provider identifiers
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_ANTHROPIC: Final[str] = "anthropic"
PROVIDER_OLLAMA: Final[str] = "ollama"

# Supported providers
SUPPORTED_PROVIDERS: Final[Set[str]] = {
    PROVIDER_OPENAI,
    PROVIDER_ANTHROPIC,
    PROVIDER_OLLAMA,
}

# Default model parameters
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_MAX_TOKENS: Final[int] = 1024
DEFAULT_TOP_P: Final[float] = 1.0

# Default LLM configuration
DEFAULT_LLM_CONFIG: Final[Dict[str, Dict[str, Any]]] = {
    "openai": {
        "api_type": "openai",
        "model": "gpt-4o",
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "top_p": DEFAULT_TOP_P,
    },
    "anthropic": {
        "api_type": "anthropic",
        "model": "claude-3-sonnet",
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "top_p": DEFAULT_TOP_P,
    },
    "ollama": {
        "api_type": "ollama",
        "base_url": "http://localhost:11434",
        "model": "llama3",
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "top_p": DEFAULT_TOP_P,
    },
}

# Default provider
DEFAULT_PROVIDER: Final[str] = "ollama"

# Request timeouts (in seconds)
DEFAULT_REQUEST_TIMEOUT: Final[float] = 60.0
STREAMING_REQUEST_TIMEOUT: Final[float] = 300.0
CONNECTION_TIMEOUT: Final[float] = 10.0

# Ollama API endpoints
OLLAMA_GENERATE_PATH: Final[str] = "api/generate"
OLLAMA_CHAT_PATH: Final[str] = "api/chat"
OLLAMA_TAGS_PATH: Final[str] = "api/tags"
OLLAMA_SHOW_PATH: Final[str] = "api/show"

# -----------------------------------------------------------------------------
# LLM Caching and Model Settings
# -----------------------------------------------------------------------------

# Caching constants
DEFAULT_CACHE_TTL: Final[int] = 3600  # 1 hour in seconds
MAX_CACHE_SIZE_MB: Final[int] = 1024  # 1 GB
MAX_CACHE_ENTRIES: Final[int] = 10000  # Maximum number of entries

# Model context sizes (maximum tokens per model)
MODEL_CONTEXT_SIZES: Final[Dict[str, int]] = {
    "gpt-3.5-turbo": 16385,
    "gpt-4": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
}

# Default models by provider
DEFAULT_MODELS: Final[Dict[str, str]] = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-sonnet",
    "ollama": "llama3",
    "cohere": "command-r-plus",
    "default": "gpt-4o",
}

# Provider rate limits (requests per minute)
PROVIDER_RATE_LIMITS: Final[Dict[str, float]] = {
    "openai": 60.0,
    "anthropic": 40.0,
    "ollama": 300.0,
    "default": 60.0,
}

# Retry configuration
MAX_RETRIES: Final[int] = 3

# -----------------------------------------------------------------------------
# Logging Constants
# -----------------------------------------------------------------------------

# Log levels as named constants
LOG_LEVEL_DEBUG: Final[str] = "DEBUG"
LOG_LEVEL_INFO: Final[str] = "INFO"
LOG_LEVEL_WARNING: Final[str] = "WARNING"
LOG_LEVEL_ERROR: Final[str] = "ERROR"
LOG_LEVEL_CRITICAL: Final[str] = "CRITICAL"

# Default logging format
DEFAULT_LOG_FORMAT: Final[str] = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# Maximum log file size before rotation (in bytes)
MAX_LOG_FILE_SIZE: Final[int] = 10  # 10 MB

# Log retention periods
LOG_RETENTION_DAYS: Final[int] = 30  # 30 days

# -----------------------------------------------------------------------------
# Security Constants
# -----------------------------------------------------------------------------

# Default sandbox execution environment
SANDBOX_DEFAULT_IMAGE: Final[str] = "python:3.12-slim"
SANDBOX_MEMORY_LIMIT: Final[str] = "512m"
SANDBOX_CPU_LIMIT: Final[float] = 1.0

# Potentially unsafe operations that require special permissions
UNSAFE_FILE_EXTENSIONS: Final[Set[str]] = {
    ".sh",
    ".exe",
    ".bat",
    ".cmd",
    ".ps1",
    ".vbs",
    ".js",
    ".dll",
    ".so",
    ".dylib",
    ".py",
    ".rb",
}

# Paths that should be protected from tool access
PROTECTED_PATHS: Final[List[str]] = [
    "/etc",
    "/var",
    "/bin",
    "/sbin",
    "/usr",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "/root",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Users\\Administrator",
]

# Python modules that should be restricted in sandboxed execution
RESTRICTED_MODULES: Final[Set[str]] = {
    "os.system",
    "subprocess",
    "importlib",
    "builtins.exec",
    "builtins.eval",
    "pty",
    "socket",
    "shutil.rmtree",
    "sys.modules",
}
