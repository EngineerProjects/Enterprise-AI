#!/usr/bin/env python
"""
Enterprise AI - Single Agent Interactive Test

This script creates a single intelligent agent that uses the full Enterprise AI
framework capabilities:
- Uses all available tools through the proper tool registry
- Implements reasoning framework (ReAct) for autonomous tool usage
- Uses proper prompt templates from the package
- Demonstrates interactive task processing with clean logging
- Shows real-world usage of the agent architecture

This test helps validate that all components work together properly
before moving to multi-agent team scenarios.
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import logging

# Rich imports for beautiful terminal output
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.syntax import Syntax
from rich.table import Table
from rich.logging import RichHandler
from rich import box

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import Enterprise AI components
from enterprise_ai.agent.core import create_agent
from enterprise_ai.agent.core.types import AgentProtocol
from enterprise_ai.llm import create_provider
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.tool.core.base import ToolCapability
from enterprise_ai.prompt.base import PromptTemplate, get_prompt_library
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger, setup_logger
from enterprise_ai.config import get_config
from enterprise_ai.mcp.client import ToolFilterStrategy

# Setup workspace and logging
WORKSPACE_DIR = Path(__file__).parent / "workspace"
LOG_FILE = WORKSPACE_DIR / "single_agent.log"
WORKSPACE_DIR.mkdir(exist_ok=True)

# Setup logging to file only, redirect all output
setup_logger(
    name="single_agent_test",
    level="INFO",
    log_file=str(LOG_FILE),
)

# Capture warnings and redirect them to the log file
import warnings
original_showwarning = warnings.showwarning

def warning_to_logger(message, category, filename, lineno, file=None, line=None):
    logger = logging.getLogger("single_agent_test")
    logger.warning(f"{category.__name__}: {message}")

warnings.showwarning = warning_to_logger

# Configure comprehensive logging to file for all enterprise_ai modules
for module_name in ["enterprise_ai", "single_agent_test", "agent", "tool", "mcp", "llm"]:
    module_logger = logging.getLogger(module_name)
    module_logger.setLevel(logging.INFO)
    
    # Remove any existing console handlers to prevent console spam
    for handler in module_logger.handlers[:]:
        if isinstance(handler, (logging.StreamHandler, RichHandler)) and not isinstance(handler, logging.FileHandler):
            module_logger.removeHandler(handler)
    
    # Ensure file handler exists
    if not any(isinstance(h, logging.FileHandler) for h in module_logger.handlers):
        file_handler = logging.FileHandler(LOG_FILE)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        module_logger.addHandler(file_handler)

# Configure the root logger to only log to file, not console
root_logger = logging.getLogger()
root_logger.handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]

# Add comprehensive file handler to root logger if needed
if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    root_file_handler = logging.FileHandler(LOG_FILE)
    root_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    root_file_handler.setFormatter(root_formatter)
    root_logger.addHandler(root_file_handler)
    root_logger.setLevel(logging.INFO)

# Use rich for console output
console = Console()
logger = get_logger("single_agent_test")

# Path to prompt file
PROMPT_DIR = Path(__file__).parent / "prompts"


def print_header():
    """Print beautiful header for the test."""
    header_text = """
    ███████╗███╗   ██╗████████╗███████╗██████╗ ██████╗ ██████╗ ██╗███████╗███████╗
    ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║██╔════╝██╔════╝
    █████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝██████╔╝██████╔╝██║███████╗█████╗  
    ██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔═══╝ ██╔══██╗██║╚════██║██╔══╝  
    ███████╗██║ ╚████║   ██║   ███████╗██║  ██║██║     ██║  ██║██║███████║███████╗
    ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚══════╝
                                
                          🤖 SINGLE AGENT INTERACTIVE TEST 🤖
    """
    console.print(Panel(header_text, style="bold cyan", padding=(1, 2)))


def print_section(title: str, style: str = "bold blue"):
    """Print a section header."""
    console.print(f"\n[{style}]{'='*60}[/]")
    console.print(f"[{style}]{title.center(60)}[/]")
    console.print(f"[{style}]{'='*60}[/]\n")


def load_prompt(filename: str) -> str:
    """Load a prompt from file."""
    prompt_file = PROMPT_DIR / filename
    if not prompt_file.exists():
        logger.warning(f"Prompt file not found: {prompt_file}")
        return ""
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


async def discover_tools(show_details: bool = True) -> Dict[str, Dict[str, Any]]:
    """Discover all available tools using the package's registry."""
    console.print("🔧 [yellow]Discovering available tools...[/]")
    
    # Get the registry from the package
    registry = get_registry()
    tools_info = {}
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Discovering tools...", total=None)
        
        # Get all available tool categories
        categories = registry.get_all_category_names()
        progress.update(task, description=f"Found {len(categories)} tool categories")
        
        # Get all tools by category
        for category in categories:
            tools = registry.get_tools_by_category(category)
            if tools:
                for tool_cls in tools:
                    # Properly extract tool information from the class
                    try:
                        # For tools that define fields as class attributes
                        if hasattr(tool_cls, 'model_fields'):
                            # Pydantic v2 style
                            name_field = tool_cls.model_fields.get('name')
                            desc_field = tool_cls.model_fields.get('description')
                            tool_name = name_field.default if name_field and name_field.default else tool_cls.__name__
                            description = desc_field.default if desc_field and desc_field.default else "No description available"
                        else:
                            # Fallback to direct attribute access
                            tool_name = getattr(tool_cls, "name", tool_cls.__name__)
                            description = getattr(tool_cls, "description", "No description available")
                        
                        # Ensure description is not empty
                        if not description or description.strip() == "":
                            description = "No description available"
                        
                        capabilities = getattr(tool_cls, "capabilities", set())
                        cap_list = []
                        for cap in capabilities:
                            if isinstance(cap, ToolCapability):
                                cap_list.append(cap.value)
                            else:
                                cap_list.append(str(cap))
                        
                        tools_info[tool_name] = {
                            "category": category,
                            "description": description,
                            "capabilities": cap_list
                        }
                        
                        # Log successful tool discovery
                        logger.debug(f"Discovered tool: {tool_name} with description: {description[:100]}...")
                        
                    except Exception as e:
                        logger.warning(f"Error discovering tool {tool_cls.__name__}: {e}")
                        # Add with minimal info as fallback
                        fallback_name = getattr(tool_cls, "__name__", "Unknown")
                        tools_info[fallback_name] = {
                            "category": category,
                            "description": f"Tool: {fallback_name} (description unavailable)",
                            "capabilities": []
                        }
        
        progress.update(task, description=f"Discovered {len(tools_info)} tools")
    
    console.print(f"✅ [green]Discovered {len(tools_info)} tools successfully![/]")
    
    # Display tools table if requested
    if show_details:
        # Create enhanced tool table with better visibility
        table = Table(
            title="🔧 Available Tools", 
            show_header=True, 
            header_style="bold magenta",
            title_style="bold cyan",
            border_style="bright_blue",
            box=box.DOUBLE_EDGE
        )
        table.add_column("Tool Name", style="cyan", no_wrap=True, width=20)
        table.add_column("Category", style="blue", width=15)
        table.add_column("Description", style="white", width=50)
        table.add_column("Capabilities", style="green", width=25)
        
        # Divide tools by category for better organization
        tools_by_category: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
        
        for tool_name, info in tools_info.items():
            category = info["category"]
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append((tool_name, info))
        
        # Sort categories and tools within categories
        for category, tools in sorted(tools_by_category.items()):
            # Add category divider
            table.add_row(
                f"[bold yellow]{category.upper()} TOOLS[/]", 
                "", "", "",
                style="bright_yellow"
            )
            
            # Add tools in this category
            for tool_name, info in sorted(tools, key=lambda x: x[0]):
                # Get a shorter version of the description for display
                short_desc = info["description"]
                if short_desc and len(short_desc) > 120:
                    short_desc = short_desc[:117] + "..."
                
                # Format capabilities for display
                capabilities = info.get("capabilities", [])
                cap_display = ", ".join(capabilities[:3])  # Show first 3 capabilities
                if len(capabilities) > 3:
                    cap_display += f" (+{len(capabilities)-3} more)"
                    
                table.add_row(
                    tool_name, 
                    category, 
                    short_desc or "No description available",
                    cap_display or "None"
                )
        
        # Add separator for better visual organization
        console.print()
        console.print(Panel(
            table,
            title="[bold cyan]Available Tools[/]",
            subtitle=f"[bold green]Total: {len(tools_info)} tools[/]",
            border_style="blue"
        ))
        console.print()
    
    return tools_info


