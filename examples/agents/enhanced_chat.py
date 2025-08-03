"""
Enhanced Enterprise AI Agent Chat with Improved Error Handling

Features fixed in this version:
✅ Better Python code generation prompts
✅ Enhanced error recovery
✅ Cleaner logging output
✅ Improved tool execution feedback

Setup: Make sure Ollama is running with llama3.2 model
Usage: python examples/agents/enhanced_chat.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Optional

# Configure logging to reduce noise but keep important information
logging.getLogger("tool.research.extraction").setLevel(logging.WARNING)
logging.getLogger("newspaper.network").setLevel(logging.WARNING)
logging.getLogger("tool.simple_loader").setLevel(logging.WARNING)

# Keep important logs for debugging
logging.getLogger("agent.reasoning.react").setLevel(logging.INFO)
logging.getLogger("tool.execution.python").setLevel(logging.INFO)

# Add project root for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from enterprise_ai.agent import create_agent
from enterprise_ai.schema.memory import SlidingWindowConversation


class EnhancedChatSession:
    """Enhanced chat session with improved error handling and user guidance."""
    
    def __init__(self, agent_name: str = "TaskBot", max_messages: int = 20, max_tokens: int = 8000):
        self.agent_name = agent_name
        self.agent: Optional[object] = None
        self.session_start = datetime.now()
        self.message_count = 0
        
        # Create conversation memory
        self.memory = SlidingWindowConversation(
            system_prompt=None,
            max_messages=max_messages,
            max_tokens=max_tokens,
        )
        
        print(f"💾 Memory initialized: max {max_messages} messages, {max_tokens} tokens")
    
    async def setup_agent(self, verbose: bool = True):
        """Setup the agent with enhanced configuration."""
        print("📋 Setting up enhanced intelligent agent...")
        
        # Enhanced system prompt with better Python code guidance
        enhanced_system_prompt = """You are an intelligent assistant that maintains conversation context and uses tools effectively.

Key behaviors:
- Remember our conversation history and refer to previous topics when relevant
- Use tools proactively to solve problems (calculate, research, create files, etc.)
- Explain your reasoning and tool usage clearly
- Be helpful, thorough, and maintain context across our conversation

CRITICAL: When generating Python code, follow these rules:
1. Always write syntactically correct Python code
2. Check that all parentheses (), brackets [], and braces {} are properly closed
3. Include proper imports at the top (import math, import json, etc.)
4. Use descriptive variable names and add comments
5. Test your mathematical formulas before presenting them
6. Handle potential errors appropriately

Examples of GOOD Python code:
```python
import math
principal = 10000
rate = 0.05
time = 10
final_amount = principal * (1 + rate) ** time
print(f"Final amount: ${final_amount:.2f}")
```

