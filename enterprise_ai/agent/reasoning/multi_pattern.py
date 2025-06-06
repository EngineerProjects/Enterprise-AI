"""
Multi-pattern reasoning execution for Enterprise AI agents.
Coordinates multiple reasoning patterns working together.
"""

import asyncio
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from enterprise_ai.logger import get_optimized_logger
from .patterns.base import BaseReasoningPattern
from .patterns.react import ReActPattern
from .patterns.cot import ChainOfThoughtPattern
from .patterns.swe import SoftwareEngineeringPattern
from .patterns.browser import BrowserPattern
from .patterns.reflection import ReflectionPattern

logger = get_optimized_logger("agent.reasoning.multi_pattern")


class MultiPatternReasoning:
    """Multi-pattern reasoning coordinator."""
    
    def __init__(
        self,
        agent,
        primary_pattern: str = "react",
        secondary_patterns: List[str] = None,
        max_iterations: int = 5
    ):
        self.agent = agent
        self.max_iterations = max_iterations
        
        # Initialize patterns
        self.patterns = {
            "react": ReActPattern(agent, max_iterations),
            "cot": ChainOfThoughtPattern(agent, max_iterations),
            "swe": SoftwareEngineeringPattern(agent, max_iterations),
            "browser": BrowserPattern(agent, max_iterations),
            "reflection": ReflectionPattern(agent, max_iterations)
        }
        
        self.primary_pattern = primary_pattern
        self.secondary_patterns = secondary_patterns or []
        self.active_patterns: List[BaseReasoningPattern] = []
        self.pattern_results: Dict[str, Any] = {}

    async def process(self, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process task using multiple reasoning patterns."""
        try:
            # Activate patterns
            self._activate_patterns()
            
            # Primary pattern execution
            primary_result = await self._execute_primary_pattern(task, context)
            
            # Secondary pattern execution (if any)
            secondary_results = await self._execute_secondary_patterns(task, context)
            
            # Synthesize results
            final_result = await self._synthesize_results(
                primary_result, secondary_results, task
            )
            
            return {
                "success": True,
                "result": final_result,
                "primary_pattern": self.primary_pattern,
                "secondary_patterns": self.secondary_patterns,
                "pattern_results": self.pattern_results
            }
            
        except Exception as e:
            logger.error(f"Multi-pattern reasoning failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "pattern_results": self.pattern_results
            }
    
    def _activate_patterns(self) -> None:
        """Activate the selected reasoning patterns."""
        self.active_patterns = []
        
        # Add primary pattern
        if self.primary_pattern in self.patterns:
            self.active_patterns.append(self.patterns[self.primary_pattern])
        
        # Add secondary patterns
        for pattern_name in self.secondary_patterns:
            if pattern_name in self.patterns and pattern_name != self.primary_pattern:
                self.active_patterns.append(self.patterns[pattern_name])
    
    async def _execute_primary_pattern(self, task: str, context: Dict[str, Any]) -> Any:
        """Execute the primary reasoning pattern."""
        pattern = self.patterns[self.primary_pattern]
        result = await pattern.process(task, context)
        self.pattern_results[self.primary_pattern] = result
        return result
    
    async def _execute_secondary_patterns(self, task: str, context: Dict[str, Any]) -> List[Any]:
        """Execute secondary patterns in parallel."""
        if not self.secondary_patterns:
            return []
        
        tasks = []
        for pattern_name in self.secondary_patterns:
            pattern = self.patterns[pattern_name]
            tasks.append(pattern.process(task, context))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, pattern_name in enumerate(self.secondary_patterns):
            self.pattern_results[pattern_name] = results[i]
        
        return results

    async def _synthesize_results(
        self, 
        primary_result: Any, 
        secondary_results: List[Any], 
        task: str
    ) -> Any:
        """Synthesize results from multiple patterns."""
        if not secondary_results:
            return primary_result.get("result") if isinstance(primary_result, dict) else primary_result
        
        # Simple synthesis: use primary result but augment with insights from secondary patterns
        synthesis_prompt = f"""
        Original task: {task}
        
        Primary reasoning result: {primary_result}
        
        Additional insights from other reasoning patterns: {secondary_results}
        
        Synthesize these perspectives into a comprehensive final result.
        Focus on the primary result but incorporate valuable insights from other patterns.
        """
        
        messages = [{"role": "user", "content": synthesis_prompt}]
        response = await self.agent.llm.acomplete(messages)
        
        return response.content
