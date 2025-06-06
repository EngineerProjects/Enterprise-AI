"""
Reflection pattern implementation for Enterprise AI agents.
Enables self-assessment, learning, and strategy adaptation.
"""

from typing import Any, Dict, Optional

from enterprise_ai.prompt import reflection
from enterprise_ai.logger import get_optimized_logger
from .base import BaseReasoningPattern

logger = get_optimized_logger("agent.reasoning.patterns.reflection")


class ReflectionPattern(BaseReasoningPattern):
    """
    Reflection reasoning pattern.
    Enables agents to reflect on performance, learn from experience,
    and adapt strategies based on outcomes.
    """
    
    def __init__(self, agent, max_steps: int = 3):
        super().__init__(agent, max_steps)
        self.reflection_focus = "performance"  # performance, strategy, learning
        self.insights_gathered: list = []
    
    def is_complete(self, step_result: Dict[str, Any]) -> bool:
        """Check if reflection process is complete."""
        return (
            step_result.get("is_final", False) or
            step_result.get("step_type") == "adaptation_generation" or
            self.current_step >= self.max_steps - 1
        )

    async def execute_step(
        self, 
        context: str, 
        step_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute one step of reflection reasoning."""
        
        if self.current_step == 0:
            # Step 1: Assess current situation and performance
            return await self._assess_performance(context, step_data)
        elif self.current_step == 1:
            # Step 2: Identify patterns and insights
            return await self._identify_insights(context, step_data)
        else:
            # Step 3: Generate improvements and adaptations
            return await self._generate_adaptations(context, step_data)
    
    async def _assess_performance(self, context: str, step_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Assess current performance and outcomes."""
        assessment_prompt = f"""
        Reflect on your recent performance:
        
        Context: {context}
        Previous actions: {step_data.get('history', []) if step_data else []}
        
        Assess:
        1. What worked well?
        2. What didn't work as expected?
        3. What were the key outcomes?
        4. How effective was your approach?
        
        Provide an honest performance assessment.
        """
        
        messages = [
            {"role": "system", "content": reflection.SYSTEM_PROMPT},
            {"role": "user", "content": assessment_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        assessment = response.content
        
        return {
            "step_type": "assessment",
            "assessment": assessment,
            "focus": "performance",
            "updated_context": f"{context}\n\nPerformance Assessment: {assessment}"
        }

    async def _identify_insights(self, context: str, step_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Identify patterns and extract insights."""
        insight_prompt = f"""
        Based on your performance assessment, identify key insights:
        
        Context: {context}
        
        Look for:
        1. Recurring patterns in your approach
        2. Common success factors
        3. Frequent failure modes
        4. Environmental factors that affect performance
        5. Learning opportunities
        
        Extract 3-5 key insights that could improve future performance.
        """
        
        messages = [
            {"role": "system", "content": reflection.SYSTEM_PROMPT},
            {"role": "user", "content": insight_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        insights = response.content
        
        # Store insights for future use
        self.insights_gathered.append(insights)
        
        return {
            "step_type": "insight_identification",
            "insights": insights,
            "patterns_identified": True,
            "updated_context": f"{context}\n\nKey Insights: {insights}"
        }
    
    async def _generate_adaptations(self, context: str, step_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate specific adaptations and improvements."""
        adaptation_prompt = f"""
        Based on your insights, generate specific adaptations:
        
        Context: {context}
        Insights gathered: {self.insights_gathered}
        
        Create:
        1. Specific strategy adjustments
        2. Process improvements
        3. Decision-making refinements
        4. Risk mitigation approaches
        5. Success amplification tactics
        
        Focus on actionable, specific improvements for future tasks.
        """
        
        messages = [
            {"role": "system", "content": reflection.SYSTEM_PROMPT},
            {"role": "user", "content": adaptation_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        adaptations = response.content
        
        return {
            "step_type": "adaptation_generation",
            "adaptations": adaptations,
            "is_final": True,
            "result": adaptations,
            "updated_context": f"{context}\n\nAdaptations: {adaptations}"
        }
