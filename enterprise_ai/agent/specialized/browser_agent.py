"""
Browser automation specialized agent for Enterprise AI.
Optimized for web interaction, navigation, and data extraction tasks.
"""

from typing import Any, Dict, Optional

from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.reasoning import ReasoningEngine
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.specialized.browser")


class BrowserAgent(BaseAgent):
    """
    Specialized agent for browser automation tasks.
    
    Optimized for:
    - Web navigation and interaction
    - Form filling and submission
    - Data extraction from websites
    - Multi-page workflows
    - Content analysis and summarization
    """
    
    def __init__(
        self,
        name: str = "browser_agent",
        llm_provider=None,
        mcp_server=None,
        **kwargs
    ):
        super().__init__(
            name=name,
            llm_provider=llm_provider,
            mcp_server=mcp_server,
            **kwargs
        )
        
        # Initialize with browser-focused reasoning
        self.reasoning_engine = ReasoningEngine(
            self,
            max_iterations=15,  # Browser tasks often need more steps
            enable_reflection=True,
            enable_planning=True,
            verbose=kwargs.get('verbose', False)
        )
        
        # Browser-specific state
        self.current_url = None
        self.navigation_history = []
        self.extracted_data = {}
        
        logger.info(f"BrowserAgent '{name}' initialized")
    
    async def think(self, input_text: str) -> str:
        """Browser-focused thinking with web context awareness."""
        browser_prompt = f"""
        Browser Task: {input_text}
        
        Current URL: {self.current_url or 'Not set'}
        Navigation History: {self.navigation_history[-3:] if self.navigation_history else 'None'}
        
        As a browser automation specialist, analyze this task and plan your approach.
        Consider:
        - What websites or pages you might need to visit
        - What data you need to extract or forms to fill
        - The sequence of browser actions required
        - Potential challenges (loading times, dynamic content, etc.)
        
        Think step-by-step about the browser automation strategy.
        """
        
        messages = [{"role": "user", "content": browser_prompt}]
        response = await self.llm.acomplete(messages)
        return response.content
    
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Plan browser-specific actions."""
        # Prioritize browser-related tools
        if "navigate" in thought.lower() or "go to" in thought.lower() or "visit" in thought.lower():
            return {
                "tool_name": "browser_use",
                "arguments": {"action": "go_to_url"},
                "reasoning": "Need to navigate to a website"
            }
        elif "click" in thought.lower() or "button" in thought.lower():
            return {
                "tool_name": "browser_use", 
                "arguments": {"action": "click_element"},
                "reasoning": "Need to click an element"
            }
        elif "extract" in thought.lower() or "data" in thought.lower():
            return {
                "tool_name": "browser_use",
                "arguments": {"action": "extract_content"},
                "reasoning": "Need to extract content from page"
            }
        elif "search" in thought.lower():
            return {
                "tool_name": "browser_use",
                "arguments": {"action": "web_search"},
                "reasoning": "Need to perform web search"
            }
        
        return None
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced tool execution with browser state tracking."""
        result = await super().execute_tool(tool_name, arguments)
        
        # Track browser state changes
        if tool_name == "browser_use" and result.get("success"):
            action = arguments.get("action")
            if action == "go_to_url":
                self.current_url = arguments.get("url")
                self.navigation_history.append(self.current_url)
            elif action == "extract_content":
                goal = arguments.get("goal", "general")
                self.extracted_data[goal] = result.get("result")
        
        return result
    
    def get_browser_summary(self) -> Dict[str, Any]:
        """Get summary of browser session."""
        return {
            "agent": self.name,
            "current_url": self.current_url,
            "pages_visited": len(self.navigation_history),
            "navigation_history": self.navigation_history,
            "extracted_data_types": list(self.extracted_data.keys()),
            "session_active": self.current_url is not None
        }
