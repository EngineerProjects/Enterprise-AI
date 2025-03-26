"""
Constants and paths for Enterprise AI.

This module defines global constants and paths used throughout the Enterprise AI
framework, ensuring they are centrally defined and can be imported without causing
circular dependencies. These constants are used across the system for configuration,
file operations, token management, and other core functionality.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Final, Union


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
WORKSPACE_ROOT.mkdir(exist_ok=True, parents=True)
LOGS_DIR.mkdir(exist_ok=True, parents=True)
CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Default configuration file paths
DEFAULT_CONFIG_PATH: Final[str] = str(CONFIG_DIR / "config.yaml")
DEFAULT_CONFIG_TOML: Final[str] = str(CONFIG_DIR / "config.toml")
DEFAULT_CONFIG_YAML: Final[str] = str(CONFIG_DIR / "config.yaml")


# -----------------------------------------------------------------------------
# LLM Constants
# -----------------------------------------------------------------------------

# Default model parameters
DEFAULT_TEMPERATURE: Final[float] = 0.7
DEFAULT_MAX_TOKENS: Final[int] = 1024
DEFAULT_TOP_P: Final[float] = 1.0
DEFAULT_FREQUENCY_PENALTY: Final[float] = 0.0
DEFAULT_PRESENCE_PENALTY: Final[float] = 0.0

# Default context window sizes for different model types
# These are conservative defaults that can be overridden in config
MODEL_CONTEXT_SIZES: Final[Dict[str, int]] = {
    # OpenAI models
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    # Anthropic models
    "claude-2": 100000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
    # Open source models
    "llama2": 4096,
    "llama3": 8192,
    "mistral": 8192,
    "mixtral": 32768,
    "phi": 2048,
    "gemma": 8192,
}

# Default model for each provider
DEFAULT_MODELS: Final[Dict[str, str]] = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-sonnet",
    "ollama": "llama3",
    "default": "gpt-4o",
}

# Request timeouts (in seconds)
DEFAULT_REQUEST_TIMEOUT: Final[float] = 60.0
STREAMING_REQUEST_TIMEOUT: Final[float] = 300.0
CONNECTION_TIMEOUT: Final[float] = 10.0
ASYNC_TIMEOUT: Final[float] = 90.0

# Retry configuration
MAX_RETRIES: Final[int] = 3
RETRY_INITIAL_DELAY: Final[float] = 1.0
RETRY_MAX_DELAY: Final[float] = 60.0
RETRY_BACKOFF_FACTOR: Final[float] = 2.0

# Provider rate limits (requests per minute)
PROVIDER_RATE_LIMITS: Final[Dict[str, float]] = {
    "openai": 60.0,  # 60 requests per minute for OpenAI
    "anthropic": 30.0,  # 30 requests per minute for Anthropic
    "ollama": 20.0,  # 20 requests per minute for Ollama (local)
    "default": 30.0,  # Default for other providers
}

# Cache constants
DEFAULT_CACHE_TTL: Final[int] = 3600  # 1 hour in seconds
MAX_CACHE_SIZE_MB: Final[int] = 500  # 500 MB
MAX_CACHE_ENTRIES: Final[int] = 1000  # 1000 entries
CACHE_RETENTION_DAYS: Final[int] = 7  # 7 days


# -----------------------------------------------------------------------------
# Message Constants
# -----------------------------------------------------------------------------

# Maximum allowed length for different message components (in characters)
MAX_CONTENT_LENGTH: Final[int] = 100000
MAX_NAME_LENGTH: Final[int] = 64
MAX_TOOL_NAME_LENGTH: Final[int] = 64
MAX_SYSTEM_PROMPT_LENGTH: Final[int] = 32000

# Special tokens or markers for message processing
SYSTEM_PROMPT_MARKER: Final[str] = "<system>"
SYSTEM_PROMPT_END_MARKER: Final[str] = "</system>"
USER_PROMPT_MARKER: Final[str] = "<user>"
USER_PROMPT_END_MARKER: Final[str] = "</user>"
ASSISTANT_RESPONSE_MARKER: Final[str] = "<assistant>"
ASSISTANT_RESPONSE_END_MARKER: Final[str] = "</assistant>"
TOOL_RESPONSE_MARKER: Final[str] = "<tool>"
TOOL_RESPONSE_END_MARKER: Final[str] = "</tool>"


# -----------------------------------------------------------------------------
# Tool Constants
# -----------------------------------------------------------------------------

# Default operation timeouts for different tool types (in seconds)
TOOL_DEFAULT_TIMEOUT: Final[float] = 30.0
FILE_OPERATION_TIMEOUT: Final[float] = 10.0
PYTHON_EXECUTION_TIMEOUT: Final[float] = 60.0
TERMINAL_COMMAND_TIMEOUT: Final[float] = 30.0
WEB_REQUEST_TIMEOUT: Final[float] = 30.0
DATABASE_QUERY_TIMEOUT: Final[float] = 60.0

# File size limits for different operations (in bytes)
MAX_FILE_READ_SIZE: Final[int] = 10 * 1024 * 1024  # 10 MB
MAX_FILE_WRITE_SIZE: Final[int] = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_SIZE: Final[int] = 5 * 1024 * 1024  # 5 MB


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
MAX_LOG_FILE_SIZE: Final[int] = 10 * 1024 * 1024  # 10 MB

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
