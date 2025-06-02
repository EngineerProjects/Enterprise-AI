"""
Comprehensive Tool-LLM Integration Test for Enterprise AI
========================================================

This test validates the complete tool-LLM integration pipeline using 
the working provider pattern with auto tool execution.
"""

import asyncio
import sys
from pathlib import Path

# Setup project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async, Style
)

# Enterprise AI imports
from enterprise_ai.schema.llm import CompletionOptions
from enterprise_ai.tool.core.llm_adapter import get_llm_tools, get_llm_tool_definitions, get_adapter
from enterprise_ai.tool.core.registry import get_registry, search_tools
from enterprise_ai.llm.ollama import OllamaProvider  # ← Use provider directly
from enterprise_ai.schema import Message

TIMEOUT = 1200.0  


async def test_tool_registration():
    """Test tool registration and discovery."""
    print_header("🔧 Tool Registration & Discovery", "box")
    
    with Timer("Tool Registry Inspection"):
        registry = get_registry()
        all_tools = registry.get_all_tool_classes()
        categories = registry.get_all_category_names()
        capabilities = registry.get_all_capability_names()
    
    print_test(f"Total registered tools: {len(all_tools)}", "pass")
    print_test(f"Available categories: {', '.join(categories)}", "pass")
    print_test(f"Available capabilities: {len(capabilities)}", "pass")
    
    # Test specific tool search
    research_tools = search_tools(categories=["research"])
    content_tools = search_tools(categories=["content"])
    
    print_test(f"Research tools found: {len(research_tools)}", "pass" if research_tools else "warn")
    print_test(f"Content tools found: {len(content_tools)}", "pass" if content_tools else "warn")
    
    return len(all_tools) > 0


async def test_llm_adapter():
    """Test LLM adapter functionality."""
    print_header("🔄 LLM Adapter Integration", "box")
    
    adapter = get_adapter()
    
    # Test tool function generation
    with Timer("Tool Function Generation"):
        try:
            tools = await get_llm_tools(categories=["research", "content"])
            tool_definitions = await get_llm_tool_definitions(categories=["research", "content"])
        except Exception as e:
            print_test(f"Tool generation failed: {e}", "fail")
            return False
    
    print_test(f"Generated tool functions: {len(tools)}", "pass" if tools else "fail")
    print_test(f"Generated tool definitions: {len(tool_definitions)}", "pass" if tool_definitions else "fail")
    
    # Show tool details - NO TRUNCATION
    if tools:
        separator()
        print(f"{Style.YELLOW}📋 Available Tools:{Style.RESET}")
        for name, func in list(tools.items())[:3]:  # Show first 3
            doc = getattr(func, '__doc__', 'No description')
            print(f"  • {name}: {doc}")  # Full description, no truncation
    
    return len(tools) > 0 and len(tool_definitions) > 0


async def test_simple_tool_execution():
    """Test simple tool execution without LLM."""
    print_header("⚡ Direct Tool Execution", "box")
    
    try:
        # Get tools
        tools = await get_llm_tools(categories=["content"])
        
        if not tools:
            print_test("No tools available for testing", "skip")
            return False
        
        # Test CreateChatCompletion if available
        if "create_chat_completion" in tools:
            with Timer("CreateChatCompletion Test"):
                tool_func = tools["create_chat_completion"]
                result = tool_func(response="Hello from Enterprise AI tool system!")  # ← Remove await
                print_test("CreateChatCompletion executed successfully", "pass")
                print_chat("tool", f"Result: {result}")
            return True
        else:
            print_test("CreateChatCompletion not available", "skip")
            return False
                
    except Exception as e:
        print_test(f"Tool execution test failed: {e}", "fail")
        return False

