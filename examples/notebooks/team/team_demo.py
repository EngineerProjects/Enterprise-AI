#!/usr/bin/env python3
"""
Enterprise AI: Team Demo

This script demonstrates the Team module with a manager and worker agents.
"""

import asyncio
import sys
from typing import Dict, List

from enterprise_ai.agent import AgentRole
from enterprise_ai.team import Team, create_team
from enterprise_ai.team.prompts.manager import MANAGER_SYSTEM_PROMPT
from enterprise_ai.team.prompts.collaboration import COLLABORATION_SYSTEM_PROMPT


async def team_demo():
    """
    Demonstrate the Team module with a simple task.
    """
    print("🚀 Enterprise AI Team Demo")
    print("=" * 80)
    
    # Define roles for team agents
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
    
    analyst_role = AgentRole(
        name="Analyst",
        system_prompt=f"{COLLABORATION_SYSTEM_PROMPT}\n\nYou are an Analysis Specialist with expertise in evaluating data, identifying patterns, and drawing insights. Focus on critical thinking and providing balanced, nuanced perspectives."
    )
    
    # Define agent roles dictionary
    agent_roles = {
        "researcher": researcher_role,
        "writer": writer_role,
        "analyst": analyst_role
    }
    
    # Create team
    print("🤖 Creating team with manager and worker agents...")
    
    team = create_team(
        name="ResearchTeam",
        agent_roles=agent_roles,
        manager_role=manager_role,
        reasoning_patterns={
            "manager": "react",
            "researcher": "react",
            "writer": "cot",
            "analyst": "cot"
        },
        verbose=True
    )
    
    print(f"✅ Created team '{team.name}' with manager and {len(team.agents)} worker agents")
    
    # Process tasks with the team
    tasks = [
        "What are the key challenges and opportunities in implementing responsible AI governance?",
        "Compare and contrast the environmental impact of electric vehicles versus traditional combustion engine vehicles.",
        "Explain the concept of quantum computing and its potential applications in simple terms."
    ]
    
    for i, task in enumerate(tasks):
        print(f"\n\n📝 Task {i+1}: {task}")
        print("-" * 80)
        
        try:
            # Process task with team
            print("⏳ Processing task with team (this may take a while)...")
            response = await team.process(task)
            
            print("\n💬 Team Response:")
            print("-" * 80)
            print(response)
            print("-" * 80)
            
            # Reset team for next task
            if i < len(tasks) - 1:
                team.reset()
                print("\n🔄 Reset team for next task")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n🏁 Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(team_demo())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)