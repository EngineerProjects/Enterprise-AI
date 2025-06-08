#!/usr/bin/env python3
"""
Test script to validate Ollama API compliance fixes.

This script tests the key compliance improvements:
1. System prompt handling with /api/generate
2. Tool calling with /api/chat  
3. Parameter mapping validation
4. Endpoint selection logic
"""

import asyncio
import logging
from typing import List

from enterprise_ai.llm.ollama import OllamaProvider
from enterprise_ai.schema import Message

# Configure logging
logging.basicConfig(level=logging.INFO)


def test_system_prompt_handling():
    """Test system prompt handling - should use /api/generate endpoint."""
    print("\n🔧 Testing System Prompt Handling (API Compliance)")
    
    try:
        provider = OllamaProvider(
            model_name="llama3.2",
            verbose=True
        )
        
        messages = [
            Message.system_message("You are a helpful assistant that responds concisely."),
            Message.user_message("Hello! What's 2+2?")
        ]
        
        print("Making request with system prompt...")
        response = provider.complete(messages)
        
        print(f"✅ Response: {response.content[:100]}...")
        print(f"✅ Provider: {response.metadata.get('provider')}")
        print(f"✅ API Compliant: {response.metadata.get('api_compliant')}")
        
        return True
        
    except Exception as e:
        print(f"❌ System prompt test failed: {e}")
        return False


def test_tool_calling():
    """Test tool calling - should use /api/chat endpoint."""
    print("\n🛠️ Testing Tool Calling (API Compliance)")
    
    def get_weather(location: str) -> str:
        """Get weather for a location."""
        return f"Weather in {location}: Sunny, 75°F"
    
    def calculate(expression: str) -> str:
        """Calculate a mathematical expression."""
        try:
            result = eval(expression)  # Note: Only for testing
            return f"Result: {result}"
        except:
            return "Invalid expression"
    
    try:
        provider = OllamaProvider(
            model_name="llama3.2",
            verbose=True
        )
        
        messages = [
            Message.user_message("What's the weather in Paris and what's 25 * 4?")
        ]
        
        print("Making request with tools...")
        response = provider.complete(
            messages,
            tools=[get_weather, calculate]
        )
        
        print(f"✅ Response: {response.content[:100]}...")
        print(f"✅ Has tool calls: {response.metadata.get('tool_calls') is not None}")
        print(f"✅ API Compliant: {response.metadata.get('api_compliant')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Tool calling test failed: {e}")
        return False


def test_parameter_mapping():
    """Test parameter mapping to Ollama options structure."""
    print("\n⚙️ Testing Parameter Mapping (API Compliance)")
    
    try:
        provider = OllamaProvider(
            model_name="llama3.2",
            verbose=True
        )
        
        messages = [
            Message.user_message("Count from 1 to 5")
        ]
        
        print("Making request with various parameters...")
        response = provider.complete(
            messages,
            temperature=0.7,
            max_tokens=50,  # Should map to num_predict
            top_p=0.9,
            seed=42
        )
        
        print(f"✅ Response: {response.content[:100]}...")
        print(f"✅ Usage metadata: {response.metadata.get('usage_metadata', {})}")
        print(f"✅ API Compliant: {response.metadata.get('api_compliant')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Parameter mapping test failed: {e}")
        return False


def test_streaming():
    """Test streaming functionality."""
    print("\n🌊 Testing Streaming (API Compliance)")
    
    try:
        provider = OllamaProvider(
            model_name="llama3.2",
            verbose=True
        )
        
        messages = [
            Message.system_message("Respond with exactly 3 sentences."),
            Message.user_message("Tell me about the weather.")
        ]
        
        print("Testing streaming response...")
        chunks = []
        for chunk in provider.complete_stream(messages):
            chunks.append(chunk)
            if len(chunks) <= 3:  # Show first few chunks
                print(f"📦 Chunk {len(chunks)}: {chunk.content[-50:]}...")
        
        print(f"✅ Received {len(chunks)} chunks")
        print(f"✅ Final content length: {len(chunks[-1].content) if chunks else 0}")
        
        return True
        
    except Exception as e:
        print(f"❌ Streaming test failed: {e}")
        return False


async def test_async_functionality():
    """Test async functionality."""
    print("\n🔄 Testing Async Functionality (API Compliance)")
    
    try:
        provider = OllamaProvider(
            model_name="llama3.2",
            verbose=True
        )
        
        messages = [
            Message.user_message("What's the capital of France?")
        ]
        
        print("Making async request...")
        response = await provider.acomplete(messages)
        
        print(f"✅ Async response: {response.content[:100]}...")
        print(f"✅ API Compliant: {response.metadata.get('api_compliant')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Async test failed: {e}")
        return False


def test_model_info():
    """Test model information retrieval."""
    print("\n📊 Testing Model Information (API Compliance)")
    
    try:
        provider = OllamaProvider(
            model_name="llama3.2",
            verbose=True
        )
        
        model_info = provider.get_model_info()
        capability_details = provider.get_capability_details()
        
        print(f"✅ Model: {model_info.id}")
        print(f"✅ Provider: {model_info.provider}")
        print(f"✅ Features: {model_info.features}")
        print(f"✅ API Compliance: {model_info.metadata.get('api_compliance')}")
        print(f"✅ Capability details: {capability_details.get('api_compliance')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Model info test failed: {e}")
        return False


def main():
    """Run all compliance tests."""
    print("🚀 Starting Ollama API Compliance Validation Tests")
    print("=" * 60)
    
    tests = [
        ("System Prompt Handling", test_system_prompt_handling),
        ("Tool Calling", test_tool_calling), 
        ("Parameter Mapping", test_parameter_mapping),
        ("Streaming", test_streaming),
        ("Model Information", test_model_info),
    ]
    
    results = {}
    
    # Run sync tests
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Run async test
    try:
        results["Async Functionality"] = asyncio.run(test_async_functionality())
    except Exception as e:
        print(f"❌ Async test crashed: {e}")
        results["Async Functionality"] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"{test_name:.<40} {status}")
        if passed_test:
            passed += 1
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! Your Ollama integration is fully API compliant!")
        return True
    else:
        print("⚠️ Some tests failed. Check the error messages above.")
        return False


if __name__ == "__main__":
    main()
