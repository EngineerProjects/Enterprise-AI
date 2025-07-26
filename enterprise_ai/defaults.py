"""
Smart defaults for Enterprise AI package.

This module provides sensible defaults that work out-of-the-box,
with optional environment variable overrides.
"""

import os
from typing import Dict, Any, Optional


# === LLM DEFAULTS ===
DEFAULT_LLM_TIMEOUT = float(os.environ.get("ENTERPRISE_AI_TIMEOUT", "60.0"))
DEFAULT_LLM_TEMPERATURE = float(os.environ.get("ENTERPRISE_AI_TEMPERATURE", "0.7"))
DEFAULT_LLM_MAX_TOKENS = int(os.environ.get("ENTERPRISE_AI_MAX_TOKENS", "1024"))
DEFAULT_LLM_TOP_P = float(os.environ.get("ENTERPRISE_AI_TOP_P", "1.0"))
DEFAULT_MAX_RETRIES = int(os.environ.get("ENTERPRISE_AI_MAX_RETRIES", "3"))

# Ollama defaults
DEFAULT_OLLAMA_MODEL = os.environ.get("ENTERPRISE_AI_OLLAMA_MODEL", "llama3.2")
DEFAULT_OLLAMA_BASE_URL = os.environ.get("ENTERPRISE_AI_OLLAMA_URL", "http://localhost:11434")
DEFAULT_OLLAMA_TIMEOUT = float(os.environ.get("ENTERPRISE_AI_OLLAMA_TIMEOUT", "1200.0"))

