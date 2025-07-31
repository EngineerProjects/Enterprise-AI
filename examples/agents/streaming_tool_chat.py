#!/usr/bin/env python3
"""
Enterprise-AI Streaming Chat App for Tool Testing  
==================================================

Enhanced interactive chat with real-time streaming to see agent thinking.
Perfect for testing tool usage on slower devices.

Shows agent reasoning process as it happens:
- Agent thinking steps
- Tool selection and execution
- Real-time response generation
"""

import asyncio
import sys
import os
from typing import Optional

# Add parent directory to path to import enterprise_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.mcp import create_simple_mcp
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("streaming_chat_app")


class StreamingToolTestChat:
    """Interactive streaming chat app for testing agent tool usage."""
    
    def __init__(self):
        from typing import Any
        self.agent: Optional[Any] = None
        self.conversation_count = 0
        
    async def initialize_agent(self):
        """Initialize agent with all tools and high timeouts."""
        print("🔧 Initializing Agent with All Tools...")
        print("   (This may take a moment due to tool discovery)")
        
        try:
            # Create MCP with all tools and very high timeout for slow devices
            mcp = create_simple_mcp(timeout=1000.0)  # 1000 seconds
            available_tools = mcp.get_available_tools()
            
            print(f"   ✅ MCP loaded {len(available_tools)} tools")
            print(f"   🔧 Available: {', '.join(available_tools[:6])}{'...' if len(available_tools) > 6 else ''}")
            
            # Create agent optimized for slow devices
            self.agent = create_agent(
                name="ToolExplorer",
                role="Assistant", 
                reasoning_pattern="react",  # ReAct for tool usage
                mcp=mcp,
                verbose=True,  # Show detailed tool execution
                llm_config={
                    "timeout": 1000.0,  # Very high timeout
                    "model_name": "llama3.2",
                    "temperature": 0.1,  # More focused responses
                }
            )
            
            print(f"   ✅ Agent ready with {len(self.agent.get_available_tools())} tools")
            print(f"   ⚡ Streaming enabled for real-time feedback")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to initialize: {e}")
            return False
    
    def print_welcome(self):
        """Print welcome with streaming chat info."""
        print()
        print("🎉 ENTERPRISE-AI STREAMING TOOL TEST CHAT")
        print("=" * 50)
        print("💫 STREAMING MODE: See agent thinking in real-time!")
        print()
        print("🎯 GREAT QUESTIONS TO TEST TOOLS:")
        print("   📝 'Create a file with today's date and time'")
        print("   🔍 'Find all Python files in this project'") 
        print("   🧮 'Calculate the factorial of 15 using Python'")
        print("   📊 'Write a Python script that generates 10 random numbers'")
        print("   🗂️  'Show me the contents of the enterprise_ai directory'")
        print("   🐍 'Run Python code to check if 97 is a prime number'")
        print()
        print("⚡ STREAMING FEATURES:")
        print("   - Real-time response generation")
        print("   - Live tool execution feedback")
        print("   - Agent reasoning process visible")
        print()
        print("💬 COMMANDS:")
        print("   'quit'/'exit' - Stop chat")
        print("   'tools'       - List available tools")
        print("   'clear'       - Clear screen")
        print("=" * 50)
        print()
    
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_tools(self):
        """Print available tools in a nice format."""
        if not self.agent:
            print("❌ Agent not initialized")
            return
            
        tools = self.agent.get_available_tools()
        print(f"\n🛠️  AVAILABLE TOOLS ({len(tools)}):")
        
        # Group tools by category for better display
        tool_categories = {
            "File Operations": [t for t in tools if any(x in t.lower() for x in ['file', 'editor'])],
            "Code Execution": [t for t in tools if any(x in t.lower() for x in ['python', 'bash', 'execute'])],
            "Search & Discovery": [t for t in tools if any(x in t.lower() for x in ['search', 'find', 'code_search'])],
            "System Operations": [t for t in tools if any(x in t.lower() for x in ['system', 'process', 'manager'])],
            "Web & Research": [t for t in tools if any(x in t.lower() for x in ['web', 'research', 'browser'])],
            "Other Tools": []
        }
        
        # Add remaining tools to "Other"
        categorized = set()
        for category_tools in tool_categories.values():
            categorized.update(category_tools)
        
        tool_categories["Other Tools"] = [t for t in tools if t not in categorized]
        
        # Print by category
        for category, category_tools in tool_categories.items():
            if category_tools:
                print(f"\n   📂 {category}:")
                for tool in sorted(category_tools):
                    print(f"      • {tool}")
        print()
    
    async def stream_response(self, user_input: str):
        """Stream the agent response in real-time."""
        if not self.agent:
            print("❌ Agent not initialized")
            return
        
        self.conversation_count += 1
        print(f"\n🤖 AGENT (Response #{self.conversation_count}):")
        print("💭 Thinking", end="", flush=True)
        
        try:
            # Show thinking animation while processing
            thinking_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            thinking_task = asyncio.create_task(self._show_thinking_animation(thinking_chars))
            
            # Get streaming response
            full_response = ""
            async for chunk in self.agent.process_stream(user_input):
                # Stop thinking animation when response starts
                if not thinking_task.done():
                    thinking_task.cancel()
                    print("\r💭 Responding...")
                
                print(chunk, end="", flush=True)
                full_response += chunk
            
            print()  # New line after response
            
            # Show completion
            print(f"\n✅ Response completed ({len(full_response)} characters)")
            print("-" * 50)
            
        except Exception as e:
            if not thinking_task.done():
                thinking_task.cancel()
            print(f"\n❌ Error: {e}")
            print("-" * 50)
    
    async def _show_thinking_animation(self, chars):
        """Show animated thinking indicator."""
        i = 0
        try:
            while True:
                print(f"\r💭 Thinking {chars[i % len(chars)]}", end="", flush=True)
                await asyncio.sleep(0.1)
                i += 1
        except asyncio.CancelledError:
            pass
    
    async def run_chat_loop(self):
        """Run the main streaming chat loop."""
        self.print_welcome()
        
        while True:
            try:
                # Get user input with prompt
                user_input = input(f"💬 YOU: ").strip()
                
                # Handle commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Thanks for testing Enterprise-AI! Goodbye!")
                    break
                elif user_input.lower() == 'tools':
                    self.print_tools()
                    continue
                elif user_input.lower() == 'clear':
                    self.clear_screen()
                    self.print_welcome()
                    continue
                elif not user_input:
                    print("   💡 Try asking something like: 'Create a file called hello.txt'")
                    continue
                
                # Stream the response
                await self.stream_response(user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Thanks for testing Enterprise-AI!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print("   (Chat continues...)")
    
    async def run(self):
        """Run the complete streaming chat application."""
        print("🚀 STARTING ENTERPRISE-AI STREAMING TOOL TEST")
        print("=" * 50)
        
        # Initialize
        success = await self.initialize_agent()
        if not success:
            print("❌ Failed to start. Check your setup.")
            return
        
        # Run chat
        await self.run_chat_loop()


# Simple version for quick testing
async def quick_test():
    """Quick test function for rapid development."""
    print("🏃 QUICK TOOL TEST")
    print("=" * 30)
    
    # Quick initialization
    mcp = create_simple_mcp(timeout=1000.0)
    agent = create_agent("QuickTester", "Assistant", reasoning_pattern="react", mcp=mcp, verbose=True)
    
    print(f"✅ Quick agent ready with {len(agent.get_available_tools())} tools")
    
    # Test questions
    test_questions = [
        "List the files in the current directory",
        "Execute Python code to calculate 7 * 8",
        "Create a file called quicktest.txt with content 'Hello World'"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n🧪 Test {i}: {question}")
        try:
            response = await agent.process(question)
            print(f"✅ Response: {response[:200]}{'...' if len(response) > 200 else ''}")
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    """Main entry point with mode selection."""
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        # Quick test mode
        asyncio.run(quick_test())
    else:
        # Full interactive mode
        try:
            app = StreamingToolTestChat()
            asyncio.run(app.run())
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
