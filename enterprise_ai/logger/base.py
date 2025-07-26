"""
Base logging functionality for Enterprise AI.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

from enterprise_ai.defaults import DEFAULT_LOG_LEVEL, get_config_value

# Cache for loggers
_loggers: Dict[str, logging.Logger] = {}


def setup_logger(
    name: str, level: Optional[str] = None, log_file: Optional[str] = None
) -> logging.Logger:
    """
    Set up and configure a logger.

    Args:
        name: Logger name (usually module name)
        level: Logging level (DEBUG, INFO, etc.)
        log_file: Path to log file

    Returns:
        Configured logger instance
    """
    # Use smart defaults if not explicitly provided
    if level is None:
        level = get_config_value("logging.level", DEFAULT_LOG_LEVEL)

    if log_file is None:
        log_file = get_config_value("logging.file", "")

    # Set up the logger
    logger = logging.getLogger(name)

    # Only configure the logger once
    if logger.handlers:
        return logger

    # Set the logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Create formatter
    log_format = get_config_value(
        "logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    formatter = logging.Formatter(log_format)

    # Add console handler if enabled
    if get_config_value("logging.enable_console", True):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if configured
    if log_file:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name, creating it if necessary.

    Args:
        name: Logger name (usually module name)

    Returns:
        Logger instance
    """
    if name not in _loggers:
        _loggers[name] = setup_logger(name)
    return _loggers[name]
