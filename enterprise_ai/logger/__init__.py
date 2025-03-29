"""
Logging system for Enterprise AI.

This module provides a centralized and configurable logging system for
all components of the Enterprise AI platform. It supports contextual logging,
multiple output destinations, and custom formatting.
"""

from enterprise_ai.logger.config import LoggerConfig
from enterprise_ai.logger.utils import (
    get_logger,
    debug,
    info,
    success,
    warning,
    error,
    critical,
    exception,
    configure,
    with_context,
    trace_execution,
    shutdown,
)

__all__ = [
    # Configuration
    "LoggerConfig",
    # Core functions
    "get_logger",
    # Direct logging functions
    "debug",
    "info",
    "success",
    "warning",
    "error",
    "critical",
    "exception",
    # Utilities
    "configure",
    "with_context",
    "trace_execution",
    "shutdown",
]