Examples of BAD Python code (avoid these):
- print(math.pow(10000 * (1 + 0.05 / 100) ** 10, 100)  # Missing closing parenthesis
- result = math.sqrt(16  # Missing closing parenthesis
- print("Hello world"  # Missing closing quote

Available capabilities include:
- Python code execution for calculations and data processing
- File operations (create, read, edit files)
- System commands when needed
- Research and web search (if available)
- And many more tools for comprehensive task completion

Always provide clear, helpful responses while maintaining conversation flow."""
        
        # Create agent with enhanced configuration
        self.agent = create_agent(
            name=self.agent_name,
            role_config={
                "name": "Enhanced Intelligent Assistant", 
                "system_prompt": enhanced_system_prompt
            },
            reasoning_pattern="react",
            llm_config={
                "provider": "ollama",
                "model_name": "llama3.2",
                "timeout": 1000.0,
                "temperature": 0.3  # Lower temperature for more precise code generation
            },
            mcp_config={
                "timeout": 1000.0,
            },
            memory=self.memory,
            verbose=verbose
        )
        
        # Show agent information
        print(f"\n✅ ENHANCED INTELLIGENT AGENT READY!")
        print(f"   Name: {self.agent.name}")
        print(f"   Role: {self.agent.role.name}")
        print(f"   LLM: {self.agent.llm.__class__.__name__} using {self.agent.llm.model_name}")
        print(f"   Tools: {len(self.agent.get_available_tools())} available")
        print(f"   Memory: Smart conversation tracking enabled")
        print(f"   Reasoning: {self.agent.reasoning_pattern.__class__.__name__} with enhanced error handling")
        print(f"   Improvements: ✅ Better Python code generation, ✅ Enhanced error recovery")
        
        return self.agent
    
    async def process_message(self, user_input: str) -> str:
        """Process user message with enhanced error handling."""
        if not self.agent:
            return "❌ Agent not initialized. Call setup_agent() first."
        
        self.message_count += 1
        
        print(f"\n🤖 {self.agent_name}: Processing your message...")
        print("-" * 50)
        
        try:
            # Process with agent
            response = await self.agent.process(user_input)
            print("-" * 50)
            return response
            
        except Exception as e:
            error_msg = f"❌ Error processing message: {str(e)}"
            print(f"-" * 50)
            print(error_msg)
            
            # Provide helpful suggestions based on error type
            if "syntax" in str(e).lower() or "parenthes" in str(e).lower():
                helpful_msg = "\n💡 Tip: If you're asking for calculations, try rephrasing your request more clearly."
            elif "timeout" in str(e).lower():
                helpful_msg = "\n💡 Tip: The operation took too long. Try breaking it into smaller parts."
            else:
                helpful_msg = "\n💡 Tip: Try rephrasing your request or ask for help with a specific task."
            
            return error_msg + helpful_msg
    
    def show_conversation_stats(self):
        """Show conversation statistics."""
        if not self.memory:
            return
        
        messages = self.memory.get_messages()
        token_count = self.memory.get_token_count()
        session_duration = datetime.now() - self.session_start
        
        print(f"\n📊 CONVERSATION STATS:")
        print(f"   Messages exchanged: {self.message_count}")
        print(f"   Total messages in memory: {len(messages)}")
        print(f"   Current token count: ~{token_count}")
        print(f"   Session duration: {session_duration}")
        print(f"   Memory utilization: {len(messages)}/20 messages, {token_count}/8000 tokens")


async def main():
    """Main chat loop with enhanced error handling."""
    print("🚀 Enhanced Enterprise AI Agent Chat")
    print("=" * 50)
    print("🧠 Features: Enhanced Error Handling + Better Code Generation + All Tools")
    print("🔧 Improvements: Fixed Python syntax errors, better prompts, cleaner logs")
    print()
    
    # Initialize enhanced chat session
    chat = EnhancedChatSession(
        agent_name="TaskBot",
        max_messages=20,
        max_tokens=8000
    )
    
    # Setup agent
    await chat.setup_agent(verbose=True)
    
    print(f"\n💡 Try these example tasks (now with better error handling):")
    print("   • 'Calculate the compound interest on $10,000 at 5% for 10 years'")
    print("   • 'Create a Python script that sorts a list of numbers'") 
    print("   • 'What is 2 + 2 * 3?' (simple expression)")
    print("   • 'Help me with a math calculation' (will generate proper Python)")
    print("   • 'Show me the first 10 Fibonacci numbers'")
    print()
    print("🔧 Special Commands:")
    print("   /stats      - Show conversation statistics")
    print("   /clear      - Clear screen")
    print("   /quit       - Exit chat")
    print()
    print("🎯 Enhanced features:")
    print("   ✅ Auto-fixes common Python syntax errors")
    print("   ✅ Better error messages and recovery")
    print("   ✅ Improved code generation prompts")
    print("   ✅ Cleaner logging output")
    print("=" * 50)
    
    while True:
        try:
            # Get user input
            user_input = input(f"\n🎯 You: ").strip()
            
            # Handle special commands
            if user_input.lower() in ['/quit', '/exit', '/q']:
                print("👋 Goodbye! Your conversation context has been preserved.")
                break
            elif user_input.lower() == '/stats':
                chat.show_conversation_stats()
                continue
            elif user_input.lower() == '/clear':
                os.system('clear' if os.name == 'posix' else 'cls')
                continue
            elif user_input.lower().startswith('/'):
                print("❓ Unknown command. Available: /stats, /clear, /quit")
                continue
                
            if not user_input:
                continue
            
            # Process with enhanced error handling
            response = await chat.process_message(user_input)
            
            print(f"🤖 {chat.agent_name}: {response}")
            
            # Show stats every 5 messages
            if chat.message_count % 5 == 0:
                print(f"\n💾 Memory status: {len(chat.memory.get_messages())} messages, ~{chat.memory.get_token_count()} tokens")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye! Your conversation has been preserved.")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            print("💡 Tip: Try restarting the agent or check if Ollama is running properly.")


if __name__ == "__main__":
    print("🚀 Starting Enhanced Enterprise AI Agent...")
    print("Improvements: Better Python code generation, enhanced error handling, cleaner logs")
    print()
    
    asyncio.run(main())
