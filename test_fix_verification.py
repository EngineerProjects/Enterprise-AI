#!/usr/bin/env python3
"""
Verification script for the Ollama tool call argument serialization fix.
"""

import sys
import json
from pathlib import Path

# Add project to path
sys.path.append(str(Path(__file__).parent))

from enterprise_ai.schema import Message, ToolCall
from enterprise_ai.llm.ollama.helpers import OllamaMessageFormatter

def test_fix():
    """Test that the fix works correctly."""
    print("🔧 Testing Ollama Tool Call Argument Serialization Fix")
    print("=" * 60)
    
    # Create a tool call with dict arguments (this gets converted to string internally)
    tool_call = ToolCall.create(
        name="generate_test_data",
        arguments={"count": "10", "data_type": "users", "include_metadata": False},
        id="test_call_1"
    )
    
    print(f"✅ Original tool call created")
    print(f"   Function: {tool_call.function.name}")
    print(f"   Arguments (dict): {tool_call.get_arguments()}")
    print(f"   Arguments (internal): {tool_call.function.arguments}")
    print(f"   Arguments type: {type(tool_call.function.arguments)}")
    
    # Create message with tool calls
    message = Message(
        role="assistant",
        content="I'll generate 10 sample users for you.",
        metadata={
            "tool_calls": [tool_call.to_dict()]
        }
    )
    
    print(f"\n✅ Message created with tool calls in metadata")
    
    # Format for Ollama chat (this is where the fix applies)
    formatted = OllamaMessageFormatter.format_for_chat(message)
    
    print(f"\n✅ Message formatted for Ollama chat endpoint")
    print(f"   Message role: {formatted['role']}")
    print(f"   Has tool_calls: {'tool_calls' in formatted}")
    
    if "tool_calls" in formatted:
        tool_call_data = formatted["tool_calls"][0]
        args = tool_call_data["function"]["arguments"]
        
        print(f"   Function name: {tool_call_data['function']['name']}")
        print(f"   Arguments type: {type(args)}")
        print(f"   Arguments content: {args}")
        
        if isinstance(args, dict):
            print("\n🎉 SUCCESS: Arguments are proper JSON objects!")
            print("   This will work correctly with Ollama's Go struct unmarshaling")
            return True
        else:
            print("\n❌ FAILED: Arguments are still strings!")
            print("   This would cause the JSON unmarshaling error")
            return False
    else:
        print("\n❌ FAILED: No tool calls found!")
        return False

def test_conversation_scenario():
    """Test the specific scenario that was failing."""
    print(f"\n🔄 Testing Multi-Turn Conversation Scenario")
    print("-" * 60)
    
    # Simulate conversation messages with tool calls
    messages = [
        Message.user_message("Generate 10 sample users for my analysis."),
        Message(
            role="assistant", 
            content="I'll generate the users.",
            metadata={
                "tool_calls": [
                    ToolCall.create(
                        name="generate_test_data",
                        arguments={"count": "10", "data_type": "users", "include_metadata": False},
                        id="tool_1749388213189"
                    ).to_dict()
                ]
            }
        ),
        Message.user_message("Now calculate statistics on the ages from those users.")
    ]
    
    print(f"✅ Created {len(messages)} conversation messages")
    
    # Format each message and check tool calls
    success = True
    for i, msg in enumerate(messages):
        formatted = OllamaMessageFormatter.format_for_chat(msg)
        
        if "tool_calls" in formatted:
            print(f"   Message {i+1}: Has {len(formatted['tool_calls'])} tool calls")
            
            for tc in formatted["tool_calls"]:
                args_type = type(tc["function"]["arguments"])
                if args_type != dict:
                    print(f"   ❌ Tool {tc['function']['name']}: args are {args_type}, not dict")
                    success = False
                else:
                    print(f"   ✅ Tool {tc['function']['name']}: args are proper dict")
        else:
            print(f"   Message {i+1}: No tool calls")
    
    if success:
        print("\n🎉 SUCCESS: All conversation messages format correctly!")
        print("   Multi-turn conversations will work with Ollama")
    else:
        print("\n❌ FAILED: Some messages have invalid tool call formatting")
    
    return success

if __name__ == "__main__":
    test1_success = test_fix()
    test2_success = test_conversation_scenario()
    
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    
    if test1_success and test2_success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ The Ollama tool call argument serialization fix is working correctly")
        print("✅ Multi-turn conversations with tool calls will now work")
        print("✅ No more 'json: cannot unmarshal string' errors")
        print("\n🚀 You can now run your tool completion tests successfully!")
    else:
        print("❌ SOME TESTS FAILED!")
        print("   Please check the implementation")
    
    print("=" * 60)
