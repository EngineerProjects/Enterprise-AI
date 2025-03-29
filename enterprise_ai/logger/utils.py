"""
Utility functions for the Enterprise AI logger.

This module provides helper functions for logging, including context
management, decorators for tracing execution, and the core get_logger function.
"""

import atexit
import copy
import sys
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    cast,
    Protocol,
    runtime_checkable,
    TYPE_CHECKING,
    Union,
)

from enterprise_ai.logger.config import LoggerConfig
from enterprise_ai.constants import LOGS_DIR

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])

# For type checking
if TYPE_CHECKING:
    from logging import Logger as StdLogger

    try:
        from loguru import Logger as LoguruLogger

        AnyLogger = Union["LoguruLogger", "StdLogger"]
    except ImportError:
        from logging import Logger as AnyLogger


@runtime_checkable
class LoggerInterface(Protocol):
    """Protocol for logger interface with context attribute."""

    def bind(self, **kwargs: Any) -> Any: ...
    def debug(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def info(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def success(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def error(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def critical(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def exception(self, message: Any, *args: Any, **kwargs: Any) -> None: ...
    def log(self, level: Any, message: Any, *args: Any, **kwargs: Any) -> None: ...


# Runtime behavior - import actual modules
try:
    from loguru import logger as _logger

    HAS_LOGURU = True
except ImportError:
    # Fallback for when loguru is not installed
    import logging

    # Configure basic logging if loguru is not available
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _logger = logging.getLogger("enterprise_ai")  # type: ignore
    HAS_LOGURU = False


class EnterpriseLogger:
    """Centralized logging facility for Enterprise AI."""

    _instance: Optional["EnterpriseLogger"] = None
    _initialized: bool = False
    _context_var: Dict[str, Any] = {}
    _handler_ids: List[int] = []  # Track handler IDs for cleanup

    def __new__(cls, *args: Any, **kwargs: Any) -> "EnterpriseLogger":
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super(EnterpriseLogger, cls).__new__(cls)
        return cls._instance

    def __init__(self, logger_config: Optional[LoggerConfig] = None):
        """Initialize the logger.

        Args:
            logger_config: Configuration for the logger
        """
        # Only initialize once (singleton pattern)
        if self._initialized:
            return

        self._logger_config = logger_config or LoggerConfig()
        self._configure_logger()
        self._initialized = True

    def __enter__(self) -> "EnterpriseLogger":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Context manager exit with cleanup."""
        self.shutdown()

    def _configure_logger(self) -> None:
        """Configure the loguru logger with our settings."""
        # Only perform loguru-specific configuration if available
        if not HAS_LOGURU:
            return

        # Remove existing handlers and clear handler IDs
        for handler_id in self._handler_ids:
            try:
                _logger.remove(handler_id)
            except ValueError:
                # Handler already removed, just continue
                pass
        self._handler_ids.clear()

        try:
            _logger.remove()  # Remove any default handlers
        except ValueError:
            # No default handlers to remove
            pass

        # Add console handler
        console_handler_id = _logger.add(
            sys.stderr,
            level=self._logger_config.console_level,
            format=self._logger_config.format,
            colorize=True,
        )
        self._handler_ids.append(console_handler_id)

        # Add file handler
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = self._logger_config.log_dir / f"enterprise_ai_{current_time}.log"

        file_handler_id = _logger.add(
            log_file,
            level=self._logger_config.file_level,
            format=self._logger_config.format,
            rotation=self._logger_config.rotation,
            retention=self._logger_config.retention,
            compression="zip",
        )
        self._handler_ids.append(file_handler_id)

    def get_logger(self, name: str) -> Any:
        """Get a logger for a specific component.

        Args:
            name: Name of the component

        Returns:
            Logger instance with component context
        """
        if HAS_LOGURU:
            # Create a logger with name bound to the metadata
            bound_logger = _logger.bind(name=name)

            # Store the metadata in a property accessible for testing
            setattr(bound_logger, "context", {"name": name})

            return bound_logger
        else:
            # Use standard logging
            return logging.getLogger(f"enterprise_ai.{name}")

    def with_context(self, **context: Any) -> Callable:
        """Decorator to add context to log messages.

        Args:
            **context: Context key-value pairs

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Save original context (make a deep copy to avoid shared references)
                original_context = copy.deepcopy(self._context_var)

                try:
                    # Create new context by updating with provided context
                    new_context = {**original_context, **context}
                    self._context_var = new_context

                    # Execute function with contextual logger (if loguru is available)
                    if HAS_LOGURU:
                        with _logger.contextualize(**self._context_var):
                            return func(*args, **kwargs)
                    else:
                        # Standard logging doesn't support contextualization in the same way
                        return func(*args, **kwargs)
                finally:
                    # Always restore original context, even if an exception occurs
                    self._context_var = original_context

            return wrapper

        return decorator

    def trace_execution(self, name: Optional[str] = None) -> Callable:
        """Decorator to trace function execution with entry/exit logs.

        Args:
            name: Optional name for the trace (defaults to function name)

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            func_name = name or func.__name__

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _logger.debug(f"Entering {func_name}")
                try:
                    result = await func(*args, **kwargs)
                    _logger.debug(f"Exiting {func_name}")
                    return result
                except Exception as e:
                    _logger.exception(f"Error in {func_name}: {e}")
                    raise

            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                _logger.debug(f"Entering {func_name}")
                try:
                    result = func(*args, **kwargs)
                    _logger.debug(f"Exiting {func_name}")
                    return result
                except Exception as e:
                    _logger.exception(f"Error in {func_name}: {e}")
                    raise

            return async_wrapper if asyncio_iscoroutinefunction(func) else sync_wrapper

        return decorator

    def configure(self, new_config: LoggerConfig) -> None:
        """Reconfigure the logger with new settings.

        Args:
            new_config: New configuration for the logger
        """
        self._logger_config = new_config
        self._configure_logger()

    def shutdown(self) -> None:
        """Clean up resources and handlers when shutting down."""
        if HAS_LOGURU:
            for handler_id in self._handler_ids:
                try:
                    _logger.remove(handler_id)
                except ValueError:
                    # Handler already removed, just continue
                    pass
            self._handler_ids.clear()


# Determine if a function is a coroutine function (for trace_execution)
def asyncio_iscoroutinefunction(func: Callable) -> bool:
    """Check if a function is a coroutine function.

    This function handles various cases including wrapped functions and
    the case where asyncio is not available.

    Args:
        func: Function to check

    Returns:
        True if the function is a coroutine function, False otherwise
    """
    # First check for __await__ attribute (more reliable than asyncio.iscoroutinefunction)
    if hasattr(func, "__await__"):
        return True

    # Then check for _is_coroutine attribute (set by @asyncio.coroutine)
    if hasattr(func, "_is_coroutine"):
        return True

    # Unwrap any decorated functions to check the original
    original_func = func
    while hasattr(original_func, "__wrapped__"):
        original_func = original_func.__wrapped__
        if hasattr(original_func, "__await__") or hasattr(original_func, "_is_coroutine"):
            return True

    # Finally fall back to asyncio.iscoroutinefunction if available
    try:
        import asyncio

        if asyncio.iscoroutinefunction(func) or asyncio.iscoroutinefunction(original_func):
            return True
    except ImportError:
        pass

    return False


# Create global logger instance
logger_instance = EnterpriseLogger()


# Global shutdown function for cleanup at application exit
def shutdown_logging() -> None:
    """Clean up all logging resources."""
    try:
        global logger_instance
        if logger_instance is not None:
            logger_instance.shutdown()
    except Exception:
        # Suppress exceptions during shutdown to avoid error messages
        pass


# Register shutdown function with atexit
atexit.register(shutdown_logging)


# Export common log functions and utilities
def get_logger(name: str) -> Any:
    """Get a logger for a specific component."""
    return logger_instance.get_logger(name)


def debug(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log a debug message."""
    _logger.debug(message, *args, **kwargs)


def info(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log an info message."""
    _logger.info(message, *args, **kwargs)


def success(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log a success message."""
    if HAS_LOGURU:
        _logger.success(message, *args, **kwargs)
    else:
        # Standard logging doesn't have success, so use info
        _logger.info(f"SUCCESS: {message}", *args, **kwargs)


def warning(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log a warning message."""
    _logger.warning(message, *args, **kwargs)


def error(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log an error message."""
    _logger.error(message, *args, **kwargs)


def critical(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log a critical message."""
    _logger.critical(message, *args, **kwargs)


def exception(message: Any, *args: Any, **kwargs: Any) -> None:
    """Log an exception message."""
    _logger.exception(message, *args, **kwargs)


# Export configuration functions
configure = logger_instance.configure
with_context = logger_instance.with_context
trace_execution = logger_instance.trace_execution
shutdown = shutdown_logging
