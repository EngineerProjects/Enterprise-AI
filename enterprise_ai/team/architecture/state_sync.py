"""
State synchronization for distributed team operations.

Manages shared state across team members and ensures consistency.
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("team.state_sync")


@dataclass
class StateUpdate:
    """Represents a state update event."""
    member_id: str
    state_key: str
    old_value: Any
    new_value: Any
    timestamp: datetime = field(default_factory=datetime.now)
    version: int = 1


class StateSynchronizer:
    """Manages distributed state synchronization across team members."""
    
    def __init__(self):
        self.shared_state: Dict[str, Any] = {}
        self.member_states: Dict[str, Dict[str, Any]] = {}
        self.state_history: List[StateUpdate] = []
        self.subscribers: Dict[str, Set[str]] = {}  # state_key -> set of member_ids
        self.version_counter: int = 0
        
    def register_member(self, member_id: str) -> None:
        """Register member for state synchronization."""
        if member_id not in self.member_states:
            self.member_states[member_id] = {}
            logger.info(f"Registered member '{member_id}' for state sync")
    
    def unregister_member(self, member_id: str) -> None:
        """Unregister member from state synchronization."""
        self.member_states.pop(member_id, None)
        
        # Remove from all subscriptions
        for subscribers in self.subscribers.values():
            subscribers.discard(member_id)
            
        logger.info(f"Unregistered member '{member_id}' from state sync")
    
    def subscribe_to_state(self, member_id: str, state_key: str) -> None:
        """Subscribe member to state changes."""
        if state_key not in self.subscribers:
            self.subscribers[state_key] = set()
        self.subscribers[state_key].add(member_id)
        
        # Send current state value if exists
        if state_key in self.shared_state:
            self._update_member_state(member_id, state_key, self.shared_state[state_key])
    
    def update_shared_state(self, member_id: str, state_key: str, value: Any) -> int:
        """Update shared state and notify subscribers."""
        old_value = self.shared_state.get(state_key)
        self.shared_state[state_key] = value
        
        self.version_counter += 1
        
        # Record state update
        update = StateUpdate(
            member_id=member_id,
            state_key=state_key,
            old_value=old_value,
            new_value=value,
            version=self.version_counter
        )
        self.state_history.append(update)
        
        # Notify subscribers
        self._notify_subscribers(state_key, value, exclude_member=member_id)
        
        logger.debug(f"State '{state_key}' updated by '{member_id}' to version {self.version_counter}")
        return self.version_counter
    
    def get_shared_state(self, state_key: Optional[str] = None) -> Any:
        """Get shared state value(s)."""
        if state_key:
            return self.shared_state.get(state_key)
        return dict(self.shared_state)
    
    def get_member_state(self, member_id: str, state_key: Optional[str] = None) -> Any:
        """Get member's local state."""
        member_state = self.member_states.get(member_id, {})
        if state_key:
            return member_state.get(state_key)
        return dict(member_state)
    
    def sync_member_state(self, member_id: str) -> Dict[str, Any]:
        """Synchronize member with current shared state."""
        if member_id not in self.member_states:
            self.register_member(member_id)
        
        # Update member's state with current shared state
        for state_key in self.subscribers:
            if member_id in self.subscribers[state_key]:
                if state_key in self.shared_state:
                    self._update_member_state(member_id, state_key, self.shared_state[state_key])
        
        return self.get_member_state(member_id)
    
    def get_state_conflicts(self) -> List[Dict[str, Any]]:
        """Identify state conflicts between members."""
        conflicts = []
        
        for state_key in self.shared_state:
            shared_value = self.shared_state[state_key]
            
            for member_id, member_state in self.member_states.items():
                if state_key in member_state:
                    member_value = member_state[state_key]
                    if member_value != shared_value:
                        conflicts.append({
                            "state_key": state_key,
                            "member_id": member_id,
                            "shared_value": shared_value,
                            "member_value": member_value
                        })
        
        return conflicts
    
    def resolve_conflicts(self, prefer_shared: bool = True) -> int:
        """Resolve state conflicts."""
        conflicts = self.get_state_conflicts()
        resolved_count = 0
        
        for conflict in conflicts:
            if prefer_shared:
                # Update member state to match shared state
                self._update_member_state(
                    conflict["member_id"],
                    conflict["state_key"],
                    conflict["shared_value"]
                )
            else:
                # Update shared state to match member state
                self.update_shared_state(
                    conflict["member_id"],
                    conflict["state_key"],
                    conflict["member_value"]
                )
            
            resolved_count += 1
        
        if resolved_count > 0:
            logger.info(f"Resolved {resolved_count} state conflicts")
        
        return resolved_count
    
    def _notify_subscribers(self, state_key: str, value: Any, exclude_member: str = None) -> None:
        """Notify subscribers of state changes."""
        subscribers = self.subscribers.get(state_key, set())
        
        for member_id in subscribers:
            if member_id != exclude_member:
                self._update_member_state(member_id, state_key, value)
    
    def _update_member_state(self, member_id: str, state_key: str, value: Any) -> None:
        """Update member's local state."""
        if member_id not in self.member_states:
            self.member_states[member_id] = {}
        
        self.member_states[member_id][state_key] = value
