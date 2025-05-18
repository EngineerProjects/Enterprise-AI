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

T = TypeVar("T")


class TimerContext:
    """Context manager for timing code blocks."""

    def __init__(self, name: str) -> None:
        """Initialize the timer context.

        Args:
            name: Name for this timer
        """
        self.name = name
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None

    def __enter__(self) -> "TimerContext":
        """Start the timer."""
        self.start_time = datetime.datetime.now()
        logger.debug(f"Starting {self.name}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the timer and log the duration."""
        self.end_time = datetime.datetime.now()
        elapsed = (self.end_time - self.start_time).total_seconds() * 1000 if self.start_time else 0
        logger.debug(f"Completed {self.name} in {elapsed:.2f}ms")

    async def __aenter__(self) -> "TimerContext":
        """Start the timer in async context."""
        self.start_time = datetime.datetime.now()
        logger.debug(f"Starting async {self.name}")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the timer and log the duration in async context."""
        self.end_time = datetime.datetime.now()
        elapsed = (self.end_time - self.start_time).total_seconds() * 1000 if self.start_time else 0
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


def timer(name: Optional[str] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to time function execution.

    Args:
        name: Optional name for the timer

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
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
