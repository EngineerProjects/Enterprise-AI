"""
General-purpose Enterprise AI agent.
Versatile agent similar to OpenManus Manus for handling various tasks.
"""

from typing import Any, Dict, Optional

from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.reasoning import ReasoningEngine
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.specialized.general_purpose")


class GeneralPurposeAgent(BaseAgent):
    """
    Versatile general-purpose agent for Enterprise AI.
    
    Can handle:
    - Coding and development tasks
    - Research and information gathering  
    - Browser automation
    - Data analysis and processing
    - Content creation and editing
    """
    
    def __init__(
        self,
        name: str = "general_agent", 
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
        
        # Multi-pattern reasoning for versatility
        self.reasoning_engine = ReasoningEngine(
            self,
            max_iterations=12,
            enable_reflection=True,
            enable_planning=True,
            verbose=kwargs.get('verbose', False)
        )
        
        # Track specialization based on usage
        self.task_history = []
        self.preferred_patterns = ["react", "cot"]
        
        logger.info(f"GeneralPurposeAgent '{name}' initialized")
    
    async def think(self, input_text: str) -> str:
        """Adaptive thinking based on task type."""
        context_prompt = f"""
        Task: {input_text}
        
        Recent Task Types: {[t.get('type') for t in self.task_history[-3:]]}
        My Capabilities: Coding, Research, Browser Automation, Analysis, Content Creation
        
        Analyze this task and determine the best approach:
        - What type of task is this?
        - What tools and reasoning patterns would be most effective?
        - What's the expected outcome?
        
        Think adaptively about the optimal strategy.
        """
        
        messages = [{"role": "user", "content": context_prompt}]
        response = await self.llm.acomplete(messages)
        
        # Track task type for learning
        task_type = self._classify_task(input_text)
        self.task_history.append({"type": task_type, "input": input_text})
        
        return response.content
    
    def _classify_task(self, input_text: str) -> str:
        """Simple task classification for learning."""
        text_lower = input_text.lower()
        if any(word in text_lower for word in ["code", "program", "debug", "implement"]):
            return "coding"
        elif any(word in text_lower for word in ["search", "find", "research", "analyze"]):
            return "research"
        elif any(word in text_lower for word in ["browse", "website", "navigate", "click"]):
            return "browser"
        else:
            return "general"
    
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Intelligent action planning based on context."""
        # Use recent task history to inform decisions
        recent_types = [t.get('type') for t in self.task_history[-3:]]
        
        # Simple adaptive planning
        if "code" in thought.lower() or recent_types.count("coding") > 1:
            return {"tool_name": "python_execute", "arguments": {}}
        elif "search" in thought.lower() or recent_types.count("research") > 1:
            return {"tool_name": "web_search", "arguments": {}}
        elif "browse" in thought.lower() or recent_types.count("browser") > 1:
            return {"tool_name": "browser_use", "arguments": {}}
        
        return None
