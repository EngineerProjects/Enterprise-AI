"""
Utility functions for the agent module.

This module provides common helper functions used across the agent system,
focusing on pure functions with minimal dependencies.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.types import MessageProtocol, Serializable

logger = get_logger("agent.utils")

T = TypeVar('T')


def generate_id(prefix: str = "") -> str:
    """Generate a unique identifier with optional prefix.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        Unique identifier string
    """
    id_value = str(uuid.uuid4())
    return f"{prefix}{id_value}" if prefix else id_value


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create an event loop for async operations.
    
    Returns:
        An asyncio event loop
    """
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        # If no event loop exists in this thread, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def run_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run an async function synchronously.
    
    Args:
        func: Async function to run
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the async function
    """
    loop = ensure_event_loop()
    if loop.is_running():
        # Create a task to be executed in the current running loop
        return asyncio.create_task(func(*args, **kwargs))
    else:
        # Run the function to completion in the loop
        return loop.run_until_complete(func(*args, **kwargs))


def safe_serialize(obj: Any) -> Dict[str, Any]:
    """Safely serialize an object to a dictionary.
    
    Args:
        obj: Object to serialize
        
    Returns:
        Dictionary representation
    """
    if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
        return cast(Serializable, obj).to_dict()
    elif hasattr(obj, '__dict__'):
        return dict(obj.__dict__)
    elif isinstance(obj, (dict, list, str, int, float, bool, type(None))):
        return obj if isinstance(obj, dict) else {"value": obj}
    else:
        return {"type": type(obj).__name__, "repr": repr(obj)}


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary to merge into the first
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursive merge for nested dictionaries
            result[key] = merge_dicts(result[key], value)
        else:
            # Replace or add value
            result[key] = value
            
    return result


def format_timestamp(timestamp: Optional[datetime] = None) -> str:
    """Format a timestamp for logging and display.
    
    Args:
        timestamp: Timestamp to format, or current time if None
        
    Returns:
        Formatted timestamp string
    """
    ts = timestamp or datetime.now()
    return ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def parse_tool_args(args_str: str) -> Dict[str, Any]:
    """Parse tool arguments from a string representation.
    
    Args:
        args_str: String representation of tool arguments
        
    Returns:
        Dictionary of parsed arguments
    """
    # Try parsing as JSON first
    try:
        return json.loads(args_str)
    except json.JSONDecodeError:
        # Fall back to parsing key=value pairs
        result = {}
        parts = args_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Handle different value types
                if value.lower() == 'true':
                    result[key] = True
                elif value.lower() == 'false':
                    result[key] = False
                elif value.isdigit():
                    result[key] = int(value)
                elif value.replace('.', '', 1).isdigit():
                    result[key] = float(value)
                else:
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    result[key] = value
        
        return result


def deduplicate_list(items: List[T]) -> List[T]:
    """Remove duplicates from a list while preserving order.
    
    Args:
        items: List to deduplicate
        
    Returns:
        Deduplicated list
    """
    seen: Set[Any] = set()
    result: List[T] = []
    
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
            
    return result


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length with a suffix.
    
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


def timer(name: Optional[str] = None) -> Callable:
    """Decorator to time function execution.
    
    Args:
        name: Optional name for the timer
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            timer_name = name or func.__name__
            start_time = datetime.now()
            logger.debug(f"Starting {timer_name}")
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                logger.debug(f"Completed {timer_name} in {elapsed:.2f}ms")
                
        return wrapper
        
    return decorator