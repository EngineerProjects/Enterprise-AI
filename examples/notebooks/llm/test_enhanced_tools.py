"""
Enhanced function calling test for the new LLM tool adapter system.

This script demonstrates how to use the new enhanced tool calling functionality
with proper tool formatting and extraction.
"""

from enterprise_ai.llm import LLM, create_provider
from enterprise_ai.schema import Message


def test_enhanced_function_calling():
    """Test the enhanced function calling with the new tool adapter system."""
    print("🔧 Testing Enhanced Function Calling")
    print("-" * 60)
    
    # Create LLM instance (this will automatically use the enhanced adapters)
    llm = LLM(provider_name="ollama", model_name="llama3.2")
    
    # Define tools in the standard format
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "A simple calculator that can add, subtract, multiply, and divide",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": ["add", "subtract", "multiply", "divide"],
                            "description": "The operation to perform"
                        },
                        "a": {
                            "type": "number",
                            "description": "The first number"
                        },
                        "b": {
                            "type": "number",
                            "description": "The second number"
                        }
                    },
                    "required": ["operation", "a", "b"]
                }
            }
        }
    ]
    
    # Create messages
    messages = [
        Message.system_message(
            "You have access to a calculator tool. Use it when needed. "
            "When you need to perform calculations, use the calculator tool."
        ),
        Message.user_message("Calculate 142 divided by 17.75")
    ]
    
    print("📤 Sending function calling request...")
    
    try:
        # Call the LLM with tools
        response = llm.complete(messages, tools=tools)
        
        print("📥 Response received:")
        print("-" * 40)
        print(response.content)
        print("-" * 40)
        
        # Use the enhanced tool call extraction
        tool_calls = llm.extract_tool_calls(response)
        
        if tool_calls:
            print("✅ Tool calls detected using enhanced adapter!")
            print("🔧 Tool calls found:")
            for i, tool_call in enumerate(tool_calls, 1):
                print(f"  Tool call {i}:")
                print(f"    Name: {tool_call.get('name', 'Unknown')}")
                print(f"    Parameters: {tool_call.get('parameters', {})}")
                print(f"    Type: {tool_call.get('type', 'Unknown')}")
                if 'id' in tool_call:
                    print(f"    ID: {tool_call['id']}")
            return True
        else:
            # Also check the old format in metadata for backward compatibility
            if (hasattr(response, "metadata") and response.metadata and 
                "tool_calls" in response.metadata):
                print("⚠️  Tool calls found in metadata (old format):")
                for i, tool_call in enumerate(response.metadata["tool_calls"], 1):
                    print(f"  Tool call {i}:")
                    # Handle both old and new formats
                    if "function" in tool_call:
                        # Old OpenAI format
                        print(f"    Name: {tool_call['function'].get('name', 'Unknown')}")
                        print(f"    Arguments: {tool_call['function'].get('arguments', '{}')}")
                    else:
                        # New standardized format
                        print(f"    Name: {tool_call.get('name', 'Unknown')}")
                        print(f"    Parameters: {tool_call.get('parameters', {})}")
                return True
            else:
                print("❌ No tool calls detected.")
                print("💡 The model may support function calling but didn't use it for this prompt.")
                print("   Try with a more explicit request or a model that supports tools better.")
                return False
                
    except Exception as e:
        print(f"❌ Function calling test failed: {e}")
        return False


def test_tool_formatting():
    """Test the new tool formatting capabilities."""
    print("\n🔧 Testing Tool Formatting")
    print("-" * 60)
    
    try:
        llm = LLM(provider_name="ollama", model_name="llama3.2")
        
        # Test tools in different formats
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Simple calculator",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string"}
                        }
                    }
                }
            }
        ]
        
        print("📝 Original tools:")
        for i, tool in enumerate(tools, 1):
            print(f"  Tool {i}: {tool.get('name') or tool.get('function', {}).get('name', 'Unknown')}")
        
        # Format tools using the new adapter system
        formatted_tools = llm.format_tools(tools)
        
        print("✅ Tools formatted successfully!")
        print(f"📊 Formatted {len(formatted_tools)} tools for Ollama")
        
        for i, tool in enumerate(formatted_tools, 1):
            if "function" in tool:
                print(f"  Formatted Tool {i}: {tool['function']['name']}")
            else:
                print(f"  Formatted Tool {i}: {tool.get('name', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool formatting test failed: {e}")
        return False


def test_provider_with_adapters():
    """Test creating provider with automatic adapter assignment."""
    print("\n🔧 Testing Provider with Adapters")
    print("-" * 60)
    
    try:
        # Create provider using the factory (automatically assigns adapter)
        provider = create_provider("ollama", model_name="llama3.2")
        
        print(f"✅ Provider created: {provider.__class__.__name__}")
        print(f"📡 Model: {provider.get_model_name()}")
        
        # Check if tool adapter is properly assigned
        if hasattr(provider, '_tool_adapter'):
            adapter = provider._tool_adapter
            print(f"🔧 Tool adapter: {adapter.__class__.__name__}")
            print(f"📝 Adapter format: {adapter.default_format}")
            return True
        else:
            print("⚠️  Tool adapter not found")
            return False
            
    except Exception as e:
        print(f"❌ Provider creation test failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Enhanced LLM Tool Calling Tests")
    print("=" * 60)
    
    results = []
    
    # Run all tests
    results.append(test_tool_formatting())
    results.append(test_provider_with_adapters())
    results.append(test_enhanced_function_calling())
    
    print("\n" + "=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All enhanced tool tests passed! ({passed}/{total})")
        print("✅ Your enhanced LLM tool system is working correctly!")
    else:
        print(f"⚠️  Some tests failed: {passed}/{total}")
        print("Check the errors above for details.")
    
    print("\n💡 Usage Examples:")
    print("   # Create LLM with enhanced tool support")
    print("   llm = LLM(provider_name='ollama', model_name='llama3.2')")
    print("   ")
    print("   # Format tools automatically")
    print("   formatted_tools = llm.format_tools(your_tools)")
    print("   ")
    print("   # Extract tool calls with enhanced parsing")
    print("   tool_calls = llm.extract_tool_calls(response)")
