#!/usr/bin/env python3
"""
Quick test to verify Enterprise AI demo components work correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from enterprise_ai.schema.message import Message
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.config import MCPConfig
from enterprise_ai.mcp.server import EnterpriseMCPServer

async def test_basic_components():
    """Test basic component initialization."""
    
    print("🧪 Testing Enterprise AI Components")
    print("=" * 50)
    
    # Test Message creation
    print("1. Testing Message creation...")
    try:
        msg = Message.user_message("Hello, this is a test message")
        print(f"   ✅ Message created: {msg.role} - {msg.content[:30]}...")
        
        # Test message attributes
        assert hasattr(msg, 'role'), "Message should have role attribute"
        assert hasattr(msg, 'content'), "Message should have content attribute"
        print("   ✅ Message attributes verified")
        
    except Exception as e:
        print(f"   ❌ Message creation failed: {e}")
        return False
    
    # Test MCP Config
    print("2. Testing MCP Configuration...")
    try:
        config = MCPConfig(execution_mode="auto", verbose_logging=True)
        print(f"   ✅ MCP Config created: {config.execution_mode}")
    except Exception as e:
        print(f"   ❌ MCP Config failed: {e}")
        return False
    
    # Test MCP Server
    print("3. Testing MCP Server...")
    try:
        mcp_server = EnterpriseMCPServer(config)
        print("   ✅ MCP Server created successfully")
    except Exception as e:
        print(f"   ❌ MCP Server failed: {e}")
        return False
    
    # Test LLM Provider
    print("4. Testing LLM Provider creation...")
    try:
        llm = create_provider("ollama", "llama3.2", timeout=60, verbose=True)
        print(f"   ✅ LLM Provider created: {llm.model_name}")
        
        # Test simple completion with Message objects
        print("5. Testing LLM completion with proper messages...")
        messages = [Message.user_message("Say hello in a friendly way")]
        
        response = await llm.acomplete(messages)
        print(f"   ✅ LLM responded: {response.content[:50]}...")
        
    except Exception as e:
        print(f"   ❌ LLM Provider test failed: {e}")
        print(f"   💡 This might be expected if Ollama is not running")
        return False
    
    print("\n🎉 All basic components work correctly!")
    return True

if __name__ == "__main__":
    print("Enterprise AI Basic Component Test")
    print("Make sure Ollama is running locally before this test")
    print()
    
    try:
        result = asyncio.run(test_basic_components())
        if result:
            print("\n✅ Ready to run the full demo!")
        else:
            print("\n❌ Some components failed. Check your setup.")
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
