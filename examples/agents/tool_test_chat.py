#!/usr/bin/env python3
"""
Enterprise-AI Interactive Chat App for Tool Testing
==================================================

Interactive chat interface to test agent tool usage with real questions.
Better than trying to get LLM to list tools - ask questions that require tools!

Examples to try:
- "Create a file called test.txt with hello world content"
- "List files in the current directory"
- "Execute Python code to calculate 15 * 47"
- "Search for .py files in the enterprise_ai directory"
"""

import asyncio
import sys
import os
from typing import Any, Optional

# Add parent directory to path to import enterprise_ai
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.mcp import create_simple_mcp
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("chat_app")


class ToolTestChatApp:
    """Interactive chat app for testing agent tool usage."""
    
    def __init__(self):
        self.agent: Optional[Any] = None
        self.conversation_history = []
        
    async def initialize_agent(self):
        """Initialize agent with all tools and high timeouts."""
        print("🔧 Initializing Agent with All Tools...")
        print("   (This may take a moment due to tool discovery)")
        
        try:
            # Create MCP with all tools and high timeout for your device
            mcp = create_simple_mcp(timeout=1000.0)  # 1000 seconds timeout
            available_tools = mcp.get_available_tools()
            
            print(f"   ✅ MCP loaded {len(available_tools)} tools")
            print(f"   🔧 Available tools: {', '.join(available_tools[:8])}{'...' if len(available_tools) > 8 else ''}")
            
            # Create agent with ReAct pattern (includes tool definitions in prompts)
            self.agent = create_agent(
                name="ToolTestAssistant",
                role="Assistant", 
                reasoning_pattern="react",  # ReAct for tool usage
                mcp=mcp,
                verbose=True,  # Show tool execution details
                llm_config={
                    "timeout": 1000.0,  # High timeout for LLM on slow devices
                    "model_name": "llama3.2"  # You can change this if needed
                }
            )
            
            print(f"   ✅ Agent '{self.agent.name}' ready with {len(self.agent.get_available_tools())} tools")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to initialize agent: {e}")
            return False
    
    def print_welcome(self):
        """Print welcome message with example questions."""
        print()
        print("🎉 ENTERPRISE-AI TOOL TESTING CHAT")
        print("=" * 45)
        print("Ask questions that require tool usage to test your agent!")
        print()
        print("💡 EXAMPLE QUESTIONS TO TRY:")
        print("   📁 'Create a file called test.txt with some content'")
        print("   📋 'List all files in the current directory'") 
        print("   🐍 'Execute Python code to calculate 123 * 456'")
        print("   🔍 'Search for Python files in the enterprise_ai folder'")
        print("   📊 'Create a simple Python script that prints numbers 1-10'")
        print("   🌐 'Search the web for latest Python news' (if enabled)")
        print()
        print("💬 TYPE YOUR QUESTIONS:")
        print("   - Type 'quit', 'exit', or press Ctrl+C to stop")
        print("   - Type 'tools' to see available tools")
        print("   - Type 'history' to see conversation history")
        print("=" * 45)
        print()
    
    def print_available_tools(self):
        """Print all available tools."""
        if not self.agent:
            print("❌ Agent not initialized")
            return
            
        tools = self.agent.get_available_tools()
        print(f"\n🛠️  AVAILABLE TOOLS ({len(tools)}):")
        for i, tool in enumerate(tools, 1):
            print(f"   {i:2d}. {tool}")
        print()
    
    def print_history(self):
        """Print conversation history."""
        if not self.conversation_history:
            print("\n📜 No conversation history yet")
            return
            
        print(f"\n📜 CONVERSATION HISTORY ({len(self.conversation_history)} exchanges):")
        for i, (question, response) in enumerate(self.conversation_history, 1):
            print(f"\n--- Exchange {i} ---")
            print(f"❓ YOU: {question}")
            print(f"🤖 AGENT: {response[:200]}{'...' if len(response) > 200 else ''}")
        print()
    
    async def process_user_input(self, user_input: str) -> str:
        """Process user input and get agent response."""
        if not self.agent:
            return "❌ Agent not initialized. Please restart the app."
        
        try:
            print(f"\n🤖 Processing: '{user_input}'")
            print("   (This may take time depending on tools used)")
            
            # Get response from agent
            response = await self.agent.process(user_input)
            
            # Store in history
            self.conversation_history.append((user_input, response))
            
            return response
            
        except Exception as e:
            error_msg = f"❌ Error processing request: {e}"
            self.conversation_history.append((user_input, error_msg))
            return error_msg
    
    async def run_chat_loop(self):
        """Run the main chat loop."""
        self.print_welcome()
        
        while True:
            try:
                # Get user input
                user_input = input("💬 YOU: ").strip()
                
                # Handle special commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye! Thanks for testing Enterprise-AI tools!")
                    break
                elif user_input.lower() == 'tools':
                    self.print_available_tools()
                    continue
                elif user_input.lower() == 'history':
                    self.print_history()
                    continue
                elif not user_input:
                    print("   (Please enter a question or command)")
                    continue
                
                # Process with agent
                response = await self.process_user_input(user_input)
                
                # Display response
                print(f"\n🤖 AGENT: {response}")
                print()
                print("-" * 50)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Thanks for testing Enterprise-AI tools!")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                print("   (Continuing chat...)")
    
    async def run(self):
        """Run the complete chat application."""
        print("🚀 STARTING ENTERPRISE-AI TOOL TEST CHAT")
        print("=" * 50)
        
        # Initialize agent
        success = await self.initialize_agent()
        if not success:
            print("❌ Failed to start. Check your configuration.")
            return
        
        # Run chat loop
        await self.run_chat_loop()


def main():
    """Main entry point."""
    try:
        app = ToolTestChatApp()
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
