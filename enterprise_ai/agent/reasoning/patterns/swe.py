"""
Software Engineering (SWE) pattern implementation.
Specialized reasoning for software development tasks.
"""

from typing import Any, Dict, Optional

from enterprise_ai.prompt import swe
from enterprise_ai.logger import get_optimized_logger
from .base import BaseReasoningPattern

logger = get_optimized_logger("agent.reasoning.patterns.swe")


class SoftwareEngineeringPattern(BaseReasoningPattern):
    """
    Software Engineering reasoning pattern.
    Optimized for coding, debugging, and development tasks.
    """
    
    def __init__(self, agent, max_steps: int = 5):
        super().__init__(agent, max_steps)
        self.development_phase = "analysis"  # analysis -> design -> implement -> test
    
    async def execute_step(
        self, 
        context: str, 
        step_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute one step of software engineering reasoning."""
        phase_prompt = f"""
        Development Phase: {self.development_phase}
        Context: {context}
        
        {swe.NEXT_STEP_PROMPT}
        
        Focus on the current phase: {self.development_phase}
        """
        
        messages = [
            {"role": "system", "content": swe.SYSTEM_PROMPT},
            {"role": "user", "content": phase_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        step_result = response.content
        
        # Update development phase
        self._update_development_phase(step_result)
        
        return {
            "step_type": "development",
            "phase": self.development_phase,
            "output": step_result,
            "updated_context": f"{context}\n\nPhase {self.development_phase}: {step_result}"
        }
    
    def _update_development_phase(self, output: str) -> None:
        """Update development phase based on output."""
        if self.development_phase == "analysis" and ("design" in output.lower() or "implement" in output.lower()):
            self.development_phase = "design"
        elif self.development_phase == "design" and "code" in output.lower():
            self.development_phase = "implement"
        elif self.development_phase == "implement" and "test" in output.lower():
            self.development_phase = "test"
        elif self.development_phase == "test":
            self.development_phase = "complete"
    
    def is_complete(self, step_result: Dict[str, Any]) -> bool:
        """Check if development process is complete."""
        return (
            self.development_phase == "complete" or
            "completed" in step_result.get("output", "").lower()
        )
