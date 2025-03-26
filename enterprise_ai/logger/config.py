"""
Configuration for the Enterprise AI logger.

This module defines the configuration classes for the logging system,
including formatting, output destinations, and log levels.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from enterprise_ai.constants import (
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_CRITICAL,
    DEFAULT_LOG_FORMAT,
    LOGS_DIR,
    LOG_RETENTION_DAYS,
    MAX_LOG_FILE_SIZE,
)


class LoggerConfig:
    """Configuration for the logging system."""

    # Constants for log levels
    DEBUG = LOG_LEVEL_DEBUG
    INFO = LOG_LEVEL_INFO
    WARNING = LOG_LEVEL_WARNING
    ERROR = LOG_LEVEL_ERROR
    CRITICAL = LOG_LEVEL_CRITICAL

    def __init__(
        self,
        console_level: str = INFO,
        file_level: str = DEBUG,
        log_dir: Optional[Path] = None,
        format: str = DEFAULT_LOG_FORMAT,
        retention: str = f"{LOG_RETENTION_DAYS} days",
        rotation: str = f"{MAX_LOG_FILE_SIZE} bytes",
        enable_context: bool = True,
    ):
        """Initialize logger configuration.

        Args:
            console_level: Minimum level for console output
            file_level: Minimum level for file output
            log_dir: Directory to store log files (defaults to LOGS_DIR)
            format: Log message format
            retention: How long to keep log files
            rotation: When to rotate log files
            enable_context: Whether to enable contextual logging
        """
        self.console_level = console_level
        self.file_level = file_level
        self.log_dir = log_dir or LOGS_DIR
        self.format = format
        self.retention = retention
        self.rotation = rotation
        self.enable_context = enable_context

        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
