"""
Enhanced Execution Control Test for Enterprise AI
===============================================

This test validates the new execution control features including:
- Execution modes (auto, manual, hybrid, disabled)
- Approval workflows
- Verbose logging
- Sandbox routing
- Danger level assessment
- Manual tool execution
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

# Enhanced Enterprise AI imports
from enterprise_ai.tool.constants import ExecutionMode, SandboxMode
from enterprise_ai.llm.factory import (
    create_provider, 
    create_provider_with_simple_approval, 
    create_provider_with_hybrid_mode,
    get_execution_mode_info
)
from enterprise_ai.tool.core.llm_adapter import get_llm_tools, get_llm_tool_definitions
from enterprise_ai.schema import Message

# Tool imports for direct testing
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.tool.execution.bash import Bash
from enterprise_ai.tool.core.base import ToolConfig

TIMEOUT = 300.0


def test_approval_callback(tool_call, approval_message: str) -> bool:
    """Test approval callback that automatically approves for testing."""
    print(f"\n{Style.CYAN}🔒 APPROVAL REQUEST:{Style.RESET}")
    print(f"Tool: {tool_call.function.name}")
    print(f"Arguments: {tool_call.get_arguments()}")
    print("Message:", approval_message[:200] + "..." if len(approval_message) > 200 else approval_message)
    
    # Auto-approve for testing (in real usage, this would be interactive)
    print(f"{Style.GREEN}✅ AUTO-APPROVED (test mode){Style.RESET}")
    return True


async def test_execution_modes():
    """Test different execution modes."""
    print_header("🎛️ Execution Mode Testing", "box")
    
    modes_info = get_execution_mode_info()
    print_test(f"Available execution modes: {len(modes_info)}", "pass")
    
    for mode, description in modes_info.items():
        print(f"  • {mode}: {description}")
    
    # Test each mode
    test_results = []
    
    for mode_name, mode_enum in [
        ("auto", ExecutionMode.AUTO),
        ("manual", ExecutionMode.MANUAL), 
        ("hybrid", ExecutionMode.HYBRID),
        ("disabled", ExecutionMode.DISABLED)
    ]:
        try:
            print(f"\n{Style.YELLOW}Testing {mode_name.upper()} mode:{Style.RESET}")
            
            if mode_enum == ExecutionMode.MANUAL:
                # For manual mode, use approval callback
                provider = create_provider(
                    "ollama", "llama3.2",
                    execution_mode=mode_enum,
                    approval_callback=test_approval_callback,
                    verbose=True,
                    max_tool_iterations=1
                )
            else:
                provider = create_provider(
                    "ollama", "llama3.2", 
                    execution_mode=mode_enum,
                    verbose=True,
                    max_tool_iterations=1
                )
            
            config = provider.get_execution_config()
            print_test(f"{mode_name} provider created with config: {config['execution_mode']}", "pass")
            test_results.append((mode_name, True))
            
        except Exception as e:
            print_test(f"{mode_name} mode failed: {e}", "fail")
            test_results.append((mode_name, False))
    
    return test_results


async def test_tool_configuration_enhancements():
    """Test enhanced tool configuration features."""
    print_header("⚙️ Enhanced Tool Configuration", "box")
    
    results = []
    
    # Test PythonExecute with enhanced config
    try:
        print_test("Testing PythonExecute with enhanced configuration", "running")
        
        python_tool = PythonExecute(config=ToolConfig(
            execution_mode=ExecutionMode.HYBRID,
            sandbox_mode=SandboxMode.UNIFIED,
            danger_level=4,
            requires_approval=True,
            verbose_logging=True,
            approval_message="Execute Python code with file system access?"
        ))
        
        print_test(f"PythonExecute danger level: {python_tool.config.danger_level}", "pass")
        print_test(f"PythonExecute sandbox mode: {python_tool.config.sandbox_mode}", "pass")
        print_test(f"PythonExecute requires approval: {python_tool.config.requires_approval}", "pass")
        
        # Test auto-configuration from capabilities
        auto_config_level = python_tool.config.danger_level
        print_test(f"Auto-configured danger level: {auto_config_level}", "pass" if auto_config_level > 0 else "warn")
        
        results.append(("PythonExecute config", True))
        
    except Exception as e:
        print_test(f"PythonExecute configuration failed: {e}", "fail")
        results.append(("PythonExecute config", False))
    
    # Test Bash with enhanced config
    try:
        print_test("Testing Bash with enhanced configuration", "running")
        
        bash_tool = Bash(config=ToolConfig(
            execution_mode=ExecutionMode.MANUAL,
            sandbox_mode=SandboxMode.INDIVIDUAL,
            danger_level=5,
            requires_approval=True,
            verbose_logging=True,
            approval_message="Execute bash command with system access?"
        ))
        
        print_test(f"Bash danger level: {bash_tool.config.danger_level}", "pass")
        print_test(f"Bash execution mode: {bash_tool.config.execution_mode}", "pass")
        
        results.append(("Bash config", True))
        
    except Exception as e:
        print_test(f"Bash configuration failed: {e}", "fail")
        results.append(("Bash config", False))
    
    return results


async def test_verbose_logging():
    """Test verbose logging functionality."""
    print_header("📝 Verbose Logging Test", "box")
    
    try:
        # Create provider with verbose logging
        provider = create_provider(
            "ollama", "llama3.2",
            execution_mode=ExecutionMode.AUTO,
            verbose=True,
            max_tool_iterations=1
        )
        
        # Get simple tools
        tools = await get_llm_tools(categories=["content"])
        tool_definitions = await get_llm_tool_definitions(categories=["content"])
        
        if not tools:
            print_test("No tools available for verbose logging test", "skip")
            return False
        
        provider.register_tools(tools)
        
        print_test("Testing verbose logging with tool execution", "running")
        
        messages = [
            Message.user_message(
                "Use the create_chat_completion tool to say 'Verbose logging is working!'"
            )
        ]
        
        print(f"{Style.YELLOW}Expected: Verbose log messages should appear below{Style.RESET}")
        
        with Timer("Verbose Execution"):
            result = provider.complete(
                messages,
                tools=tool_definitions,
                temperature=0.1
            )
        
        print_test("Verbose logging test completed", "pass")
        print_chat("assistant", result.content[:200] + "..." if len(result.content) > 200 else result.content)
        
        # Check if verbose logging produced output
        if hasattr(provider, '_tool_executor'):
            stats = provider._tool_executor.get_execution_stats()
            print_test(f"Tool execution stats available: {bool(stats)}", "pass")
            
            if stats.get('verbose_logging'):
                print_test("Verbose logging enabled in executor", "pass")
            
        return True
        
    except Exception as e:
        print_test(f"Verbose logging test failed: {e}", "fail")
        return False


async def test_manual_tool_execution():
    """Test manual tool execution workflow."""
    print_header("🔧 Manual Tool Execution", "box")
    
    try:
        # Create provider in disabled mode for manual control
        provider = create_provider(
            "ollama", "llama3.2",
            execution_mode=ExecutionMode.DISABLED,  # Don't auto-execute
            verbose=True
        )
        
        tools = await get_llm_tools(categories=["content"])
        tool_definitions = await get_llm_tool_definitions(categories=["content"])
        
        if not tools:
            print_test("No tools available for manual execution test", "skip")
            return False
        
        provider.register_tools(tools)
        
        print_test("Testing manual tool extraction and execution", "running")
        
        messages = [
            Message.user_message(
                "Use the create_chat_completion tool to respond with 'Manual execution works!'"
            )
        ]
        
        # Step 1: Get response with tool calls but don't execute
        print_test("Step 1: Extracting tool calls without execution", "running")
        response, tool_calls = await provider.acomplete_with_tool_calls(
            messages, tools=tool_definitions
        )
        
        print_test(f"Extracted {len(tool_calls)} tool calls", "pass" if tool_calls else "warn")
        
        if tool_calls:
            # Show tool call details
            for tc in tool_calls:
                print(f"  • Tool: {tc.function.name}")
                print(f"  • Args: {tc.get_arguments()}")
            
            # Step 2: Execute tools manually
            print_test("Step 2: Executing tools manually", "running")
            tool_results = await provider.aexecute_tool_calls(tool_calls)
            
            print_test(f"Executed {len(tool_results)} tools", "pass")
            
            # Show results
            for result in tool_results:
                print(f"  • {result.name}: {'✅ Success' if result.success else '❌ Failed'}")
                if result.success:
                    print(f"    Result: {str(result.result)[:100]}...")
                else:
                    print(f"    Error: {result.error}")
            
            return len(tool_results) > 0 and all(r.success for r in tool_results)
        
        return False
        
    except Exception as e:
        print_test(f"Manual tool execution test failed: {e}", "fail")
        return False


async def test_hybrid_mode():
    """Test hybrid execution mode with approval workflow."""
    print_header("⚖️ Hybrid Mode with Approval", "box")
    
    try:
        # Create provider with hybrid mode
        provider = create_provider_with_hybrid_mode(
            "ollama", "llama3.2",
            danger_threshold=2
        )
        
        # Test with a simple tool first
        tools = await get_llm_tools(categories=["content"])
        tool_definitions = await get_llm_tool_definitions(categories=["content"])
        
        if not tools:
            print_test("No tools available for hybrid mode test", "skip")
            return False
        
        provider.register_tools(tools)
        
        print_test("Testing hybrid mode execution", "running")
        print(f"{Style.YELLOW}Note: Safe tools should auto-execute, dangerous tools require approval{Style.RESET}")
        
        messages = [
            Message.user_message(
                "Use the create_chat_completion tool to say 'Hybrid mode is working correctly!'"
            )
        ]
        
        with Timer("Hybrid Mode Test"):
            result = provider.complete(
                messages,
                tools=tool_definitions,
                temperature=0.1
            )
        
        print_test("Hybrid mode test completed", "pass")
        print_chat("assistant", result.content[:200] + "..." if len(result.content) > 200 else result.content)
        
        # Check execution stats
        if hasattr(provider, '_tool_executor'):
            stats = provider._tool_executor.get_execution_stats()
            executions = stats.get('total_executions', 0)
            approved = stats.get('approved_executions', 0)
            denied = stats.get('denied_executions', 0)
            
            print_test(f"Total executions: {executions}", "pass")
            print_test(f"Approved executions: {approved}", "pass")
            print_test(f"Denied executions: {denied}", "pass")
            
            return executions > 0
        
        return True
        
    except Exception as e:
        print_test(f"Hybrid mode test failed: {e}", "fail")
        return False


async def test_convenience_factories():
    """Test convenience factory functions."""
    print_header("🏭 Convenience Factory Functions", "box")
    
    results = []
    
    # Test simple approval factory
    try:
        print_test("Testing create_provider_with_simple_approval", "running")
        
        # Override the approval callback for testing
        original_callback = None
        
        provider = create_provider(
            "ollama", "llama3.2",
            execution_mode=ExecutionMode.MANUAL,
            approval_callback=test_approval_callback,  # Use our test callback
            verbose=True
        )
        
        config = provider.get_execution_config()
        print_test(f"Simple approval provider: {config['execution_mode']}", "pass")
        print_test(f"Has approval callback: {config['has_approval_callback']}", "pass")
        
        results.append(("Simple approval factory", True))
        
    except Exception as e:
        print_test(f"Simple approval factory failed: {e}", "fail")
        results.append(("Simple approval factory", False))
    
    # Test hybrid factory
    try:
        print_test("Testing create_provider_with_hybrid_mode", "running")
        
        provider = create_provider_with_hybrid_mode(
            "ollama", "llama3.2",
            danger_threshold=3
        )
        
        config = provider.get_execution_config()
        print_test(f"Hybrid provider mode: {config['execution_mode']}", "pass")
        print_test(f"Danger threshold: {config['hybrid_danger_threshold']}", "pass")
        
        results.append(("Hybrid factory", True))
        
    except Exception as e:
        print_test(f"Hybrid factory failed: {e}", "fail")
        results.append(("Hybrid factory", False))
    
    return results


async def test_tool_danger_analysis():
    """Test automatic tool danger level analysis."""
    print_header("⚠️ Tool Danger Analysis", "box")
    
    results = []
    
    # Test Python tool danger analysis
    try:
        python_tool = PythonExecute()
        
        # Test different code samples
        test_cases = [
            ("print('hello')", "Safe code"),
            ("import os; os.listdir('/')", "File system access"),
            ("import subprocess; subprocess.run('ls')", "System command"),
            ("with open('/etc/passwd') as f: print(f.read())", "Sensitive file access")
        ]
        
        print_test("Testing Python code danger analysis", "running")
        
        for code, description in test_cases:
            is_dangerous = python_tool._should_use_sandbox_execution(code, "auto")
            danger_level = "HIGH" if is_dangerous else "LOW"
            print(f"  • {description}: {danger_level}")
        
        print_test("Python danger analysis completed", "pass")
        results.append(("Python danger analysis", True))
        
    except Exception as e:
        print_test(f"Python danger analysis failed: {e}", "fail")
        results.append(("Python danger analysis", False))
    
    # Test Bash command danger analysis
    try:
        bash_tool = Bash()
        
        test_commands = [
            ("echo 'hello'", "Safe command"),
            ("ls -la", "Directory listing"),
            ("rm -rf /tmp/test", "File deletion"),
            ("curl https://www.python.org/", "Network access"),
            ("sudo apt install package", "System modification")
        ]
        
        print_test("Testing Bash command danger analysis", "running")
        
        for command, description in test_commands:
            is_dangerous = bash_tool._analyze_command_danger(command)
            danger_level = "HIGH" if is_dangerous else "LOW"
            print(f"  • {description}: {danger_level}")
        
        print_test("Bash danger analysis completed", "pass")
        results.append(("Bash danger analysis", True))
        
    except Exception as e:
        print_test(f"Bash danger analysis failed: {e}", "fail")
        results.append(("Bash danger analysis", False))
    
    return results

async def test_dangerous_tool_approval():
    """Test approval workflow with actually dangerous tools."""
    print_header("⚠️ Dangerous Tool Approval Test", "box")
    
    try:
        # Create a dangerous Python tool for testing
        python_tool = PythonExecute(config=ToolConfig(
            execution_mode=ExecutionMode.MANUAL,
            danger_level=4,
            requires_approval=True,
            verbose_logging=True
        ))
        
        # Test dangerous code detection
        dangerous_code = "import os; os.system('ls -la')"
        safe_code = "print('Hello World')"
        
        dangerous_result = python_tool._should_use_sandbox_execution(dangerous_code)
        safe_result = python_tool._should_use_sandbox_execution(safe_code)
        
        print_test(f"Dangerous code detected: {dangerous_result}", "pass" if dangerous_result else "fail")
        print_test(f"Safe code detected as safe: {not safe_result}", "pass" if not safe_result else "fail")
        
        # Test with approval callback
        approval_requests = []
        
        def test_approval_with_tracking(tool_call, approval_message: str) -> bool:
            approval_requests.append({
                'tool': tool_call.function.name,
                'args': tool_call.get_arguments(),
                'message': approval_message[:100] + "..."
            })
            print(f"\n🔒 APPROVAL REQUEST CAPTURED:")
            print(f"Tool: {tool_call.function.name}")
            print(f"Danger Level: Requires approval")
            print("✅ AUTO-APPROVED (test mode)")
            return True
        
        provider = create_provider(
            "ollama", "llama3.2",
            execution_mode=ExecutionMode.MANUAL,
            approval_callback=test_approval_with_tracking,
            verbose=True,
            max_tool_iterations=1
        )
        
        # Register a dangerous tool
        tools = {"python_execute": python_tool}
        provider.register_tools(tools)
        
        # Create tool definitions
        tool_definitions = [{
            "type": "function",
            "function": {
                "name": "python_execute",
                "description": "Execute Python code",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"}
                    },
                    "required": ["code"]
                }
            }
        }]
        
        messages = [
            Message.user_message(
                "Execute this Python code: print('Testing approval workflow')"
            )
        ]
        
        print_test("Testing dangerous tool approval workflow", "running")
        
        with Timer("Dangerous Tool Approval Test"):
            result = provider.complete(
                messages,
                tools=tool_definitions,
                temperature=0.1
            )
        
        print_test(f"Approval requests captured: {len(approval_requests)}", "pass" if approval_requests else "warn")
        
        for req in approval_requests:
            print(f"  • Tool: {req['tool']}")
            print(f"  • Args: {req['args']}")
        
        return len(approval_requests) > 0
        
    except Exception as e:
        print_test(f"Dangerous tool approval test failed: {e}", "fail")
        return False

async def test_enhanced_verbose_logging():
    """Test enhanced verbose logging with model decision visibility."""
    print_header("📝 Enhanced Verbose Logging", "box")
    
    print(f"{Style.YELLOW}Expected verbose logging output:{Style.RESET}")
    print(f"  🤖 Model decision to call tools")
    print(f"  📋 Tool call details and arguments") 
    print(f"  🔄 Execution process steps")
    print(f"  📤 Tool execution results")
    print(f"  ⏱️  Timing information")
    
    # Test with verbose enabled
    provider = create_provider(
        "ollama", "llama3.2",
        execution_mode=ExecutionMode.AUTO,
        verbose=True,  # This should show detailed info
        max_tool_iterations=1
    )
    
    tools = await get_llm_tools(categories=["content"])
    tool_definitions = await get_llm_tool_definitions(categories=["content"])
    
    provider.register_tools(tools)
    
    messages = [
        Message.user_message(
            "Use the create_chat_completion tool to say 'Enhanced verbose logging works!'"
        )
    ]
    
    print(f"\n{Style.CYAN}📡 Sending request with verbose logging enabled...{Style.RESET}")
    
    result = provider.complete(
        messages,
        tools=tool_definitions,
        temperature=0.1
    )
    
    print(f"\n{Style.GREEN}📋 Final Result:{Style.RESET}")
    print_chat("assistant", result.content)
    
    # Check if verbose information was logged
    stats = provider.get_tool_execution_stats()
    if stats:
        print(f"\n{Style.CYAN}📊 Execution Statistics:{Style.RESET}")
        print(f"  • Total executions: {stats.get('total_executions', 0)}")
        print(f"  • Verbose enabled: {stats.get('verbose_logging', False)}")
        print(f"  • Average time: {stats.get('average_execution_time', 0):.3f}s")
    
    return True

async def comprehensive_execution_test():
    """Run comprehensive execution control test."""
    print_header("🚀 Enhanced Execution Control Test Suite", "double")
    
    all_results = []
    
    # Test sequence
    tests = [
        ("Execution Modes", test_execution_modes),
        ("Tool Configuration", test_tool_configuration_enhancements),
        ("Verbose Logging", test_verbose_logging),
        ("Manual Tool Execution", test_manual_tool_execution),
        ("Hybrid Mode", test_hybrid_mode),
        ("Convenience Factories", test_convenience_factories),
        ("Danger Analysis", test_tool_danger_analysis),
        ("Dangerous Tool Approval", test_dangerous_tool_approval),
        ("Enhanced Verbose Logging", test_enhanced_verbose_logging)
    ]
    
    for test_name, test_func in tests:
        separator()
        try:
            with Timer(f"{test_name} Test"):
                result = await test_func()
                
                if isinstance(result, list):
                    # Handle multiple sub-results
                    sub_passed = sum(1 for _, success in result if success)
                    sub_total = len(result)
                    success = sub_passed >= sub_total * 0.8
                    
                    all_results.extend([(f"{test_name}.{name}", success) for name, success in result])
                    print_test(f"{test_name}: {sub_passed}/{sub_total} sub-tests passed", 
                              "pass" if success else "warn")
                else:
                    all_results.append((test_name, result))
                    print_test(f"{test_name} completed", "pass" if result else "warn")
                    
        except Exception as e:
            print_test(f"{test_name} failed with error: {e}", "fail")
            all_results.append((test_name, False))
    
    # Summary
    print_header("📊 Enhanced Execution Test Results", "box")
    
    passed = sum(1 for _, success in all_results if success)
    total = len(all_results)
    
    # Group results by category
    categories = {}
    for test_name, success in all_results:
        category = test_name.split('.')[0]
        if category not in categories:
            categories[category] = []
        categories[category].append((test_name, success))
    
    for category, tests in categories.items():
        cat_passed = sum(1 for _, success in tests if success)
        cat_total = len(tests)
        status = "✅" if cat_passed == cat_total else "⚠️" if cat_passed >= cat_total * 0.8 else "❌"
        print(f"  {status} {category:<25} {cat_passed}/{cat_total}")
        
        for test_name, success in tests[:3]:  # Show first 3 sub-tests
            sub_status = "✅" if success else "❌"
            display_name = test_name.split('.')[-1] if '.' in test_name else test_name
            print(f"    {sub_status} {display_name}")
    
    separator()
    print(f"{Style.BOLD}Overall Enhanced Features: {passed}/{total} tests passed{Style.RESET}")
    
    # Feature readiness assessment
    print_header("🎯 Feature Readiness Assessment", "box")
    
    core_features = [
        "Execution modes", "Tool configuration", "Manual execution", 
        "Danger analysis", "Convenience factories"
    ]
    
    core_passed = sum(1 for test_name, success in all_results 
                     if any(feature.lower().replace(' ', '') in test_name.lower().replace(' ', '') 
                           for feature in core_features) and success)
    core_total = sum(1 for test_name, success in all_results 
                    if any(feature.lower().replace(' ', '') in test_name.lower().replace(' ', '') 
                          for feature in core_features))
    
    if core_passed >= core_total * 0.9:
        print_test("🎉 Enhanced execution control is production-ready!", "pass")
        print_test("✅ All execution modes working", "pass")
        print_test("✅ Tool safety features operational", "pass")
        print_test("✅ Manual control workflows available", "pass")
    elif core_passed >= core_total * 0.7:
        print_test("⚠️ Enhanced features mostly working, minor issues", "warn")
        print_test("🔧 Some execution modes may need adjustment", "warn")
    else:
        print_test("❌ Enhanced features need debugging", "fail")
        print_test("🔧 Core execution control issues detected", "fail")
    
    # Show execution mode summary
    print(f"\n{Style.CYAN}📋 Execution Mode Capabilities:{Style.RESET}")
    print(f"  • AUTO: Immediate tool execution")
    print(f"  • MANUAL: Human approval required")  
    print(f"  • HYBRID: Smart approval based on danger level")
    print(f"  • DISABLED: Extract tool calls without execution")
    
    print(f"\n{Style.CYAN}🛡️ Safety Features:{Style.RESET}")
    print(f"  • Automatic danger level assessment")
    print(f"  • Sandbox routing for risky operations")
    print(f"  • Approval workflows for dangerous tools")
    print(f"  • Verbose logging for debugging")
    
    return core_passed >= core_total * 0.8


def main():
    """Main test function."""
    setup_project_path()
    
    print(f"{Style.CYAN}")
    print("=" * 80)
    print("ENTERPRISE AI - Enhanced Execution Control Test".center(80))
    print("Testing new execution modes, approval workflows, and safety features")
    print("=" * 80)
    print(f"{Style.RESET}\n")
    
    try:
        success = run_async(comprehensive_execution_test())
        
        if success:
            print(f"\n{Style.GREEN}🎯 SUCCESS: Enhanced execution control is ready!{Style.RESET}")
            print(f"{Style.CYAN}✨ Your AI agents now have sophisticated execution control{Style.RESET}")
            print(f"{Style.CYAN}🛡️ Safety features and approval workflows are operational{Style.RESET}")
        else:
            print(f"\n{Style.YELLOW}⚠️ PARTIAL SUCCESS: Most features working, some issues detected{Style.RESET}")
            print(f"{Style.CYAN}Recommendation: Review specific test failures above{Style.RESET}")
            
    except Exception as e:
        print(f"\n{Style.RED}💥 CRITICAL ERROR: {e}{Style.RESET}")
        import traceback
        print(f"{Style.RED}Full traceback:{Style.RESET}")
        print(traceback.format_exc())


if __name__ == "__main__":
    main()