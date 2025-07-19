#!/usr/bin/env python3
"""
Enterprise AI: Simple Team Demo

This script demonstrates a minimal team setup with a manager and one worker agent.
"""

import asyncio
import sys
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import Team, create_team
from enterprise_ai.team.prompts.manager import MANAGER_SYSTEM_PROMPT
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def simple_team_demo():
    """
    Demonstrate the Team module with a minimal setup.
    """
    print("🚀 Enterprise AI Simple Team Demo")
    print("=" * 80)
    
    # Define roles for team agents
    print("\n📋 Creating agent roles...")
    
    manager_role = AgentRole(
        name="Team Manager",
        system_prompt=MANAGER_SYSTEM_PROMPT
    )
    
    assistant_role = AgentRole(
        name="Research Assistant",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are a Research Assistant with expertise in finding and analyzing information. You excel at web searches, data analysis, and providing concise summaries."
    )
    
    # Create team
    print("🤖 Creating team with manager and assistant...")
    
    team = create_team(
        name="SimpleTeam",
        agent_roles={"assistant": assistant_role},
        manager_role=manager_role,
        verbose=True
    )
    
    print(f"✅ Created team '{team.name}' with manager and {len(team.agents)} worker agent")
    
    # Process a task with the team
    user_input = "Give me a concise summary of quantum computing and why it's important."
    
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
    
    print("\n🏁 Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(simple_team_demo())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)