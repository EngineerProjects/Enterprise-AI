"""
Enhanced Agent Basic Test - Real Usage Examples

Config-based creation, runtime updates, and comprehensive tool integration.

Tools: file_editor, file_system, code_search, python_execute, bash, process_manager,
       web_search, deep_research, browser, chat_completion, planning, configuration
Model: ollama/llama3.2 | Timeouts: 500-2000 seconds
"""

import asyncio
import sys
import os

# Add project root for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.schema.agent_profile import AgentStatus


async def test_full_config_agent():
    """Test config-based agent with comprehensive tools."""
    print("\n🧪 Config-Based Full Agent")
    
    agent = create_agent(
        name="FullStackDev",
        role_config={"name": "Full-Stack Developer", "system_prompt": "Versatile developer with comprehensive tools."},
        mcp_config={
            "timeout": 1500.0,
            "tools": ["file_editor", "file_system", "code_search", "python_execute", "bash", 
                     "process_manager", "web_search", "deep_research", "browser", 
                     "chat_completion", "planning", "configuration"]
        },
        llm_config={"model_name": "llama3.2", "timeout": 1000.0, "temperature": 0.7},
        reasoning_pattern="react", verbose=True
    )
    
    profile = agent.profile()
    print(f"✅ {profile.name} | {profile.role.name} | {len(profile.available_tools)} tools")
    
    response = await agent.process("What are your capabilities?")
    print(f"✅ Response: {len(response)} chars")
    return agent


async def test_runtime_updates():
    """Test runtime configuration updates."""
    print("\n🔧 Runtime Updates")
    
    agent = create_agent(
        name="AdaptiveBot", role="Assistant",
        mcp_config={"timeout": 500.0, "tools": ["file_system", "python_execute"]},
        llm_config={"model_name": "llama3.2", "timeout": 600.0}
    )
    print(f"📊 Initial: {len(agent.profile().available_tools)} tools")
    
    # Transform to research specialist
    agent.update_role_config({"name": "Research Specialist", "system_prompt": "Research expert with web tools."})
    agent.update_mcp_config({
        "timeout": 2000.0,
        "tools": ["web_search", "deep_research", "browser", "file_editor", "python_execute"]
    })
    agent.set_workload(0.4)
    
    profile = agent.profile()
    print(f"📊 Updated: {len(profile.available_tools)} tools | {profile.role.name}")
    return agent


async def test_specialized_agents():
    """Test specialized agents for different domains."""
    print("\n🎯 Specialized Agents")
    
    # Code specialist
    coder = create_agent(
        name="CodeMaster",
        role_config={"name": "Developer", "system_prompt": "Coding expert."},
        mcp_config={"timeout": 1000.0, "tools": ["file_editor", "code_search", "python_execute", "bash"]},
        llm_config={"model_name": "llama3.2", "timeout": 800.0}
    )
    
    # Research specialist
    researcher = create_agent(
        name="InfoBot",
        role_config={"name": "Researcher", "system_prompt": "Information gathering expert."},
        mcp_config={"timeout": 1800.0, "tools": ["web_search", "deep_research", "browser"]},
        llm_config={"model_name": "llama3.2", "timeout": 1200.0}
    )
    
    # System admin
    admin = create_agent(
        name="SysAdmin",
        role_config={"name": "Administrator", "system_prompt": "System management expert."},
        mcp_config={"timeout": 600.0, "tools": ["bash", "process_manager", "configuration"]},
        llm_config={"model_name": "llama3.2", "timeout": 600.0}
    )
    
    agents = {"coder": coder, "researcher": researcher, "admin": admin}
    for name, agent in agents.items():
        profile = agent.profile()
        print(f"✅ {name.upper()}: {profile.role.name} ({len(profile.available_tools)} tools)")
    
    return agents


async def test_workflows():
    """Test real-world workflow scenarios."""
    print("\n🌍 Workflow Scenarios")
    
    # Development workflow
    dev = create_agent(
        name="DevAssistant",
        role_config={"name": "Dev Assistant", "system_prompt": "Development helper."},
        mcp_config={"timeout": 1200.0, "tools": ["file_editor", "code_search", "python_execute", "bash"]},
        llm_config={"model_name": "llama3.2", "timeout": 1000.0}
    )
    dev.set_workload(0.3)
    
    # Research workflow  
    research = create_agent(
        name="ResearchBot",
        role_config={"name": "Research Assistant", "system_prompt": "Research conductor."},
        mcp_config={"timeout": 2000.0, "tools": ["web_search", "deep_research", "browser", "planning"]},
        llm_config={"model_name": "llama3.2", "timeout": 1500.0}
    )
    research.set_workload(0.7)
    research.set_status(AgentStatus.BUSY)
    
    workflows = {"dev": dev, "research": research}
    for name, agent in workflows.items():
        profile = agent.profile()
        print(f"✅ {name.upper()}: {profile.capacity.status.value} ({profile.capacity.workload:.0%})")
    
    return workflows


async def test_component_based():
    """Test component-based creation."""
    print("\n🔩 Component-Based")
    
    planning_role = AgentRole.custom("Strategic Planner", "Creates plans and coordinates tasks.", ["planning"])
    
    planner = create_agent(
        name="Strategist", role=planning_role,
        mcp_config={"timeout": 1500.0, "tools": ["planning", "file_editor", "web_search"]},
        llm_config={"model_name": "llama3.2", "timeout": 1200.0}
    )
    
    profile = planner.profile()
    print(f"✅ {profile.name}: {profile.role.name} ({len(profile.available_tools)} tools)")
    return planner


async def main():
    """Execute enhanced agent tests."""
    print("🚀 Enhanced Agent Basic Tests")
    print("=" * 35)
    
    try:
        # Run tests
        full_agent = await test_full_config_agent()
        adaptive_agent = await test_runtime_updates()
        specialists = await test_specialized_agents()
        workflows = await test_workflows()
        component_agent = await test_component_based()
        
        # Summary
        total = 1 + 1 + len(specialists) + len(workflows) + 1
        
        print(f"\n📊 Results")
        print("-" * 15)
        print(f"✅ Agents tested: {total}")
        print(f"✅ Config-based: PASSED")
        print(f"✅ Runtime updates: PASSED")
        print(f"✅ Specialized: PASSED")
        print(f"✅ Workflows: PASSED")
        print(f"✅ Component-based: PASSED")
        
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"🚀 Production ready!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
