"""
Browser automation pattern implementation for Enterprise AI agents.
Specialized reasoning for web interaction and browser automation tasks.
"""

import json
from typing import Any, Dict, Optional

from enterprise_ai.prompt import browser
from enterprise_ai.logger import get_optimized_logger
from .base import BaseReasoningPattern

logger = get_optimized_logger("agent.reasoning.patterns.browser")


class BrowserPattern(BaseReasoningPattern):
    """
    Browser automation reasoning pattern.
    Optimized for web navigation, interaction, and data extraction tasks.
    """
    
    def __init__(self, agent, max_steps: int = 10):
        super().__init__(agent, max_steps)
        self.browser_state = None
        self.navigation_history = []
        self.extraction_goals = []
    
    def is_complete(self, step_result: Dict[str, Any]) -> bool:
        """Check if browser automation process is complete."""
        return (
            step_result.get("is_final", False) or
            step_result.get("step_type") == "analysis_complete" or
            "complete" in step_result.get("result", "").lower()
        )

    async def execute_step(
        self, 
        context: str, 
        step_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute one step of browser automation reasoning."""
        
        # Get current browser state
        await self._update_browser_state()
        
        # Analyze the current situation and plan next action
        browser_context = await self._format_browser_context(context)
        next_action = await self._plan_browser_action(browser_context)
        
        # Execute the browser action
        if next_action.get("action"):
            result = await self._execute_browser_action(next_action)
            
            # Update navigation history
            self.navigation_history.append({
                "action": next_action,
                "result": result,
                "timestamp": self.current_step
            })
            
            return {
                "step_type": "browser_action",
                "action": next_action,
                "result": result,
                "browser_state": self.browser_state,
                "updated_context": f"{context}\n\nAction: {next_action['action']}\nResult: {result.get('result', 'No result')}"
            }
        else:
            return {
                "step_type": "analysis_complete",
                "result": next_action.get("result", "Browser task completed"),
                "is_final": True,
                "updated_context": context
            }
    
    async def _update_browser_state(self) -> None:
        """Update current browser state."""
        try:
            # Use the browser tool to get current state
            state_result = await self.agent.execute_tool("browser_use", {"action": "get_current_state"})
            
            if state_result.get("success"):
                self.browser_state = json.loads(state_result.get("result", "{}"))
            else:
                logger.warning(f"Failed to get browser state: {state_result.get('error')}")
                self.browser_state = {"error": "Could not retrieve browser state"}
        except Exception as e:
            logger.error(f"Error updating browser state: {e}")
            self.browser_state = {"error": str(e)}

    async def _format_browser_context(self, context: str) -> str:
        """Format context with current browser state information."""
        state_info = ""
        if self.browser_state and not self.browser_state.get("error"):
            state_info = f"""
Current Browser State:
- URL: {self.browser_state.get('url', 'Unknown')}
- Title: {self.browser_state.get('title', 'Unknown')}
- Interactive Elements: {self.browser_state.get('interactive_elements', 'None')}
- Scroll Info: {self.browser_state.get('scroll_info', {})}
"""
        elif self.browser_state and self.browser_state.get("error"):
            state_info = f"Browser State Error: {self.browser_state['error']}"
        
        return f"{context}\n\n{state_info}"
    
    async def _plan_browser_action(self, browser_context: str) -> Dict[str, Any]:
        """Plan the next browser action based on current context."""
        planning_prompt = f"""
        {browser_context}
        
        {browser.NEXT_STEP_PROMPT}
        
        Based on the current browser state and your goal, decide the next action.
        
        Respond in JSON format:
        {{
            "action": "action_name" | null,
            "parameters": {{}} if action needed,
            "reasoning": "why this action",
            "result": "final_result" if task complete
        }}
        
        Available actions: go_to_url, click_element, input_text, scroll_down, scroll_up, 
        extract_content, web_search, wait, get_current_state
        """
        
        messages = [
            {"role": "system", "content": browser.SYSTEM_PROMPT},
            {"role": "user", "content": planning_prompt}
        ]
        
        response = await self.agent.llm.acomplete(messages)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {
                "action": None,
                "result": response.content,
                "reasoning": "Could not parse action decision"
            }
    
    async def _execute_browser_action(self, action_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the planned browser action."""
        action = action_plan.get("action")
        parameters = action_plan.get("parameters", {})
        
        if not action:
            return {"success": False, "error": "No action specified"}
        
        # Add the action to parameters
        parameters["action"] = action
        
        # Execute via browser tool
        return await self.agent.execute_tool("browser_use", parameters)
