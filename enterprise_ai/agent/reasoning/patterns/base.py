"""
Base reasoning pattern for Enterprise AI agents.
Provides common interface for all reasoning patterns.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.reasoning.patterns.base")


class BaseReasoningPattern(ABC):
    """Base class for all reasoning patterns."""
    
    def __init__(self, agent, max_steps: int = 5):
        """Initialize the reasoning pattern."""
        self.agent = agent
        self.max_steps = max_steps
        self.current_step = 0
        self.pattern_history: List[Dict[str, Any]] = []
    
    @abstractmethod
    async def execute_step(
        self, 
        context: str, 
        step_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute one step of the reasoning pattern."""
        pass
    
    @abstractmethod
    def is_complete(self, step_result: Dict[str, Any]) -> bool:
        """Check if the reasoning process is complete."""
        pass
    
    def get_pattern_name(self) -> str:
        """Get the name of this reasoning pattern."""
        return self.__class__.__name__.replace("Pattern", "").lower()

    async def process(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Main processing loop for the pattern."""
        self.current_step = 0
        self.pattern_history = []
        
        current_context = task
        if context:
            current_context += f"\nContext: {context}"
        
        for step in range(self.max_steps):
            self.current_step = step
            
            step_result = await self.execute_step(current_context, context)
            self.pattern_history.append(step_result)
            
            if self.is_complete(step_result):
                return {
                    "success": True,
                    "result": step_result.get("result"),
                    "pattern_history": self.pattern_history,
                    "steps_completed": step + 1
                }
            
            # Update context for next step
            if step_result.get("updated_context"):
                current_context = step_result["updated_context"]
        
        return {
            "success": False,
            "error": "Maximum steps reached without completion",
            "pattern_history": self.pattern_history,
            "steps_completed": self.max_steps
        }
