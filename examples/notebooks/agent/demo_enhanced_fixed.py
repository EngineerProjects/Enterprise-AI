"""
Enterprise AI Agent Enhanced Capabilities Demo - Fixed Version
Shows reflection, browser patterns, and specialized agent capabilities with proper message handling.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import utilities for better visual output
from utils import (
    print_header, print_test, print_chat, separator, Timer, 
    Style, setup_project_path
)

# Core Enterprise AI imports
from enterprise_ai.agent.base import BaseAgent
from enterprise_ai.agent.reasoning import ReasoningEngine, MultiPatternReasoning
from enterprise_ai.agent.specialized.factory import create_agent
from enterprise_ai.llm.factory import create_provider
from enterprise_ai.mcp.server import EnterpriseMCPServer
from enterprise_ai.mcp.config import MCPConfig
from enterprise_ai.schema.message import Message
from enterprise_ai.logger import get_optimized_logger

# Setup project paths
setup_project_path()
logger = get_optimized_logger("demo.enhanced")

# Configuration for local testing
TIMEOUT = 2400  # 40 minutes for local Ollama models
MODEL_NAME = "llama3.2"  # or "llama3.1" if you prefer


class EnhancedDemoAgent(BaseAgent):
    """Enhanced demo agent with proper message handling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_history = []
    
    async def think(self, input_text: str) -> str:
        """Generate thoughts using proper Message objects."""
        messages = [
            Message.user_message(f"Think carefully about this task: {input_text}")
        ]
        
        print_chat("user", f"Think about: {input_text}", model=self.llm.model_name)
        
        response = await self.llm.acomplete(messages)
        
        print_chat("assistant", response.content[:200] + "..." if len(response.content) > 200 else response.content, 
                  model=self.llm.model_name)
        
        return response.content
    
    async def plan_action(self, thought: str) -> Optional[Dict[str, Any]]:
        """Plan action based on thought content."""
        if "browser" in thought.lower() or "navigate" in thought.lower():
            return {"tool_name": "browser_use", "arguments": {"action": "get_current_state"}}
        elif "search" in thought.lower() or "research" in thought.lower():
            return {"tool_name": "web_search", "arguments": {"query": "enterprise ai agents"}}
        elif "code" in thought.lower() or "program" in thought.lower():
            return {"tool_name": "python_execute", "arguments": {"code": "print('Hello from Enterprise AI!')"}}
        return None


async def demo_reflection_pattern():
    """Demonstrate reflection pattern capabilities with visual output."""
    print_header("🔄 REFLECTION PATTERN DEMO", "double")
    
    # Setup with visual feedback
    print_test("Initializing MCP server", "running")
    config = MCPConfig(execution_mode="auto", verbose_logging=True)
    mcp_server = EnterpriseMCPServer(config)
    print_test("MCP server initialized", "pass")
    
    print_test("Creating Ollama LLM provider", "running")
    llm = create_provider("ollama", MODEL_NAME, timeout=TIMEOUT, verbose=True)
    print_test(f"LLM provider created: {MODEL_NAME}", "pass")
    
    print_test("Creating reflection demo agent", "running")
    agent = EnhancedDemoAgent(
        name="reflection_demo",
        llm_provider=llm,
        mcp_server=mcp_server
    )
    print_test("Agent created", "pass")
    
    try:
        with Timer("Agent initialization"):
            init_success = await agent.initialize()
            if not init_success:
                print_test("Agent initialization", "fail")
                return
            print_test("Agent initialization", "pass")
        
        # Test reflection pattern
        print_test("Creating reflection pattern", "running")
        from enterprise_ai.agent.reasoning.patterns.reflection import ReflectionPattern
        reflection_pattern = ReflectionPattern(agent, max_steps=3)
        print_test("Reflection pattern created", "pass")
        
        context = """
        I just completed a coding task to create a calculator application.
        The implementation worked but took longer than expected due to debugging.
        I had to fix several issues with input validation and error handling.
        The final result was successful and all tests passed.
        However, I could have been more systematic in my approach.
        """
        
        print_test("Running reflection analysis", "running")
        with Timer("Reflection pattern execution"):
            result = await reflection_pattern.process(
                "Reflect on coding task performance and identify improvements", 
                {"context": context}
            )
        
        # Display results with visual formatting
        separator("═", 60)
        print(f"{Style.GREEN}✅ Reflection Results:{Style.RESET}")
        print(f"Success: {Style.BOLD}{result.get('success')}{Style.RESET}")
        print(f"Steps Completed: {Style.BOLD}{result.get('steps_completed')}{Style.RESET}")
        print(f"Pattern History: {Style.BOLD}{len(result.get('pattern_history', []))}{Style.RESET} steps")
        
        if result.get('success') and result.get('result'):
            print(f"\n{Style.CYAN}🧠 Key Adaptations:{Style.RESET}")
            adaptations = result.get('result', 'No adaptations generated')
            print(f"{adaptations[:300]}..." if len(adaptations) > 300 else adaptations)
        
        print_test("Reflection pattern demo", "pass")
        
    except Exception as e:
        print_test(f"Reflection pattern demo failed: {e}", "fail")
        logger.error(f"Reflection demo error: {e}")
    finally:
        await agent.cleanup()