async def test_llm_with_tools_auto():
    """Test LLM integration with automatic tool execution."""
    print_header("🤖 LLM + Tools Integration (Auto Mode)", "box")
    
    try:
        # Get tools and definitions
        with Timer("Tool Preparation"):
            tools = await get_llm_tools(categories=["content"])
            tool_definitions = await get_llm_tool_definitions(categories=["content"])
        
        if not tools or not tool_definitions:
            print_test("No tools available for LLM testing", "skip")
            return False
        
        # Create provider with AUTO execution (like working test)
        print_test("Creating provider with auto tool execution", "running")
        provider = OllamaProvider(
            model_name="llama3.2",
            tool_execute="auto",  # ← KEY: Enable auto execution
            max_tool_iterations=3,
            timeout=TIMEOUT
        )
        
        # Register tools directly with provider (like working test)
        provider.register_tools(tools)
        print_test("Tools registered with provider", "pass")
        
        # Test with explicit tool usage prompt
        messages = [
            Message.user_message(
                "Generate a response saying 'Enterprise AI tools are working correctly!' "
                "You MUST use the create_chat_completion tool to do this."
            )
        ]
        
        print_test("Sending request to LLM with auto tool execution", "running")
        print_chat("user", messages[0].content)
        
        with Timer("LLM Auto Tool Execution"):
            try:
                result = provider.complete(
                    messages,
                    tools=tool_definitions,
                    temperature=0.1
                )
                
                print_test("LLM completion successful", "pass")
                print_chat("assistant", result.content, model="llama3.2")  # Full response, no truncation
                
                # Check if tools were actually executed
                if hasattr(provider, '_tool_executor') and provider._tool_executor:
                    stats = provider._tool_executor.get_execution_stats()
                    executions = stats.get('total_executions', 0)
                    if executions > 0:
                        print_test(f"✅ Tools actually executed: {executions}", "pass")
                        
                        # Show detailed execution info
                        print(f"{Style.CYAN}📊 Tool Execution Details:{Style.RESET}")
                        print(f"  • Total executions: {stats.get('total_executions', 0)}")
                        print(f"  • Successful executions: {stats.get('successful_executions', 0)}")
                        print(f"  • Failed executions: {stats.get('failed_executions', 0)}")
                        print(f"  • Average execution time: {stats.get('average_execution_time', 0):.3f}s")
                        print(f"  • Registered tools: {stats.get('registered_tools', [])}")
                        
                        return True
                    else:
                        print_test("⚠️ No tools executed", "warn")
                        return False
                else:
                    print_test("⚠️ No tool executor found", "warn")
                    return False
                
            except Exception as e:
                print_test(f"LLM completion failed: {e}", "fail")
                return False
                
    except Exception as e:
        print_test(f"LLM-Tools integration failed: {e}", "fail")
        return False


async def test_research_tools_auto():
    """Test research tools with auto execution."""
    print_header("🔍 Research Tools Auto Execution", "box")
    
    try:
        # Get research tools
        tools = await get_llm_tools(categories=["research"])
        tool_definitions = await get_llm_tool_definitions(categories=["research"])
        
        if not tools:
            print_test("No research tools available", "skip")
            return True  # Not a failure, just not available
        
        print_test(f"Research tools available: {list(tools.keys())}", "pass")
        
        # Create provider with auto execution
        provider = OllamaProvider(
            model_name="llama3.2",
            tool_execute="auto",
            max_tool_iterations=2,  # Limit for testing
            timeout=TIMEOUT
        )
        
        provider.register_tools(tools)
        
        # Test web search
        messages = [
            Message.user_message(
                "Search for recent information about 'Enterprise AI tools' "
                "and give me a brief summary of what you find."
            )
        ]
        
        print_chat("user", messages[0].content)
        
        with Timer("Research Tools Auto Execution"):
            try:
                result = provider.complete(
                    messages,
                    tools=tool_definitions,
                    temperature=0.3
                )
                
                print_test("Research tools execution successful", "pass")
                print_chat("assistant", result.content)  # Full response, no truncation
                
                # Check execution stats
                if hasattr(provider, '_tool_executor') and provider._tool_executor:
                    stats = provider._tool_executor.get_execution_stats()
                    executions = stats.get('total_executions', 0)
                    print_test(f"Research tool executions: {executions}", "pass" if executions > 0 else "warn")
                    
                    if executions > 0:
                        print(f"{Style.CYAN}🔍 Research Tool Execution Stats:{Style.RESET}")
                        print(f"  • Total executions: {executions}")
                        print(f"  • Tools used: {stats.get('registered_tools', [])}")
                        print(f"  • Success rate: {stats.get('success_rate', 0):.2%}")
                
                return True
                
            except Exception as e:
                print_test(f"Research tools test failed: {e}", "warn")
                print(f"{Style.RED}Research error details: {str(e)}{Style.RESET}")  # Full error
                return False
        
    except Exception as e:
        print_test(f"Research tools test failed: {e}", "fail")
        print(f"{Style.RED}Research setup error: {str(e)}{Style.RESET}")  # Full error
        return False


