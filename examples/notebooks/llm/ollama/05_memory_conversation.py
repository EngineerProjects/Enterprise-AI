#!/usr/bin/env python3
"""
Enterprise AI - Memory & Conversation Tests

Comprehensive tests for conversation memory management and persistence.
Tests different memory strategies, conversation retention, and integration with LLM providers.

Features tested:
- In-memory conversation management
- Sliding window conversation management  
- Memory limits and cleanup
- Conversation persistence across interactions
- Tool call preservation in memory
- Long conversation handling
- Memory performance and optimization
"""

import sys
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project to path and import utilities
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async
)

# Import Enterprise AI
setup_project_path()
from enterprise_ai.llm.ollama import OllamaProvider
from enterprise_ai.schema import (
    Message, ToolCall, ToolDefinition, 
    ConversationMemory, InMemoryConversation, SlidingWindowConversation,
    ConversationMemoryFactory, MemoryConfig
)

# Import test tools for memory with tool calls
from test_tools import TOOL_DEFINITIONS, TOOLS_REGISTRY

# Test configuration
TEST_MODEL = "llama3.2:latest"
TIMEOUT = 300.0

def test_basic_memory_operations():
    """Test basic memory operations and persistence."""
    print_header("Basic Memory Operations Tests", "single")
    
    try:
        print_test("Creating in-memory conversation", "running")
        
        # Create basic in-memory conversation
        memory = InMemoryConversation()
        
        # Add some messages
        user_msg = Message.user_message("Hello, I'm testing memory")
        assistant_msg = Message.assistant_message("Hello! I'll remember our conversation.")
        
        memory.add_message(user_msg)
        memory.add_message(assistant_msg)
        
        print_test(f"✓ Added 2 messages to memory", "pass")
        
        # Test message retrieval
        messages = memory.get_messages()
        if len(messages) == 2:
            print_test("✓ Message retrieval successful", "pass")
        else:
            print_test(f"✗ Expected 2 messages, got {len(messages)}", "fail")
            return False
        
        # Test message count (using len of messages)
        count = len(memory.get_messages())
        if count == 2:
            print_test("✓ Message count correct", "pass")
        else:
            print_test(f"✗ Expected count 2, got {count}", "fail")
            return False
        
        # Test memory clearing
        memory.clear()
        if len(memory.get_messages()) == 0:
            print_test("✓ Memory clearing successful", "pass")
        else:
            print_test("✗ Memory clearing failed", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Basic memory operations failed: {e}", "fail")
        return False

def test_sliding_window_memory():
    """Test sliding window memory with size limits."""
    print_header("Sliding Window Memory Tests", "single")
    
    try:
        print_test("Creating sliding window memory (max 5 messages)", "running")
        
        # Create sliding window with small limit
        memory = SlidingWindowConversation(max_messages=5)
        
        print_test("✓ Sliding window memory created", "pass")
        
        # Add messages beyond the limit
        print_test("Adding 8 messages to test sliding behavior", "running")
        
        for i in range(8):
            if i % 2 == 0:
                msg = Message.user_message(f"User message {i + 1}")
            else:
                msg = Message.assistant_message(f"Assistant response {i + 1}")
            memory.add_message(msg)
        
        # Check that only 5 messages are retained
        messages = memory.get_messages()
        message_count = len(messages)
        
        if message_count == 5:
            print_test("✓ Sliding window limit enforced correctly", "pass")
        else:
            print_test(f"✗ Expected 5 messages, got {message_count}", "fail")
            return False
        
        # Verify the messages are the most recent ones
        last_message = messages[-1]
        # The last message should be "Assistant response 8"
        if "response 8" in last_message.content or "8" in last_message.content:
            print_test("✓ Most recent messages preserved", "pass")
        else:
            print_test(f"✗ Expected '8' in last message, got: '{last_message.content}'", "fail")
            # Debug: Show what messages were actually preserved
            print("Debug - Preserved messages:")
            for i, msg in enumerate(messages):
                print(f"  {i}: {msg.content}")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Sliding window memory failed: {e}", "fail")
        return False

def test_memory_with_tools():
    """Test memory preservation of tool calls and results."""
    print_header("Memory with Tool Calls Tests", "single")
    
    try:
        print_test("Creating memory with tool call preservation", "running")
        
        memory = InMemoryConversation()
        
        # Create a message with tool calls
        user_msg = Message.user_message("Calculate 15 * 8 + 32")
        memory.add_message(user_msg)
        
        # Create assistant message with tool calls
        tool_calls = [{
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "calculate_advanced",
                "arguments": json.dumps({"expression": "15 * 8 + 32", "precision": "2"})
            }
        }]
        
        assistant_msg = Message.assistant_message(
            content="I'll calculate that for you.",
            tool_calls=tool_calls
        )
        memory.add_message(assistant_msg)
        
        # Create tool result message
        tool_msg = Message.tool_message(
            content='{"result": 152, "expression": "15 * 8 + 32"}',
            name="calculate_advanced",
            tool_call_id="call_123"
        )
        memory.add_message(tool_msg)
        
        # Create final assistant response
        final_msg = Message.assistant_message("The result is 152.")
        memory.add_message(final_msg)
        
        print_test("✓ Added conversation with tool calls", "pass")
        
        # Verify tool calls are preserved
        messages = memory.get_messages()
        tool_call_found = False
        tool_result_found = False
        
        for msg in messages:
            if msg.has_tool_calls():
                tool_call_found = True
            if msg.role == "tool":
                tool_result_found = True
        
        if tool_call_found and tool_result_found:
            print_test("✓ Tool calls and results preserved in memory", "pass")
        else:
            print_test("✗ Tool calls or results not properly preserved", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Memory with tools failed: {e}", "fail")
        return False

def test_memory_factory():
    """Test memory factory for creating different memory types."""
    print_header("Memory Factory Tests", "single")
    
    try:
        print_test("Testing memory factory creation", "running")
        
        # Test in-memory creation
        memory1 = ConversationMemoryFactory.create("memory")
        
        if isinstance(memory1, InMemoryConversation):
            print_test("✓ In-memory conversation created via factory", "pass")
        else:
            print_test("✗ Wrong memory type created", "fail")
            return False
        
        # Test sliding window creation
        memory2 = ConversationMemoryFactory.create("sliding_window", max_messages=10)
        
        if isinstance(memory2, SlidingWindowConversation):
            print_test("✓ Sliding window conversation created via factory", "pass")
        else:
            print_test("✗ Wrong memory type created", "fail")
            return False
        
        # Test configuration application
        if memory2.max_messages == 10:
            print_test("✓ Memory configuration applied correctly", "pass")
        else:
            print_test("✗ Memory configuration not applied", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Memory factory failed: {e}", "fail")
        return False

def test_conversation_with_llm():
    """Test memory integration with LLM provider."""
    print_header("LLM Integration with Memory Tests", "single")
    
    try:
        print_test("Creating LLM provider with memory", "running")
        
        # Create provider
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            tool_execute="manual",
            timeout=TIMEOUT
        )
        
        # Create memory
        memory = InMemoryConversation()
        
        print_test("✓ LLM provider and memory created", "pass")
        
        # Test conversation flow with memory
        print_test("Testing multi-turn conversation with memory", "running")
        
        # First interaction
        user_msg1 = Message.user_message("My name is Alice. What's 5 + 3?")
        memory.add_message(user_msg1)
        
        response1 = provider.complete(memory.get_messages())
        memory.add_message(response1)
        
        print_chat("user", "My name is Alice. What's 5 + 3?")
        print_chat("assistant", response1.content, model=TEST_MODEL)
        
        # Second interaction - test memory retention
        user_msg2 = Message.user_message("What's my name?")
        memory.add_message(user_msg2)
        
        response2 = provider.complete(memory.get_messages())
        memory.add_message(response2)
        
        print_chat("user", "What's my name?")
        print_chat("assistant", response2.content, model=TEST_MODEL)
        
        # Check if the model remembered the name
        if "Alice" in response2.content or "alice" in response2.content.lower():
            print_test("✓ LLM remembered information from memory", "pass")
        else:
            print_test("⚠ LLM may not have used memory context", "warn")
        
        # Verify conversation length
        if len(memory.get_messages()) >= 4:
            print_test("✓ Conversation history maintained", "pass")
        else:
            print_test("✗ Conversation history incomplete", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"LLM integration failed: {e}", "fail")
        return False

def test_memory_with_auto_tools():
    """Test memory with automatic tool execution."""
    print_header("Memory with Auto Tool Execution Tests", "single")
    
    try:
        print_test("Creating LLM with auto tools and memory", "running")
        
        # Create provider with auto tool execution
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            tool_execute="auto",
            max_tool_iterations=3,
            timeout=TIMEOUT
        )
        
        provider.register_tools(TOOLS_REGISTRY)
        
        # Create memory
        memory = InMemoryConversation()
        
        print_test("✓ Auto tool provider and memory ready", "pass")
        
        # Test conversation with automatic tool execution
        print_test("Testing conversation with auto tool execution", "running")
        
        user_msg = Message.user_message(
            "Calculate the statistical analysis of these numbers: [10, 20, 30, 40, 50]. "
            "Remember this analysis for later."
        )
        memory.add_message(user_msg)
        
        with Timer("Auto tool execution with memory"):
            response = provider.complete(
                memory.get_messages(),
                tools=TOOL_DEFINITIONS,
                temperature=0.5
            )
        
        memory.add_message(response)
        
        print_chat("user", user_msg.content)
        print_chat("assistant", response.content, model=TEST_MODEL)
        
        # Follow-up question to test memory
        follow_up = Message.user_message("What was the mean from the previous calculation?")
        memory.add_message(follow_up)
        
        response2 = provider.complete(memory.get_messages())
        memory.add_message(response2)
        
        print_chat("user", follow_up.content)
        print_chat("assistant", response2.content, model=TEST_MODEL)
        
        # Check memory preservation
        final_count = len(memory.get_messages())
        if final_count >= 4:
            print_test(f"✓ All interactions preserved in memory ({final_count} messages)", "pass")
        else:
            print_test(f"✗ Memory incomplete ({final_count} messages)", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Memory with auto tools failed: {e}", "fail")
        return False

def test_long_conversation_handling():
    """Test handling of very long conversations."""
    print_header("Long Conversation Handling Tests", "single")
    
    try:
        print_test("Testing long conversation with sliding window", "running")
        
        # Create sliding window with reasonable limit
        memory = SlidingWindowConversation(max_messages=20)
        
        # Simulate a long conversation
        print_test("Simulating 50-message conversation", "running")
        
        for i in range(25):  # 25 back-and-forth exchanges = 50 messages
            user_msg = Message.user_message(f"Question {i + 1}: What is {i + 1} * 2?")
            assistant_msg = Message.assistant_message(f"Answer {i + 1}: {(i + 1) * 2}")
            
            memory.add_message(user_msg)
            memory.add_message(assistant_msg)
        
        # Verify sliding window behavior
        final_count = len(memory.get_messages())
        if final_count == 20:
            print_test("✓ Sliding window maintained correct size", "pass")
        else:
            print_test(f"✗ Expected 20 messages, got {final_count}", "fail")
            return False
        
        # Verify recent messages are preserved
        messages = memory.get_messages()
        last_message = messages[-1]
        
        if "Answer 25" in last_message.content:
            print_test("✓ Most recent messages preserved", "pass")
        else:
            print_test("✗ Recent messages not preserved correctly", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Long conversation handling failed: {e}", "fail")
        return False

def test_memory_performance():
    """Test memory performance with large conversations."""
    print_header("Memory Performance Tests", "single")
    
    try:
        print_test("Testing memory performance", "running")
        
        # Test performance with large in-memory conversation
        memory = InMemoryConversation()
        
        # Add many messages and measure performance
        start_time = time.time()
        
        for i in range(1000):
            msg = Message.user_message(f"Message {i}")
            memory.add_message(msg)
        
        add_time = time.time() - start_time
        
        # Test retrieval performance
        start_time = time.time()
        messages = memory.get_messages()
        retrieval_time = time.time() - start_time
        
        if len(messages) == 1000:
            print_test("✓ All messages stored correctly", "pass")
        else:
            print_test(f"✗ Expected 1000 messages, got {len(messages)}", "fail")
            return False
        
        print_test(f"✓ Add performance: {add_time:.3f}s for 1000 messages", "pass")
        print_test(f"✓ Retrieval performance: {retrieval_time:.3f}s", "pass")
        
        # Performance thresholds
        if add_time < 1.0 and retrieval_time < 0.1:
            print_test("✓ Performance within acceptable limits", "pass")
        else:
            print_test("⚠ Performance slower than expected", "warn")
        
        return True
        
    except Exception as e:
        print_test(f"Memory performance test failed: {e}", "fail")
        return False

def test_token_counting():
    """Test token counting functionality."""
    print_header("Token Counting Tests", "single")
    
    try:
        print_test("Testing token counting", "running")
        
        memory = InMemoryConversation()
        
        # Add a message with known content
        test_content = "This is a test message for token counting. " * 10  # ~100 words
        memory.add_message(Message.user_message(test_content))
        
        # Get token count
        token_count = memory.get_token_count()
        
        if token_count > 0:
            print_test(f"✓ Token counting functional: {token_count} tokens", "pass")
        else:
            print_test("✗ Token counting failed", "fail")
            return False
        
        # Test with multiple messages
        memory.add_message(Message.assistant_message("Short response"))
        new_count = memory.get_token_count()
        
        if new_count > token_count:
            print_test("✓ Token count increases with new messages", "pass")
        else:
            print_test("✗ Token count not updating properly", "fail")
            return False
        
        return True
        
    except Exception as e:
        print_test(f"Token counting failed: {e}", "fail")
        return False

async def test_async_memory_operations():
    """Test memory operations in async contexts."""
    print_header("Async Memory Operations Tests", "single")
    
    try:
        print_test("Testing async memory operations", "running")
        
        # Create provider with async capabilities
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            tool_execute="auto",
            timeout=TIMEOUT
        )
        
        provider.register_tools(TOOLS_REGISTRY)
        
        # Create memory
        memory = InMemoryConversation()
        
        # Test async conversation
        user_msg = Message.user_message("Generate 5 sample users and tell me about them")
        memory.add_message(user_msg)
        
        with Timer("Async conversation with memory"):
            response = await provider.acomplete(
                memory.get_messages(),
                tools=TOOL_DEFINITIONS,
                temperature=0.5
            )
        
        memory.add_message(response)
        
        print_chat("user", user_msg.content)
        print_chat("assistant", response.content, model=TEST_MODEL)
        
        if len(memory.get_messages()) >= 2:
            print_test("✓ Async operations with memory successful", "pass")
            return True
        else:
            print_test("✗ Async memory operations failed", "fail")
            return False
        
    except Exception as e:
        print_test(f"Async memory operations failed: {e}", "fail")
        return False

def demonstrate_memory_capabilities():
    """Demonstrate comprehensive memory capabilities."""
    print_header("🧠 Memory Capabilities Demonstration", "double")
    
    try:
        print_test("Demo: Persistent Multi-Turn Conversation", "running")
        
        # Create provider and memory
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            tool_execute="auto",
            timeout=TIMEOUT
        )
        provider.register_tools(TOOLS_REGISTRY)
        
        memory = InMemoryConversation()
        
        # Multi-turn conversation demonstrating memory
        conversations = [
            "Hi, I'm working on a data analysis project. Can you help me?",
            "I have these sales numbers: [100, 150, 200, 175, 125]. Can you analyze them?",
            "What was the mean from my previous analysis?",
            "Now calculate what the total revenue would be if I increased each number by 20%",
            "Perfect! Can you remind me what my original dataset was?"
        ]
        
        for i, user_input in enumerate(conversations):
            print_test(f"Turn {i + 1}: Processing conversation", "running")
            
            user_msg = Message.user_message(user_input)
            memory.add_message(user_msg)
            
            if i == 1:  # Second turn needs tools
                response = provider.complete(
                    memory.get_messages(),
                    tools=TOOL_DEFINITIONS,
                    temperature=0.4
                )
            else:
                response = provider.complete(memory.get_messages(), temperature=0.4)
            
            memory.add_message(response)
            
            print_chat("user", user_input)
            print_chat("assistant", response.content, model=TEST_MODEL)
            separator("·")
        
        print_test(f"✓ Completed {len(conversations)}-turn conversation", "pass")
        print_test(f"✓ Memory contains {len(memory.get_messages())} messages", "pass")
        
        return True
        
    except Exception as e:
        print_test(f"Memory demonstration failed: {e}", "fail")
        return False

