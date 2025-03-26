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
)

try:
    from loguru import logger as _logger
except ImportError:
    # Fallback for when loguru is not installed
    import logging as _logging

    _logger = _logging.getLogger("enterprise_ai")

from enterprise_ai.logger.config import LoggerConfig
from enterprise_ai.constants import LOGS_DIR

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


@runtime_checkable
class LoguruLogger(Protocol):
    """Protocol for a Loguru logger with added context attribute."""

    context: Dict[str, Any]

    def bind(self, **kwargs: Any) -> "LoguruLogger": ...
    def debug(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def info(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def success(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def warning(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def error(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def critical(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def exception(self, __message: Any, *args: Any, **kwargs: Any) -> None: ...
    def log(self, __level: Any, __message: Any, *args: Any, **kwargs: Any) -> None: ...


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

    def get_logger(self, name: str) -> LoguruLogger:
        """Get a logger for a specific component.

        Args:
            name: Name of the component

        Returns:
            Logger instance with component context
        """
        # Create a logger with name bound to the metadata
        bound_logger = _logger.bind(name=name)

        # Store the metadata in a property accessible for testing
        bound_logger.context = {"name": name}  # type: ignore

        return cast(LoguruLogger, bound_logger)

    def get_agent_logger(self, agent_id: str, agent_type: str) -> LoguruLogger:
        """Get a logger for a specific agent.

        Args:
            agent_id: Unique ID of the agent
            agent_type: Type of the agent

        Returns:
            Logger instance with agent context
        """
        context = {
            "name": "agent",
            "agent_id": agent_id,
            "agent_type": agent_type,
        }

        bound_logger = _logger.bind(**context)

        # Store the metadata in a property accessible for testing
        bound_logger.context = context  # type: ignore

        return cast(LoguruLogger, bound_logger)

    def get_team_logger(self, team_id: str) -> LoguruLogger:
        """Get a logger for a specific team.

        Args:
            team_id: Unique ID of the team

        Returns:
            Logger instance with team context
        """
        context = {
            "name": "team",
            "team_id": team_id,
        }

        bound_logger = _logger.bind(**context)

        # Store the metadata in a property accessible for testing
        bound_logger.context = context  # type: ignore

        return cast(LoguruLogger, bound_logger)

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

                    # Execute function with contextual logger
                    with _logger.contextualize(**self._context_var):
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


# Export common log functions directly
debug = _logger.debug
info = _logger.info
success = _logger.success
warning = _logger.warning
error = _logger.error
critical = _logger.critical
exception = _logger.exception

# Export logger configuration function
configure = logger_instance.configure

# Export context creation function
with_context = logger_instance.with_context

# Export logger getters
get_logger = logger_instance.get_logger
get_agent_logger = logger_instance.get_agent_logger
get_team_logger = logger_instance.get_team_logger

# Export execution tracing
trace_execution = logger_instance.trace_execution

# Export shutdown function
shutdown = shutdown_logging
