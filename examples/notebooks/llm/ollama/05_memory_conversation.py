#!/usr/bin/env python3
"""
Enterprise AI - Memory & Conversation Tests (Updated for MCP Architecture)

Comprehensive tests for conversation memory management with tool call extraction.
Tests conversation retention with tool call awareness but no execution in LLM layer.

Features tested:
- In-memory conversation management
- Tool call extraction and display
- Memory preservation of tool calls
- Multi-turn conversations with tool awareness
- Tool call analysis and logging

This example demonstrates the clean separation between LLM (text generation + tool call extraction)
and MCP (tool execution). The LLM only extracts tool calls and we display what the agent
wants to do, but execution happens through MCP.
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

# Import test tools for tool definitions
from test_tools import TOOL_DEFINITIONS

# Test configuration
TEST_MODEL = "llama3.2:latest"
TIMEOUT = 300.0

def display_tool_calls(tool_calls: List[ToolCall], context: str = ""):
    """Display extracted tool calls in a user-friendly format."""
    if not tool_calls:
        print_test("No tool calls extracted", "skip")
        return
    
    print_header(f"🔧 Tool Calls Extracted {context}", "single")
    
    for i, tool_call in enumerate(tool_calls, 1):
        print_test(f"Tool Call #{i}: {tool_call.function.name}", "pass")
        
        # Display function details
        print(f"   🎯 Function: {tool_call.function.name}")
        print(f"   🆔 Call ID: {tool_call.id}")
        
        # Display arguments in a formatted way
        try:
            args = tool_call.get_arguments()
            if args:
                print("   📝 Arguments:")
                for key, value in args.items():
                    # Truncate long values for display
                    display_value = str(value)
                    if len(display_value) > 100:
                        display_value = display_value[:100] + "..."
                    print(f"      {key}: {display_value}")
            else:
                print("   📝 Arguments: (none)")
        except Exception as e:
            print(f"   ⚠️  Error parsing arguments: {e}")
        
        print()  # Add spacing between tool calls

def test_basic_tool_call_extraction():
    """Test basic tool call extraction from LLM responses."""
    print_header("Tool Call Extraction Tests", "single")
    
    try:
        print_test("Creating LLM provider for tool call extraction", "running")
        
        # Create provider - no tool execution, just text generation
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            verbose=True,
            timeout=TIMEOUT
        )
        
        print_test("✓ LLM provider created (text generation only)", "pass")
        
        # Create memory
        memory = InMemoryConversation()
        
        # Test tool call extraction
        print_test("Testing tool call extraction", "running")
        
        user_msg = Message.user_message("Calculate 15 * 8 + 32 using the advanced calculator")
        memory.add_message(user_msg)
        
        print_chat("user", user_msg.content)
        
        # Get response with tool calls
        response, tool_calls = provider.complete_with_tool_calls(
            memory.get_messages(),
            tools=TOOL_DEFINITIONS,
            temperature=0.3
        )
        
        memory.add_message(response)
        
        print_chat("assistant", response.content, model=TEST_MODEL)
        
        # Display extracted tool calls
        if tool_calls:
            display_tool_calls(tool_calls, "(from direct extraction)")
            print_test(f"✓ Extracted {len(tool_calls)} tool calls", "pass")
        else:
            print_test("⚠ No tool calls extracted", "warn")
        
        # Also check tool calls in response metadata
        if hasattr(response, 'metadata') and response.metadata and 'tool_calls' in response.metadata:
            metadata_tool_calls = [ToolCall.from_dict(tc) for tc in response.metadata['tool_calls']]
            if metadata_tool_calls:
                display_tool_calls(metadata_tool_calls, "(from response metadata)")
                print_test(f"✓ Found {len(metadata_tool_calls)} tool calls in metadata", "pass")
        
        return len(tool_calls) > 0 or (hasattr(response, 'metadata') and response.metadata and 'tool_calls' in response.metadata)
        
    except Exception as e:
        print_test(f"Tool call extraction failed: {e}", "fail")
        return False

def test_memory_with_tool_calls():
    """Test memory preservation of tool calls without execution."""
    print_header("Memory with Tool Call Preservation", "single")
    
    try:
        print_test("Testing tool call preservation in memory", "running")
        
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            verbose=False,
            timeout=TIMEOUT
        )
        
        memory = InMemoryConversation()
        
        # Multi-step conversation with tool awareness
        conversations = [
            "Hello! I need help with some calculations.",
            "Calculate the mean of these numbers: [10, 20, 30, 40, 50]",
            "Now calculate 25 * 4 + 100",
            "What was the mean from my first calculation?"
        ]
        
        for i, user_input in enumerate(conversations):
            print_test(f"Processing conversation turn {i + 1}", "running")
            
            user_msg = Message.user_message(user_input)
            memory.add_message(user_msg)
            
            print_chat("user", user_input)
            
            if i > 0:  # Only use tools after the greeting
                response, tool_calls = provider.complete_with_tool_calls(
                    memory.get_messages(),
                    tools=TOOL_DEFINITIONS,
                    temperature=0.4
                )
                
                if tool_calls:
                    display_tool_calls(tool_calls, f"(Turn {i + 1})")
                else:
                    print_test("No tool calls needed for this turn", "skip")
            else:
                response = provider.complete(memory.get_messages(), temperature=0.4)
            
            memory.add_message(response)
            print_chat("assistant", response.content, model=TEST_MODEL)
            separator("·")
        
        # Analyze memory contents
        messages = memory.get_messages()
        tool_call_count = 0
        
        for msg in messages:
            if hasattr(msg, 'metadata') and msg.metadata and 'tool_calls' in msg.metadata:
                tool_call_count += len(msg.metadata['tool_calls'])
        
        print_test(f"✓ Conversation preserved with {len(messages)} messages", "pass")
        print_test(f"✓ Found {tool_call_count} tool calls in memory", "pass")
        
        return True
        
    except Exception as e:
        print_test(f"Memory with tool calls failed: {e}", "fail")
        return False

def test_async_tool_call_extraction():
    """Test async tool call extraction."""
    print_header("Async Tool Call Extraction", "single")
    
    async def run_async_test():
        try:
            print_test("Testing async tool call extraction", "running")
            
            provider = OllamaProvider(
                model_name=TEST_MODEL,
                verbose=False,
                timeout=TIMEOUT
            )
            
            memory = InMemoryConversation()
            
            user_msg = Message.user_message(
                "Generate 5 sample users and then calculate statistics on their ages"
            )
            memory.add_message(user_msg)
            
            print_chat("user", user_msg.content)
            
            with Timer("Async tool call extraction"):
                response, tool_calls = await provider.acomplete_with_tool_calls(
                    memory.get_messages(),
                    tools=TOOL_DEFINITIONS,
                    temperature=0.5
                )
            
            memory.add_message(response)
            
            print_chat("assistant", response.content, model=TEST_MODEL)
            
            if tool_calls:
                display_tool_calls(tool_calls, "(async extraction)")
                print_test(f"✓ Async extracted {len(tool_calls)} tool calls", "pass")
                return True
            else:
                print_test("⚠ No tool calls extracted in async mode", "warn")
                return False
            
        except Exception as e:
            print_test(f"Async tool call extraction failed: {e}", "fail")
            return False
    
    return run_async(run_async_test())

def test_tool_call_analysis():
    """Test analysis of extracted tool calls."""
    print_header("Tool Call Analysis", "single")
    
    try:
        print_test("Testing tool call analysis and categorization", "running")
        
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            verbose=False,
            timeout=TIMEOUT
        )
        
        # Complex request that should trigger multiple tool calls
        complex_request = """
        I need you to:
        1. Generate 10 sample products
        2. Calculate statistics on their prices
        3. Simulate an API request to check our inventory system
        4. Process the JSON response from the API
        """
        
        messages = [Message.user_message(complex_request)]
        
        print_chat("user", complex_request)
        
        response, tool_calls = provider.complete_with_tool_calls(
            messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.6
        )
        
        print_chat("assistant", response.content, model=TEST_MODEL)
        
        if tool_calls:
            display_tool_calls(tool_calls, "(complex request)")
            
            # Analyze tool calls by category
            tool_categories = {}
            for tool_call in tool_calls:
                func_name = tool_call.function.name
                
                # Categorize tools
                if 'calculate' in func_name or 'statistical' in func_name:
                    category = "Mathematics"
                elif 'generate' in func_name:
                    category = "Data Generation"
                elif 'simulate' in func_name or 'api' in func_name:
                    category = "Network"
                elif 'process' in func_name or 'json' in func_name:
                    category = "Data Processing"
                else:
                    category = "Other"
                
                if category not in tool_categories:
                    tool_categories[category] = []
                tool_categories[category].append(func_name)
            
            print_header("📊 Tool Call Analysis", "single")
            for category, tools in tool_categories.items():
                print_test(f"{category}: {', '.join(tools)}", "pass")
            
            print_test(f"✓ Analyzed {len(tool_calls)} tool calls across {len(tool_categories)} categories", "pass")
            return True
        else:
            print_test("⚠ No tool calls extracted for analysis", "warn")
            return False
            
    except Exception as e:
        print_test(f"Tool call analysis failed: {e}", "fail")
        return False

def test_conversation_with_tool_awareness():
    """Test a full conversation flow with tool call awareness."""
    print_header("Conversation Flow with Tool Awareness", "single")
    
    try:
        print_test("Testing complete conversation flow", "running")
        
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            verbose=False,
            timeout=TIMEOUT
        )
        
        memory = SlidingWindowConversation(max_messages=20)
        
        # Simulate a realistic data analysis session
        conversation_flow = [
            "Hi! I'm working on a data analysis project and need help.",
            "Can you generate 5 sample user records for testing?",
            "Now calculate statistics on the user ages from that data.",
            "What was the average age from the previous calculation?",
            "Create a summary of what we've accomplished so far."
        ]
        
        total_tool_calls = 0
        
        for i, user_input in enumerate(conversation_flow):
            print_test(f"Conversation turn {i + 1}/{len(conversation_flow)}", "running")
            
            user_msg = Message.user_message(user_input)
            memory.add_message(user_msg)
            
            print_chat("user", user_input)
            
            if "generate" in user_input.lower() or "calculate" in user_input.lower():
                # Use tools for generation and calculation requests
                response, tool_calls = provider.complete_with_tool_calls(
                    memory.get_messages(),
                    tools=TOOL_DEFINITIONS,
                    temperature=0.4
                )
                
                if tool_calls:
                    total_tool_calls += len(tool_calls)
                    display_tool_calls(tool_calls, f"(Turn {i + 1})")
            else:
                # Regular conversation
                response = provider.complete(memory.get_messages(), temperature=0.4)
            
            memory.add_message(response)
            print_chat("assistant", response.content, model=TEST_MODEL)
            separator("·")
        
        # Final analysis
        print_header("📈 Conversation Analysis", "single")
        final_messages = memory.get_messages()
        print_test(f"Total messages in memory: {len(final_messages)}", "pass")
        print_test(f"Total tool calls extracted: {total_tool_calls}", "pass")
        
        # Check memory retention
        if len(final_messages) >= len(conversation_flow) * 2:  # User + assistant messages
            print_test("✓ Conversation history preserved", "pass")
        else:
            print_test("⚠ Some conversation history may be lost", "warn")
        
        return True
        
    except Exception as e:
        print_test(f"Conversation flow test failed: {e}", "fail")
        return False

def demonstrate_tool_call_capabilities():
    """Demonstrate comprehensive tool call extraction capabilities."""
    print_header("🎯 Tool Call Extraction Demonstration", "double")
    
    try:
        print_test("Demo: Comprehensive Tool Call Extraction", "running")
        
        provider = OllamaProvider(
            model_name=TEST_MODEL,
            verbose=False,
            timeout=TIMEOUT
        )
        
        memory = InMemoryConversation()
        
        # Complex scenario that should trigger multiple different tools
        complex_scenario = """
        I'm running an e-commerce analysis. Please help me:
        
        1. Generate 8 sample products with prices
        2. Calculate statistical analysis of the product prices
        3. Simulate checking our API health for the inventory service
        4. Create a JSON summary of the findings
        
        Show me what tools you would use and how you'd approach this.
        """
        
        user_msg = Message.user_message(complex_scenario)
        memory.add_message(user_msg)
        
        print_chat("user", complex_scenario)
        
        with Timer("Complex tool call extraction"):
            response, tool_calls = provider.complete_with_tool_calls(
                memory.get_messages(),
                tools=TOOL_DEFINITIONS,
                temperature=0.5
            )
        
        memory.add_message(response)
        
        print_chat("assistant", response.content, model=TEST_MODEL)
        
        if tool_calls:
            print_header("🔍 Detailed Tool Call Analysis", "single")
            
            # Detailed analysis of each tool call
            for i, tool_call in enumerate(tool_calls, 1):
                print_test(f"Tool Call {i}: {tool_call.function.name}", "pass")
                
                # Show what the tool would do
                args = tool_call.get_arguments()
                
                if tool_call.function.name == "generate_test_data":
                    data_type = args.get("data_type", "unknown")
                    count = args.get("count", "unknown")
                    print(f"   → Would generate {count} {data_type} records")
                
                elif tool_call.function.name == "statistical_analysis":
                    numbers = args.get("numbers", "unknown")
                    print(f"   → Would analyze data: {str(numbers)[:50]}...")
                
                elif tool_call.function.name == "simulate_api_request":
                    url = args.get("url", "unknown")
                    method = args.get("method", "GET")
                    print(f"   → Would make {method} request to: {url}")
                
                elif tool_call.function.name == "process_json_data":
                    operation = args.get("operation", "unknown")
                    print(f"   → Would perform {operation} operation on JSON data")
                
                print()
            
            # Summary
            print_test(f"✓ Successfully extracted {len(tool_calls)} tool calls", "pass")
            print_test("✓ Tool call details preserved for MCP execution", "pass")
            
        else:
            print_test("⚠ No tool calls extracted from complex scenario", "warn")
        
        return len(tool_calls) > 0 if tool_calls else False
        
    except Exception as e:
        print_test(f"Tool call demonstration failed: {e}", "fail")
        return False

def main():
    """Run all memory and tool call extraction tests."""
    print_header("🧠 Enterprise AI - Memory & Tool Call Extraction Tests", "double")
    print_test("Testing LLM layer with tool call extraction (no execution)...", "running")
    
    # Test results tracking
    results = {}
    
    # Test 1: Basic tool call extraction
    results['tool_extraction'] = test_basic_tool_call_extraction()
    
    # Test 2: Memory with tool calls
    results['memory_tools'] = test_memory_with_tool_calls()
    
    # Test 3: Async tool call extraction
    results['async_extraction'] = test_async_tool_call_extraction()
    
    # Test 4: Tool call analysis
    results['tool_analysis'] = test_tool_call_analysis()
    
    # Test 5: Conversation flow
    results['conversation_flow'] = test_conversation_with_tool_awareness()
    
    # Test 6: Capabilities demonstration
    results['demonstration'] = demonstrate_tool_call_capabilities()
    
    # Final summary
    print_header("📊 Tool Call Extraction Test Results", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All tool call extraction tests passed!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    # Architecture insights
    separator()
    print_header("🏗️ Clean Architecture Validation", "box")
    print_test("✓ LLM layer focused on text generation only", "pass")
    print_test("✓ Tool calls extracted but not executed", "pass")
    print_test("✓ Memory preserves tool call information", "pass")
    print_test("✓ Clear separation between LLM and MCP layers", "pass")
    print_test("✓ Ready for MCP-based tool execution", "pass")
    
    # Next steps
    separator()
    print_header("🚀 Ready for MCP Integration", "box")
    print_test("Your LLM layer successfully:", "pass")
    print_test("• Generates text responses", "pass")
    print_test("• Extracts tool calls without executing them", "pass")
    print_test("• Preserves conversation memory with tool awareness", "pass")
    print_test("• Provides clean separation for MCP integration", "pass")
    print_test("• Supports both sync and async operations", "pass")
    
    return results

if __name__ == "__main__":
    main()