"""
Error handling system for agent module.

This module provides centralized error handling, classification,
and recovery strategies for the agent system.
"""

import asyncio
import time
import random
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar, Union, cast

from enterprise_ai.exceptions import EnterpriseAIError
from enterprise_ai.logger import get_logger

logger = get_logger("agent.errors")


class AgentErrorCode(str, Enum):
    """Error codes for agent system errors."""
    
    # General errors
    UNKNOWN = "UNKNOWN"
    INITIALIZATION_FAILED = "INITIALIZATION_FAILED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    
    # Runtime errors
    EXECUTION_FAILED = "EXECUTION_FAILED"
    TIMEOUT = "TIMEOUT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    
    # Tool errors
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    TOOL_INITIALIZATION_FAILED = "TOOL_INITIALIZATION_FAILED"
    INVALID_TOOL_PARAMETERS = "INVALID_TOOL_PARAMETERS"
    
    # Communication errors
    NETWORK_ERROR = "NETWORK_ERROR"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    API_ERROR = "API_ERROR"
    
    # LLM errors
    LLM_ERROR = "LLM_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    CONTENT_FILTER = "CONTENT_FILTER"
    
    # State errors
    STATE_ERROR = "STATE_ERROR"
    PERSISTENCE_ERROR = "PERSISTENCE_ERROR"
    
    # Permission errors
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"


