#!/usr/bin/env python3
"""
Enterprise AI Manual Tool Validation Example - CORRECTED VERSION

This example demonstrates:
1. Setting up Ollama provider with llama3.2 using actual code structure
2. Manual tool execution with user approval using existing approval system
3. Using the LLMToolAdapter to register tools properly
4. Interactive terminal validation workflow
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import utilities
from examples.notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, Style
)

# Import Enterprise AI components - USING ACTUAL IMPORTS
from enterprise_ai.llm.factory import create_provider 
from enterprise_ai.tool.core.base import ExecutionMode
from enterprise_ai.tool.core.llm_adapter import get_llm_tools, get_llm_tool_definitions
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Setup logging
logger = get_logger("manual_validation_corrected")


def create_approval_callback():
    """Create an interactive approval callback for tool execution."""
    
    def approval_callback(tool_call, approval_message):
        """
        Interactive approval callback that asks user for validation.
        
        Args:
            tool_call: The ToolCall object containing function details
            approval_message: Formatted message about the tool call
            
        Returns:
            bool: True if approved, False if denied
        """
        print(f"\n{Style.YELLOW}{'='*80}{Style.RESET}")
        print(f"{Style.BOLD}{Style.CYAN}🤖 MODEL DECISION: Execute Tool{Style.RESET}")
        print(f"{Style.YELLOW}{'='*80}{Style.RESET}")
        
        print(f"\n{Style.BOLD}Tool Call Details:{Style.RESET}")
        print(f"  {Style.GREEN}Function:{Style.RESET} {tool_call.function.name}")
        print(f"  {Style.GREEN}Call ID:{Style.RESET} {tool_call.id}")
        print(f"  {Style.GREEN}Arguments:{Style.RESET}")
        
        args = tool_call.get_arguments()
        for key, value in args.items():
            # Truncate long values for display
            display_value = str(value)
            if len(display_value) > 100:
                display_value = display_value[:97] + "..."
            print(f"    {Style.CYAN}{key}:{Style.RESET} {display_value}")
        
        print(f"\n{Style.BOLD}Approval Details:{Style.RESET}")
        print(f"  {approval_message}")
        
        print(f"\n{Style.YELLOW}{'='*80}{Style.RESET}")
        
        while True:
            try:
                response = input(f"{Style.BOLD}Approve execution? (y/n/q): {Style.RESET}").strip().lower()
                
                if response in ['y', 'yes']:
                    print(f"{Style.GREEN}✅ APPROVED{Style.RESET} - Tool will execute\n")
                    return True
                elif response in ['n', 'no']:
                    print(f"{Style.RED}❌ DENIED{Style.RESET} - Tool execution cancelled\n")
                    return False
                elif response in ['q', 'quit']:
                    print(f"{Style.RED}🚪 QUIT{Style.RESET} - Exiting example\n")
                    sys.exit(0)
                else:
                    print(f"{Style.YELLOW}Please enter 'y' for yes, 'n' for no, or 'q' to quit{Style.RESET}")
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Style.RED}❌ DENIED{Style.RESET} - Tool execution cancelled\n")
                return False
    
    return approval_callback


async def setup_provider_with_tools():
    """Setup Ollama provider with manual execution mode and tools."""
    
    print_test("Setting up Ollama provider with llama3.2", "running")
    
    try:
        # Create approval callback
        approval_callback = create_approval_callback()
        
        # Create Ollama provider with manual execution mode - USING CORRECT FACTORY
        provider = create_provider(
            provider_name="ollama",  # Correct parameter name
            model_name="llama3.2",
            execution_mode=ExecutionMode.MANUAL,  # Require approval for all tools
            approval_callback=approval_callback,
            timeout=1200.0,
            verbose=True,  # Enable verbose logging
            tool_execution_timeout=200.0,
            max_tool_iterations=3,  # Limit iterations for demo
        )
        
        print_test("Ollama provider created successfully", "pass")
        print_test(f"Provider type: {type(provider).__name__}", "pass")
        print_test(f"Execution mode: {provider.execution_mode}", "pass")
        
        # Register tools using the LLMToolAdapter - CORRECT METHOD
        print_test("Registering tools via LLMToolAdapter", "running")
        
        # Get tools for specific categories 
        tool_functions = await get_llm_tools(categories=["research"])
        tool_definitions = await get_llm_tool_definitions(categories=["research"])
        
        if tool_functions:
            # Register the function versions with the provider
            provider.register_tools(tool_functions)
            print_test(f"Registered {len(tool_functions)} tools", "pass")
            
            for tool_name in tool_functions.keys():
                print_test(f"  ✓ {tool_name}", "pass")
        else:
            print_test("No tools found to register", "warn")
        
        return provider, tool_definitions
        
    except Exception as e:
        print_test(f"Provider setup failed: {str(e)}", "fail")
        logger.error(f"Setup error: {str(e)}", exc_info=True)
        raise


async def run_interactive_example():
    """Run the interactive example with manual tool validation."""
    
    print_header("Enterprise AI - Manual Tool Validation (Corrected)", "double")
    
    print_chat("system", "This example demonstrates manual tool execution with user approval.")
    print_chat("system", "The model will suggest tool calls, and you'll be asked to approve them.")
    print_chat("system", "Using actual Enterprise AI code structure and patterns.")
    
    separator("─", 80)
    
    # Setup provider and get tool definitions
    provider, tool_definitions = await setup_provider_with_tools()
    
    print_test("System ready for interactive demo", "pass")
    
    # Convert tool definitions to the format expected by provider
    tools_for_llm = [td.to_dict() for td in tool_definitions] if tool_definitions else []
    
    if tools_for_llm:
        print(f"\n{Style.BOLD}Available tools:{Style.RESET}")
        for tool_def in tool_definitions:
            tool_name = tool_def.get_name()
            tool_desc = tool_def.get_description()
            print(f"  • {Style.CYAN}{tool_name}{Style.RESET}: {tool_desc}")
    else:
        print_test("No tools available for demonstration", "warn")
        return
    
    separator("─", 80)
    
    # Interactive loop
    print(f"\n{Style.BOLD}🎯 Interactive Tool Validation Demo{Style.RESET}")
    print(f"Ask questions that would benefit from research tools!")
    print(f"Example: 'What are the latest developments in AI in 2024?'")
    print(f"Type 'quit' to exit.\n")
    
    conversation_history = []
    
    while True:
        try:
            # Get user input
            user_input = input(f"{Style.GREEN}You: {Style.RESET}").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print(f"{Style.YELLOW}Goodbye!{Style.RESET}")
                break
            
            if not user_input:
                continue
            
            # Add user message to conversation
            user_message = Message.user_message(user_input)
            conversation_history.append(user_message)
            
            print_chat("user", user_input)
            
            # Get model response with potential tool calls
            print_test("Sending message to model...", "running")
            
            with Timer("Model response"):
                try:
                    # Use the provider's complete method with tools
                    response = provider.complete(
                        messages=conversation_history,
                        tools=tools_for_llm,
                        temperature=0.7
                    )
                    
                    print_chat("assistant", response.content, model="llama3.2")
                    
                    # Add assistant response to conversation
                    conversation_history.append(response)
                    
                except Exception as e:
                    print_test(f"Model error: {str(e)}", "fail")
                    print_chat("system", f"Error: {str(e)}")
                    logger.error(f"Model error: {str(e)}", exc_info=True)
            
            separator("─", 60)
            
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Style.YELLOW}Goodbye!{Style.RESET}")
            break
        except Exception as e:
            print_test(f"Unexpected error: {str(e)}", "fail")
            logger.error(f"Error in interactive loop: {str(e)}", exc_info=True)


def main():
    """Main entry point."""
    try:
        # Setup project
        setup_project_path()
        
        # Run the interactive example
        asyncio.run(run_interactive_example())
        
    except KeyboardInterrupt:
        print(f"\n{Style.YELLOW}Demo interrupted by user{Style.RESET}")
    except Exception as e:
        print_test(f"Demo failed: {str(e)}", "fail")
        logger.error(f"Demo error: {str(e)}", exc_info=True)


if __name__ == "__main__":
    main()