# OpenAI defaults
DEFAULT_OPENAI_MODEL = os.environ.get("ENTERPRISE_AI_OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_OPENAI_TIMEOUT = float(os.environ.get("ENTERPRISE_AI_OPENAI_TIMEOUT", "60.0"))


# === TOOL DEFAULTS ===
DEFAULT_TOOL_TIMEOUT = float(os.environ.get("ENTERPRISE_AI_TOOL_TIMEOUT", "30.0"))
DEFAULT_MAX_ITERATIONS = int(os.environ.get("ENTERPRISE_AI_MAX_ITERATIONS", "5"))


# === BROWSER DEFAULTS ===
DEFAULT_BROWSER_HEADLESS = os.environ.get("ENTERPRISE_AI_BROWSER_HEADLESS", "true").lower() == "true"
DEFAULT_BROWSER_DISABLE_SECURITY = os.environ.get("ENTERPRISE_AI_BROWSER_DISABLE_SECURITY", "true").lower() == "true"


# === RESEARCH DEFAULTS ===
DEFAULT_RESEARCH_DEPTH = int(os.environ.get("ENTERPRISE_AI_RESEARCH_DEPTH", "2"))
DEFAULT_RESEARCH_MAX_INSIGHTS = int(os.environ.get("ENTERPRISE_AI_RESEARCH_MAX_INSIGHTS", "20"))
DEFAULT_RESEARCH_RESULTS_PER_SEARCH = int(os.environ.get("ENTERPRISE_AI_RESEARCH_RESULTS_PER_SEARCH", "5"))


# === SANDBOX DEFAULTS ===
DEFAULT_SANDBOX_IMAGE = os.environ.get("ENTERPRISE_AI_SANDBOX_IMAGE", "python:3.12-slim")
DEFAULT_SANDBOX_MEMORY = os.environ.get("ENTERPRISE_AI_SANDBOX_MEMORY", "512m")
DEFAULT_SANDBOX_CPU_LIMIT = float(os.environ.get("ENTERPRISE_AI_SANDBOX_CPU_LIMIT", "0.5"))
DEFAULT_SANDBOX_TIMEOUT = int(os.environ.get("ENTERPRISE_AI_SANDBOX_TIMEOUT", "60"))
DEFAULT_SANDBOX_NETWORK = os.environ.get("ENTERPRISE_AI_SANDBOX_NETWORK", "false").lower() == "true"


# === LOGGING DEFAULTS ===
DEFAULT_LOG_LEVEL = os.environ.get("ENTERPRISE_AI_LOG_LEVEL", "INFO")
DEFAULT_VERBOSE = os.environ.get("ENTERPRISE_AI_VERBOSE", "false").lower() == "true"


def get_default_llm_config(provider: str = "ollama") -> Dict[str, Any]:
    """
    Get default LLM configuration for a provider.
    
    Args:
        provider: LLM provider name ("ollama", "openai")
        
    Returns:
        Default configuration dictionary
    """
    base_config = {
        "timeout": DEFAULT_LLM_TIMEOUT,
        "temperature": DEFAULT_LLM_TEMPERATURE,
        "max_tokens": DEFAULT_LLM_MAX_TOKENS,
        "top_p": DEFAULT_LLM_TOP_P,
        "max_retries": DEFAULT_MAX_RETRIES,
    }
    
    if provider.lower() == "ollama":
        base_config.update({
            "model_name": DEFAULT_OLLAMA_MODEL,
            "base_url": DEFAULT_OLLAMA_BASE_URL,
            "timeout": DEFAULT_OLLAMA_TIMEOUT,
        })
    elif provider.lower() == "openai":
        base_config.update({
            "model_name": DEFAULT_OPENAI_MODEL,
            "timeout": DEFAULT_OPENAI_TIMEOUT,
        })
    
    return base_config


def get_default_tool_config() -> Dict[str, Any]:
    """Get default tool configuration."""
    return {
        "timeout": DEFAULT_TOOL_TIMEOUT,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
        "verbose": DEFAULT_VERBOSE,
    }


def get_default_browser_config() -> Dict[str, Any]:
    """Get default browser configuration."""
    return {
        "headless": DEFAULT_BROWSER_HEADLESS,
        "disable_security": DEFAULT_BROWSER_DISABLE_SECURITY,
        "extra_chromium_args": [],
    }


def get_default_research_config() -> Dict[str, Any]:
    """Get default research configuration."""
    return {
        "default_depth": DEFAULT_RESEARCH_DEPTH,
        "max_insights": DEFAULT_RESEARCH_MAX_INSIGHTS,
        "results_per_search": DEFAULT_RESEARCH_RESULTS_PER_SEARCH,
        "content_analysis_timeout": 120.0,
        "search_engines": ["google", "bing", "duckduckgo"],
    }


def get_env_override(key: str, default: Any = None) -> Any:
    """
    Get environment variable override for a configuration key.
    
    Args:
        key: Configuration key (e.g., "llm.timeout")
        default: Default value if not found
        
    Returns:
        Environment value or default
    """
    env_key = f"ENTERPRISE_AI_{key.upper().replace('.', '_')}"
    return os.environ.get(env_key, default)


# === OPTIONAL CONFIG FILE SUPPORT ===
def load_optional_config() -> Dict[str, Any]:
    """
    Load optional configuration file if it exists.
    
    This is for advanced users who want file-based configuration.
    The package works perfectly without any config files.
    
    Returns:
        Configuration dictionary (empty if no file found)
    """
    try:
        import yaml
    except ImportError:
        # PyYAML not installed, skip config file support
        return {}
    
    # Look for config in common locations (but don't require it)
    possible_paths = [
        "enterprise_ai_config.yml",
        "~/.enterprise_ai/config.yml",
        os.path.expanduser("~/.config/enterprise_ai/config.yml"),
        "/etc/enterprise_ai/config.yml"
    ]
    
    for path_str in possible_paths:
        path = os.path.expanduser(path_str)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                continue  # Config file issues are not fatal
    
    return {}  # No config found, that's perfectly fine


def get_default_sandbox_config() -> Dict[str, Any]:
    """Get default sandbox configuration."""
    return {
        "image": DEFAULT_SANDBOX_IMAGE,
        "memory_limit": DEFAULT_SANDBOX_MEMORY,
        "cpu_limit": DEFAULT_SANDBOX_CPU_LIMIT,
        "timeout": DEFAULT_SANDBOX_TIMEOUT,
        "network_enabled": DEFAULT_SANDBOX_NETWORK,
        "work_dir": "/workspace",
    }


def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get configuration value with smart fallback chain.
    
    Priority order:
    1. Environment variables (ENTERPRISE_AI_*)
    2. Optional config file (if exists)
    3. Provided default
    
    Args:
        key: Configuration key (e.g., "llm.timeout")
        default: Default value
        
    Returns:
        Configuration value
    """
    # 1. Check environment first (highest priority)
    env_value = get_env_override(key)
    if env_value is not None:
        return env_value
    
    # 2. Check optional config file
    config = load_optional_config()
    if config:
        parts = key.split('.')
        current = config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                break
        else:
            return current  # Found in config file
    
    # 3. Return default
    return default
