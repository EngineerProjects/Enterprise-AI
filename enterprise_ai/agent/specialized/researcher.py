"""
Research specialized agent for Enterprise AI.
Optimized for information gathering, analysis, and research tasks.
"""

from typing import Any, Dict, Optional

from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.reasoning import ReasoningEngine
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.specialized.researcher")


class ResearcherAgent(BaseAgent):
    """
    Specialized agent for research and information gathering.
    
    Optimized for:
    - Web research and fact-finding
    - Data collection and analysis
    - Report generation
    - Information synthesis
    - Content summarization
    """
    
    def __init__(
        self,
        name: str = "researcher_agent",
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
        
        # Research-focused reasoning
        self.reasoning_engine = ReasoningEngine(
            self,
            max_iterations=10,
            enable_reflection=True,
            enable_planning=True,
            verbose=kwargs.get('verbose', False)
        )
        
        # Research state
        self.research_findings = []
        self.sources_used = []
        
        logger.info(f"ResearcherAgent '{name}' initialized")
    
    async def think(self, input_text: str) -> str:
        """Research-focused thinking."""
        research_prompt = f"""
        Research Task: {input_text}
        
        Previous Findings: {len(self.research_findings)} items collected
        Sources Used: {len(self.sources_used)} sources
        
        As a research specialist, plan your information gathering approach:
        - What specific information do you need to find?
        - What are the best sources to search?
        - How will you verify the information?
        - What analysis or synthesis is needed?
        
        Think systematically about the research strategy.
        """
        
        messages = [{"role": "user", "content": research_prompt}]
        response = await self.llm.acomplete(messages)
        return response.content
    
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Plan research-specific actions."""
        if "search" in thought.lower() or "find" in thought.lower():
            return {
                "tool_name": "web_search",
                "arguments": {},
                "reasoning": "Need to search for information"
            }
        elif "browse" in thought.lower() or "website" in thought.lower():
            return {
                "tool_name": "browser_use",
                "arguments": {"action": "go_to_url"},
                "reasoning": "Need to browse a specific website"
            }
        
        return None
