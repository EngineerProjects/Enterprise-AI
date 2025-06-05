#!/usr/bin/env python3
"""
Simple Agent Demo - Shows how to create and use Enterprise AI agents

This demonstrates:
1. Agent creation with MCP integration
2. Basic reasoning and tool usage
3. Task execution with results
"""

import asyncio
import sys
from pathlib import Path

# Setup project path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from examples.notebooks.utils import Style, print_header, print_test, print_chat, separator
from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.mcp import EnterpriseMCPServer, MCPConfig
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("agent.demo")


class SimpleAgent(BaseAgent):
    """
    A simple demonstration agent that can perform basic tasks.
    
    This agent can:
    - Execute Python code
    - Run bash commands
    - Search the web
    - Manage files
    """
    
    def __init__(self, name: str, mcp_server):
        # For demo, we'll use a simple LLM provider placeholder
        super().__init__(name, None, mcp_server)
        
        # Available tools for this agent
        self.tools = [
            "python_execute",
            "bash", 
            "filesystem",
            "web_search",
            "configuration"
        ]
    
    async def think(self, input_text: str) -> str:
        """
        Simple reasoning process.
        In a real implementation, this would use an LLM.
        """
        # For demo purposes, use rule-based reasoning
        input_lower = input_text.lower()
        
        if "python" in input_lower or "code" in input_lower:
            return f"I need to execute Python code for: {input_text}"
        elif "file" in input_lower or "directory" in input_lower or "folder" in input_lower:
            return f"I need to perform file operations for: {input_text}"
        elif "search" in input_lower or "find" in input_lower or "web" in input_lower:
            return f"I need to search for information about: {input_text}"
        elif "command" in input_lower or "bash" in input_lower or "run" in input_lower:
            return f"I need to execute a command for: {input_text}"
        else:
            return f"I need to analyze and respond to: {input_text}"
    
    async def plan_action(self, thought: str) -> dict:
        """
        Plan the next action based on the thought.
        In a real implementation, this would be more sophisticated.
        """
        thought_lower = thought.lower()
        
        if "python code" in thought_lower:
            return {
                "tool_name": "python_execute",
                "arguments": {
                    "code": "print('Hello from Enterprise AI agent!')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')"
                }
            }
        elif "file operations" in thought_lower:
            return {
                "tool_name": "filesystem",
                "arguments": {
                    "command": "list_directory",
                    "path": "/tmp"
                }
            }
        elif "search for information" in thought_lower:
            return {
                "tool_name": "web_search",
                "arguments": {
                    "query": "Enterprise AI multi-agent systems"
                }
            }
        elif "execute a command" in thought_lower:
            return {
                "tool_name": "bash",
                "arguments": {
                    "command": "echo 'Hello from Enterprise AI agent bash execution!'"
                }
            }
        else:
            # No action needed, just provide response
            return None


async def demo_simple_agent():
    """Demonstrate the simple agent functionality."""
    print_header("Enterprise AI Simple Agent Demo", style="double")
    
    # Initialize MCP Server
    print_header("1. Initializing MCP Server", style="single")
    print_test("Starting MCP Server", "running")
    config = MCPConfig(execution_mode="auto", verbose_logging=False)
    server = EnterpriseMCPServer(config)
    server.is_running = True
    await server.session_manager.start()
    print_test(f"MCP Server ready with {len(server.tool_registry.get_all_tool_classes())} tools", "pass")
    
    # Create Agent
    separator()
    print_header("2. Creating Simple Agent", style="single")
    print_test("Initializing Agent", "running")
    agent = SimpleAgent("demo_agent", server)
    success = await agent.initialize()
    if success:
        print_test(f"Agent '{agent.name}' initialized successfully", "pass")
    else:
        print_test("Agent initialization failed", "fail")
        return
    
    # Demo Tasks
    separator()
    print_header("3. Executing Demo Tasks", style="single")
    
    tasks = [
        "Execute some Python code",
        "List files in directory", 
        "Search for information about AI",
        "Run a bash command"
    ]
    
    for i, task in enumerate(tasks, 1):
        print_test(f"Task {i}: {task}", "running")
        separator(char="─", length=40)
        
        try:
            result = await agent.execute_task(task)
            
            if result.get("success", False):
                print_test(f"Success: {result.get('result', 'No details')}", "pass")
                if result.get("thought"):
                    print_chat("system", f"Thought: {result['thought']}")
                if result.get("action"):
                    action = result['action']
                    print_chat("tool", f"Action: {action['tool_name']} with {len(action.get('arguments', {}))} args")
            else:
                print_test(f"Failed: {result.get('error', 'Unknown error')}", "fail")
                
        except Exception as e:
            print_test(f"Exception: {str(e)}", "fail")
        
        # Small delay between tasks
        await asyncio.sleep(0.5)
    
    # Cleanup
    separator()
    print_header("4. Cleaning up", style="single")
    print_test("Cleaning up resources", "running")
    await agent.cleanup()
    await server.session_manager.stop()
    print_test("Cleanup completed", "pass")
    
    separator()
    print_header("Demo Completed Successfully", style="box")
    print(f"{Style.CYAN}Next steps:{Style.RESET}")
    print(f"{Style.GREEN}• Implement LLM integration for better reasoning{Style.RESET}")
    print(f"{Style.GREEN}• Add more sophisticated planning logic{Style.RESET}")
    print(f"{Style.GREEN}• Create specialized agent types{Style.RESET}")
    print(f"{Style.GREEN}• Add memory persistence{Style.RESET}")


async def main():
    """Run the agent demonstration."""
    try:
        await demo_simple_agent()
    except KeyboardInterrupt:
        print_test("Demo interrupted by user", "warn")
    except Exception as e:
        print_test(f"Demo failed: {str(e)}", "fail")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())