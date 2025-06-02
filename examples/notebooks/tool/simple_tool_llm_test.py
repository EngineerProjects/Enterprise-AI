"""Updated Simple Tool-LLM Integration Test"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.notebooks.utils import setup_project_path, print_header, print_test, print_chat, Timer, run_async, Style
from enterprise_ai.llm import create_provider
from enterprise_ai.tool.core.llm_adapter import get_llm_tools, get_llm_tool_definitions
from enterprise_ai.schema import Message

async def simple_test():
    print_header("🔧 Working Tool-LLM Test", "box")
    
    try:
        # Get tools as functions (like your working test)
        tools = await get_llm_tools(categories=["content"])
        tool_definitions = await get_llm_tool_definitions(categories=["content"])
        print_test(f"Loaded {len(tools)} tools", "pass" if tools else "fail")
        
        # Create provider with AUTO execution (like your working test)
        provider = create_provider(
            provider_name="ollama",
            model_name="llama3.2",
            tool_execute="auto",  # ← KEY: Enable auto execution
            max_tool_iterations=3,
            timeout=1200.0
        )
        
        # Register tools directly with provider (like your working test)
        provider.register_tools(tools)  # ← Direct registration
        print_test("Tools registered with provider", "pass")
        
        # Test with explicit tool call request
        messages = [Message.user_message(
            "You must use the create_chat_completion tool to generate the response "
            "'Enterprise AI tools are working correctly!' - actually call the tool, don't just describe it."
        )]
        
        print_chat("user", "Testing LLM tool integration...")
        
        # Use provider.complete (like your working test)
        result = provider.complete(
            messages,
            tools=tool_definitions,
            temperature=0.1
        )
        
        print_test("LLM completion successful", "pass")
        print_chat("assistant", result.content, model="llama3.2")
        
        # Check if tools were actually executed
        if hasattr(provider, '_tool_executor') and provider._tool_executor:
            stats = provider._tool_executor.get_execution_stats()
            executions = stats.get('total_executions', 0)
            if executions > 0:
                print_test(f"✅ Tools actually executed: {executions}", "pass")
                return True
            else:
                print_test("⚠️ No tools executed", "warn")
                return False
        
        return True
        
    except Exception as e:
        print_test(f"Test failed: {e}", "fail")
        return False

def main():
    setup_project_path()
    print_header("🚀 Enterprise AI Working Tool Test", "double")
    success = run_async(simple_test())
    print(f"\n{Style.GREEN if success else Style.RED}{'✅ SUCCESS' if success else '❌ FAILED'}{Style.RESET}")

if __name__ == "__main__":
    main()