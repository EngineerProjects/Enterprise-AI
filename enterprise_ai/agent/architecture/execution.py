"""
Execution management for agents.

This module handles the execution of messages and tasks,
coordinating between different agent components.
"""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from enterprise_ai.agent.architecture.errors import AgentError, AgentErrorCode, ErrorManager
from enterprise_ai.agent.architecture.utils import timer, TimerContext, ensure_event_loop
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message
from enterprise_ai.types import MessageProtocol

logger = get_logger("agent.execution")


class ExecutionStatus(str, Enum):
    """Status of an execution."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    TIMEOUT = "timeout"


class ExecutionType(str, Enum):
    """Type of execution."""
    
    MESSAGE = "message"
    TASK = "task"
    CONVERSATION = "conversation"
    BATCH = "batch"


class ExecutionContext:
    """Context for an execution."""
    
    def __init__(self, execution_id: str, execution_type: ExecutionType):
        """Initialize execution context.
        
        Args:
            execution_id: Unique ID for this execution
            execution_type: Type of execution
        """
        self.execution_id = execution_id
        self.execution_type = execution_type
        self.status = ExecutionStatus.PENDING
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.result: Optional[Any] = None
        self.error: Optional[Exception] = None
        self.metadata: Dict[str, Any] = {}
        self.cancelled = False
        self.timeout: Optional[float] = None
        
    def mark_started(self) -> None:
        """Mark the execution as started."""
        self.start_time = datetime.now()
        self.status = ExecutionStatus.RUNNING
        
    def mark_completed(self, result: Any) -> None:
        """Mark the execution as completed.
        
        Args:
            result: Execution result
        """
        self.end_time = datetime.now()
        self.result = result
        self.status = ExecutionStatus.COMPLETED
        
    def mark_failed(self, error: Exception) -> None:
        """Mark the execution as failed.
        
        Args:
            error: Execution error
        """
        self.end_time = datetime.now()
        self.error = error
        self.status = ExecutionStatus.FAILED
        
    def mark_canceled(self) -> None:
        """Mark the execution as canceled."""
        self.end_time = datetime.now()
        self.status = ExecutionStatus.CANCELED
        self.cancelled = True
        
    def mark_timeout(self) -> None:
        """Mark the execution as timed out."""
        self.end_time = datetime.now()
        self.status = ExecutionStatus.TIMEOUT
        
    def get_duration(self) -> Optional[float]:
        """Get the execution duration in seconds.
        
        Returns:
            Duration in seconds or None if not complete
        """
        if not self.start_time:
            return None
        
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def get_status_info(self) -> Dict[str, Any]:
        """Get execution status information.
        
        Returns:
            Dictionary of execution status information
        """
        info = {
            "execution_id": self.execution_id,
            "execution_type": self.execution_type.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.get_duration(),
            "cancelled": self.cancelled,
        }
        
        if self.error:
            info["error"] = str(self.error)
            
        if self.metadata:
            info["metadata"] = self.metadata
            
        return info


class ExecutionManagerConfig:
    """Configuration for execution manager."""
    
    def __init__(
        self,
        default_timeout: Optional[float] = None,
        parallel_execution: bool = True,
        max_parallel_executions: int = 5,
        track_execution_history: bool = True,
        max_history: int = 100,
    ):
        """Initialize execution manager configuration.
        
        Args:
            default_timeout: Default execution timeout in seconds
            parallel_execution: Whether to allow parallel execution
            max_parallel_executions: Maximum number of parallel executions
            track_execution_history: Whether to track execution history
            max_history: Maximum number of executions to keep in history
        """
        self.default_timeout = default_timeout
        self.parallel_execution = parallel_execution
        self.max_parallel_executions = max_parallel_executions
        self.track_execution_history = track_execution_history
        self.max_history = max_history


class ExecutionManager:
    """Manager for agent execution."""
    
    def __init__(
        self, 
        agent: Any, 
        config: Optional[ExecutionManagerConfig] = None,
        error_manager: Optional[ErrorManager] = None,
    ):
        """Initialize the execution manager.
        
        Args:
            agent: The agent instance
            config: Optional execution manager configuration
            error_manager: Optional error manager to use
        """
        self.agent = agent
        self.agent_id = getattr(agent, "id", "unknown")
        self.config = config or ExecutionManagerConfig()
        self._executions: Dict[str, ExecutionContext] = {}
        self._active_executions: Set[str] = set()
        self._execution_history: List[Dict[str, Any]] = []
        self._error_manager = error_manager or ErrorManager(self.agent_id)
        self._semaphore = asyncio.Semaphore(self.config.max_parallel_executions)
        
        logger.info(f"Initialized execution manager for agent {self.agent_id}")

    def create_execution_context(
        self, 
        execution_type: ExecutionType, 
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ExecutionContext:
        """Create a new execution context.
        
        Args:
            execution_type: Type of execution
            metadata: Optional execution metadata
            timeout: Optional execution timeout in seconds
            
        Returns:
            Execution context
        """
        import uuid
        execution_id = f"exec-{uuid.uuid4()}"
        
        context = ExecutionContext(execution_id, execution_type)
        if metadata:
            context.metadata = metadata.copy()
            
        # Set timeout
        context.timeout = timeout or self.config.default_timeout
        
        # Store context
        self._executions[execution_id] = context
        
        return context

    async def process_message(
        self, 
        messages: List[MessageProtocol], 
        **kwargs: Any
    ) -> MessageProtocol:
        """Process a message using the agent's reasoning framework.
        
        Args:
            messages: List of messages to process
            **kwargs: Additional processing parameters
            
        Returns:
            Response message
        """
        # Create execution context
        context = self.create_execution_context(
            ExecutionType.MESSAGE,
            metadata={"message_count": len(messages)},
            timeout=kwargs.get("timeout")
        )
        execution_id = context.execution_id
        
        # Add execution ID to active executions
        self._active_executions.add(execution_id)
        
        try:
            # Mark execution as started
            context.mark_started()
            
            # Get execution components
            reasoning_manager = getattr(self.agent, "_reasoning", None)
            if reasoning_manager is None:
                raise AgentError(
                    "Agent does not have a reasoning manager",
                    error_code=AgentErrorCode.INITIALIZATION_FAILED
                )
            
            # Process message with reasoning framework
            with TimerContext("message_processing"):
                if kwargs.get("llm_provider") is None and hasattr(self.agent, "_llm_provider"):
                    kwargs["llm_provider"] = getattr(self.agent, "_llm_provider")
                
                response = await reasoning_manager.process_input(messages, **kwargs)
            
            # Mark execution as completed
            context.mark_completed(response)
            
            # Track execution history
            if self.config.track_execution_history:
                self._record_execution_history(context)
            
            return response
        except asyncio.CancelledError:
            # Handle cancellation
            logger.warning(f"Execution {execution_id} was cancelled")
            context.mark_canceled()
            
            # Create cancellation response
            return Message.assistant_message(
                "I'm sorry, but this operation was cancelled.",
                metadata={"cancelled": True, "execution_id": execution_id}
            )
        except Exception as e:
            # Handle execution error
            logger.error(f"Error processing message: {e}")
            context.mark_failed(e)
            
            # Create error response
            error = self._error_manager.handle_error(
                e, 
                error_code=AgentErrorCode.EXECUTION_FAILED,
                context={"execution_id": execution_id}
            )
            
            # Track execution history
            if self.config.track_execution_history:
                self._record_execution_history(context)
            
            return Message.assistant_message(
                "I'm sorry, but I encountered an error while processing your message. "
                "Please try again or rephrase your query.",
                metadata={"error": str(e), "execution_id": execution_id}
            )
        finally:
            # Remove execution ID from active executions
            self._active_executions.discard(execution_id)

    async def process_task(self, task: Any, **kwargs: Any) -> Any:
        """Process a task using the agent's reasoning framework.
        
        Args:
            task: Task to process
            **kwargs: Additional processing parameters
            
        Returns:
            Task processing result
        """
        # Create execution context
        context = self.create_execution_context(
            ExecutionType.TASK,
            metadata={"task_id": getattr(task, "id", "unknown")},
            timeout=kwargs.get("timeout")
        )
        execution_id = context.execution_id
        
        # Add execution ID to active executions
        self._active_executions.add(execution_id)
        
        try:
            # Mark execution as started
            context.mark_started()
            
            # Get execution components
            reasoning_manager = getattr(self.agent, "_reasoning", None)
            if reasoning_manager is None:
                raise AgentError(
                    "Agent does not have a reasoning manager",
                    error_code=AgentErrorCode.INITIALIZATION_FAILED
                )
            
            # Process task with reasoning framework
            with TimerContext("task_processing"):
                if kwargs.get("llm_provider") is None and hasattr(self.agent, "_llm_provider"):
                    kwargs["llm_provider"] = getattr(self.agent, "_llm_provider")
                
                result = await reasoning_manager.process_task(task, **kwargs)
            
            # Mark execution as completed
            context.mark_completed(result)
            
            # Track execution history
            if self.config.track_execution_history:
                self._record_execution_history(context)
            
            return result
        except asyncio.CancelledError:
            # Handle cancellation
            logger.warning(f"Task execution {execution_id} was cancelled")
            context.mark_canceled()
            
            # Update task status if possible
            if hasattr(task, "status"):
                # Assuming TaskStatus enum exists with CANCELED attribute
                task.status = getattr(task, "CANCELED", "canceled")
            
            return task
        except Exception as e:
            # Handle execution error
            logger.error(f"Error processing task: {e}")
            context.mark_failed(e)
            
            # Create error and update task status if possible
            error = self._error_manager.handle_error(
                e, 
                error_code=AgentErrorCode.EXECUTION_FAILED,
                context={"execution_id": execution_id, "task_id": getattr(task, "id", "unknown")}
            )
            
            if hasattr(task, "status"):
                # Assuming TaskStatus enum exists with FAILED attribute
                task.status = getattr(task, "FAILED", "failed")
            
            # Track execution history
            if self.config.track_execution_history:
                self._record_execution_history(context)
            
            return task
        finally:
            # Remove execution ID from active executions
            self._active_executions.discard(execution_id)

    async def execute_with_timeout(self, context: ExecutionContext, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a function with timeout.
        
        Args:
            context: Execution context
            func: Function to execute
            *args: Function positional arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result or None if timed out
        """
        # Create task
        task = asyncio.create_task(func(*args, **kwargs))
        
        # Run with timeout if specified
        if context.timeout:
            try:
                return await asyncio.wait_for(task, timeout=context.timeout)
            except asyncio.TimeoutError:
                # Cancel task
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # Mark execution as timed out
                context.mark_timeout()
                
                # Log timeout
                logger.warning(f"Execution {context.execution_id} timed out after {context.timeout} seconds")
                
                return None
        else:
            # Run without timeout
            return await task

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel an active execution.
        
        Args:
            execution_id: ID of execution to cancel
            
        Returns:
            True if execution was cancelled, False if not found or already complete
        """
        if execution_id not in self._executions:
            return False
        
        context = self._executions[execution_id]
        
        # Check if execution is active
        if context.status != ExecutionStatus.RUNNING:
            return False
        
        # Mark as cancelled
        context.mark_canceled()
        
        # Remove from active executions
        self._active_executions.discard(execution_id)
        
        logger.info(f"Cancelled execution: {execution_id}")
        return True

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution status information.
        
        Args:
            execution_id: ID of execution to get status for
            
        Returns:
            Dictionary of execution status information or None if not found
        """
        if execution_id not in self._executions:
            return None
        
        context = self._executions[execution_id]
        return context.get_status_info()

    def _record_execution_history(self, context: ExecutionContext) -> None:
        """Record execution information in history.
        
        Args:
            context: Execution context to record
        """
        # Get execution information
        execution_info = context.get_status_info()
        
        # Add to history
        self._execution_history.append(execution_info)
        
        # Trim history if needed
        if self.config.max_history > 0 and len(self._execution_history) > self.config.max_history:
            self._execution_history = self._execution_history[-self.config.max_history:]

    def get_execution_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get execution history.
        
        Args:
            limit: Maximum number of executions to retrieve (most recent)
            
        Returns:
            List of execution information
        """
        if not self.config.track_execution_history:
            return []
        
        history = self._execution_history
        
        # Apply limit if specified
        if limit and limit > 0:
            history = history[-limit:]
        
        return history.copy()

    def get_active_executions(self) -> List[Dict[str, Any]]:
        """Get information about active executions.
        
        Returns:
            List of active execution information
        """
        active = []
        
        for execution_id in self._active_executions:
            if execution_id in self._executions:
                context = self._executions[execution_id]
                active.append(context.get_status_info())
        
        return active

    async def execute_in_parallel(
        self, 
        functions: List[Tuple[Any, Dict[str, Any]]], 
        timeout: Optional[float] = None,
    ) -> List[Any]:
        """Execute multiple functions in parallel.
        
        Args:
            functions: List of (function, kwargs) tuples
            timeout: Optional timeout for all executions
            
        Returns:
            List of execution results
        """
        if not self.config.parallel_execution:
            # Execute sequentially
            results = []
            for func, kwargs in functions:
                try:
                    result = await func(**kwargs)
                    results.append(result)
                except Exception as e:
                    results.append(e)
            return results
        
        # Create execution context
        context = self.create_execution_context(
            ExecutionType.BATCH,
            metadata={"function_count": len(functions)},
            timeout=timeout
        )
        execution_id = context.execution_id
        
        # Add execution ID to active executions
        self._active_executions.add(execution_id)
        
        try:
            # Mark execution as started
            context.mark_started()
            
            # Create tasks
            async def execute_with_semaphore(func: Any, kwargs: Dict[str, Any]) -> Any:
                async with self._semaphore:
                    return await func(**kwargs)
            
            tasks = [
                asyncio.create_task(execute_with_semaphore(func, kwargs))
                for func, kwargs in functions
            ]
            
            # Execute with timeout if specified
            if timeout:
                try:
                    results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
                except asyncio.TimeoutError:
                    # Cancel tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    
                    # Wait for tasks to be cancelled
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Mark execution as timed out
                    context.mark_timeout()
                    
                    # Return timeout exceptions
                    return [asyncio.TimeoutError(f"Execution timed out after {timeout} seconds")] * len(functions)
            else:
                # Execute without timeout
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Mark execution as completed
            context.mark_completed(results)
            
            # Track execution history
            if self.config.track_execution_history:
                self._record_execution_history(context)
            
            return results
        except Exception as e:
            # Handle execution error
            logger.error(f"Error executing functions in parallel: {e}")
            context.mark_failed(e)
            
            # Track execution history
            if self.config.track_execution_history:
                self._record_execution_history(context)
            
            # Return exceptions
            return [e] * len(functions)
        finally:
            # Remove execution ID from active executions
            self._active_executions.discard(execution_id)

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get execution metrics.
        
        Returns:
            Dictionary of execution metrics
        """
        if not self.config.track_execution_history:
            return {}
        
        # Count executions by type and status
        type_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        
        # Calculate average durations by type
        type_durations: Dict[str, List[float]] = {}
        
        for info in self._execution_history:
            # Count by type
            exec_type = info.get("execution_type", "unknown")
            type_counts[exec_type] = type_counts.get(exec_type, 0) + 1
            
            # Count by status
            status = info.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Track durations
            duration = info.get("duration")
            if duration is not None:
                if exec_type not in type_durations:
                    type_durations[exec_type] = []
                type_durations[exec_type].append(duration)
        
        # Calculate average durations
        avg_durations: Dict[str, float] = {}
        for exec_type, durations in type_durations.items():
            if durations:
                avg_durations[exec_type] = sum(durations) / len(durations)
        
        return {
            "total_executions": len(self._execution_history),
            "active_executions": len(self._active_executions),
            "by_type": type_counts,
            "by_status": status_counts,
            "avg_duration": avg_durations,
        }