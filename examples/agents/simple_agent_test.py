#!/usr/bin/env python3
"""
Simple Agent Creation and Usage Test
===================================

Test agent creation and usage through Enterprise-AI's agent system.
Simple validation (under 150 lines) to verify:
✅ Agent creation with Ollama works
✅ Role definition (simple and custom roles)  
✅ Standard vs streaming generation modes
"""

import asyncio
import sys
import os

# Add parent directory to path to import enterprise_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent_test")


async def test_simple_role_creation():
    """Test agent creation with simple string role."""
    print("🤖 Testing Simple Role Creation...")
    
    agent = create_agent(
        name="TestBot",
        role="Assistant",  # Simple string role
        reasoning_pattern="react",
        verbose=True
    )
    
    print(f"✅ Agent created: {agent.name} | Tools: {len(agent.get_available_tools())}")
    return agent


async def test_custom_role_creation():
    """Test agent creation with custom role."""
    print("🎭 Testing Custom Role Creation...")
    
    custom_role = AgentRole.custom(
        name="Data Analyst",
        system_prompt="You are a skilled data analyst specializing in interpreting datasets.",
        capabilities=["data_analysis", "statistical_reasoning"]
    )
    
    agent = create_agent(name="DataBot", role=custom_role, reasoning_pattern="cot", verbose=True)
    print(f"✅ Custom agent: {agent.name} | Role: {agent.role.name}")
    return agent


async def test_generation_modes(agent):
    """Test both standard and streaming generation."""
    if not agent:
        return False, False
    
    # Test standard generation
    print("💬 Testing Standard Generation...")
    try:
        response = await agent.process("Hello! Introduce yourself briefly.")
        print(f"✅ Standard: {len(response)} chars | Preview: {response[:1000]}...")
        standard_ok = True
    except Exception as e:
        print(f"❌ Standard failed: {e}")
        standard_ok = False
    
    # Test streaming generation
    print("🌊 Testing Streaming Generation...")
    try:
        print("   Stream: ", end="", flush=True)
        full_response = ""
        chunk_count = 0
        
        async for chunk in agent.process_stream("List 3 key benefits of AI in one sentence each."):
            print(chunk, end="", flush=True)
            full_response += chunk
            chunk_count += 1
        
        print(f"\n✅ Streaming: {chunk_count} chunks, {len(full_response)} chars")
        streaming_ok = True
    except Exception as e:
        print(f"\n❌ Streaming failed: {e}")
        streaming_ok = False
    
    return standard_ok, streaming_ok


async def main():
    """Run all agent tests."""
    print("🚀 ENTERPRISE-AI AGENT SYSTEM TESTS")
    print("=" * 45)
    
    results = []
    
    # Test 1: Simple role creation
    try:
        simple_agent = await test_simple_role_creation()
        results.append(("Simple Role", True))
    except Exception as e:
        print(f"❌ Simple role failed: {e}")
        results.append(("Simple Role", False))
        simple_agent = None
    
    # Test 2: Custom role creation
    try:
        custom_agent = await test_custom_role_creation()
        results.append(("Custom Role", True))
    except Exception as e:
        print(f"❌ Custom role failed: {e}")
        results.append(("Custom Role", False))
        custom_agent = None
    
    # Test 3 & 4: Generation modes (use custom agent if available)
    test_agent = custom_agent or simple_agent
    if test_agent:
        standard_ok, streaming_ok = await test_generation_modes(test_agent)
        results.extend([("Standard Generation", standard_ok), ("Streaming Generation", streaming_ok)])
        
        print(f"\n📊 Agent Summary: {test_agent.get_summary()}")
    else:
        results.extend([("Standard Generation", False), ("Streaming Generation", False)])
    
    # Results summary
    print(f"\n🎯 TEST RESULTS")
    print("=" * 15)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\n🏆 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All agent tests successful! Enterprise-AI agent system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check Ollama server and dependencies.")


if __name__ == "__main__":
    asyncio.run(main())