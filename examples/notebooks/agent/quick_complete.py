"""
Quick fixed test - forces tool usage with proper async handling.
"""

import asyncio
from enterprise_ai.agent import create_agent
from enterprise_ai.schema import Message

async def auto_approve_all(tool_call):
    """Auto-approve all tools for quick testing."""
    print(f"\n🔧 TOOL APPROVAL REQUEST")
    print(f"   Tool: {tool_call.function.name}")
    print(f"   Arguments: {tool_call.get_arguments()}")
    
    # Simulate user interaction
    response = input("   Approve? (y/n): ").strip().lower()
    approved = response in ['y', 'yes']
    
    if approved:
        print(f"   ✅ APPROVED")
    else:
        print(f"   ❌ DENIED")
    
    return approved

async def main():
    print("🚀 Quick Fixed Test - No Truncation")
    print("=" * 60)
    
    # Create agent with manual approval
    agent = create_agent(
        llm_provider="ollama",
        model_name="llama3.2",
        timeout=500.0,
        require_tool_approval=True,
        tool_approval_callback=auto_approve_all,
        verbose=True
    )
    
    print(f"✅ Agent: {agent.agent_name}")
    print(f"📊 Available categories: {list(agent.get_tool_categories().keys())}")
    
    # Show available tools properly
    print("\n📋 Available Tools:")
    try:
        tools = await agent.get_available_tools()
        for tool in tools[:5]:  # Show first 5 tools
            # ✅ CORRECT - access via function key
            function = tool.get('function', {})
            name = function.get('name', 'Unknown')
            description = function.get('description', 'No description')
            print(f"  • {name}: {description[:100]}...")
    except Exception as e:
        print(f"❌ Failed to get tools: {e}")
    
    # Force tool usage with very specific prompt
    messages = [
        Message.user_message(
            "I need to search the web for the latest news about AI advancements in 2025. Please use the web_search tool to get the latest articles with the query 'AI advancements 2025 latest news'."
        )
    ]
    
    print("\n💬 Starting conversation...")
    print(f"User: {messages[0].content}")
    
    conversation = await agent.chat(
        messages=messages,
        tools="all",
        max_iterations=3
    )
    
    print(f"\n📊 RESULTS:")
    print(f"Total messages: {len(conversation)}")
    print(f"Tool executions: {agent.get_agent_info()['tool_execution_count']}")
    
    print(f"\n💬 COMPLETE CONVERSATION:")
    print("=" * 60)
    
    for i, msg in enumerate(conversation):
        print(f"\n{i+1}. [{msg.role.upper()}]")
        if hasattr(msg, 'metadata') and msg.metadata and msg.metadata.get('tool_calls'):
            print(f"   🔧 Called {len(msg.metadata['tool_calls'])} tools")
        print(f"   Content: {msg.content}")
        if hasattr(msg, 'name') and msg.name:
            print(f"   Tool: {msg.name}")

if __name__ == "__main__":
    asyncio.run(main())