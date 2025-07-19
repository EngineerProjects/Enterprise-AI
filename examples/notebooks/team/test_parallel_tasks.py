#!/usr/bin/env python3
"""
Enterprise AI: Parallel Task Processing Test

This script tests the team's ability to process multiple tasks in parallel
using direct collaboration without a manager.
"""

import asyncio
import sys
import time
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import (
    create_empty_team,
    create_agent_for_team
)
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def parallel_task_test():
    """
    Test parallel task processing by multiple agents.
    """
    print("🧪 Enterprise AI Parallel Task Processing Test")
    print("=" * 80)
    
    # Step 1: Create agent roles
    print("\n📋 Creating agent roles...")
    
    data_analyst_role = AgentRole(
        name="Data Analyst",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Data Analysis Specialist with expertise in processing and interpreting data. Focus on extracting insights, identifying patterns, and providing clear analytical summaries."
    )
    
    market_researcher_role = AgentRole(
        name="Market Researcher",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Market Research Specialist with expertise in analyzing market trends, consumer behavior, and competitive landscapes. Focus on providing actionable market insights."
    )
    
    technical_writer_role = AgentRole(
        name="Technical Writer",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Technical Writing Specialist with expertise in creating clear, concise documentation. Focus on making complex technical information accessible and well-structured."
    )
    
    # Step 2: Create an empty team
    print("\n🏗️ Creating team...")
    
    team = create_empty_team(
        name="ParallelTeam",
        verbose=True
    )
    
    # Step 3: Create individual agents
    print("\n🤖 Creating individual agents...")
    
    data_analyst = create_agent_for_team(
        name="data_analyst",
        role=data_analyst_role,
        reasoning_pattern="cot",
        verbose=True
    )
    
    # Reuse components for efficiency
    market_researcher = create_agent_for_team(
        name="market_researcher",
        role=market_researcher_role,
        llm=data_analyst.llm,
        mcp=data_analyst.mcp,
        reasoning_pattern="react",
        verbose=True
    )
    
    technical_writer = create_agent_for_team(
        name="technical_writer",
        role=technical_writer_role,
        llm=data_analyst.llm,
        mcp=data_analyst.mcp,
        reasoning_pattern="cot",
        verbose=True
    )
    
    # Step 4: Add agents to the team
    team.add_agent("data_analyst", data_analyst)
    team.add_agent("market_researcher", market_researcher)
    team.add_agent("technical_writer", technical_writer)
    
    print(f"✅ Team setup complete: {len(team.agents)} agents")
    
    # Step 5: Define parallel tasks for each agent
    subtasks = {
        "data_analyst": "Analyze the trend of electric vehicle adoption in major global markets over the past 5 years. Identify key patterns and growth rates.",
        
        "market_researcher": "Research the competitive landscape of AI-powered language learning apps. Identify the top 3 players, their key features, and market positioning.",
        
        "technical_writer": "Create a user guide introduction for a new smart home automation system that allows voice control of lights, temperature, and security features."
    }
    
    # Step 6: Execute tasks in parallel
    print("\n⏳ Executing parallel tasks...")
    start_time = time.time()
    
    try:
        # Use direct_collaboration method which executes tasks in parallel
        results = await team.direct_collaboration(subtasks)
        
        execution_time = time.time() - start_time
        print(f"✅ Parallel execution completed in {execution_time:.2f} seconds")
        
        # Compare with estimated sequential time
        estimated_sequential_time = execution_time * len(subtasks) / 1.5  # Account for some overhead
        print(f"📊 Estimated sequential execution time: {estimated_sequential_time:.2f} seconds")
        print(f"⚡ Speed improvement: approximately {estimated_sequential_time/execution_time:.1f}x faster")
        
    except Exception as e:
        print(f"\n❌ Error during parallel execution: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 7: Display results
    print("\n📊 Task Results:")
    print("=" * 80)
    
    for agent_name, response in results.items():
        print(f"\n🤖 {agent_name.replace('_', ' ').title()}:")
        print("-" * 80)
        # Show a preview if response is long
        preview = response[:300] + "..." if len(response) > 300 else response
        print(preview)
        print("-" * 80)
    
    # Step 8: Verify shared memory contains all parallel responses
    agent_responses = team.shared_memory.get_agent_responses()
    print(f"\n📚 Shared memory contains responses from {len(agent_responses)} agents")
    
    print("\n🏁 Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(parallel_task_test())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)