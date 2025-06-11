#!/usr/bin/env python3
"""
Interactive test of Enterprise AI: LLM + Tools + MCP

This script provides an interactive CLI to test the integration between
LLM models, tool execution, and the MCP coordinator.
"""

import asyncio
import json
from typing import List, Optional
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message, ToolCall

async def interactive_test(
    model_name: str = "llama3.2",
    provider: str = "ollama",
    llm_timeout: float = 1200.0,
    mcp_timeout: float = 500.0,
    verbose: bool = True
):
    """
    Interactive test for Enterprise AI with LLM + Tools + MCP integration.
    
    Args:
        model_name: Name of the LLM model to use
        provider: LLM provider ("ollama" or "openai")
        llm_timeout: Timeout for LLM requests
        mcp_timeout: Timeout for tool execution
        verbose: Enable verbose logging
    """
    print(f"🚀 Enterprise AI Interactive Test")
    print(f"Model: {provider}/{model_name}")
    
    # Initialize components
    try:
        llm = create_provider(provider, model_name, timeout=llm_timeout, verbose=verbose)
        mcp = ToolMCP(timeout=mcp_timeout, auto_load_tools=True)
        
        # Get tool definitions
        tools = mcp.get_tool_definitions()
        tool_count = len(tools)
        print(f"✅ Loaded {tool_count} tools")
        
        # Show first few tools
        print("Key tools available (type 'tools' to see all):")
        key_tools = ["web_search", "python_execute", "code_search", "filesystem", "bash"]
        displayed_tools = 0
        
        for i, tool in enumerate(tools):
            name = tool['function']['name']
            if name in key_tools:
                desc = tool['function']['description']
                print(f"  • {name}: {desc}")
                displayed_tools += 1
        
        if displayed_tools < tool_count:
            print(f"  ... and {tool_count - displayed_tools} more tools")
    
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Conversation history
    messages = []
    
    print("\n💬 Chat with Enterprise AI (type 'quit' to exit, 'tools' to see all tools)")
    print("=" * 50)
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'bye']:
            break
        
        if user_input.lower() == 'tools':
            # Show available tools
            print(f"\nAll Available Tools ({len(tools)}):")
            for i, tool in enumerate(tools):
                name = tool['function']['name']
                desc = tool['function']['description']
                desc_preview = desc[:70] + "..." if len(desc) > 70 else desc
                print(f"  {i+1}. {name}: {desc_preview}")
            continue
        
        if user_input.lower() == 'help':
            print("\n📚 Help:")
            print("  • Type your message to chat with the AI")
            print("  • Type 'tools' to see all available tools")
            print("  • Type 'help' to see this help message")
            print("  • Type 'quit', 'exit', or 'bye' to end the session")
            continue
        
        if not user_input:
            continue
        
        # Add user message
        messages.append(Message(role="user", content=user_input))
        
        try:
            # Get LLM response with potential tool calls
            print(f"\n🧠 Thinking...")
            response, tool_calls = await llm.acomplete_with_tool_calls(
                messages=messages, 
                tools=tools
            )
            
            # Add AI response to history
            messages.append(response)
            
            # If no tool calls, just show the response
            if not tool_calls:
                print(f"\nAI: {response.content}")
                continue
            
            # Show that tools will be executed
            print(f"\n🔧 Executing {len(tool_calls)} tool(s)...")
            
            # Execute tools
            results = await mcp.execute_tool_calls(tool_calls)
            
            # Add tool results to conversation
            for tool_call, result in zip(tool_calls, results):
                tool_msg = Message(
                    role="tool",
                    content=str(result.result if result.success else result.error),
                    metadata={"tool_call_id": tool_call.id}
                )
                messages.append(tool_msg)
                
                # Show tool execution result
                status = "✅" if result.success else "❌"
                print(f"\n{status} Tool: {tool_call.function.name}")
                if result.success:
                    result_str = str(result.result)
                    if len(result_str) > 200:  # Truncate long results
                        print(f"Result: {result_str[:200]}...")
                        print("(Result truncated for display. Full result is in conversation context.)")
                    else:
                        print(f"Result: {result_str}")
                else:
                    print(f"Error: {result.error}")
            
            # Get final response with tool results
            print("\n🧠 Generating final response...")
            final_response = await llm.acomplete(messages)
            messages.append(final_response)
            
            print(f"\nAI: {final_response.content}")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Show execution stats at the end
    print("\n📊 Execution Statistics:")
    stats = mcp.get_stats()
    print(f"  Total tool executions: {stats['total_executions']}")
    print(f"  Successful executions: {stats['successful_executions']}")
    print(f"  Failed executions: {stats['failed_executions']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    
    print("\n👋 Enterprise AI session ended")

if __name__ == "__main__":
    asyncio.run(interactive_test())
