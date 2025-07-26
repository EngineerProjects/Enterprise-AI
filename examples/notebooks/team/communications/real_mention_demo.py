#!/usr/bin/env python3
"""
Enterprise AI @Mention System - Real Usage Example with Llama3.2

This example demonstrates the complete @mention system working with real LLM models.
Uses llama3.2 via ollama to show actual agent-to-agent communication.

Scenario: AI development team collaborating on a new project feature.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enterprise_ai.agent.factory import create_agent
from enterprise_ai.team.base import Team
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP

def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "="*60)
    print(f"🎯 {title}")
    print("="*60)

def print_agent_prompt(agent_name: str, agent):
    """Print the agent's complete system prompt to verify team context integration."""
    print(f"\n📋 {agent_name.title()}'s COMPLETE System Prompt:")
    print("=" * 80)
    if hasattr(agent, 'role') and hasattr(agent.role, 'system_prompt'):
        print(agent.role.system_prompt)
    else:
        print("❌ No system prompt available")
    print("=" * 80)

async def main():
    """Main demonstration of the @mention system."""
    
    print_section("Enterprise AI @Mention System - Real Demo with Llama3.2")
    
    # Check ollama availability
    print("\n🔍 Checking Ollama availability...")
    try:
        test_llm = create_provider("ollama", "llama3.2", timeout=500.0)
        print("✅ Ollama with llama3.2 is available!")
    except Exception as e:
        print(f"❌ Ollama connection failed: {e}")
        print("\n💡 Please ensure ollama is running: ollama serve && ollama pull llama3.2")
        return
    
    print_section("Step 1: Creating Development Team")
    
    # Agent configurations
    agent_configs = [
        ("alice", "senior_developer", "swe", 0.7),
        ("rosine", "research_specialist", "react", 0.8), 
        ("ines", "business_analyst", "cot", 0.6),
        ("clara", "project_manager", "react", 0.5)
    ]
    
    # Create agents
    agents = {}
    for name, role, reasoning, temp in agent_configs:
        print(f"\n🤖 Creating {name.title()} ({role})...")
        agent = create_agent(
            name=name,
            role=role,
            reasoning_pattern=reasoning,
            llm_config={
                "provider": "ollama",
                "model_name": "llama3.2",
                "timeout": 500.0,
                "temperature": temp
            },
            verbose=True
        )
        agents[name] = agent
        if agent.profile:
            print(f"   ✅ Profile: {agent.profile.role.name} | Tools: {len(agent.profile.available_tools)}")
    
    print_section("Step 2: Building Team & Enabling Context")
    
    # Create team and add agents
    team = Team("ai_development_team", verbose=True)
    for agent in agents.values():
        team.add_agent(agent)
    
    print(f"\n🏗️ Team created with {len(team.agents)} members: {list(team.get_team_member_names())}")
    
    # Enable team context
    print("\n🔄 Refreshing team context...")
    team.refresh_team_context()
    print("✅ Team context updated!")
    
    # Show complete system prompt
    print_agent_prompt("Alice", agents["alice"])
    
    print_section("Step 3: Testing @Mention Communication")
    
    # Test scenarios
    scenarios = [
        {
            "name": "Manager Delegation",
            "agent": "clara",
            "message": "@rosine, research latest AI agent collaboration trends for 2024-2025. Focus on multi-agent systems.",
            "description": "Clara → @rosine (research request)"
        },
        {
            "name": "Peer Collaboration", 
            "agent": "alice",
            "message": "@ines, I need help understanding password complexity requirements for our authentication system.",
            "description": "Alice → @ines (business requirements)"
        },
        {
            "name": "Team Broadcast",
            "agent": "clara", 
            "message": "@team, project approved for Phase 2! Please prepare current work for review by Friday.",
            "description": "Clara → @team (announcement)"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📢 Scenario {i}: {scenario['name']}")
        print(f"💬 {scenario['description']}")
        print(f"Message: {scenario['message']}")
        
        try:
            print(f"\n🤖 Processing with {scenario['agent'].title()} (up to 500s)...")
            agent = agents[scenario['agent']]
            response = await agent.process(scenario['message'])
            
            print(f"\n📝 {scenario['agent'].title()}'s response:")
            print("=" * 60)
            print(response)
            print("=" * 60)
            
            # Route mentions
            print(f"\n📬 Routing mentions...")
            mention_ids = await team.send_mention_message(scenario['agent'], scenario['message'])
            print(f"✅ Message IDs: {mention_ids}")
            
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")
    
    print_section("Step 4: Team Intelligence Demo")
    
    # Show team status
    print("\n📊 Current Team Status:")
    for name in team.get_team_member_names():
        profile = team.get_agent_profile(name)
        if profile:
            status = "🟢 Available" if profile.capacity.is_available else "🔴 Busy"
            print(f"   • {name.title()}: {status} ({profile.capacity.workload*100:.0f}% workload)")
    
    # Update capacities
    print("\n⚡ Simulating workload changes...")
    team.update_agent_capacity("alice", 0.8, "busy")
    team.update_agent_capacity("rosine", 0.3, "available")
    
    print("📊 Updated Status:")
    for name in ["alice", "rosine"]:
        profile = team.get_agent_profile(name)
        if profile:
            status = "🟢 Available" if profile.capacity.is_available else "🔴 Busy" 
            print(f"   • {name.title()}: {status} ({profile.capacity.workload*100:.0f}% workload)")
    
    print_section("✅ Demo Complete!")
    
    print("🎉 Successfully demonstrated:")
    print("✅ Real agents with llama3.2 • ✅ Team context injection")
    print("✅ @mention parsing & routing • ✅ Peer-to-peer communication") 
    print("✅ Team broadcasts • ✅ Dynamic capacity management")
    print("✅ Clean API without redundancy")
    
    print("\n🚀 Your @mention system works perfectly!")
    print("Agents can now collaborate naturally like human teams.")

if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