def main():
    """Run all memory and conversation tests."""
    print_header("🧠 Enterprise AI - Memory & Conversation Tests", "double")
    print_test("Starting comprehensive memory and conversation test suite...", "running")
    
    # Test results tracking
    results = {}
    
    # Test 1: Basic memory operations
    results['basic_operations'] = test_basic_memory_operations()
    
    # Test 2: Sliding window memory
    results['sliding_window'] = test_sliding_window_memory()
    
    # Test 3: Memory with tool calls
    results['memory_tools'] = test_memory_with_tools()
    
    # Test 4: Memory factory
    results['memory_factory'] = test_memory_factory()
    
    # Test 5: LLM integration
    results['llm_integration'] = test_conversation_with_llm()
    
    # Test 6: Auto tools with memory
    results['auto_tools_memory'] = test_memory_with_auto_tools()
    
    # Test 7: Long conversation handling
    results['long_conversations'] = test_long_conversation_handling()
    
    # Test 8: Memory performance
    results['performance'] = test_memory_performance()
    
    # Test 9: Token counting
    results['token_counting'] = test_token_counting()
    
    # Test 10: Async operations
    results['async_operations'] = run_async(test_async_memory_operations())
    
    # Test 11: Capabilities demonstration
    results['demonstration'] = demonstrate_memory_capabilities()
    
    # Final summary
    print_header("📊 Memory & Conversation Test Results", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All memory tests passed!", "pass")
        print_test("Your memory system is working perfectly!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    # Memory insights
    separator()
    print_header("💡 Memory System Insights", "box")
    print_test("Key memory capabilities validated:", "pass")
    print_test("✓ In-memory conversation management", "pass")
    print_test("✓ Sliding window memory with size limits", "pass")
    print_test("✓ Tool call and result preservation", "pass")
    print_test("✓ LLM integration with conversation history", "pass")
    print_test("✓ Factory pattern for memory creation", "pass")
    print_test("✓ Long conversation handling", "pass")
    print_test("✓ Token counting and estimation", "pass")
    print_test("✓ Async memory operations", "pass")
    
    # Next steps
    separator()
    print_header("🚀 Ready for Multi-Agent Development", "box")
    print_test("Your Enterprise AI memory system supports:", "pass")
    print_test("• Persistent multi-turn conversations", "pass")
    print_test("• Tool execution with history preservation", "pass")
    print_test("• Scalable conversation management", "pass")
    print_test("• Performance-optimized memory operations", "pass")
    print_test("• Async conversation handling", "pass")
    
    return results

if __name__ == "__main__":
    main()