"""
Custom log handlers for Enterprise AI.
This module provides specialized handlers for directing log messages to
different outputs, including console, files, and external services.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    from loguru import logger as loguru_logger
except ImportError:
    # Fallback for when loguru is not installed
    loguru_logger = None


class EnterpriseHandler:
    """Base class for Enterprise AI log handlers."""

    def __init__(self, level: str = "INFO"):
        """Initialize the handler.
        Args:
            level: Minimum log level to process
        """
        self.level = level
        self.handler_id: Optional[int] = None  # Explicitly type as Optional[int]

    def setup(self) -> int:
        """Set up the handler and return its ID.
        Returns:
            Handler ID for reference
        """
        raise NotImplementedError("Subclasses must implement setup()")

    def remove(self) -> None:
        """Remove the handler."""
        if self.handler_id is not None and loguru_logger is not None:
            loguru_logger.remove(self.handler_id)
        self.handler_id = None


class ConsoleHandler(EnterpriseHandler):
    """Handler for console output."""

    def __init__(self, level: str = "INFO", colorize: bool = True):
        """Initialize the console handler.
        Args:
            level: Minimum log level to process
            colorize: Whether to colorize output
        """
        super().__init__(level)
        self.colorize = colorize

    def setup(self) -> int:
        """Set up the console handler.
        Returns:
            Handler ID
        """
        if loguru_logger is None:
            return -1

        # Store result in a temporary variable to handle possible None
        result = loguru_logger.add(
            sys.stderr,
            level=self.level,
            colorize=self.colorize,
        )

        # Ensure we return an int even if result is None
        self.handler_id = -1 if result is None else result
        return self.handler_id


class FileHandler(EnterpriseHandler):
    """Handler for file output."""

    def __init__(
        self,
        file_path: Union[str, Path],
        level: str = "DEBUG",
        rotation: str = "10 MB",
        retention: str = "1 month",
        compression: str = "zip",
    ):
        """Initialize the file handler.
        Args:
            file_path: Path to log file
            level: Minimum log level to process
            rotation: When to rotate log files
            retention: How long to keep log files
            compression: Compression format for rotated logs
        """
        super().__init__(level)
        self.file_path = Path(file_path)
        self.rotation = rotation
        self.retention = retention
        self.compression = compression

    def setup(self) -> int:
        """Set up the file handler.
        Returns:
            Handler ID
        """
        if loguru_logger is None:
            return -1

        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Store result in a temporary variable to handle possible None
        result = loguru_logger.add(
            str(self.file_path),
            level=self.level,
            rotation=self.rotation,
            retention=self.retention,
            compression=self.compression,
        )

        # Ensure we return an int even if result is None
        self.handler_id = -1 if result is None else result
        return self.handler_id
