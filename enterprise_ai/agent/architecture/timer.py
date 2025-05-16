#!/usr/bin/env python
"""
Enhanced Timer Context Class for Enterprise AI

This module provides an enhanced timer context class that addresses
issues with using timer in async code.
"""

import time
import datetime
import functools
import logging
import asyncio
from typing import Any, Callable, Optional, TypeVar, cast

from enterprise_ai.logger import get_logger

logger = get_logger("agent.utils.timer")

T = TypeVar('T')

class TimerContext:
    """Context manager for timing code blocks."""
    
    def __init__(self, name: str):
        """Initialize the timer context.
        
        Args:
            name: Name for this timer
        """
        self.name = name
        self.start_time = None
        self.end_time = None
        
    def __enter__(self):
        """Start the timer."""
        self.start_time = datetime.datetime.now()
        logger.debug(f"Starting {self.name}")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log the duration."""
        self.end_time = datetime.datetime.now()
        elapsed = (self.end_time - self.start_time).total_seconds() * 1000
        logger.debug(f"Completed {self.name} in {elapsed:.2f}ms")
        
    async def __aenter__(self):
        """Start the timer in async context."""
        self.start_time = datetime.datetime.now()
        logger.debug(f"Starting async {self.name}")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer and log the duration in async context."""
        self.end_time = datetime.datetime.now()
        elapsed = (self.end_time - self.start_time).total_seconds() * 1000
        logger.debug(f"Completed async {self.name} in {elapsed:.2f}ms")
        
    @property
    def duration(self) -> float:
        """Get the elapsed duration in seconds.
        
        Returns:
            Duration in seconds
        """
        if not self.start_time:
            return 0.0
            
        end = self.end_time or datetime.datetime.now()
        return (end - self.start_time).total_seconds()


def timer(name: Optional[str] = None) -> Callable:
    """Decorator to time function execution.
    
    Args:
        name: Optional name for the timer
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            timer_name = name or func.__name__
            start_time = datetime.datetime.now()
            logger.debug(f"Starting {timer_name}")
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = (datetime.datetime.now() - start_time).total_seconds() * 1000
                logger.debug(f"Completed {timer_name} in {elapsed:.2f}ms")
                
        return wrapper
        
    return decorator