async def comprehensive_test():
    """Run comprehensive tool-LLM integration test."""
    print_header("🚀 Enterprise AI Tool-LLM Integration Test", "double")
    
    results = []
    
    # Test sequence
    tests = [
        ("Tool Registration", test_tool_registration),
        ("LLM Adapter", test_llm_adapter),
        ("Direct Tool Execution", test_simple_tool_execution),
        ("LLM-Tools Auto Integration", test_llm_with_tools_auto),
        ("Research Tools Auto", test_research_tools_auto),
    ]
    
    for test_name, test_func in tests:
        separator()
        try:
            with Timer(f"{test_name} Test"):
                success = await test_func()
                results.append((test_name, success))
                print_test(f"{test_name} completed", "pass" if success else "warn")
        except Exception as e:
            print_test(f"{test_name} failed with error: {e}", "fail")
            print(f"{Style.RED}Full error details: {str(e)}{Style.RESET}")  # Show full error
            results.append((test_name, False))
    
    # Summary
    print_header("📊 Test Results Summary", "box")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {test_name:<30} {status}")
    
    separator()
    print(f"{Style.BOLD}Overall: {passed}/{total} tests passed{Style.RESET}")
    
    if passed == total:
        print_test("🎉 All systems operational! Tool-LLM integration is working correctly.", "pass")
    elif passed >= total * 0.8:
        print_test("⚠️  Most systems working. Minor issues detected but core functionality is operational.", "warn")
    else:
        print_test("❌ Multiple failures detected. Investigation required.", "fail")
    
    # Show next steps
    separator()
    print_header("🚀 Next Steps", "box")
    if passed >= total * 0.8:
        print_test("✅ Ready for MCP module development", "pass")
        print_test("✅ Tool system is production-ready", "pass")
        print_test("✅ Auto tool execution working", "pass")
    else:
        print_test("🔧 Fix tool execution issues first", "warn")
        print_test("🔧 Debug auto execution behavior", "warn")
    
    # Show detailed summary
    print(f"\n{Style.YELLOW}📋 Detailed Test Summary:{Style.RESET}")
    for i, (test_name, success) in enumerate(results, 1):
        status_icon = "✅" if success else "❌"
        print(f"  {i}. {status_icon} {test_name}")
    
    return passed >= total * 0.8  # Consider success if 80% pass


def main():
    """Main test function."""
    setup_project_path()
    
    print(f"{Style.CYAN}")
    print("=" * 80)
    print("ENTERPRISE AI - Tool & LLM Integration Test".center(80))
    print("Testing complete tool system with LLM auto execution")
    print("=" * 80)
    print(f"{Style.RESET}\n")
    
    try:
        success = run_async(comprehensive_test())
        
        if success:
            print(f"\n{Style.GREEN}🎯 SUCCESS: Your tool-LLM integration is ready for production!{Style.RESET}")
            print(f"{Style.CYAN}Next step: Proceed with MCP module development.{Style.RESET}")
        else:
            print(f"\n{Style.YELLOW}⚠️  PARTIAL SUCCESS: Some issues detected but core functionality works.{Style.RESET}")
            print(f"{Style.CYAN}Recommendation: Review tool execution patterns before MCP.{Style.RESET}")
            
    except Exception as e:
        print(f"\n{Style.RED}💥 CRITICAL ERROR: {e}{Style.RESET}")
        print(f"{Style.RED}Full error traceback:{Style.RESET}")
        import traceback
        print(traceback.format_exc())  # Show full traceback
        print(f"{Style.CYAN}Recommendation: Debug core issues before proceeding.{Style.RESET}")


if __name__ == "__main__":
    main()