class ErrorSeverity(str, Enum):
    """Severity levels for errors."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(str, Enum):
    """Categories of errors."""
    
    TRANSIENT = "TRANSIENT"  # Temporary errors that may resolve with retry
    PERMANENT = "PERMANENT"  # Permanent errors that won't resolve with retry
    CONFIGURATION = "CONFIGURATION"  # Errors in configuration
    RESOURCE = "RESOURCE"  # Resource-related errors
    PERMISSION = "PERMISSION"  # Permission and access errors
    SYSTEM = "SYSTEM"  # System-level errors
    USER = "USER"  # User-related errors


class AgentError(EnterpriseAIError):
    """Base class for agent system errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Union[AgentErrorCode, str] = AgentErrorCode.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        is_retryable: bool = False,
    ):
        """Initialize an agent error.
        
        Args:
            message: Error message
            error_code: Error code
            severity: Error severity
            category: Error category
            details: Additional error details
            cause: Original exception that caused this error
            is_retryable: Whether this error is retryable
        """
        self.error_code = error_code if isinstance(error_code, AgentErrorCode) else error_code
        self.severity = severity
        self.category = category
        self.details = details or {}
        self.cause = cause
        self.is_retryable = is_retryable
        self.timestamp = datetime.now()
        
        # Construct full message
        full_message = f"{self.error_code}: {message}"
        if cause:
            full_message += f" Caused by: {str(cause)}"
            
        super().__init__(full_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation.
        
        Returns:
            Dictionary representation of the error
        """
        return {
            "error_code": str(self.error_code),
            "message": str(self),
            "severity": str(self.severity),
            "category": str(self.category),
            "details": self.details,
            "is_retryable": self.is_retryable,
            "timestamp": self.timestamp.isoformat(),
        }


class ToolError(AgentError):
    """Error related to tool execution or management."""
    
    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        error_code: Union[AgentErrorCode, str] = AgentErrorCode.TOOL_EXECUTION_FAILED,
        **kwargs: Any,
    ):
        """Initialize a tool error.
        
        Args:
            message: Error message
            tool_name: Name of the tool
            error_code: Error code
            **kwargs: Additional arguments to pass to AgentError
        """
        details = kwargs.pop("details", {}) or {}
        if tool_name:
            details["tool_name"] = tool_name
            
        super().__init__(message, error_code=error_code, details=details, **kwargs)


class LLMError(AgentError):
    """Error related to LLM operations."""
    
    def __init__(
        self,
        message: str,
        model_name: Optional[str] = None,
        error_code: Union[AgentErrorCode, str] = AgentErrorCode.LLM_ERROR,
        **kwargs: Any,
    ):
        """Initialize an LLM error.
        
        Args:
            message: Error message
            model_name: Name of the LLM model
            error_code: Error code
            **kwargs: Additional arguments to pass to AgentError
        """
        details = kwargs.pop("details", {}) or {}
        if model_name:
            details["model_name"] = model_name
            
        super().__init__(message, error_code=error_code, details=details, **kwargs)


class StateError(AgentError):
    """Error related to agent state management."""
    
    def __init__(
        self,
        message: str,
        agent_id: Optional[str] = None,
        error_code: Union[AgentErrorCode, str] = AgentErrorCode.STATE_ERROR,
        **kwargs: Any,
    ):
        """Initialize a state error.
        
        Args:
            message: Error message
            agent_id: ID of the agent
            error_code: Error code
            **kwargs: Additional arguments to pass to AgentError
        """
        details = kwargs.pop("details", {}) or {}
        if agent_id:
            details["agent_id"] = agent_id
            
        super().__init__(message, error_code=error_code, details=details, **kwargs)


class ErrorManager:
    """Manager for handling errors in the agent system."""
    
    def __init__(self, agent_id: Optional[str] = None):
        """Initialize the error manager.
        
        Args:
            agent_id: Optional ID of the associated agent
        """
        self.agent_id = agent_id
        self._error_counts: Dict[str, int] = {}
        self._error_history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._circuit_breakers: Dict[str, Dict[str, Any]] = {}
    
    def handle_error(
        self,
        error: Union[Exception, str],
        error_code: Optional[Union[AgentErrorCode, str]] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentError:
        """Handle an error.
        
        Args:
            error: The error to handle
            error_code: Optional error code
            category: Optional error category
            severity: Optional error severity
            context: Optional error context
            
        Returns:
            Processed agent error
        """
        # Convert string to exception
        if isinstance(error, str):
            error_message = error
            error = Exception(error_message)
        else:
            error_message = str(error)
        
        # Get error code
        if error_code is None:
            if isinstance(error, AgentError):
                error_code = error.error_code
            else:
                error_code = AgentErrorCode.UNKNOWN
        
        # Get category
        if category is None:
            if isinstance(error, AgentError):
                category = error.category
            else:
                category = ErrorCategory.SYSTEM
        
        # Get severity
        if severity is None:
            if isinstance(error, AgentError):
                severity = error.severity
            else:
                severity = ErrorSeverity.ERROR
        
        # Create or use the agent error
        if isinstance(error, AgentError):
            agent_error = error
        else:
            # Determine if error is retryable based on category
            is_retryable = category == ErrorCategory.TRANSIENT
            
            # Create agent error
            agent_error = AgentError(
                message=error_message,
                error_code=error_code,
                severity=severity,
                category=category,
                details=context or {},
                cause=error if not isinstance(error, str) else None,
                is_retryable=is_retryable,
            )
        
        # Track error
        self._track_error(agent_error)
        
        # Log error
        self._log_error(agent_error)
        
        return agent_error
    
    def _track_error(self, error: AgentError) -> None:
        """Track error for monitoring and circuit breaking.
        
        Args:
            error: The error to track
        """
        # Increment error count
        error_key = str(error.error_code)
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        
        # Add to history
        self._error_history.append(error.to_dict())
        if len(self._error_history) > self._max_history:
            self._error_history = self._error_history[-self._max_history:]
        
        # Check circuit breakers
        if error_key in self._circuit_breakers:
            circuit = self._circuit_breakers[error_key]
            circuit["count"] += 1
            
            # Check if circuit should trip
            if circuit["count"] >= circuit["threshold"]:
                circuit["tripped"] = True
                circuit["tripped_at"] = datetime.now()
                
                # Log circuit breaker tripped
                service = circuit.get("service")
                logger.warning(
                    f"Circuit breaker tripped for {error_key}" + 
                    (f" ({service})" if service else "")
                )
    
    def _log_error(self, error: AgentError) -> None:
        """Log error with appropriate severity.
        
        Args:
            error: The error to log
        """
        message = f"{error}"
        if self.agent_id:
            message = f"[Agent {self.agent_id}] {message}"
        
        if error.severity == ErrorSeverity.DEBUG:
            logger.debug(message)
        elif error.severity == ErrorSeverity.INFO:
            logger.info(message)
        elif error.severity == ErrorSeverity.WARNING:
            logger.warning(message)
        elif error.severity == ErrorSeverity.ERROR:
            logger.error(message)
        elif error.severity == ErrorSeverity.CRITICAL:
            logger.critical(message)
    
    def set_circuit_breaker(
        self,
        error_code: Union[AgentErrorCode, str],
        threshold: int,
        reset_after: float,
        service: Optional[str] = None,
    ) -> None:
        """Set up a circuit breaker for a specific error code.
        
        Args:
            error_code: Error code to monitor
            threshold: Number of errors before tripping
            reset_after: Seconds after which to reset the circuit
            service: Optional service name for logging
        """
        error_key = str(error_code)
        self._circuit_breakers[error_key] = {
            "threshold": threshold,
            "reset_after": reset_after,
            "count": 0,
            "tripped": False,
            "tripped_at": None,
            "service": service,
        }
    
    def check_circuit_breaker(self, error_code: Union[AgentErrorCode, str]) -> bool:
        """Check if a circuit breaker is tripped.
        
        Args:
            error_code: Error code to check
            
        Returns:
            True if circuit is tripped, False otherwise
        """
        error_key = str(error_code)
        if error_key not in self._circuit_breakers:
            return False
        
        circuit = self._circuit_breakers[error_key]
        if not circuit["tripped"]:
            return False
        
        # Check if circuit should be reset
        if circuit["tripped_at"] is not None:
            elapsed = (datetime.now() - circuit["tripped_at"]).total_seconds()
            if elapsed >= circuit["reset_after"]:
                # Reset circuit
                circuit["tripped"] = False
                circuit["count"] = 0
                circuit["tripped_at"] = None
                
                # Log circuit breaker reset
                service = circuit.get("service")
                logger.info(
                    f"Circuit breaker reset for {error_key}" + 
                    (f" ({service})" if service else "")
                )
                return False
        
        return True
    
    def reset_circuit_breaker(self, error_code: Union[AgentErrorCode, str]) -> None:
        """Manually reset a circuit breaker.
        
        Args:
            error_code: Error code to reset
        """
        error_key = str(error_code)
        if error_key in self._circuit_breakers:
            circuit = self._circuit_breakers[error_key]
            circuit["tripped"] = False
            circuit["count"] = 0
            circuit["tripped_at"] = None


class RetryOptions:
    """Options for retry operations."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.1,
    ):
        """Initialize retry options.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Factor to increase delay by after each attempt
            jitter: Random jitter factor to add to delay
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a retry attempt.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Calculate base exponential backoff
        delay = self.base_delay * (self.backoff_factor ** attempt)
        
        # Apply jitter
        if self.jitter > 0:
            jitter_amount = delay * self.jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        # Cap at max delay
        return min(delay, self.max_delay)


async def retry_async(
    func: Callable[..., Any],
    options: Optional[RetryOptions] = None,
    retry_on: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        options: Retry options
        retry_on: Exception types to retry on
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the async function
        
    Raises:
        Exception: The last exception raised by the function
    """
    # Set default options
    if options is None:
        options = RetryOptions()
    
    # Set default retry exceptions
    if retry_on is None:
        retry_on = (Exception,)
    
    # Initialize variables
    attempt = 0
    last_exception = None
    
    # Retry loop
    while attempt <= options.max_retries:
        try:
            # Execute function
            return await func(*args, **kwargs)
        except retry_on as e:
            # Store exception
            last_exception = e
            
            # Check if we've used all retries
            if attempt >= options.max_retries:
                break
            
            # Calculate delay
            delay = options.get_delay(attempt)
            
            # Log retry
            logger.warning(
                f"Retry {attempt + 1}/{options.max_retries} after {delay:.2f}s: {str(e)}"
            )
            
            # Wait before retrying
            await asyncio.sleep(delay)
            
            # Increment attempt counter
            attempt += 1
    
    # If we get here, all retries failed
    if last_exception:
        logger.error(f"All {options.max_retries} retry attempts failed")
        raise last_exception
    
    # This should never happen
    raise RuntimeError("Unexpected state in retry_async")


