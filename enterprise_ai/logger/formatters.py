"""
Custom log formatters for Enterprise AI.

This module provides specialized formatters for log messages, enabling
consistent and informative logging across the framework.
"""

from typing import Any, Dict, Optional, TYPE_CHECKING, Union, cast

# Type definitions for type checker only
if TYPE_CHECKING:
    from logging import Logger as StdLogger

    try:
        from loguru import Logger as LoguruLogger

        AnyLogger = Union["LoguruLogger", "StdLogger"]
    except ImportError:
        from logging import Logger as AnyLogger

# Runtime imports
try:
    from loguru import logger as loguru_logger

    HAS_LOGURU = True
except ImportError:
    # Fallback for when loguru is not installed
    import logging

    loguru_logger = None  # type: ignore
    HAS_LOGURU = False


class EnterpriseFormatter:
    """Custom formatter for Enterprise AI logs.

    This formatter enhances log records with additional information like
    component names, context, and structured data.
    """

    def __init__(self, format_string: Optional[str] = None):
        """Initialize the formatter.

        Args:
            format_string: Custom format string (uses default if None)
        """
        self.format_string = format_string or (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    def format(self, record: Dict[str, Any]) -> str:
        """Format a log record.

        Args:
            record: Log record dictionary

        Returns:
            Formatted log message
        """
        # Add extra fields to the record if needed
        if "extra" not in record:
            record["extra"] = {}

        # Return formatted message using loguru's default formatter
        # In a real implementation, you would process the format_string
        # and apply it to the record, but we're delegating to loguru here
        return self.format_string
