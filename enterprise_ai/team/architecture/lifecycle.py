"""
Team lifecycle management.

Handles team creation, state transitions, and cleanup.
"""

from typing import Dict, List, Optional, Callable
from enterprise_ai.team.core import TeamStatus, LifecycleEvent
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.lifecycle")


class LifecycleManager:
    """Manages team lifecycle and state transitions."""
    
    def __init__(self, team_name: str):
        self.team_name = team_name
        self.current_status = TeamStatus.IDLE
        self.event_handlers: Dict[LifecycleEvent, List[Callable]] = {}
        self.state_history: List[tuple] = []  # (status, timestamp, event)
        
    def transition_to(self, new_status: TeamStatus, event: LifecycleEvent) -> bool:
        """Transition team to new status."""
        if not self._is_valid_transition(self.current_status, new_status):
            logger.warning(f"Invalid transition from {self.current_status} to {new_status}")
            return False
            
        old_status = self.current_status
        self.current_status = new_status
        
        # Record state change
        from datetime import datetime
        self.state_history.append((new_status, datetime.now(), event))
        
        # Trigger event handlers
        self._trigger_event(event, old_status, new_status)
        
        logger.info(f"Team '{self.team_name}' transitioned from {old_status.value} to {new_status.value}")
        return True
    
    def register_event_handler(self, event: LifecycleEvent, handler: Callable) -> None:
        """Register event handler."""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    def handle_member_added(self, member_name: str) -> None:
        """Handle member addition."""
        if self.current_status == TeamStatus.IDLE and len(self.state_history) > 0:
            self.transition_to(TeamStatus.ACTIVE, LifecycleEvent.MEMBER_ADDED)
        self._trigger_event(LifecycleEvent.MEMBER_ADDED, member_name=member_name)
    
    def handle_member_removed(self, member_name: str, remaining_members: int) -> None:
        """Handle member removal."""
        self._trigger_event(LifecycleEvent.MEMBER_REMOVED, member_name=member_name)
        
        if remaining_members == 0:
            self.transition_to(TeamStatus.IDLE, LifecycleEvent.MEMBER_REMOVED)
    
    def handle_task_started(self, task_id: str) -> None:
        """Handle task start."""
        if self.current_status == TeamStatus.ACTIVE:
            self.transition_to(TeamStatus.BUSY, LifecycleEvent.TASK_STARTED)
        self._trigger_event(LifecycleEvent.TASK_STARTED, task_id=task_id)
    
    def handle_task_completed(self, task_id: str) -> None:
        """Handle task completion."""
        if self.current_status == TeamStatus.BUSY:
            self.transition_to(TeamStatus.ACTIVE, LifecycleEvent.TASK_COMPLETED)
        self._trigger_event(LifecycleEvent.TASK_COMPLETED, task_id=task_id)
    
    def handle_error(self, error: Exception) -> None:
        """Handle team error."""
        self.transition_to(TeamStatus.ERROR, LifecycleEvent.ERROR_OCCURRED)
        self._trigger_event(LifecycleEvent.ERROR_OCCURRED, error=error)
    
    def _is_valid_transition(self, from_status: TeamStatus, to_status: TeamStatus) -> bool:
        """Check if status transition is valid."""
        valid_transitions = {
            TeamStatus.IDLE: [TeamStatus.ACTIVE],
            TeamStatus.ACTIVE: [TeamStatus.BUSY, TeamStatus.IDLE, TeamStatus.ERROR],
            TeamStatus.BUSY: [TeamStatus.ACTIVE, TeamStatus.ERROR],
            TeamStatus.ERROR: [TeamStatus.ACTIVE, TeamStatus.IDLE]
        }
        
        return to_status in valid_transitions.get(from_status, [])
    
    def _trigger_event(self, event: LifecycleEvent, *args, **kwargs) -> None:
        """Trigger registered event handlers."""
        handlers = self.event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"Event handler failed for {event}: {e}")