async def create_intelligent_agent(tools_info: Dict[str, Dict[str, Any]] = None) -> AgentProtocol:
    """Create an intelligent agent with all available tools and reasoning."""
    console.print("🧠 [yellow]Creating intelligent agent...[/]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Setting up agent...", total=4)
        
        # Step 1: Create LLM provider using the factory function
        progress.update(task, description="Creating LLM provider...")
        # Get any custom LLM config from environment or config
        llm_provider_name = os.environ.get("LLM_PROVIDER", "ollama")
        model_name = os.environ.get("LLM_MODEL", "llama3.2")
        base_url = os.environ.get("LLM_BASE_URL", "http://localhost:11434")
        
        llm_provider = create_provider(
            provider_name=llm_provider_name,
            model_name=model_name,
            base_url=base_url,
            timeout=1200.0
        )
        progress.advance(task)
        
        # Step 2: Load system prompt from file
        progress.update(task, description="Loading system prompt...")
        system_prompt = load_prompt("single_agent.prompt")
        if not system_prompt:
            logger.warning("Prompt file not found, using default system prompt")
            system_prompt = """You are an intelligent AI assistant with access to various tools.
Use the ReAct framework to solve tasks:
1. Think about the problem step by step
2. Act using appropriate tools
3. Observe the results
4. Repeat until complete

When you need to use a tool, use the following format:
Action: tool_name(param1=value1, param2=value2)

Always think before deciding which tool to use. For each task:
1. First understand what's being asked and what information you need
2. Select the most appropriate tool for the task
3. Use the tool with the correct parameters
4. Review the results and determine if you need more information
5. Repeat until you have enough information to provide a complete answer

IMPORTANT: You have multiple tools available. Don't make up answers if you can use a tool instead.
"""
        progress.advance(task)
        
        # Step 3: Create agent using the AgentBuilder pattern
        progress.update(task, description="Creating agent with tools...")
        from enterprise_ai.agent.core import AgentBuilder
        
        # First, ensure tools are properly registered in the registry
        registry = get_registry()
        
        # Import and register key tools to ensure they're available
        try:
            from enterprise_ai.tool.research.web_search import WebSearch
            from enterprise_ai.tool.research.deep_research import DeepResearch
            # Register these tools explicitly if not already registered
            if not registry.get_tool_class("WebSearch"):
                registry.register(WebSearch, "research")
            if not registry.get_tool_class("DeepResearch"): 
                registry.register(DeepResearch, "research")
        except ImportError as e:
            logger.warning(f"Could not import some tools: {e}")
        
        # Get all available tools with their descriptions for agent configuration
        tool_descriptions = {}
        tool_categories = [
            "browser", 
            "file", 
            "research",
            "planning",
            "content", 
            "execution",
            "utility"
        ]
        
        # Build comprehensive tool descriptions from discovered tools
        for tool_name, tool_info in tools_info.items():
            if tool_info.get("description") and tool_info["description"] != "No description available":
                tool_descriptions[tool_name] = tool_info["description"]
        
        # Log tool registration status
        logger.info(f"Registering {len(tool_descriptions)} tools with descriptions")
        for name, desc in tool_descriptions.items():
            logger.debug(f"Tool {name}: {desc[:100]}...")

        # Now create the agent with proper tool configuration
        agent = (AgentBuilder()
            .with_type("llm")
            .with_id("intelligent-agent-001")
            .with_name("EnterpriseAssistant")
            .with_llm_provider(llm_provider)
            .with_reasoning("react")  # Use ReAct reasoning framework
            .with_tools(True)         # Enable tools
            .with_mcp(True)           # Enable Model Control Protocol
            .with_tool_categories(tool_categories)
            .with_filter_strategy(ToolFilterStrategy.INCLUDE)
            .with_param("system_prompt", system_prompt)
            .with_param("tool_descriptions", tool_descriptions)  # Pass tool descriptions directly
            .with_param("max_tool_calls", 10)  # Increase maximum tool calls allowed per conversation
            .with_param("use_tools_first", True)  # Encourage agent to use tools first rather than trying to answer directly
            .with_param("mandatory_tools", ["WebSearch", "DeepResearch", "FileEditor", "PythonExecute"])  # Make certain tools mandatory
            .with_param("reasoning_mode", "explicit")  # Ensure agent shows its reasoning explicitly
            .build())
        
        progress.advance(task)
        
        # Step 4: Initialize agent
        progress.update(task, description="Initializing agent...")
        await agent.initialize()
        progress.advance(task)
    
    console.print("✅ [green]Intelligent agent created successfully![/]")
    return agent


