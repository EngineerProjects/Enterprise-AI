#!/usr/bin/env python3
"""
Full test of all Enterprise AI tool descriptions and selection
"""

import asyncio
import json
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.executor import ToolMCP
from enterprise_ai.schema import Message

async def test_improved_tool_selection():
    """Test if the MCP properly handles tool descriptions and selection."""
    
    print("🔍 ENTERPRISE AI TOOL SELECTION TEST 🔍")
    print("======================================")
    
    # Initialize MCP with auto-loaded tools
    print("\n1️⃣ Initializing MCP and loading tools...")
    mcp = ToolMCP(timeout=30.0, auto_load_tools=True)
    
    # Get tool definitions
    tools = mcp.get_tool_definitions()
    print(f"✅ Successfully loaded {len(tools)} tools")
    
    # Display all tool descriptions
    print("\n2️⃣ Checking all tool descriptions:")
    all_tools_improved = True
    
    for tool in tools:
        name = tool['function']['name']
        desc = tool['function']['description']
        
        # Check if it's a proper description (not just generic "Tool: name")
        has_proper_desc = f"Tool: {name}" != desc
        
        status = "✅" if has_proper_desc else "❌"
        print(f"{status} {name}: {desc}")
        
        if not has_proper_desc:
            all_tools_improved = False
    
    if all_tools_improved:
        print("\n✅ SUCCESS: All tools have proper descriptions!")
    else:
        print("\n⚠️ WARNING: Some tools still have generic descriptions.")
    
    # Test tool selection with specific test cases
    print("\n3️⃣ Testing tool selection with test cases...")
    
    # Create LLM provider
    llm = create_provider("ollama", "llama3.2", timeout=60.0, verbose=False)
    
    # Test cases for common confusion points
    test_cases = [
        {
            "name": "Web Search",
            "query": "What are the latest news about AI in 2025?",
            "expected_tool": "web_search"
        },
        {
            "name": "Math Calculation",
            "query": "Calculate 3.14159 * 2.71828 using Python",
            "expected_tool": "python_execute"
        },
        {
            "name": "Code Search",
            "query": "Find all instances of 'import tensorflow' in my project files",
            "expected_tool": "code_search"
        },
        {
            "name": "Calculator Ambiguity",
            "query": "What is 25 * 135 + 47?",
            "expected_tool": "python_execute"
        },
        {
            "name": "News Query",
            "query": "Find recent news about Google's AI announcements",
            "expected_tool": "web_search"
        }
    ]
    
    # Run each test case
    success_count = 0
    for test in test_cases:
        print(f"\n📝 Test: {test['name']}")
        print(f"Query: \"{test['query']}\"")
        
        messages = [Message(role="user", content=test['query'])]
        
        try:
            # Get response with potential tool calls
            response, tool_calls = await llm.acomplete_with_tool_calls(
                messages=messages,
                tools=tools
            )
            
            # Report tool calls
            if tool_calls:
                used_tools = [tc.function.name for tc in tool_calls]
                print(f"Tools selected: {used_tools}")
                
                # Check if expected tool was used
                if test['expected_tool'] in used_tools:
                    print(f"✅ SUCCESS: Used expected tool '{test['expected_tool']}'")
                    success_count += 1
                else:
                    print(f"❌ FAILURE: Expected tool '{test['expected_tool']}' but got {used_tools}")
            else:
                print(f"❌ FAILURE: No tool calls were generated, expected '{test['expected_tool']}'")
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    # Final summary
    print("\n4️⃣ Test Results Summary:")
    print(f"Passed {success_count} out of {len(test_cases)} tests")
    
    if success_count == len(test_cases):
        print("\n🎉 ALL TESTS PASSED! Tool selection is working correctly.")
    else:
        print("\n⚠️ SOME TESTS FAILED. Tool selection needs further improvement.")
        
    print("\nImprovement recommendations:")
    print("1. Make tool descriptions even clearer about their purpose")
    print("2. Use explicit examples in short descriptions for common use cases")
    print("3. For commonly confused tools, include explicit notes about what they can't do")
    print("4. Consider adding format hints to the description for better tool selection")

if __name__ == "__main__":
    asyncio.run(test_improved_tool_selection())
