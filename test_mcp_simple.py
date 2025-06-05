#!/usr/bin/env python3
"""
Simple MCP test to check tool names and descriptions
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from enterprise_ai.mcp import EnterpriseMCPServer, MCPConfig
from enterprise_ai.mcp.protocols.mcp_protocol import MCPMessage, MCPMessageType


async def main():
    """Simple MCP test."""
    print("🔍 Simple MCP Tool Registration Test")
    print("=" * 40)
    
    # Initialize MCP server
    config = MCPConfig(execution_mode="auto", verbose_logging=False)
    server = EnterpriseMCPServer(config)
    server.is_running = True
    await server.session_manager.start()
    
    try:
        # List available tools
        print("\n📋 Available Tools:")
        tools = server.tool_registry.get_all_tool_classes()
        
        for i, (tool_name, tool_class) in enumerate(tools.items(), 1):
            # Try to get description from model fields
            model_fields = getattr(tool_class, 'model_fields', {})
            description = ""
            
            if 'description' in model_fields:
                description = model_fields['description'].default or ""
            
            if not description:
                description = getattr(tool_class, "description", "")
            
            if not description and tool_class.__doc__:
                description = tool_class.__doc__.strip().split('\n')[0]
            
            print(f"{i:2d}. {tool_name}")
            print(f"    Class: {tool_class.__name__}")
            print(f"    Description: {description[:80]}...")
            print()
        
        print(f"\nTotal tools: {len(tools)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await server.session_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