async def display_agent_info(agent: AgentProtocol):
    """Display agent information and capabilities."""
    console.print("\n🤖 [yellow]Agent Information:[/]")
    
    info_panel = f"""
[bold]Agent ID:[/] {agent.id}
[bold]Name:[/] {agent.name}
[bold]Type:[/] LLM Agent with ReAct reasoning
[bold]Status:[/] {agent.get_status().get('state', 'Unknown')}
[bold]Tools Enabled:[/] ✅ Yes
[bold]MCP Enabled:[/] ✅ Yes
"""
    
    console.print(Panel(info_panel, title="Agent Details", style="blue"))
    
    # Display available tools
    if hasattr(agent, '_tool_manager'):
        tool_manager = getattr(agent, '_tool_manager')
        if hasattr(tool_manager, 'list_tools'):
            tool_names = tool_manager.list_tools()
            tool_descriptions = tool_manager.get_tool_descriptions()
            
            if tool_names:
                tools_table = Table(title="Available Agent Tools", show_header=True, header_style="bold green")
                tools_table.add_column("Tool Name", style="cyan")
                tools_table.add_column("Description", style="white")
                
                for tool_name in tool_names:
                    description = tool_descriptions.get(tool_name, "No description available")
                    # Truncate long descriptions for display
                    if description and len(description) > 80:
                        description = description[:77] + "..."
                    tools_table.add_row(tool_name, description or "No description available")
                
                console.print(tools_table)


