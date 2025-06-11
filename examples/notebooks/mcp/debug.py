#!/usr/bin/env python3
"""
Test the registry fix for Pydantic parameter extraction
"""

import asyncio
import json
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message

async def test_fix():
    """Test that the fix works."""
    
    print("🧪 Testing Registry Fix")
    
    # Test LLM + Tools with proper parameter schema
    llm = create_provider("ollama", "llama3.2", timeout=500.0, verbose=True)
    mcp = ToolMCP(timeout=30.0, auto_load_tools=True)
    
    # Get tool definitions (should now have proper parameters)
    tools = mcp.get_tool_definitions()
    python_tool = None
    for tool in tools:
        if tool['function']['name'] == 'python_execute':
            python_tool = tool
            break
    
    if python_tool:
        print("✅ Python tool definition after fix:")
        print(json.dumps(python_tool, indent=2))
        
        # Check if it has the code parameter
        params = python_tool['function']['parameters']
        if 'properties' in params and 'code' in params['properties']:
            print("✅ 'code' parameter found in schema!")
        else:
            print("❌ 'code' parameter still missing")
            return
    else:
        print("❌ python_execute tool not found")
        return
    
    # Test actual LLM interaction
    print("\n🧠 Testing LLM interaction:")
    messages = [Message(role="user", content="Calculate sin(57 degrees) using Python")]
    
    response, tool_calls = await llm.acomplete_with_tool_calls(
        messages=messages,
        tools=tools
    )
    
    print(f"Response: {response.content}")
    print(f"Tool calls: {len(tool_calls)}")
    
    if tool_calls:
        for tc in tool_calls:
            print(f"Tool: {tc.function.name}")
            print(f"Args: {tc.function.arguments}")
            
            # Check if the arguments are correct format
            if tc.function.name == 'python_execute':
                args = tc.function.arguments
                if isinstance(args, dict) and 'code' in args:
                    print("✅ Correct parameter format!")
                    
                    # Test execution
                    print("\n🔧 Testing execution:")
                    results = await mcp.execute_tool_calls([tc])
                    result = results[0]
                    print(f"Success: {result.success}")
                    if result.success:
                        print(f"Result: {result.result}")
                    else:
                        print(f"Error: {result.error}")
                else:
                    print("❌ Still wrong parameter format")
    else:
        print("❌ No tool calls generated")

if __name__ == "__main__":
    asyncio.run(test_fix())