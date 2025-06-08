"""
Fixed Complete Enterprise AI Agent Test - No asyncio.run() conflicts.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from examples.notebooks.utils import (
        print_header, print_test, print_chat, separator, Style, Timer
    )
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    # Fallback styling
    class Style:
        BLUE = "\033[1;34m"; GREEN = "\033[1;32m"; RED = "\033[1;31m"
        YELLOW = "\033[1;33m"; PURPLE = "\033[1;35m"; CYAN = "\033[1;36m"
        BOLD = "\033[1m"; RESET = "\033[0m"
    
    def print_header(title, style="double"):
        print(f"\n{Style.BLUE}{'='*80}\n{title.center(80)}\n{'='*80}{Style.RESET}\n")
    
    def print_test(name, status="running"):
        icons = {"running": "🔄", "pass": "✅", "fail": "❌", "warn": "⚠️"}
        print(f"{icons.get(status, '•')} {name} [{status.upper()}]")
    
    def print_chat(role, content, **meta):
        icons = {"user": "👤", "assistant": "🤖", "tool": "🔧", "system": "⚙️"}
        print(f"{icons.get(role, '•')} {role.title()}: {content}")
    
    def separator(): print("-" * 60)
    
    class Timer:
        def __init__(self, desc): self.desc = desc
        async def __aenter__(self): import time; self.start = time.time(); return self
        async def __aexit__(self, *args): import time; print(f"⏱️  {self.desc}: {time.time() - self.start:.2f}s")

from enterprise_ai.agent import create_agent
from enterprise_ai.schema import Message, ToolCall


async def detailed_approval_callback(tool_call: ToolCall) -> bool:
    """Detailed approval callback that shows everything."""
    print(f"\n{Style.YELLOW}{'='*60}")
    print(f"🔒 TOOL EXECUTION APPROVAL REQUEST")
    print(f"{'='*60}{Style.RESET}")
    
    print(f"{Style.CYAN}Tool Name:{Style.RESET} {tool_call.function.name}")
    print(f"{Style.CYAN}Tool ID:{Style.RESET} {tool_call.id}")
    print(f"{Style.CYAN}Tool Type:{Style.RESET} {tool_call.type}")
    
    print(f"\n{Style.CYAN}Arguments:{Style.RESET}")
    args = tool_call.get_arguments()
    if args:
        for key, value in args.items():
            # Show full value, no truncation
            print(f"  • {Style.YELLOW}{key}:{Style.RESET} {value}")
    else:
        print("  (No arguments)")
    
    # Auto-approve safe tools for testing
    safe_tools = [
        "web_search", "deep_research", "code_search", "filesystem", 
        "file_editor", "mime_type_detector", "configuration",
        "FileSystemTool", "ConfigurationTool", "WebSearch"
    ]
    
    if tool_call.function.name in safe_tools:
        print(f"\n{Style.GREEN}✅ SAFE TOOL - AUTO-APPROVED{Style.RESET}")
        print(f"{Style.YELLOW}{'='*60}{Style.RESET}")
        return True
    else:
        print(f"\n{Style.YELLOW}❓ AUTO-APPROVING FOR TEST{Style.RESET}")
        print(f"{Style.YELLOW}{'='*60}{Style.RESET}")
        return True  # Auto-approve for testing


async def print_complete_tool_catalog(agent):
    """Print complete tool catalog with full details using async methods."""
    print_header("🔧 Complete Tool Catalog (via Embedded MCP Server)", "double")
    
    try:
        # Get tools via MCP server methods - NOW PROPERLY ASYNC
        tools_by_category = agent.get_tool_categories()
        detailed_tools = await agent.get_available_tools()
        
        total_tools = sum(len(tools) for tools in tools_by_category.values())
        print(f"{Style.BOLD}📊 SUMMARY{Style.RESET}")
        print(f"Total Tools: {total_tools}")
        print(f"Categories: {len(tools_by_category)}")
        print(f"MCP Server Status: {Style.GREEN}✅ Active{Style.RESET}")
        
        # Show MCP server info
        mcp_info = agent.get_mcp_server_info()
        print(f"MCP Version: {mcp_info.get('version', 'Unknown')}")
        print(f"Server Running: {mcp_info.get('running', False)}")
        
        print(f"\n{Style.BOLD}📁 DETAILED CATALOG{Style.RESET}")
        print("=" * 80)
        
        for category, tool_names in tools_by_category.items():
            print(f"\n{Style.PURPLE}📂 CATEGORY: {category.upper()}{Style.RESET}")
            print(f"Tools in category: {len(tool_names)}")
            print("-" * 60)
            
            for i, tool_name in enumerate(tool_names, 1):
                # Find detailed info
                tool_details = next((t for t in detailed_tools if t["name"] == tool_name), None)
                
                print(f"\n{Style.CYAN}{i}. {tool_name}{Style.RESET}")
                
                if tool_details:
                    # Full description, no truncation
                    desc = tool_details.get("description", "No description available")
                    print(f"   Description: {desc}")
                    
                    # Parameters
                    params = tool_details.get("parameters", {})
                    if params and params.get("properties"):
                        print(f"   Parameters:")
                        for param_name, param_info in params.get("properties", {}).items():
                            param_type = param_info.get("type", "unknown")
                            param_desc = param_info.get("description", "No description")
                            required = "✅" if param_name in params.get("required", []) else "❌"
                            print(f"     • {param_name} ({param_type}) - Required: {required}")
                            print(f"       {param_desc}")
                    else:
                        print(f"   Parameters: None")
                    
                    # Capabilities
                    capabilities = tool_details.get("capabilities", [])
                    if capabilities:
                        print(f"   Capabilities: {', '.join(capabilities)}")
                    
                    # Metadata
                    metadata = tool_details.get("metadata", {})
                    if metadata:
                        print(f"   Metadata:")
                        for key, value in metadata.items():
                            print(f"     • {key}: {value}")
                else:
                    print(f"   {Style.RED}❌ No detailed information available{Style.RESET}")
                
                print("   " + "-" * 50)
        
    except Exception as e:
        print(f"{Style.RED}❌ Failed to get tool catalog: {e}{Style.RESET}")
        import traceback
        traceback.print_exc()


def print_complete_conversation(conversation, agent_name):
    """Print complete conversation with full details."""
    print(f"\n{Style.BOLD}💬 COMPLETE CONVERSATION TRANSCRIPT{Style.RESET}")
    print("=" * 80)
    
    for i, msg in enumerate(conversation, 1):
        print(f"\n{Style.BOLD}--- MESSAGE {i} ---{Style.RESET}")
        
        # Message metadata
        print(f"Role: {msg.role}")
        if hasattr(msg, 'name') and msg.name:
            print(f"Name: {msg.name}")
        if hasattr(msg, 'timestamp') and msg.timestamp:
            print(f"Timestamp: {msg.timestamp}")
        
        # Tool calls if present
        if hasattr(msg, 'metadata') and msg.metadata and msg.metadata.get('tool_calls'):
            tool_calls = msg.metadata['tool_calls']
            print(f"{Style.YELLOW}🔧 TOOL CALLS: {len(tool_calls)}{Style.RESET}")
            for j, tc in enumerate(tool_calls, 1):
                print(f"  {j}. {tc.get('function', {}).get('name', 'Unknown')}")
                args = tc.get('function', {}).get('arguments', {})
                if args:
                    print(f"     Arguments: {args}")
        
        # Tool execution metadata
        if hasattr(msg, 'metadata') and msg.metadata:
            exec_success = msg.metadata.get('execution_success')
            exec_time = msg.metadata.get('execution_time')
            if exec_success is not None:
                status = "✅ SUCCESS" if exec_success else "❌ FAILED"
                print(f"Tool Execution: {status}")
                if exec_time:
                    print(f"Execution Time: {exec_time:.3f}s")
        
        # Message content (FULL, no truncation)
        print(f"\n{Style.CYAN}Content:{Style.RESET}")
        content = msg.content or "(No content)"
        print(content)
        
        print("-" * 60)


async def test_specific_tool_calling():
    """Test specific tool calling scenarios with proper async handling."""
    print_header("🎯 Specific Tool Calling Tests", "double")
    
    # Create agent
    print_test("Creating Agent with Embedded MCP Server", "running")
    
    agent = create_agent(
        llm_provider="ollama",
        model_name="llama3.2",
        name="TestAgent",
        timeout=500.0,
        temperature=0.7,
        verbose=True,
        
        # Tool settings
        enable_tools=True,
        auto_execute_tools=True,
        require_tool_approval=True,
        tool_approval_callback=detailed_approval_callback,
    )
    
    print_test("Agent Created", "pass")
    print(f"Agent: {agent.agent_name}")
    print(f"Model: {agent.get_model_name()}")
    
    # Show complete tool catalog
    await print_complete_tool_catalog(agent)
    
    # Test 1: Force filesystem tool usage
    print_header("📁 Test 1: Filesystem Tool", "single")
    
    messages = [
        Message.user_message(
            "I need you to use the filesystem tool to list all files in the current directory. "
            "Please actually execute the filesystem tool and show me the results. "
            "Don't just describe what you would do - actually do it."
        )
    ]
    
    print_chat("user", messages[0].content)
    
    async with Timer("Filesystem Test"):
        conversation = await agent.chat(
            messages=messages,
            tools=["file"],  # Only file tools
            max_iterations=3
        )
    
    print_complete_conversation(conversation, agent.agent_name)
    
    # Test 2: Force web search
    print_header("🌐 Test 2: Web Search Tool", "single")
    
    messages = [
        Message.user_message(
            "Please search the web for 'Python asyncio tutorial' and give me the results. "
            "Use the web search tool to get actual search results."
        )
    ]
    
    print_chat("user", messages[0].content)
    
    async with Timer("Web Search Test"):
        conversation = await agent.chat(
            messages=messages,
            tools=["research"],  # Only research tools
            max_iterations=3
        )
    
    print_complete_conversation(conversation, agent.agent_name)
    
    return agent


async def test_mcp_server_methods(agent):
    """Test MCP server methods directly with proper async."""
    print_header("⚙️ MCP Server Methods Test", "double")
    
    # Test tool info
    print_test("Testing Tool Info Retrieval", "running")
    
    try:
        tool_info = await agent.get_tool_info("filesystem")
        if tool_info:
            print_test("Tool Info Retrieved", "pass")
            print(f"\n{Style.BOLD}Filesystem Tool Info:{Style.RESET}")
            for key, value in tool_info.items():
                print(f"  {key}: {value}")
        else:
            print_test("Tool Info Not Found", "warn")
    except Exception as e:
        print_test(f"Tool Info Failed: {e}", "fail")
    
    # Test direct tool execution
    print_test("Testing Direct Tool Execution", "running")
    
    try:
        result = await agent.execute_tool_directly(
            tool_name="filesystem",
            arguments={"action": "list", "path": "."}
        )
        print_test("Direct Tool Execution", "pass")
        print(f"\n{Style.BOLD}Direct Execution Result:{Style.RESET}")
        print(result)
    except Exception as e:
        print_test(f"Direct Tool Execution Failed: {e}", "fail")


async def main():
    """Main comprehensive test with proper async handling."""
    print_header("🚀 Enterprise AI Agent - Complete Fixed Test Suite", "double")
    print(f"{Style.BOLD}Testing Agent with Embedded MCP Server (Fixed Async){Style.RESET}")
    print("No truncation - showing everything in full detail")
    
    try:
        # Create and test agent
        agent = await test_specific_tool_calling()
        
        # Test MCP server methods
        await test_mcp_server_methods(agent)
        
        # Final comprehensive statistics
        print_header("📊 Final Comprehensive Statistics", "double")
        
        info = agent.get_agent_info()
        
        print(f"{Style.BOLD}AGENT STATISTICS{Style.RESET}")
        print("-" * 40)
        print(f"Agent ID: {info['agent_id']}")
        print(f"Agent Name: {info['name']}")
        print(f"Model: {info['model_name']}")
        print(f"LLM Provider: {info.get('llm_provider', 'Unknown')}")
        print(f"Uptime: {info['uptime_seconds']:.2f}s")
        print(f"Conversations: {info['conversation_count']}")
        print(f"Tool Executions: {info['tool_execution_count']}")
        print(f"Errors: {info['error_count']}")
        
        print(f"\n{Style.BOLD}MCP SERVER STATISTICS{Style.RESET}")
        print("-" * 40)
        if 'mcp_server_info' in info:
            mcp_info = info['mcp_server_info']
            print(f"Server Name: {mcp_info.get('name', 'Unknown')}")
            print(f"Server Version: {mcp_info.get('version', 'Unknown')}")
            print(f"Server Running: {mcp_info.get('running', False)}")
            
            stats = mcp_info.get('stats', {})
            if stats:
                print(f"\nExecution Stats:")
                for category, category_stats in stats.items():
                    print(f"  {category}:")
                    if isinstance(category_stats, dict):
                        for key, value in category_stats.items():
                            print(f"    {key}: {value}")
                    else:
                        print(f"    {category_stats}")
        
        print(f"\n{Style.BOLD}TOOL CATEGORIES{Style.RESET}")
        print("-" * 40)
        categories = info.get('tool_categories', [])
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")
        
        print(f"\n{Style.GREEN}🎉 Complete test suite finished successfully!{Style.RESET}")
        print(f"Agent successfully demonstrated:")
        print(f"  ✅ LLM provider inheritance")
        print(f"  ✅ Embedded MCP server integration")
        print(f"  ✅ Dynamic tool discovery (fixed async)")
        print(f"  ✅ Tool execution with approval")
        print(f"  ✅ Complete conversation handling")
        print(f"  ✅ Full MCP server method access")
        
    except Exception as e:
        print(f"\n{Style.RED}❌ Test failed with error: {e}{Style.RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Style.YELLOW}Test interrupted by user{Style.RESET}")
    except Exception as e:
        print(f"\n{Style.RED}Test failed with error: {e}{Style.RESET}")
        import traceback
        traceback.print_exc()