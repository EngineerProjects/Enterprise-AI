#!/usr/bin/env python3
"""
Enterprise AI: Flexible Team Construction Demo

This script demonstrates the flexible approach to team construction,
where agents are created separately and then added to the team.
"""

import asyncio
import sys
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import (
    Team, 
    create_empty_team,
    create_agent_for_team,
    create_manager_agent
)
from enterprise_ai.team.prompts.manager import MANAGER_SYSTEM_PROMPT
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def flexible_team_demo():
    """
    Demonstrate flexible team construction.
    """
    print("🚀 Enterprise AI Flexible Team Construction Demo")
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
    
    # Step 2: Create an empty team
    print("\n🏗️ Creating empty team...")
    
    team = create_empty_team(
        name="FlexibleTeam",
        verbose=True
    )
    
    print(f"✅ Created empty team '{team.name}'")
    
    # Step 3: Create individual agents
    print("\n🤖 Creating individual agents...")
    
    # Create LLM and MCP only once to share across agents
    researcher = create_agent_for_team(
        name="researcher",
        role=researcher_role,
        reasoning_pattern="react",
        verbose=True
    )
    
    # Reuse the LLM and MCP from the researcher
    writer = create_agent_for_team(
        name="writer",
        role=writer_role,
        llm=researcher.llm,
        mcp=researcher.mcp,
        reasoning_pattern="cot",
        verbose=True
    )
    
    # Step 4: Add agents to the team
    print("\n➕ Adding agents to team...")
    
    team.add_agent("researcher", researcher)
    team.add_agent("writer", writer)
    
    # Step 5: Create and set the manager
    print("\n👔 Creating and setting manager...")
    
    manager = create_manager_agent(
        name="manager",
        role=manager_role,
        team_agents=["researcher", "writer"],
        llm=researcher.llm,  # Reuse LLM
        mcp=researcher.mcp,  # Reuse MCP
        verbose=True
    )
    
    team.set_manager(manager)
    
    print(f"✅ Team construction complete: {len(team.agents)} agents + manager")
    
    # Step 6: Process a task with the team
    user_input = "Compare solar and wind energy as renewable energy sources. Include their efficiency, cost, and environmental impact."
    
    print(f"\n\n📝 Task: {user_input}")
    print("-" * 80)
    
    try:
        # Process task with team
        print("⏳ Processing task with team...")
        response = await team.process(user_input)
        
        print("\n💬 Team Response:")
        print("-" * 80)
        print(response)
        print("-" * 80)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 7: Demonstrate direct delegation without going through manager
    print("\n🔄 Demonstrating direct delegation to researcher...")
    
    research_task = "Find and summarize three recent innovations in solar panel technology."
    
    try:
        research_response = await team.delegate_task("researcher", research_task)
        
        print("\n🔍 Researcher Response:")
        print("-" * 80)
        print(research_response)
        print("-" * 80)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
    print("\n🏁 Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(flexible_team_demo())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)