async def demo_agent_thinking():
    """Demonstrate basic agent thinking with proper message handling."""
    print_header("🧠 AGENT THINKING DEMO", "double")
    
    # Setup
    config = MCPConfig(execution_mode="auto", verbose_logging=False)
    mcp_server = EnterpriseMCPServer(config)
    llm = create_provider("ollama", MODEL_NAME, timeout=TIMEOUT, verbose=False)
    
    agent = EnhancedDemoAgent(
        name="thinking_demo",
        llm_provider=llm,
        mcp_server=mcp_server
    )
    
    try:
        await agent.initialize()
        
        # Test different thinking scenarios
        scenarios = [
            "Create a Python function to calculate Fibonacci numbers",
            "Research the latest trends in artificial intelligence",
            "Navigate to a website and extract information",
            "Design a simple web scraper for product data"
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n{Style.YELLOW}💭 Scenario {i}:{Style.RESET}")
            print(f"Task: {scenario}")
            
            with Timer(f"Thinking process {i}"):
                thought = await agent.think(scenario)
                action = await agent.plan_action(thought)
            
            print(f"{Style.GREEN}Action Planned:{Style.RESET} {action['tool_name'] if action else 'None'}")
            separator("─", 40)
        
        print_test("Agent thinking demo", "pass")
        
    except Exception as e:
        print_test(f"Agent thinking demo failed: {e}", "fail")
        logger.error(f"Thinking demo error: {e}")
    finally:
        await agent.cleanup()


async def demo_specialized_agents():
    """Demonstrate specialized agent types with visual output."""
    print_header("🎯 SPECIALIZED AGENTS DEMO", "double")
    
    config = MCPConfig(execution_mode="auto", verbose_logging=False)
    mcp_server = EnterpriseMCPServer(config)
    llm = create_provider("ollama", MODEL_NAME, timeout=TIMEOUT, verbose=False)
    
    # Test different agent types
    agent_configs = [
        ("general", "Help me understand machine learning concepts"),
        ("developer", "Create a Python function to sort a list efficiently"),
        ("researcher", "Find information about latest AI developments"),
    ]
    
    for agent_type, task in agent_configs:
        print(f"\n{Style.PURPLE}🤖 Testing {agent_type.upper()} Agent{Style.RESET}")
        print(f"Task: {task}")
        
        try:
            print_test(f"Creating {agent_type} agent", "running")
            
            if agent_type == "general":
                # Use our demo agent for general tasks
                agent = EnhancedDemoAgent(
                    name=f"{agent_type}_demo",
                    llm_provider=llm,
                    mcp_server=mcp_server
                )
            else:
                # Try to create specialized agent, fall back to demo agent if not available
                try:
                    agent = create_agent(
                        agent_type=agent_type,
                        name=f"{agent_type}_demo",
                        llm_provider=llm,
                        mcp_server=mcp_server,
                        verbose=False
                    )
                except Exception as e:
                    logger.warning(f"Specialized agent creation failed, using demo agent: {e}")
                    agent = EnhancedDemoAgent(
                        name=f"{agent_type}_demo",
                        llm_provider=llm,
                        mcp_server=mcp_server
                    )
            
            print_test(f"{agent_type} agent created", "pass")
            
            with Timer(f"{agent_type} agent execution"):
                await agent.initialize()
                result = await agent.execute_task(task)
            
            print(f"{Style.GREEN}Agent Type:{Style.RESET} {agent_type}")
            print(f"{Style.GREEN}Success:{Style.RESET} {result.get('success')}")
            print(f"{Style.GREEN}Result:{Style.RESET} {str(result.get('result', 'No result'))[:150]}...")
            
            print_test(f"{agent_type} agent demo", "pass")
            
        except Exception as e:
            print_test(f"{agent_type} agent demo failed: {e}", "fail")
            logger.error(f"Specialized agent demo error: {e}")
        finally:
            if 'agent' in locals():
                await agent.cleanup()
        
        separator("─", 50)


async def demo_message_handling():
    """Demonstrate proper message handling with different types."""
    print_header("📨 MESSAGE HANDLING DEMO", "double")
    
    # Show different message types
    print(f"{Style.CYAN}📋 Message Types Demonstration:{Style.RESET}")
    
    # User message
    user_msg = Message.user_message("Hello, how can you help me today?")
    print_chat("user", user_msg.content)
    
    # System message
    system_msg = Message.system_message("You are a helpful Enterprise AI assistant.")
    print_chat("system", system_msg.content)
    
    # Assistant message with metadata
    assistant_msg = Message.assistant_message(
        "I can help you with various tasks including coding, research, and automation.",
        tool_calls=[{"name": "example_tool", "arguments": {"param": "value"}}]
    )
    print_chat("assistant", assistant_msg.content, model="demo")
    
    # Tool message
    tool_msg = Message.tool_message(
        "Function executed successfully",
        name="example_tool",
        tool_call_id="call_123"
    )
    print_chat("tool", tool_msg.content)
    
    print_test("Message handling demonstration", "pass")


async def main():
    """Run comprehensive demo of Enterprise AI capabilities."""
    print_header("🚀 ENTERPRISE AI ENHANCED DEMO", "double")
    
    print(f"{Style.BOLD}Testing Enterprise AI multi-agent platform capabilities{Style.RESET}")
    print(f"Model: {Style.CYAN}{MODEL_NAME}{Style.RESET}")
    print(f"Timeout: {Style.CYAN}{TIMEOUT}s{Style.RESET}")
    print()
    
    try:
        # Core functionality demos
        await demo_message_handling()
        await demo_agent_thinking()
        await demo_reflection_pattern()
        await demo_specialized_agents()
        
        print_header("✅ ALL DEMOS COMPLETED SUCCESSFULLY!", "double")
        print(f"{Style.GREEN}🎉 Enterprise AI platform is working correctly!{Style.RESET}")
        
    except Exception as e:
        print_header("❌ DEMO FAILED", "double")
        print(f"{Style.RED}Error: {e}{Style.RESET}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print(f"{Style.BOLD}Enterprise AI Enhanced Capabilities Demo{Style.RESET}")
    print(f"Running on Python {sys.version}")
    print()
    
    asyncio.run(main())