async def interactive_session(agent: AgentProtocol):
    """Run an interactive session with the agent."""
    console.print("\n🎯 [yellow]Starting Interactive Session...[/]")
    console.print("[dim]Type 'quit', 'exit', or 'bye' to end the session[/]")
    console.print("[dim]Type 'help' for example tasks[/]\n")
    
    session_count = 0
    
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold blue]You[/]", default="", show_default=False)
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
                console.print("\n👋 [yellow]Goodbye! Session ended.[/]")
                break
            
            # Handle help command
            if user_input.lower() == 'help':
                show_help()
                continue
            
            # Skip empty inputs
            if not user_input.strip():
                continue
            
            session_count += 1
            
            # Log the interaction
            logger.info(f"Session {session_count} - User: {user_input}")
            
            # Process the message with progress indicator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Agent is thinking and acting...", total=None)
                
                # Create user message using the schema
                user_message = Message.user_message(user_input)
                
                # Process with agent
                response = await agent.aprocess_message(user_message)
                
                progress.update(task, description="Response ready!")
            
            # Display agent response
            console.print(f"\n[bold green]🤖 Agent[/]:")
            if hasattr(response, 'content') and response.content:
                # Format the response nicely
                response_panel = Panel(
                    response.content,
                    title=f"Response #{session_count}",
                    style="green",
                    padding=(1, 2)
                )
                console.print(response_panel)
            else:
                console.print("[red]No response received from agent[/]")
            
            # Log the response (only to file, not console)
            if hasattr(logging.getLogger("single_agent_test"), "handlers"):
                for handler in logging.getLogger("single_agent_test").handlers:
                    if isinstance(handler, logging.FileHandler):
                        handler.handle(
                            logging.getLogger("single_agent_test").makeRecord(
                                "single_agent_test",
                                logging.INFO,
                                __file__,
                                0,
                                f"Session {session_count} - Agent: {getattr(response, 'content', 'No content')}",
                                (),
                                None,
                                "interactive_session",
                            )
                        )
            
            # Show tool usage if available
            if hasattr(response, 'metadata') and response.metadata:
                metadata = response.metadata
                if 'tool_calls' in metadata and metadata['tool_calls']:
                    tool_calls = metadata['tool_calls']
                    console.print(f"[dim]🔧 Tools used: {len(tool_calls)}[/]")
                    
                    # Create tool usage table
                    tools_table = Table(title="Tool Usage", show_header=True, header_style="dim")
                    tools_table.add_column("Tool", style="cyan")
                    tools_table.add_column("Status", style="green")
                    
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name', 'Unknown')
                        status = tool_call.get('status', 'unknown')
                        tools_table.add_row(tool_name, status)
                    
                    console.print(tools_table)
                
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Session interrupted by user[/]")
            break
        except Exception as e:
            console.print(f"\n[red]Error during interaction: {e}[/]")
            logger.error(f"Session {session_count} error: {e}")
            continue


