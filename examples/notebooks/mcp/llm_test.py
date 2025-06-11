#!/usr/bin/env python3
"""
Interactive test of Enterprise AI: LLM + Tools + MCP - WITH DEBUGGING
"""

import asyncio
import json
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message

async def interactive_test():
    """Interactive test with debugging to see why tools aren't being used."""
    
    print("🚀 Starting Enterprise AI Interactive Test (Debug Mode)")
    
    # Initialize your components
    llm = create_provider("ollama", "llama3.2", timeout=500.0, verbose=True)
    mcp = ToolMCP(timeout=30.0, auto_load_tools=True)
    
    # Get available tools and show them
    tools = mcp.get_tool_definitions()
    print(f"✅ Loaded {len(tools)} tools:")
    for tool in tools[:5]:  # Show first 5 tools
        print(f"  - {tool['function']['name']}: {tool['function']['description']}")
    
    # Show available tool names from MCP
    available_tools = mcp.get_available_tools()
    print(f"\n🔧 Available tools in MCP: {available_tools}")
    
    # Conversation history
    messages = []
    
    print("\n💬 Chat with your Enterprise AI (type 'quit' to exit)")
    print("=" * 50)
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            break
        
        if not user_input:
            continue
        
        # Add user message
        messages.append(Message(role="user", content=user_input))
        
        try:
            print(f"\n🧠 Sending {len(tools)} tools to LLM...")
            
            # Get LLM response with tool calls
            response, tool_calls = await llm.acomplete_with_tool_calls(
                messages=messages, 
                tools=tools
            )
            
            print(f"📝 LLM Response: {response.content}")
            print(f"🔧 Tool calls detected: {len(tool_calls)}")
            
            # Show tool call details
            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    print(f"  Tool {i+1}: {tool_call.function.name}")
                    print(f"    Args: {tool_call.function.arguments}")
            
            # Add AI response
            messages.append(response)
            
            # Execute tools if needed
            if tool_calls:
                print(f"\n🔧 Executing {len(tool_calls)} tools...")
                results = await mcp.execute_tool_calls(tool_calls)
                
                # Show tool results
                for tool_call, result in zip(tool_calls, results):
                    print(f"  ✅ {tool_call.function.name}: Success={result.success}")
                    if result.success:
                        print(f"    Result: {str(result.result)}")
                    else:
                        print(f"    Error: {result.error}")
                    
                    # Add tool result to conversation
                    tool_msg = Message(
                        role="tool",
                        content=f"Tool {tool_call.function.name} result: {result.result if result.success else result.error}",
                        metadata={"tool_call_id": tool_call.id}
                    )
                    messages.append(tool_msg)
                
                # Get final response with tool results
                print("\n🧠 Getting final response with tool results...")
                final_response = await llm.acomplete(messages)
                messages.append(final_response)
                print(f"\nAI: {final_response.content}")
            else:
                print(f"\nAI: {response.content}")
                print("⚠️  No tool calls were made by the LLM")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n👋 Goodbye!")

if __name__ == "__main__":
    asyncio.run(interactive_test())