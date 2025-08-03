"""
Enhanced Enterprise AI Agent Chat Demo with Conversation Memory

A simple terminal chatbot that maintains conversation history and can use all tools.
Perfect for testing and interactive tool usage.

Features:
✅ Conversation memory with intelligent limits
✅ Tool execution visibility  
✅ Chat history commands
✅ Easy setup and usage

Setup: Make sure Ollama is running with llama3.2 model
Usage: python examples/agents/simple_chat.py
"""

import asyncio
import sys
import os
import logging
import json
from datetime import datetime
from typing import Optional

# Reduce noisy tool loading logs but keep important ones
logging.getLogger("tool.research.extraction").setLevel(logging.WARNING)
logging.getLogger("newspaper.network").setLevel(logging.WARNING)
# Enable tool execution and reasoning logs so user can see activity
logging.getLogger("agent.reasoning.react").setLevel(logging.INFO)
logging.getLogger("tool.execution").setLevel(logging.INFO)
logging.getLogger("smart_tool_logger").setLevel(logging.INFO)

# Add project root for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from enterprise_ai.agent import create_agent
from enterprise_ai.schema.memory import SlidingWindowConversation, MemoryConfig


class EnhancedChatSession:
    """Enhanced chat session with conversation memory and utilities."""
    
    def __init__(self, agent_name: str = "TaskBot", max_messages: int = 20, max_tokens: int = 8000):
        """
        Initialize chat session with memory.
        
        Args:
            agent_name: Name for the agent
            max_messages: Maximum conversation messages to keep
            max_tokens: Maximum tokens to maintain in conversation
        """
        self.agent_name = agent_name
        self.agent: Optional[object] = None
        self.session_start = datetime.now()
        self.message_count = 0
        
        # Create intelligent conversation memory
        # This maintains context while preventing overflow
        self.memory = SlidingWindowConversation(
            system_prompt=None,  # Will be set by agent role
            max_messages=max_messages,  # Keep last 20 messages (10 exchanges)
            max_tokens=max_tokens,  # ~8K tokens for good context
        )
        
        print(f"💾 Memory initialized: max {max_messages} messages, {max_tokens} tokens")
    
    async def setup_agent(self, verbose: bool = True, tools: Optional[list] = None):
        """Setup the agent with memory and configuration."""
        print("📋 Setting up intelligent agent...")
        
        # Create agent with conversation memory
        self.agent = create_agent(
            name=self.agent_name,
            role_config={
                "name": "Intelligent Assistant", 
                "system_prompt": """You are an intelligent assistant that maintains conversation context and uses tools effectively.

Key behaviors:
- Remember our conversation history and refer to previous topics when relevant
- Use tools proactively to solve problems (calculate, research, create files, etc.)
- Explain your reasoning and tool usage clearly
- Be helpful, thorough, and maintain context across our conversation
- When using tools, show what you're doing step by step

Available capabilities include:
- Python code execution for calculations and data processing
- File operations (create, read, edit files)
- System commands when needed
- Research and web search (if available)
- And many more tools for comprehensive task completion

Always provide clear, helpful responses while maintaining conversation flow."""
            },
            reasoning_pattern="react",
            llm_config={
                "provider": "ollama",
                "model_name": "llama3.2",  # WORKS with tools!
                "timeout": 1000.0,
                "temperature": 0.7  # Balanced creativity
            },
            mcp_config={
                "timeout": 1000.0,
                "tools": tools  # Use specific tools if provided, otherwise load all
            },
            memory=self.memory,  # 🔑 KEY: Pass our conversation memory
            verbose=verbose
        )
        
        # Show agent information
        print(f"\n✅ INTELLIGENT AGENT READY!")
        print(f"   Name: {self.agent.name}")
        print(f"   Role: {self.agent.role.name}")
        print(f"   LLM: {self.agent.llm.__class__.__name__} using {self.agent.llm.model_name}")
        print(f"   Tools: {len(self.agent.get_available_tools())} available")
        print(f"   Memory: Smart conversation tracking enabled")
        print(f"   Reasoning: {self.agent.reasoning_pattern.__class__.__name__} with tool visibility")
        
        return self.agent
    
    async def process_message(self, user_input: str) -> str:
        """Process user message and return agent response."""
        if not self.agent:
            return "❌ Agent not initialized. Call setup_agent() first."
        
        self.message_count += 1
        
        print(f"\n🤖 {self.agent_name}: Processing your message...")
        print("-" * 50)
        
        # Process with agent (memory is handled automatically)
        response = await self.agent.process(user_input)
        
        print("-" * 50)
        return response
    
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
    
    def show_conversation_history(self, limit: int = 30):
        """Show recent conversation history."""
        if not self.memory:
            return
        
        messages = self.memory.get_messages(limit=limit * 2, include_system=False)  # *2 for user+assistant pairs
        
        print(f"\n💬 RECENT CONVERSATION HISTORY (last {limit} exchanges):")
        print("=" * 60)
        
        for i, msg in enumerate(messages):
            if msg.role == "user":
                print(f"🧑 You: {msg.content}")
            elif msg.role == "assistant":
                # Truncate long responses for readability
                content = msg.content or ""
                if len(content) > 200:
                    content = content[:200] + "... (truncated)"
                print(f"🤖 {self.agent_name}: {content}")
            print()
        print("=" * 60)
    
    def export_conversation(self, filename: Optional[str] = None) -> str:
        """Export conversation to JSON file."""
        if not self.memory:
            return "No conversation to export."
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{self.agent_name}_{timestamp}.json"
        
        messages = self.memory.get_messages()
        
        # Convert to exportable format
        conversation_data = {
            "agent_name": self.agent_name,
            "session_start": self.session_start.isoformat(),
            "export_time": datetime.now().isoformat(),
            "message_count": self.message_count,
            "total_messages": len(messages),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": getattr(msg, 'timestamp', None)
                }
                for msg in messages
            ]
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, default=str)
            return f"✅ Conversation exported to: {filename}"
        except Exception as e:
            return f"❌ Export failed: {e}"


