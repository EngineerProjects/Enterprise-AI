"""
Extraction methods for content extraction.

This module provides modular extraction methods that can be used
individually or as part of the cascade extraction system.
"""

from .base import BaseExtractionMethod, HTTPMethod, BrowserMethod, ExtractionResult
from .trafilatura import TrafilaturaMethod
from .readability import ReadabilityMethod
from .newspaper import NewspaperMethod
from .playwright import PlaywrightMethod
from .selenium import SeleniumMethod

# Export all extraction methods
__all__ = [
    # Base classes
    "BaseExtractionMethod",
    "HTTPMethod", 
    "BrowserMethod",
    "ExtractionResult",
    
    # Extraction methods (ordered by speed/reliability)
    "TrafilaturaMethod",      # Fastest, most reliable
    "ReadabilityMethod",      # Fast, good for main content
    "NewspaperMethod",        # Good for articles/news
    "PlaywrightMethod",       # Handles JS, moderate speed
    "SeleniumMethod",         # Slowest, last resort
]

# Method registry for dynamic loading
EXTRACTION_METHODS = {
    "trafilatura": TrafilaturaMethod,
    "requests_readability": ReadabilityMethod,  # Fixed name to match method
    "newspaper": NewspaperMethod,
    "playwright": PlaywrightMethod,
    "selenium": SeleniumMethod,
}

# Fast methods (should complete in <5 seconds)
FAST_METHODS = ["trafilatura", "requests_readability", "newspaper"]

# Slow methods (may take 10+ seconds)
SLOW_METHODS = ["playwright", "selenium"]

# Methods that require browser automation
BROWSER_METHODS = ["playwright", "selenium"]


def get_available_methods() -> list[str]:
    """Get list of available extraction methods (dependencies installed)."""
    available = []
    for name, method_class in EXTRACTION_METHODS.items():
        try:
            method = method_class()
            if method.is_available():
                available.append(name)
        except:
            pass
    return available


def create_method(method_name: str, timeout: int = 25, **kwargs) -> BaseExtractionMethod:
    """
    Create an extraction method instance.
    
    Args:
        method_name: Name of the method to create
        timeout: Timeout in seconds
        **kwargs: Additional method-specific configuration
        
    Returns:
        Configured extraction method instance
        
    Raises:
        ValueError: If method name is not recognized
        ImportError: If method dependencies are not available
    """
    if method_name not in EXTRACTION_METHODS:
        available = list(EXTRACTION_METHODS.keys())
        raise ValueError(f"Unknown method '{method_name}'. Available: {available}")
    
    method_class = EXTRACTION_METHODS[method_name]
    method = method_class(timeout=timeout, **kwargs)
    
    if not method.is_available():
        missing_deps = ", ".join(method.dependencies)
        raise ImportError(f"Method '{method_name}' dependencies not available: {missing_deps}")
    
    return method
