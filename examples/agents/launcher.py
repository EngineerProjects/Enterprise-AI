#!/usr/bin/env python3
"""
Enterprise-AI Tool Testing Launcher
===================================

Choose the best tool testing mode for your device and needs.
"""

import sys
import os
import subprocess
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def print_banner():
    """Print the main banner."""
    print("🚀 ENTERPRISE-AI TOOL TESTING LAUNCHER")
    print("=" * 50)
    print("Choose your testing mode:")
    print()


def print_options():
    """Print available testing options."""
    print("🎯 AVAILABLE MODES:")
    print()
    print("1. 📝 STREAMING CHAT (Recommended)")
    print("   • Real-time agent responses")
    print("   • See tool usage as it happens")
    print("   • Perfect for interactive testing")
    print("   • Best for slow devices")
    print()
    print("2. 💬 SIMPLE CHAT")
    print("   • Basic question/answer format")
    print("   • Shows full responses at once")
    print("   • Good for quick testing")
    print()
    print("3. ⚡ QUICK TEST")
    print("   • Automated tool testing")
    print("   • Runs 3 predefined tests")
    print("   • Fast validation")
    print()
    print("4. 🧪 INTEGRATION TEST")
    print("   • API-level validation")
    print("   • No LLM interaction")
    print("   • Fastest option")
    print()


def get_user_choice():
    """Get user's choice."""
    while True:
        try:
            choice = input("💬 Enter your choice (1-4) or 'q' to quit: ").strip().lower()
            
            if choice == 'q' or choice == 'quit':
                return None
            elif choice in ['1', '2', '3', '4']:
                return int(choice)
            else:
                print("   ❌ Please enter 1, 2, 3, 4, or 'q'")
        except KeyboardInterrupt:
            return None


async def run_streaming_chat():
    """Run the streaming chat app."""
    print("\n🚀 Starting Streaming Tool Test Chat...")
    print("   (Best for interactive testing)")
    print()
    
    try:
        from streaming_tool_chat import StreamingToolTestChat
        app = StreamingToolTestChat()
        await app.run()
    except ImportError:
        print("❌ Streaming chat not available. Running with subprocess...")
        subprocess.run([sys.executable, "streaming_tool_chat.py"])


async def run_simple_chat():
    """Run the simple chat app."""
    print("\n🚀 Starting Simple Tool Test Chat...")
    print()
    
    try:
        from tool_test_chat import ToolTestChatApp
        app = ToolTestChatApp()
        await app.run()
    except ImportError:
        print("❌ Simple chat not available. Running with subprocess...")
        subprocess.run([sys.executable, "tool_test_chat.py"])


async def run_quick_test():
    """Run quick automated tests."""
    print("\n🚀 Running Quick Tool Tests...")
    print("   (3 automated tests)")
    print()
    
    try:
        from streaming_tool_chat import quick_test
        await quick_test()
    except ImportError:
        print("❌ Quick test not available. Running with subprocess...")
        subprocess.run([sys.executable, "streaming_tool_chat.py", "quick"])


def run_integration_test():
    """Run integration tests."""
    print("\n🚀 Running Integration Tests...")
    print("   (API-level validation)")
    print()
    
    try:
        subprocess.run([sys.executable, "final_mcp_integration_test.py"])
    except Exception as e:
        print(f"❌ Integration test failed: {e}")


def print_tips():
    """Print helpful tips."""
    print("\n💡 HELPFUL TIPS:")
    print("   • For slow devices: Use Streaming Chat (option 1)")
    print("   • To test specific tools: Ask targeted questions")
    print("   • All modes use 1000s timeouts for slow devices")
    print("   • Press Ctrl+C to interrupt any mode")
    print()
    print("🎯 EXAMPLE QUESTIONS TO TRY:")
    print("   'Create a file called test.txt'")
    print("   'List files in the current directory'") 
    print("   'Calculate 123 * 456 using Python'")
    print("   'Find Python files in enterprise_ai folder'")
    print()


async def main():
    """Main launcher function."""
    print_banner()
    print_options()
    print_tips()
    
    while True:
        choice = get_user_choice()
        
        if choice is None:
            print("\n👋 Goodbye!")
            break
        
        try:
            if choice == 1:
                await run_streaming_chat()
            elif choice == 2:
                await run_simple_chat()
            elif choice == 3:
                await run_quick_test()
            elif choice == 4:
                run_integration_test()
            
            # Ask if they want to try another mode
            print("\n" + "=" * 50)
            continue_choice = input("🔄 Try another mode? (y/n): ").strip().lower()
            if continue_choice not in ['y', 'yes']:
                print("\n👋 Thanks for testing Enterprise-AI!")
                break
                
        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error running mode: {e}")
            print("   Try another option or check your setup.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Launcher error: {e}")