def retry_sync(
    func: Callable[..., Any],
    options: Optional[RetryOptions] = None,
    retry_on: Optional[Union[Type[Exception], Tuple[Type[Exception], ...]]] = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Retry a synchronous function with exponential backoff.
    
    Args:
        func: Synchronous function to retry
        options: Retry options
        retry_on: Exception types to retry on
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the function
        
    Raises:
        Exception: The last exception raised by the function
    """
    # Set default options
    if options is None:
        options = RetryOptions()
    
    # Set default retry exceptions
    if retry_on is None:
        retry_on = (Exception,)
    
    # Initialize variables
    attempt = 0
    last_exception = None
    
    # Retry loop
    while attempt <= options.max_retries:
        try:
            # Execute function
            return func(*args, **kwargs)
        except retry_on as e:
            # Store exception
            last_exception = e
            
            # Check if we've used all retries
            if attempt >= options.max_retries:
                break
            
            # Calculate delay
            delay = options.get_delay(attempt)
            
            # Log retry
            logger.warning(
                f"Retry {attempt + 1}/{options.max_retries} after {delay:.2f}s: {str(e)}"
            )
            
            # Wait before retrying
            time.sleep(delay)
            
            # Increment attempt counter
            attempt += 1
    
    # If we get here, all retries failed
    if last_exception:
        logger.error(f"All {options.max_retries} retry attempts failed")
        raise last_exception
    
    # This should never happen
    raise RuntimeError("Unexpected state in retry_sync")