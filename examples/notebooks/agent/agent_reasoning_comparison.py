#!/usr/bin/env python3
"""
Enterprise AI: Agent Reasoning Pattern Comparison

This script demonstrates the differences between reasoning patterns
by comparing their responses to the same query.
"""

import asyncio
import sys
import time
from typing import Tuple

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP


async def get_agent_response(
    agent_name: str, 
    agent_role: str, 
    reasoning: str, 
    query: str
) -> Tuple[str, float]:
    """
    Get a response from an agent with specified parameters.
    
    Returns:
        Tuple of (response, elapsed_time)
    """
    # Create a simple role - each reasoning pattern will add its own prompts
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
        timeout=30.0,
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
    
    # Process query with timing
    start_time = time.time()
    response = await agent.process(query)
    elapsed = time.time() - start_time
    
    return response, elapsed


async def compare_reasoning_patterns() -> None:
    """Compare different reasoning patterns on the same queries."""
    print("🔍 Enterprise AI Agent Reasoning Pattern Comparison")
    print("=" * 80)
    
    # Test queries to compare
    test_queries = [
        "Explain how neural networks work in simple terms",
        "What are the steps to debug a memory leak in a Python application?",
        "Compare and contrast different sorting algorithms",
        "What's the difference between supervised and unsupervised learning?",
    ]
    
    # Reasoning patterns to compare
    patterns = ["react", "cot", "swe"]
    
    for i, query in enumerate(test_queries):
        print(f"\n📝 Query {i+1}: {query}")
        print("-" * 80)
        
        results = {}
        
        # Get responses from each reasoning pattern
        for pattern in patterns:
            pattern_name = {
                "react": "ReAct (Reasoning + Acting)",
                "cot": "Chain of Thought",
                "swe": "Software Engineering"
            }.get(pattern, pattern)
            
            print(f"🔄 Processing with {pattern_name}...")
            response, elapsed = await get_agent_response(
                agent_name="TestAgent",
                agent_role="Assistant",
                reasoning=pattern,
                query=query
            )
            
            results[pattern] = {
                "response": response,
                "elapsed": elapsed
            }
            
            print(f"  ✅ Completed in {elapsed:.2f}s")
        
        # Display results
        print("\n📊 Results Comparison:")
        print("-" * 80)
        
        for pattern in patterns:
            pattern_name = {
                "react": "ReAct",
                "cot": "Chain of Thought",
                "swe": "Software Engineering"
            }.get(pattern, pattern)
            
            elapsed = results[pattern]["elapsed"]
            response = results[pattern]["response"]
            
            # Truncate response if too long
            preview = response[:150] + "..." if len(response) > 150 else response
            preview = preview.replace("\n", " ")
            
            print(f"📌 {pattern_name} ({elapsed:.2f}s):")
            print(f"  {preview}")
            print()
            
        print("=" * 80)
    
    print("\n🏁 Comparison completed!")


if __name__ == "__main__":
    try:
        asyncio.run(compare_reasoning_patterns())
    except KeyboardInterrupt:
        print("\n\nComparison interrupted by user.")
        sys.exit(0)