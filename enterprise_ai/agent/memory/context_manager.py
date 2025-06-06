"""
Context management for Enterprise AI agents.
Handles context switching, context persistence, and context optimization.
"""

from typing import Any, Dict, List, Optional
import json
import time

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.memory.context")


class ContextManager:
    """Context manager for individual agents."""
    
    def __init__(
        self,
        agent_name: str,
        max_context_length: int = 4000,
        context_window_size: int = 10
    ):
        """Initialize context manager."""
        self.agent_name = agent_name
        self.max_context_length = max_context_length
        self.context_window_size = context_window_size
        
        # Current context state
        self.current_context: Dict[str, Any] = {}
        self.context_history: List[Dict[str, Any]] = []
        self.important_context: Dict[str, Any] = {}
        
        logger.info(f"ContextManager initialized for {agent_name}")
    
    def update_context(self, new_context: Dict[str, Any]) -> None:
        """Update the current context with new information."""
        self.current_context.update(new_context)
        
        # Add to history
        self.context_history.append({
            "context": new_context.copy(),
            "timestamp": time.time()
        })
        
        # Optimize context if needed
        self._optimize_context()
        
        logger.debug(f"Context updated for {self.agent_name}")
    
    def get_context(self, include_history: bool = False) -> Dict[str, Any]:
        """Get current context, optionally including history."""
        context = self.current_context.copy()
        context.update(self.important_context)
        
        if include_history:
            context["history"] = self.context_history[-self.context_window_size:]
        
        return context
