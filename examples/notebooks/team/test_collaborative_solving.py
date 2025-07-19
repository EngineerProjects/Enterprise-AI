#!/usr/bin/env python3
"""
Enterprise AI: Collaborative Sequential Solving Test

This script tests the ability to solve a problem by passing it through
a sequence of agents, each contributing their expertise.
"""

import asyncio
import sys
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import (
    create_empty_team,
    create_agent_for_team
)
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def collaborative_solving_test():
    """
    Test collaborative solving with a sequence of agents.
    """
    print("🧪 Enterprise AI Collaborative Sequential Solving Test")
    print("=" * 80)
    
    # Step 1: Create agent roles
    print("\n📋 Creating agent roles...")
    
    researcher_role = AgentRole(
        name="Researcher",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Research Specialist with expertise in finding and analyzing information from various sources. Your task is to gather facts and relevant data."
    )
    
    analyst_role = AgentRole(
        name="Analyst",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are an Analysis Specialist with expertise in evaluating information and identifying patterns. Your task is to analyze data and provide insights."
    )
    
    writer_role = AgentRole(
        name="Writer",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Writing Specialist with expertise in crafting clear, engaging content. Your task is to organize information into a well-structured, compelling narrative."
    )
    
    # Step 2: Create an empty team
    print("\n🏗️ Creating team...")
    
    team = create_empty_team(
        name="SequentialTeam",
        verbose=True
    )
    
    # Step 3: Create individual agents
    print("\n🤖 Creating individual agents...")
    
    researcher = create_agent_for_team(
        name="researcher",
        role=researcher_role,
        reasoning_pattern="react",
        verbose=True
    )
    
    # Reuse components for efficiency
    analyst = create_agent_for_team(
        name="analyst",
        role=analyst_role,
        llm=researcher.llm,
        mcp=researcher.mcp,
        reasoning_pattern="cot",
        verbose=True
    )
    
    writer = create_agent_for_team(
        name="writer",
        role=writer_role,
        llm=researcher.llm,
        mcp=researcher.mcp,
        reasoning_pattern="cot",
        verbose=True
    )
    
    # Step 4: Add agents to the team
    team.add_agent("researcher", researcher)
    team.add_agent("analyst", analyst)
    team.add_agent("writer", writer)
    
    print(f"✅ Team setup complete: {len(team.agents)} agents")
    
    # Step 5: Define the main task
    main_task = "Create a comprehensive overview of artificial intelligence's impact on healthcare."
    
    # Step 6: Define the sequence of agents to process the task
    agent_sequence = ["researcher", "analyst", "writer"]
    
    # Step 7: Process the task through the sequence
    print(f"\n📝 Main Task: {main_task}")
    print(f"🔄 Processing sequence: {' → '.join(agent_sequence)}")
    
    try:
        # Use collaborative_solve method from the Team class
        final_response = await team.collaborative_solve(main_task, agent_sequence)
        
        print("\n✅ Collaborative solving completed")
        
        # Display the final result
        print("\n📊 Final Result:")
        print("=" * 80)
        print(final_response)
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error during collaborative solving: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 8: Verify shared memory for each agent's contribution
    print("\n📚 Checking shared memory for agent contributions...")
    
    agent_responses = team.shared_memory.get_agent_responses()
    for agent_name in agent_sequence:
        if agent_name in agent_responses and agent_responses[agent_name]:
            print(f"✅ Found contribution from {agent_name}")
        else:
            print(f"❌ No contribution found from {agent_name}")
    
    print("\n🏁 Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(collaborative_solving_test())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)