async def main():
    """Main chat loop with enhanced features."""
    print("🤖 Enhanced Enterprise AI Agent Chat")
    print("=" * 50)
    print("🧠 Features: Conversation Memory + All Tools + Smart Context")
    print()
    
    # Initialize enhanced chat session
    chat = EnhancedChatSession(
        agent_name="TaskBot",
        max_messages=20,  # Keep last 20 messages (good context)
        max_tokens=8000   # ~8K tokens (prevents memory overflow)
    )
    
    # Setup agent
    await chat.setup_agent(verbose=True)
    
    print(f"\n💡 Try these example tasks:")
    print("   • 'Calculate the compound interest on $10,000 at 5% for 10 years'")
    print("   • 'Create a Python script that sorts a list of numbers'") 
    print("   • 'What did we discuss earlier?' (tests memory)")
    print("   • 'Remember that I prefer detailed explanations' (sets context)")
    print("   • 'Help me analyze some data' (will use tools)")
    print()
    print("🔧 Special Commands:")
    print("   /history    - Show recent conversation")
    print("   /stats      - Show conversation statistics")
    print("   /export     - Export conversation to file")
    print("   /reset      - Reset conversation but keep agent")
    print("   /clear      - Clear screen")
    print("   /quit       - Exit chat")
    print()
    print("🔍 Watch for tool usage logs during conversations!")
    print("=" * 50)
    
    while True:
        try:
            # Get user input
            user_input = input(f"\n🎯 You: ").strip()
            
            # Handle special commands
            if user_input.lower() in ['/quit', '/exit', '/q']:
                print("👋 Goodbye! Your conversation context has been preserved.")
                break
            elif user_input.lower() == '/history':
                chat.show_conversation_history()
                continue
            elif user_input.lower() == '/stats':
                chat.show_conversation_stats()
                continue
            elif user_input.lower() == '/export':
                result = chat.export_conversation()
                print(f"\n{result}")
                continue
            elif user_input.lower() == '/reset':
                chat.agent.reset()
                print(f"\n🔄 Conversation reset! Starting fresh but keeping {chat.agent_name}.")
                continue
            elif user_input.lower() == '/clear':
                os.system('clear' if os.name == 'posix' else 'cls')
                continue
            elif user_input.lower().startswith('/'):
                print("❓ Unknown command. Available: /history, /stats, /export, /reset, /clear, /quit")
                continue
                
            if not user_input:
                continue
            
            # Process with conversation memory
            response = await chat.process_message(user_input)
            
            print(f"🤖 {chat.agent_name}: {response}")
            
            # Show stats every 5 messages
            if chat.message_count % 5 == 0:
                print(f"\n💾 Memory status: {len(chat.memory.get_messages())} messages, ~{chat.memory.get_token_count()} tokens")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye! Your conversation has been preserved.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print("Make sure Ollama is running: ollama serve")


if __name__ == "__main__":
    asyncio.run(main())
