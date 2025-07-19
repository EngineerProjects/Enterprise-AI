#!/usr/bin/env python3
"""
Enterprise AI: Direct Task Delegation Test

This script tests the ability to directly delegate tasks to specific agents
without going through the manager.
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


async def direct_delegation_test():
    """
    Test direct delegation to specific agents.
    """
    print("🧪 Enterprise AI Direct Task Delegation Test")
    print("=" * 80)
    
    # Step 1: Create agent roles
    print("\n📋 Creating agent roles...")
    
    researcher_role = AgentRole(
        name="Researcher",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Research Specialist with expertise in finding and analyzing information from various sources. Focus on providing comprehensive, accurate information while citing sources when possible."
    )
    
    writer_role = AgentRole(
        name="Writer",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Writing Specialist with expertise in crafting clear, engaging content. Focus on organizing information logically and presenting it in an accessible, compelling manner."
    )
    
    coder_role = AgentRole(
        name="Coder",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Coding Specialist with expertise in software development. Focus on writing clean, efficient code, explaining technical concepts, and providing practical implementation guidance."
    )
    
    # Step 2: Create an empty team without a manager
    print("\n🏗️ Creating team without a manager...")
    
    team = create_empty_team(
        name="DirectTeam",
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
    
    # Reuse the LLM and MCP from the researcher for efficiency
    writer = create_agent_for_team(
        name="writer",
        role=writer_role,
        llm=researcher.llm,
        mcp=researcher.mcp,
        reasoning_pattern="cot",
        verbose=True
    )
    
    coder = create_agent_for_team(
        name="coder",
        role=coder_role,
        llm=researcher.llm,
        mcp=researcher.mcp,
        reasoning_pattern="swe",
        verbose=True
    )
    
    # Step 4: Add agents to the team
    team.add_agent("researcher", researcher)
    team.add_agent("writer", writer)
    team.add_agent("coder", coder)
    
    print(f"✅ Team setup complete: {len(team.agents)} agents")
    
    # Step 5: Create tasks for each agent
    tasks = {
        "researcher": "Find three key innovations in quantum computing from the last 2 years.",
        "writer": "Write a short blog introduction about renewable energy sources.",
        "coder": "Write a Python function that checks if a string is a palindrome."
    }
    
    # Step 6: Delegate tasks directly to each agent
    results = {}
    
    print("\n🧪 Testing direct task delegation...")
    for agent_name, task in tasks.items():
        print(f"\n📝 Delegating to {agent_name}: {task}")
        try:
            response = await team.delegate_task(agent_name, task)
            results[agent_name] = response
            print(f"✅ {agent_name.capitalize()} completed the task")
        except Exception as e:
            print(f"❌ Error with {agent_name}: {e}")
    
    # Step 7: Display results
    print("\n📊 Task Results:")
    print("=" * 80)
    
    for agent_name, response in results.items():
        print(f"\n🤖 {agent_name.capitalize()}:")
        print("-" * 80)
        # Show a preview if response is long
        preview = response[:300] + "..." if len(response) > 300 else response
        print(preview)
        print("-" * 80)
    
    # Step 8: Verify shared memory contains all agent responses
    agent_responses = team.shared_memory.get_agent_responses()
    print(f"\n📚 Shared memory contains {len(agent_responses)} agent responses")
    
    print("\n🏁 Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(direct_delegation_test())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)