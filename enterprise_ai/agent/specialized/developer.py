"""
Developer specialized agent for Enterprise AI.
Optimized for coding, debugging, and software development tasks.
"""

from typing import Any, Dict, Optional

from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.reasoning import ReasoningEngine
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.specialized.developer")


class DeveloperAgent(BaseAgent):
    """
    Specialized agent for software development tasks.
    
    Optimized for:
    - Code writing and review
    - Debugging and troubleshooting
    - Architecture design
    - Testing and validation
    - Documentation creation
    """
    
    def __init__(
        self,
        name: str = "developer_agent",
        llm_provider=None,
        mcp_server=None,
        programming_languages: list = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            llm_provider=llm_provider,
            mcp_server=mcp_server,
            **kwargs
        )
        
        # Developer-specific reasoning with SWE pattern preference
        self.reasoning_engine = ReasoningEngine(
            self,
            max_iterations=12,
            enable_reflection=True,
            enable_planning=True,
            verbose=kwargs.get('verbose', False)
        )
        
        # Developer specialization
        self.programming_languages = programming_languages or ["python", "javascript", "typescript"]
        self.current_project = None
        self.code_context = {}
        
        logger.info(f"DeveloperAgent '{name}' initialized for languages: {self.programming_languages}")
    
    async def think(self, input_text: str) -> str:
        """Developer-focused thinking with coding context."""
        dev_prompt = f"""
        Development Task: {input_text}
        
        My Programming Languages: {', '.join(self.programming_languages)}
        Current Project Context: {self.current_project or 'None'}
        Code Context: {self.code_context}
        
        As a software development specialist, analyze this task:
        - What type of development work is needed?
        - Which programming language would be best?
        - What tools and approaches should I use?
        - Are there any architectural considerations?
        - What testing or validation is needed?
        
        Think like an experienced developer planning the implementation.
        """
        
        messages = [{"role": "user", "content": dev_prompt}]
        response = await self.llm.acomplete(messages)
        return response.content
    
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Plan development-specific actions."""
        thought_lower = thought.lower()
        
        if "code" in thought_lower or "implement" in thought_lower or "write" in thought_lower:
            return {
                "tool_name": "python_execute",
                "arguments": {},
                "reasoning": "Need to write or execute code"
            }
        elif "file" in thought_lower or "edit" in thought_lower:
            return {
                "tool_name": "str_replace_editor",
                "arguments": {},
                "reasoning": "Need to edit files"
            }
        elif "search" in thought_lower or "documentation" in thought_lower:
            return {
                "tool_name": "web_search",
                "arguments": {},
                "reasoning": "Need to search for documentation or examples"
            }
        
        return None
