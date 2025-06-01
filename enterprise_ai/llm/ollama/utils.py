"""
Utility functions for Ollama provider.

This module contains general utility functions used across the Ollama implementation.
"""

import json
import re
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from enterprise_ai.logger import get_logger

logger = get_logger("llm.ollama.utils")


def normalize_base_url(url: str) -> str:
    """
    Normalize Ollama base URL to consistent format.
    
    Args:
        url: Raw URL string
        
    Returns:
        Normalized URL without trailing /api or /
    """
    if not url:
        return "http://localhost:11434"
    
    # Parse URL to handle various formats
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"
    
    parsed = urlparse(url)
    
    # Rebuild URL without path
    normalized = f"{parsed.scheme}://{parsed.netloc}"
    
    # Remove common suffixes
    if normalized.endswith("/api"):
        normalized = normalized[:-4]
    if normalized.endswith("/"):
        normalized = normalized[:-1]
        
    return normalized


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON with fallback.
    
    Args:
        text: JSON string to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        logger.debug(f"JSON parsing failed: {e}")
        return default


def extract_json_objects(text: str) -> List[Dict[str, Any]]:
    """
    Extract all JSON objects from text content.
    
    Args:
        text: Text containing potential JSON objects
        
    Returns:
        List of parsed JSON objects
    """
    json_objects = []
    
    # Find JSON-like patterns
    patterns = [
        r'\{[^{}]*\}',  # Simple objects
        r'\{(?:[^{}]|\{[^{}]*\})*\}',  # Nested objects (one level)
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            obj = safe_json_loads(match)
            if obj and isinstance(obj, dict):
                json_objects.append(obj)
    
    return json_objects


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count for text.
    
    Args:
        text: Text to estimate tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Rough estimation: ~4 characters per token for English
    # This is very approximate but useful for basic checks
    return max(1, len(text) // 4)


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def merge_dicts(*dicts: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
    """
    Merge multiple dictionaries.
    
    Args:
        *dicts: Dictionaries to merge
        deep: Whether to perform deep merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    
    for d in dicts:
        if not isinstance(d, dict):
            continue
            
        if deep:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value
        else:
            result.update(d)
    
    return result


def sanitize_model_name(name: str) -> str:
    """
    Sanitize model name for safe usage.
    
    Args:
        name: Raw model name
        
    Returns:
        Sanitized model name
    """
    if not name:
        return "unknown"
    
    # Remove problematic characters
    sanitized = re.sub(r'[^\w\-\.\:]', '_', name)
    
    # Remove multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Strip leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    return sanitized or "unknown"


def format_size(size_bytes: int) -> str:
    """
    Format byte size as human-readable string.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable size string
    """
    if size_bytes == 0:
        return "0 B"
    
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"


def generate_request_id() -> str:
    """
    Generate a unique request ID.
    
    Returns:
        Unique request ID string
    """
    return f"req_{int(time.time() * 1000)}_{hash(time.time()) % 10000:04d}"


def validate_timeout(timeout: Union[int, float, None], default: float = 30.0) -> float:
    """
    Validate and normalize timeout value.
    
    Args:
        timeout: Timeout value to validate
        default: Default timeout if invalid
        
    Returns:
        Valid timeout value
    """
    if timeout is None:
        return default
    
    try:
        timeout_float = float(timeout)
        if timeout_float <= 0:
            logger.warning(f"Invalid timeout {timeout}, using default {default}")
            return default
        return timeout_float
    except (ValueError, TypeError):
        logger.warning(f"Invalid timeout {timeout}, using default {default}")
        return default

def is_valid_json(text: str) -> bool:
    """
    Check if text is valid JSON.
    
    Args:
        text: Text to check
        
    Returns:
        True if valid JSON, False otherwise
    """
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def clean_response_content(content: str) -> str:
    """
    Clean and normalize response content.
    
    Args:
        content: Raw response content
        
    Returns:
        Cleaned content
    """
    if not content:
        return ""
    
    # Remove excessive whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = re.sub(r'[ \t]+', ' ', content)
    
    # Trim
    content = content.strip()
    
    return content