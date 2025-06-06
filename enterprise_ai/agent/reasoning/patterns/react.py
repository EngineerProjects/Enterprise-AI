"""
ReAct (Reasoning + Acting) pattern implementation.
Implements the think-act-observe cycle for systematic problem solving.
"""

from typing import Any, Dict, Optional
import json

from enterprise_ai.prompt import react
from enterprise_ai.logger import get_optimized_logger
from .base import BaseReasoningPattern

logger = get_optimized_logger("agent.reasoning.patterns.react")


class ReActPattern(BaseReasoningPattern):
    """
    ReAct reasoning pattern implementation.
    Alternates between thinking, acting, and observing.
    """
    
    def __init__(self, agent, max_steps: int = 5):
        super().__init__(agent, max_steps)
        self.state = "think"  # think -> act -> observe -> think
    
    async def execute_step(
        self, 
        context: str, 
        step_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute one ReAct step."""
        if self.state == "think":
            return await self._think_step(context)
        elif self.state == "act":
            return await self._act_step(context, step_data)
        elif self.state == "observe":
            return await self._observe_step(context, step_data)
        else:
            self.state = "think"
            return await self._think_step(context)
    
    def is_complete(self, step_result: Dict[str, Any]) -> bool:
        """Check if ReAct process is complete."""
        return (
            step_result.get("step_type") == "complete" or
            self.state == "complete" or
            "final" in step_result.get("thought", "").lower()
        )

    async def _think_step(self, context: str) -> Dict[str, Any]:
        """Execute thinking step."""
        messages = [
            {"role": "system", "content": react.SYSTEM_PROMPT},
            {"role": "user", "content": f"{context}\n\n{react.NEXT_STEP_PROMPT}"}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        thought = response.content
        
        # Decide if we need to act or if we're done
        if "Action:" in thought or "tool" in thought.lower():
            self.state = "act"
            next_action = "act"
        elif "final" in thought.lower() or "complete" in thought.lower():
            self.state = "complete"
            next_action = "complete"
        else:
            self.state = "act"
            next_action = "act"
        
        return {
            "step_type": "think",
            "thought": thought,
            "next_action": next_action,
            "updated_context": f"{context}\n\nThought: {thought}"
        }
    
    async def _act_step(self, context: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action step."""
        # Extract tool call from thought if present
        thought = step_data.get("thought", "") if step_data else ""
        
        # Simple tool extraction
        if "Action:" in thought:
            action_part = thought.split("Action:")[1].split("\n")[0].strip()
            # Try to parse tool name and args
            try:
                if "(" in action_part and ")" in action_part:
                    tool_name = action_part.split("(")[0].strip()
                    args_str = action_part.split("(")[1].split(")")[0]
                    # Simple argument parsing
                    arguments = {"query": args_str} if args_str else {}
                else:
                    tool_name = action_part
                    arguments = {}
                
                result = await self.agent.execute_tool(tool_name, arguments)
                self.state = "observe"
                
                return {
                    "step_type": "act",
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "updated_context": f"{context}\n\nAction: {tool_name}({arguments})"
                }
            except Exception as e:
                self.state = "observe"
                return {
                    "step_type": "act",
                    "error": str(e),
                    "updated_context": f"{context}\n\nAction failed: {str(e)}"
                }
        else:
            # No clear action, move to completion
            self.state = "complete"
            return {
                "step_type": "complete",
                "result": thought,
                "updated_context": context
            }

    async def _observe_step(self, context: str, step_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute observation step."""
        if step_data and "result" in step_data:
            result = step_data["result"]
            if result.get("success", False):
                observation = f"Action successful: {result.get('result', 'Completed')}"
            else:
                observation = f"Action failed: {result.get('error', 'Unknown error')}"
        else:
            observation = "No action result to observe"
        
        self.state = "think"  # Go back to thinking
        
        return {
            "step_type": "observe",
            "observation": observation,
            "updated_context": f"{context}\n\nObservation: {observation}"
        }
