"""
Chain of Thought (CoT) pattern implementation.
Implements step-by-step logical reasoning for complex problems.
"""

from typing import Any, Dict, Optional, List

from enterprise_ai.prompt import cot
from enterprise_ai.logger import get_optimized_logger
from .base import BaseReasoningPattern

logger = get_optimized_logger("agent.reasoning.patterns.cot")


class ChainOfThoughtPattern(BaseReasoningPattern):
    """
    Chain of Thought reasoning pattern.
    Breaks down complex problems into logical steps.
    """
    
    def __init__(self, agent, max_steps: int = 5):
        super().__init__(agent, max_steps)
        self.reasoning_chain: List[str] = []
    
    def is_complete(self, step_result: Dict[str, Any]) -> bool:
        """Check if reasoning chain is complete."""
        return step_result.get("is_final", False)

    async def execute_step(
        self, 
        context: str, 
        step_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute one step of chain of thought reasoning."""
        step_prompt = f"""
        Current context: {context}
        
        Step {self.current_step + 1} of logical reasoning:
        {cot.NEXT_STEP_PROMPT}
        
        Previous reasoning steps: {self.reasoning_chain}
        """
        
        messages = [
            {"role": "system", "content": cot.SYSTEM_PROMPT},
            {"role": "user", "content": step_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        reasoning_step = response.content
        
        self.reasoning_chain.append(reasoning_step)
        
        # Check if this step indicates completion
        is_final = (
            "conclusion" in reasoning_step.lower() or
            "final" in reasoning_step.lower() or
            "therefore" in reasoning_step.lower() or
            self.current_step >= self.max_steps - 1
        )
        
        return {
            "step_type": "reasoning",
            "reasoning_step": reasoning_step,
            "is_final": is_final,
            "chain_so_far": list(self.reasoning_chain),
            "updated_context": f"{context}\n\nStep {self.current_step + 1}: {reasoning_step}"
        }
