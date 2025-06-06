"""
Tool integration management for individual Enterprise AI agents.
Handles how individual agents interact with and use tools.
"""

from typing import Any, Dict, List, Optional, Set
import asyncio

from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.capabilities.tool_integration")


class ToolIntegrationManager:
    """
    Tool integration manager for individual agents.
    
    Manages tool preferences, tool usage patterns,
    and tool execution optimization for single agents.
    """
    
    def __init__(self, agent_name: str):
        """Initialize tool integration manager."""
        self.agent_name = agent_name
        
        # Tool preferences and usage tracking
        self.preferred_tools: Set[str] = set()
        self.tool_usage_count: Dict[str, int] = {}
        self.tool_success_rate: Dict[str, float] = {}
        self.tool_performance_history: Dict[str, List[float]] = {}
        
        logger.info(f"ToolIntegrationManager initialized for {agent_name}")
    
    def track_tool_usage(
        self,
        tool_name: str,
        success: bool,
        execution_time: float = 0.0
    ) -> None:
        """Track tool usage statistics."""
        # Update usage count
        self.tool_usage_count[tool_name] = self.tool_usage_count.get(tool_name, 0) + 1
        
        # Update success rate
        current_rate = self.tool_success_rate.get(tool_name, 0.0)
        total_uses = self.tool_usage_count[tool_name]
        
        if success:
            new_rate = ((current_rate * (total_uses - 1)) + 1.0) / total_uses
        else:
            new_rate = (current_rate * (total_uses - 1)) / total_uses
        
        self.tool_success_rate[tool_name] = new_rate
        
        # Track performance
        if tool_name not in self.tool_performance_history:
            self.tool_performance_history[tool_name] = []
        
        self.tool_performance_history[tool_name].append(execution_time)
        
        # Keep only recent performance data
        if len(self.tool_performance_history[tool_name]) > 100:
            self.tool_performance_history[tool_name] = \
                self.tool_performance_history[tool_name][-50:]
        
        logger.debug(f"Tracked tool usage: {tool_name}, success: {success}")
    
    def get_recommended_tools(self, task_type: str = None) -> List[str]:
        """Get recommended tools based on usage patterns."""
        # Simple recommendation based on success rate and usage
        tool_scores = {}
        
        for tool_name in self.tool_success_rate:
            success_rate = self.tool_success_rate[tool_name]
            usage_count = self.tool_usage_count[tool_name]
            
            # Simple scoring: success_rate * log(usage_count + 1)
            import math
            score = success_rate * math.log(usage_count + 1)
            tool_scores[tool_name] = score
        
        # Sort by score and return top tools
        sorted_tools = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
        return [tool for tool, score in sorted_tools[:10]]
    
    def add_preferred_tool(self, tool_name: str) -> None:
        """Add a tool to the preferred tools set."""
        self.preferred_tools.add(tool_name)
        logger.info(f"Added preferred tool: {tool_name}")
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tool usage statistics."""
        return {
            "agent": self.agent_name,
            "preferred_tools": list(self.preferred_tools),
            "usage_count": dict(self.tool_usage_count),
            "success_rates": dict(self.tool_success_rate),
            "top_tools": self.get_recommended_tools()
        }
