#!/usr/bin/env python3
"""
Enterprise AI: Manager Agent Delegation Test

This script tests the manager agent's ability to automatically
delegate tasks to appropriate worker agents.
"""

import asyncio
import sys
import re
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import (
    create_empty_team,
    create_agent_for_team,
    create_manager_agent
)
from enterprise_ai.team.prompts.manager import MANAGER_SYSTEM_PROMPT
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def manager_delegation_test():
    """
    Test manager agent delegation to worker agents.
    """
    print("🧪 Enterprise AI Manager Agent Delegation Test")
    print("=" * 80)
    
    # Step 1: Create agent roles
    print("\n📋 Creating agent roles...")
    
    manager_role = AgentRole(
        name="Team Manager",
        system_prompt=MANAGER_SYSTEM_PROMPT
    )
    
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
    
    # Step 2: Create an empty team
    print("\n🏗️ Creating team...")
    
    team = create_empty_team(
        name="ManagerTeam",
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
    
    # Step 5: Create and set the manager
    print("\n👔 Creating and setting manager...")
    
    manager = create_manager_agent(
        name="manager",
        role=manager_role,
        team_agents=["researcher", "writer", "coder"],
        llm=researcher.llm,
        mcp=researcher.mcp,
        verbose=True
    )
    
    team.set_manager(manager)
    
    print(f"✅ Team setup complete: {len(team.agents)} agents + manager")
    
    # Step 6: Process a task that requires multiple agents
    user_input = """
    I need a comprehensive report on quantum computing. It should include:
    1. Recent advancements in the field
    2. A well-written explanation of quantum computing principles for non-experts
    3. Simple code examples in Python to demonstrate quantum algorithms using a simulation library
    """
    
    print(f"\n📝 Task: {user_input}")
    print("⏳ Processing with manager (this may take a while)...")
    
    try:
        # Process through the manager
        response = await team.process(user_input)
        
        print("\n✅ Task processing completed")
        
        # Check for delegation patterns in the response
        delegation_pattern = r"DELEGATE\[([^\]]+)\]:\s*(.*?)(?=DELEGATE\[|$)"
        delegations = re.findall(delegation_pattern, response, re.DOTALL)
        
        if delegations:
            print(f"\n🔍 Found {len(delegations)} delegations in the manager's response")
            for agent_name, task in delegations:
                print(f"  • Delegated to {agent_name.strip()}: {task.strip()[:50]}...")
        else:
            print("\n⚠️ No explicit delegations found in the response")
        
        # Display the final result
        print("\n📊 Final Response (excerpt):")
        print("=" * 80)
        excerpt = response[:500] + "..." if len(response) > 500 else response
        print(excerpt)
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 7: Check for individual agent contributions in shared memory
    print("\n📚 Checking agent contributions in shared memory...")
    
    agent_responses = team.shared_memory.get_agent_responses()
    for agent_name in team.agents.keys():
        if agent_name in agent_responses and agent_responses[agent_name]:
            print(f"✅ Found contribution from {agent_name}")
        else:
            print(f"❓ No recorded contribution from {agent_name}")
    
    print("\n🏁 Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(manager_delegation_test())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)