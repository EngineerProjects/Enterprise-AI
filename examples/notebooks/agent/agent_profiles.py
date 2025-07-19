#!/usr/bin/env python3
"""
Enterprise AI: Agent Profile Demo with Enhanced ToolMCP

Demonstrates the new ToolMCP tools parameter for role-specific tool assignment.
"""

import asyncio
import sys

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP


async def enhanced_agent_demo():
    """Demo with enhanced ToolMCP supporting tools parameter."""
    print("🎯 Enterprise AI Agent Profile Demo - Enhanced ToolMCP")
    print("=" * 60)
    
    # Create shared LLM
    print("\n🧠 Creating LLM...")
    llm = create_provider(
        provider_name="ollama", 
        model_name="llama3.2",
        timeout=60.0,
        verbose=False
    )
    print("✅ LLM created")
    
    # Agent configurations with specific tools using the new parameter
    configs = [
        {
            "name": "alice",
            "role": AgentRole(
                name="developer",
                description="Backend Python developer specializing in API development and file management"
            ),
            "tools": ['python_execute', 'bash', 'file_editor', 'filesystem', 'code_search', 'configuration'],
            "pattern": "react"
        },
        {
            "name": "bob", 
            "role": AgentRole(
                name="researcher",
                description="Research analyst specializing in web research and deep analysis"
            ),
            "tools": ['web_search', 'deep_research', 'browser_use', 'filesystem', 'mime_type_detector'],
            "pattern": "cot"
        },
        {
            "name": "carol",
            "role": AgentRole(
                name="engineer", 
                description="Software engineer focused on system management and planning"
            ),
            "tools": ['planning', 'process_manager', 'bash', 'filesystem', 'terminate', 'configuration'],
            "pattern": "swe"
        },
        {
            "name": "dave",
            "role": AgentRole(
                name="assistant",
                description="AI assistant for communication and general tasks"
            ),
            "tools": ['create_chat_completion', 'web_search', 'filesystem', 'mime_type_detector'],
            "pattern": "cot"
        }
    ]
    
    # Create agents using the new ToolMCP tools parameter
    print(f"\n🤖 Creating agents with enhanced ToolMCP:")
    agents = []
    
    for config in configs:
        print(f"   🔧 Creating MCP for {config['name']} with tools: {config['tools']}")
        
        # Use the new tools parameter - much cleaner!
        role_mcp = ToolMCP(
            timeout=30.0, 
            auto_load_tools=False,  # Don't load all tools
            tools=config["tools"]   # Load only these specific tools
        )
        
        # Create agent
        agent = create_agent(
            name=config["name"],
            role=config["role"],
            llm=llm,
            mcp=role_mcp,
            reasoning_pattern=config["pattern"],
            verbose=False
        )
        agents.append(agent)
        print(f"   ✅ {config['name']}: {len(config['tools'])} tools loaded ({config['pattern']} pattern)")
    
    # Show detailed profiles
    print(f"\n📊 Agent Profiles with Role-Specific Tools:")
    print("=" * 60)
    
    for agent in agents:
        if agent.profile:
            profile = agent.profile.to_dict()
            
            print(f"\n👤 {agent.name.upper()}")
            print(f"   Role: {profile['role']['name']}")
            print(f"   Description: {profile['role']['description']}")
            print(f"   Available Tools ({len(profile['available_tools'])}):")
            for tool in profile['available_tools']:
                print(f"     • {tool}")
            print(f"   Capacity: {profile['capacity']['workload']:.1%} workload, {profile['capacity']['status']}")
            print(f"   Reasoning Pattern: {agent.reasoning_pattern.__class__.__name__}")
        else:
            print(f"\n👤 {agent.name.upper()}: No profile")
    
    # Test enhanced capabilities
    print(f"\n🔍 Enhanced Capability Testing:")
    capability_tests = [
        ("Who can execute Python code?", "python_execute"),
        ("Who can do web research?", "web_search"), 
        ("Who can do deep research?", "deep_research"),
        ("Who can manage processes?", "process_manager"),
        ("Who can edit files?", "file_editor"),
        ("Who can do planning?", "planning"),
        ("Who can use browser?", "browser_use"),
        ("Who can handle chat completion?", "create_chat_completion")
    ]
    
    for question, tool in capability_tests:
        matches = [agent.name for agent in agents 
                  if agent.profile and agent.profile.has_tool(tool)]
        print(f"   {question} → {matches if matches else 'None'}")
    
    # Show tool distribution summary
    print(f"\n📈 Tool Distribution Summary:")
    all_tools = set()
    for agent in agents:
        if agent.profile:
            all_tools.update(agent.profile.available_tools)
    
    print(f"   Total unique tools across team: {len(all_tools)}")
    print(f"   Tools: {', '.join(sorted(all_tools))}")
    
    # Show role specialization
    print(f"\n🎯 Role Specialization:")
    for agent in agents:
        if agent.profile:
            role_tools = len(agent.profile.available_tools)
            print(f"   {agent.name}: {agent.profile.role.name} with {role_tools} specialized tools")
    
    print(f"\n🎉 Enhanced ToolMCP Demo Complete!")
    print(f"\n✅ Key Benefits Demonstrated:")
    print(f"   • Clean tool assignment: ToolMCP(tools=['tool1', 'tool2'])")
    print(f"   • Role-specific capabilities: Each agent has relevant tools only")
    print(f"   • Automatic tool filtering: No manual registration loops") 
    print(f"   • Better team organization: Clear tool responsibilities")


if __name__ == "__main__":
    try:
        asyncio.run(enhanced_agent_demo())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
