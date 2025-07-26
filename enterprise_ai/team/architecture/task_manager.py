"""
Advanced task management for teams.

Handles task queuing, prioritization, execution tracking, and completion.
"""

from typing import Dict, List, Optional, Callable, Any
import asyncio
from datetime import datetime, timedelta
from enterprise_ai.team.core import TeamTask, TaskStatus, TaskPriority
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.task_manager")


class TaskManager:
    """Advanced task management system for teams."""
    
    def __init__(self, max_concurrent_tasks: int = 5):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_queue: List[TeamTask] = []
        self.active_tasks: Dict[str, TeamTask] = {}
        self.completed_tasks: Dict[str, TeamTask] = {}
        self.failed_tasks: Dict[str, TeamTask] = {}
        self.task_callbacks: Dict[str, List[Callable]] = {}
        self.execution_history: List[Dict[str, Any]] = []
        
    def add_task(self, task: TeamTask, priority: Optional[TaskPriority] = None) -> str:
        """Add task to queue with optional priority."""
        if priority:
            task.priority = priority.value
        
        task.status = TaskStatus.QUEUED.value
        
        # Insert task in priority order
        inserted = False
        for i, queued_task in enumerate(self.task_queue):
            if task.priority > queued_task.priority:
                self.task_queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self.task_queue.append(task)
        
        logger.info(f"Added task {task.id} to queue with priority {task.priority}")
        return task.id
    
    def get_next_task(self) -> Optional[TeamTask]:
        """Get next highest priority task from queue."""
        if not self.task_queue:
            return None
        
        # Check if we have capacity for more tasks
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return None
        
        task = self.task_queue.pop(0)
        task.status = TaskStatus.IN_PROGRESS.value
        self.active_tasks[task.id] = task
        
        self._record_execution_event(task.id, "started")
        logger.info(f"Started task {task.id}: {task.description[:50]}...")
        
        return task
    
    def complete_task(self, task_id: str, result: Any = None) -> bool:
        """Mark task as completed and trigger callbacks."""
        if task_id not in self.active_tasks:
            logger.warning(f"Cannot complete task {task_id}: not in active tasks")
            return False
        
        task = self.active_tasks.pop(task_id)
        task.status = TaskStatus.COMPLETED.value
        if result:
            task.metadata["result"] = result
        
        self.completed_tasks[task_id] = task
        self._record_execution_event(task_id, "completed", {"result": result})
        
        # Trigger completion callbacks
        self._trigger_callbacks(task_id, "completed", task)
        
        logger.info(f"Completed task {task_id}")
        return True
    
    def fail_task(self, task_id: str, error: Exception) -> bool:
        """Mark task as failed."""
        if task_id not in self.active_tasks:
            logger.warning(f"Cannot fail task {task_id}: not in active tasks")
            return False
        
        task = self.active_tasks.pop(task_id)
        task.status = TaskStatus.FAILED.value
        task.metadata["error"] = str(error)
        
        self.failed_tasks[task_id] = task
        self._record_execution_event(task_id, "failed", {"error": str(error)})
        
        # Trigger failure callbacks
        self._trigger_callbacks(task_id, "failed", task)
        
        logger.error(f"Failed task {task_id}: {error}")
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel pending or active task."""
        # Check if task is in queue
        for i, task in enumerate(self.task_queue):
            if task.id == task_id:
                task.status = TaskStatus.CANCELLED.value
                self.task_queue.pop(i)
                self._record_execution_event(task_id, "cancelled")
                logger.info(f"Cancelled queued task {task_id}")
                return True
        
        # Check if task is active
        if task_id in self.active_tasks:
            task = self.active_tasks.pop(task_id)
            task.status = TaskStatus.CANCELLED.value
            self._record_execution_event(task_id, "cancelled")
            logger.info(f"Cancelled active task {task_id}")
            return True
        
        return False
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """Get current status of task."""
        # Check all task collections
        for task_dict in [self.active_tasks, self.completed_tasks, self.failed_tasks]:
            if task_id in task_dict:
                return task_dict[task_id].status
        
        # Check queue
        for task in self.task_queue:
            if task.id == task_id:
                return task.status
        
        return None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queued_tasks": len(self.task_queue),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "failed_tasks": len(self.failed_tasks),
            "capacity_used": len(self.active_tasks) / self.max_concurrent_tasks
        }
    
    def register_callback(self, task_id: str, event: str, callback: Callable) -> None:
        """Register callback for task events."""
        key = f"{task_id}_{event}"
        if key not in self.task_callbacks:
            self.task_callbacks[key] = []
        self.task_callbacks[key].append(callback)
    
    def get_task_history(self, task_id: str) -> List[Dict[str, Any]]:
        """Get execution history for specific task."""
        return [event for event in self.execution_history if event["task_id"] == task_id]
    
    def cleanup_completed_tasks(self, older_than_hours: int = 24) -> int:
        """Clean up old completed tasks."""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        cleaned_count = 0
        
        # Clean completed tasks
        to_remove = []
        for task_id, task in self.completed_tasks.items():
            # Check if task has completion timestamp in metadata
            if "completed_at" in task.metadata:
                completed_at = task.metadata["completed_at"]
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at)
                if completed_at < cutoff_time:
                    to_remove.append(task_id)
        
        for task_id in to_remove:
            self.completed_tasks.pop(task_id)
            cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old completed tasks")
        
        return cleaned_count
    
    def _record_execution_event(self, task_id: str, event: str, data: Dict[str, Any] = None) -> None:
        """Record task execution event."""
        event_record = {
            "task_id": task_id,
            "event": event,
            "timestamp": datetime.now(),
            "data": data or {}
        }
        self.execution_history.append(event_record)
    
    def _trigger_callbacks(self, task_id: str, event: str, task: TeamTask) -> None:
        """Trigger registered callbacks for task event."""
        key = f"{task_id}_{event}"
        callbacks = self.task_callbacks.get(key, [])
        
        for callback in callbacks:
            try:
                callback(task)
            except Exception as e:
                logger.error(f"Task callback failed for {task_id}_{event}: {e}")
