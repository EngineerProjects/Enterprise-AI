"""
Example usage of the reasoning engine with Enterprise AI agents.
This demonstrates how to create and use agents with different reasoning patterns.
"""

import asyncio
from typing import Dict, Any, Optional

from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.reasoning import ReasoningEngine
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.server import EnterpriseMCPServer
from enterprise_ai.mcp.config import MCPConfig


class SimpleAgent(BaseAgent):
    """Simple agent implementation for demonstration."""
    
    async def think(self, input_text: str) -> str:
        """Generate thoughts for the input."""
        messages = [{"role": "user", "content": f"Think about: {input_text}"}]
        response = await self.llm.acomplete(messages)
        return response.content
    
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Plan the next action based on current thought."""
        if "search" in thought.lower():
            return {
                "tool_name": "search",
                "arguments": {"query": "relevant search terms"}
            }
        elif "complete" in thought.lower():
            return None
        else:
            return {
                "tool_name": "analyze", 
                "arguments": {"data": thought}
            }


async def demo_reasoning_patterns():
    """Demonstrate different reasoning patterns."""
    
    # Setup MCP server
    config = MCPConfig(execution_mode="auto", verbose_logging=True)
    mcp_server = EnterpriseMCPServer(config)
    
    # Setup LLM
    llm = create_provider("ollama", "llama3.2", verbose=True)
    
    # Create agent with reasoning engine
    agent = SimpleAgent(
        name="demo_agent",
        llm_provider=llm,
        mcp_server=mcp_server,
        reasoning_engine=None  # Will be set below
    )
    
    # Initialize agent
    await agent.initialize()
    
    # Test different reasoning patterns
    patterns_to_test = [
        ("react", "Solve this problem: What is the capital of France?"),
        ("cot", "Analyze step-by-step: How does photosynthesis work?"),
        ("swe", "Design and implement a simple calculator function in Python"),
    ]
    
    for pattern, task in patterns_to_test:
        print(f"\n{'='*60}")
        print(f"Testing {pattern.upper()} pattern")
        print(f"Task: {task}")
        print(f"{'='*60}")
        
        # Create reasoning engine with specific pattern
        if pattern == "react":
            reasoning_engine = ReasoningEngine(
                agent,
                enable_planning=False,
                enable_reflection=True,
                verbose=True
            )
        elif pattern == "cot":
            reasoning_engine = ReasoningEngine(
                agent,
                enable_planning=True,
                enable_reflection=False,
                verbose=True
            )
        else:  # swe
            reasoning_engine = ReasoningEngine(
                agent,
                enable_planning=True,
                enable_reflection=True,
                verbose=True
            )
        
        agent.reasoning_engine = reasoning_engine
        
        # Execute task
        result = await agent.execute_task(task)
        
        print(f"\nResult: {result.get('success', False)}")
        if result.get('success'):
            print(f"Output: {result.get('result', {}).get('result', 'No result')}")
            print(f"Patterns used: {result.get('patterns_used', [])}")
            print(f"Iterations: {result.get('iterations', 0)}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
    
    # Cleanup
    await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(demo_reasoning_patterns())