def show_help():
    """Show example tasks that can be performed."""
    help_text = """
[bold]🎯 Example Tasks You Can Try:[/]

[bold cyan]Research & Information:[/]
• "Research the latest developments in AI and create a summary"
• "Search for information about renewable energy trends"
• "Find and analyze recent news about climate change"
• "Explain the concept of distributed systems"

[bold cyan]File Operations:[/]
• "Create a TODO list file for my project"
• "Create a CSV file with sample data"
• "Create a Python script that calculates Fibonacci numbers"
• "Read a file and analyze its contents"

[bold cyan]Planning & Organization:[/]
• "Create a project plan for building a web application"
• "Help me break down a complex task into manageable steps"
• "Plan a learning schedule for a new programming language"
• "Create a mind map structure for a research project"

[bold cyan]Creative & Analysis:[/]
• "Analyze a problem and suggest solutions"
• "Brainstorm ideas for a marketing campaign"
• "Help me write a persuasive email"
• "Create a story outline based on key elements"

[bold]💡 Tips:[/]
• Be specific about what you want to accomplish
• The agent will use multiple tools and reasoning steps
• Check the log file for detailed execution traces
• Ask the agent to explain its reasoning process
"""
    
    console.print(Panel(help_text, title="Help & Examples", style="blue"))


async def cleanup_session(agent: AgentProtocol):
    """Clean up resources after the session."""
    console.print("\n🧹 [yellow]Cleaning up resources...[/]")
    
    try:
        # Terminate agent
        await agent.terminate()
        console.print("✅ [green]Agent terminated successfully[/]")
        
        # Close any open LLM provider clients
        if hasattr(agent, '_llm_provider') and agent._llm_provider is not None and hasattr(agent._llm_provider, 'close'):
            try:
                await agent._llm_provider.close()
                console.print("✅ [green]LLM provider closed[/]")
            except Exception as e:
                logger.warning(f"Non-critical error closing LLM provider: {e}")
        
        console.print("✅ [green]Cleanup completed[/]")
        
    except Exception as e:
        console.print(f"[red]Error during cleanup: {e}[/]")
        logger.error(f"Cleanup error: {e}")


async def main():
    """Main function to run the single agent test."""
    try:
        # Print header
        print_header()
        
        # Step 1: Discover available tools
        print_section("Step 1: Tool Discovery")
        tools_info = await discover_tools()
        
        # Step 2: Create intelligent agent
        print_section("Step 2: Agent Creation")
        agent = await create_intelligent_agent(tools_info=tools_info)
        
        # Step 3: Display agent info
        print_section("Step 3: Agent Information")
        await display_agent_info(agent)
        
        # Step 4: Interactive session
        print_section("Step 4: Interactive Session")
        await interactive_session(agent)
        
        # Step 5: Cleanup
        print_section("Step 5: Cleanup")
        await cleanup_session(agent)
        
        # Final message
        console.print(f"\n[bold green]✅ Test completed successfully![/]")
        console.print(f"[dim]Check the log file at: {LOG_FILE}[/]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Test failed: {e}[/]")
        logger.error(f"Main test error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    # Run the test
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
