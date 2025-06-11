#!/usr/bin/env python3
"""
Enterprise AI: Agent Tool Usage Demo

This script demonstrates the Agent module with ReAct reasoning
specifically focused on tool usage.
"""

import asyncio
import sys
import time
from typing import AsyncIterator

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP


async def simulate_streaming_output(stream: AsyncIterator[str]) -> None:
    """Simulate streaming output with clear display."""
    print("\n💬 Response (streaming):")
    print("-" * 80)
    
    full_response = ""
    
    async for chunk in stream:
        full_response += chunk
        print(f"\r{full_response}", end="", flush=True)
        await asyncio.sleep(0.01)
    
    print("\n" + "-" * 80)


async def interactive_agent_demo() -> None:
    """Run an interactive agent demo focusing on tool usage."""
    print("🛠️ Enterprise AI Agent Tool Usage Demo")
    print("=" * 80)
    
    # Create a research assistant role - ReAct pattern will handle tool prompts
    role = AgentRole(
        name="Research Assistant",
        system_prompt="You are a Research Assistant specialized in finding and analyzing information. "
                     "Use tools effectively when needed to provide accurate, up-to-date information.",
    )
    
    # Create LLM - fixed the create_provider call with provider_name
    print("\n🧠 Creating LLM...")
    llm = create_provider(
        provider_name="ollama", 
        model_name="llama3.2",
        timeout=90.0,
        verbose=False
    )
    print("✅ LLM created")
    
    # Create MCP with tools
    print("\n🧰 Creating MCP with tools...")
    mcp = ToolMCP(
        timeout=60.0,
        auto_load_tools=True
    )
    tools = mcp.get_available_tools()
    print(f"✅ MCP created with {len(tools)} tools")
    
    # Sample tools to display
    important_tools = ["web_search", "python_execute", "code_search", "filesystem", "bash"]
    print("\nKey tools available:")
    for tool in important_tools:
        if tool in tools:
            print(f"  • {tool}")
    
    # Create agent
    print("\n🤖 Creating Research Assistant agent...")
    agent = create_agent(
        name="ResearchBot",
        role=role,
        llm=llm,
        mcp=mcp,
        reasoning_pattern="react",  # ReAct pattern already uses appropriate prompts
        verbose=False
    )
    print("✅ Agent created with ReAct reasoning pattern")
    
    # Interactive loop
    print("\n💬 Interactive Agent Demo")
    print("Type your questions (type 'exit' to quit, 'stream' to toggle streaming)")
    print("=" * 80)
    
    use_streaming = False
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ["exit", "quit", "bye"]:
            break
            
        if user_input.lower() == "stream":
            use_streaming = not use_streaming
            print(f"Streaming mode: {'ON' if use_streaming else 'OFF'}")
            continue
            
        if not user_input:
            continue
        
        # Process with timing
        start_time = time.time()
        
        try:
            if use_streaming:
                # Use streaming processing
                stream = agent.process_stream(user_input)
                await simulate_streaming_output(stream)
            else:
                # Regular processing
                print("\n🔍 Processing...")
                response = await agent.process(user_input)
                elapsed = time.time() - start_time
                
                print(f"\n💬 Response (completed in {elapsed:.2f}s):")
                print("-" * 80)
                print(response)
                print("-" * 80)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue
    
    print("\n🏁 Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(interactive_agent_demo())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)