#!/usr/bin/env python3
"""
Enterprise AI: Agent Demo with Streaming Support

This script demonstrates the Agent module with different reasoning patterns
and showcases both regular and streaming processing.
"""

import asyncio
import sys
import time
from typing import AsyncIterator

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP


async def simulate_streaming_output(stream: AsyncIterator[str]) -> None:
    """Simulate streaming output with clear display."""
    print("\n💬 Response (streaming):")
    print("-" * 80)
    
    full_response = ""
    
    # For smooth display, we'll accumulate chunks and redisplay
    async for chunk in stream:
        full_response += chunk
        # Clear the line and display the updated response
        print(f"\r{full_response}", end="", flush=True)
        # Add a small delay to make streaming more visible
        await asyncio.sleep(0.01)
    
    print("\n" + "-" * 80)


async def get_single_response(agent_name: str, agent_role: str, reasoning: str, query: str, use_streaming: bool = False) -> None:
    """Get a single response from an agent with specified parameters."""
    print(f"\n🤖 Testing {agent_name} with {reasoning} reasoning")
    print(f"📝 Query: {query}")
    
    # Create simple role - the reasoning pattern will handle specific prompts
    role = AgentRole(
        name=agent_role,
        system_prompt=f"You are a {agent_role} specialized in providing detailed, helpful responses.",
    )
    
    # Create LLM - fixed the create_provider call with provider_name
    llm = create_provider(
        provider_name="ollama", 
        model_name="llama3.2",
        timeout=60.0,
        verbose=False
    )
    
    # Create MCP
    mcp = ToolMCP(
        timeout=300.0,
        auto_load_tools=True
    )
    
    # Create agent
    agent = create_agent(
        name=agent_name,
        role=role,
        llm=llm,
        mcp=mcp,
        reasoning_pattern=reasoning,
        verbose=False
    )
    
    # Process query
    start_time = time.time()
    
    if use_streaming:
        # Use streaming
        stream = agent.process_stream(query)
        await simulate_streaming_output(stream)
    else:
        # Regular processing
        response = await agent.process(query)
        elapsed = time.time() - start_time
        
        print(f"\n💬 Response (completed in {elapsed:.2f}s):")
        print("-" * 80)
        print(response)
        print("-" * 80)


async def run_agent_demo() -> None:
    """Run the agent demo with multiple tests."""
    print("🚀 Enterprise AI Agent Demo with Streaming Support")
    print("=" * 80)
    
    # Test scenarios
    tests = [
        # Format: (agent_name, agent_role, reasoning_pattern, query, use_streaming)
        ("FactBot", "Research Assistant", "react", "What are three interesting facts about quantum computing?", False),
        ("FactBot", "Research Assistant", "react", "What are three interesting facts about quantum computing?", True),
        ("MathHelper", "Mathematics Tutor", "cot", "Explain how to solve this equation: 2x + 5 = 15", False),
        ("MathHelper", "Mathematics Tutor", "cot", "Explain how to solve this equation: 2x + 5 = 15", True),
        ("CodeExpert", "Software Engineer", "swe", "Write a Python function to check if a string is a palindrome", False),
        ("ToolExpert", "Research Assistant", "react", "What's the current weather in New York City?", True),
    ]
    
    for agent_name, agent_role, reasoning, query, streaming in tests:
        await get_single_response(agent_name, agent_role, reasoning, query, streaming)
        print("\n" + "=" * 80)
    
    print("\n🏁 Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(run_agent_demo())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)