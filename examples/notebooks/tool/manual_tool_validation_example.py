#!/usr/bin/env python3
"""
Enterprise AI Manual Tool Validation Example - FIXED VERSION

This example demonstrates:
1. Setting up Ollama provider with llama3.2 using optimized logging
2. Manual tool execution with user approval using three-tier logging
3. Using the LLMToolAdapter to register tools properly
4. Interactive terminal validation workflow with clean UI
5. PROPER conversation history management
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import utilities
from examples.notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, Style
)

# Import Enterprise AI components - USING OPTIMIZED IMPORTS
from enterprise_ai.llm.factory import create_provider 
from enterprise_ai.tool.core.base import ExecutionMode
from enterprise_ai.tool.core.llm_adapter import get_llm_tools, get_llm_tool_definitions
from enterprise_ai.schema import Message
from enterprise_ai.logger import setup_enterprise_logging, get_optimized_logger, Colors

# Setup optimized logging for this demo - CLEAN TERMINAL ONLY
config = setup_enterprise_logging(
    debug_file="/tmp/enterprise_ai_demo.log",  # All logs go to file
    tool_verbose=False,                        # No verbose terminal output
    clean_terminal=True                        # Only clean output
)

logger = get_optimized_logger("manual_validation_demo", config)


def create_approval_callback():
    """Create an interactive approval callback for tool execution."""
    
    def approval_callback(tool_call, approval_message):
        """
        Interactive approval callback that asks user for validation.
        Uses optimized logging and clean terminal output.
        
        Args:
            tool_call: The ToolCall object containing function details
            approval_message: Formatted message about the tool call
            
        Returns:
            bool: True if approved, False if denied
        """
        # Clean tool execution display
        args = tool_call.get_arguments()
        
        print(f"\n{Colors.BG_YELLOW}{Colors.BLACK} ⚠️  MANUAL APPROVAL REQUIRED ⚠️ {Colors.RESET}")
        print(f"{Colors.YELLOW}{'─'*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}Tool:{Colors.RESET} {Colors.CYAN}{tool_call.function.name}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW}Call ID:{Colors.RESET} {Colors.WHITE}{tool_call.id}{Colors.RESET}")
        
        if args:
            print(f"{Colors.BOLD}{Colors.YELLOW}Arguments:{Colors.RESET}")
            for key, value in args.items():
                value_str = str(value)
                print(f"  {Colors.CYAN}{key}:{Colors.RESET} {value_str}")
        
        print(f"{Colors.YELLOW}{'─'*60}{Colors.RESET}")
        
        while True:
            try:
                # Clean user prompt
                response = input(f"{Colors.BOLD}{Colors.BLUE}➤{Colors.RESET} Approve execution? (y/n/q): ").strip().lower()
                
                if response in ['y', 'yes']:
                    print(f"{Colors.GREEN}✓{Colors.RESET} Tool execution APPROVED")
                    return True
                elif response in ['n', 'no']:
                    print(f"{Colors.YELLOW}•{Colors.RESET} Tool execution DENIED")
                    return False
                elif response in ['q', 'quit']:
                    print(f"{Colors.YELLOW}•{Colors.RESET} Demo terminated by user")
                    sys.exit(0)
                else:
                    print(f"{Colors.YELLOW}Please enter 'y' for yes, 'n' for no, or 'q' to quit{Colors.RESET}")
            except (KeyboardInterrupt, EOFError):
                print(f"{Colors.YELLOW}•{Colors.RESET} Tool execution cancelled")
                return False
    
    return approval_callback


async def setup_provider_with_tools():
    """Setup Ollama provider with manual execution mode and tools."""
    
    print_test("Setting up Ollama provider with llama3.2", "running")
    
    try:
        # Create approval callback
        approval_callback = create_approval_callback()
        
        # Load timeout from config
        from enterprise_ai.config import get_config
        execution_timeout = get_config("execution.timeout", 500.0)
        
        # Create Ollama provider with manual execution mode
        provider = create_provider(
            provider_name="ollama",
            model_name="llama3.2",
            execution_mode=ExecutionMode.MANUAL,
            approval_callback=approval_callback,
            timeout=1200.0,
            verbose=False,  # Disable provider verbose to keep terminal clean
            tool_execution_timeout=execution_timeout,  # Use config timeout
            max_tool_iterations=3,
        )
        
        print_test("Ollama provider created successfully", "pass")
        print_test(f"Provider type: {type(provider).__name__}", "pass")
        print_test(f"Execution mode: {provider.execution_mode}", "pass")
        print_test(f"Tool timeout: {execution_timeout}s", "pass")
        
        # Register tools using the LLMToolAdapter
        print_test("Registering tools via LLMToolAdapter", "running")
        
        # Get tools for research and web search
        tool_functions = await get_llm_tools(categories=[
            "research", "file", "execution", "browser", 
            "content", "planning", "utility"
        ])
        tool_definitions = await get_llm_tool_definitions(categories=[
            "research", "file", "execution", "browser", 
            "content", "planning", "utility"
        ])
        
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
        raise


async def run_interactive_example():
    """Run simplified tool validation with PROPER conversation history management and fixed serialization."""
    
    print_header("Enterprise AI - Tool Execution Demo (Fixed)", "double")
    
    # Setup provider and get tool definitions
    try:
        provider, tool_definitions = await setup_provider_with_tools()
        logger.success("System ready for tool execution demo")
    except Exception as e:
        print_test(f"Failed to setup provider: {str(e)}", "fail")
        return
    
    # Convert tool definitions 
    tools_for_llm = [td.to_dict() for td in tool_definitions] if tool_definitions else []
    
    # Show available tools
    if tools_for_llm:
        print(f"\n{Colors.BOLD}Available tools:{Colors.RESET}")
        for tool_def in tool_definitions:
            tool_name = tool_def.get_name()
            tool_desc = tool_def.get_description()
            print(f"\n{Colors.CYAN}📋 {tool_name}{Colors.RESET}")
            print(f"{Colors.DIM}{tool_desc}{Colors.RESET}")
        print()
    
    separator("─", 80)
    
    # Interactive loop - FIXED TO PROPERLY MANAGE CONVERSATION HISTORY
    print(f"\n{Colors.BOLD}🔧 Tool Execution Demo{Colors.RESET}")
    print(f"{Colors.DIM}The model will suggest tool calls, you approve, and see the raw output.{Colors.RESET}")
    print(f"{Colors.DIM}Type 'quit' to exit.{Colors.RESET}\n")
    
    # 🔥 CRITICAL FIX: Properly maintain conversation history
    conversation_history = []
    
    def safe_result_to_content(tool_result):
        """Safely convert tool result to string content for Ollama."""
        try:
            if not tool_result.success and hasattr(tool_result, 'error') and tool_result.error:
                return f"Error: {tool_result.error}"
            
            result_data = tool_result.result if hasattr(tool_result, 'result') else tool_result
            
            if isinstance(result_data, str):
                return result_data
            elif isinstance(result_data, dict):
                # Handle our wrapped tool_output format
                if "tool_output" in result_data and len(result_data) == 1:
                    inner_result = result_data["tool_output"]
                    if isinstance(inner_result, dict):
                        # Extract the actual output if available
                        if "output" in inner_result:
                            return str(inner_result["output"])
                        else:
                            import json
                            return json.dumps(inner_result, indent=2, default=str)
                    else:
                        return str(inner_result)
                else:
                    import json
                    return json.dumps(result_data, indent=2, default=str)
            elif isinstance(result_data, list):
                import json
                return json.dumps(result_data, indent=2, default=str)
            else:
                return str(result_data)
                
        except Exception as e:
            return f"Tool executed but result formatting failed: {str(e)}"
    
    while True:
        try:
            user_input = input(f"{Colors.BOLD}{Colors.BLUE}➤{Colors.RESET} Your question: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                logger.success("Demo completed!")
                break
            
            if not user_input:
                continue
            
            # 1. Add user message to conversation history
            user_message = Message.user_message(user_input)
            conversation_history.append(user_message)
            
            print_chat("user", user_input)
            
            # Get model's tool call suggestions (no automatic response)
            logger.status("Getting tool suggestions from model...")
            
            try:
                # 2. Get response and tool calls based on FULL conversation history
                response, tool_calls = provider.complete_with_tool_calls(
                    messages=conversation_history,
                    tools=tools_for_llm,
                    temperature=0.7
                )
                
                if tool_calls:
                    print(f"\n{Colors.YELLOW}🤖 Model suggests {len(tool_calls)} tool call(s):{Colors.RESET}")
                    
                    # 3. Add assistant response to conversation history BEFORE executing tools
                    assistant_message = Message.assistant_message(
                        content=response.content or "I'll help you with that.",
                        tool_calls=[tc.to_dict() for tc in tool_calls],
                        metadata=response.metadata
                    )
                    conversation_history.append(assistant_message)
                    
                    for i, tool_call in enumerate(tool_calls, 1):
                        print(f"\n{Colors.CYAN}Tool {i}: {tool_call.function.name}{Colors.RESET}")
                        
                        print(f"\n{Colors.BLUE}🔧 Executing {tool_call.function.name}...{Colors.RESET}")
                        
                        # 4. Execute tool calls
                        tool_results = provider.execute_tool_calls([tool_call])
                        
                        if tool_results:
                            result = tool_results[0]
                            
                            # 🔥 FIX: Properly serialize tool result content to string
                            tool_content = safe_result_to_content(result)
                            
                            # 5. Add tool message to conversation history with STRING content
                            tool_message = Message.tool_message(
                                content=tool_content,  # ✅ Always string now
                                name=tool_call.function.name,
                                tool_call_id=tool_call.id,
                                metadata={
                                    "execution_success": result.success if hasattr(result, 'success') else True,
                                    "execution_time": result.execution_time if hasattr(result, 'execution_time') else None
                                }
                            )
                            conversation_history.append(tool_message)
                            
                            print(f"\n{Colors.GREEN}✅ Tool Output:{Colors.RESET}")
                            print(f"{Colors.WHITE}{'='*60}{Colors.RESET}")
                            
                            # Clean, formatted output for display
                            if hasattr(result, 'result') and result.result:
                                if isinstance(result.result, dict) and "tool_output" in result.result:
                                    # Extract clean output for display
                                    tool_output = result.result["tool_output"]
                                    if isinstance(tool_output, dict) and "output" in tool_output:
                                        print(tool_output["output"])
                                    else:
                                        print(str(tool_output))
                                else:
                                    print(result.result)
                            elif hasattr(result, 'content') and result.content:
                                print(result.content)
                            else:
                                print(str(result))
                            
                            print(f"{Colors.WHITE}{'='*60}{Colors.RESET}")
                        else:
                            print(f"{Colors.RED}❌ Tool execution failed{Colors.RESET}")
                            
                            # Add failed tool message to history with string content
                            tool_message = Message.tool_message(
                                content="Tool execution failed",  # ✅ String content
                                name=tool_call.function.name,
                                tool_call_id=tool_call.id,
                                metadata={"execution_success": False}
                            )
                            conversation_history.append(tool_message)
                else:
                    print(f"{Colors.DIM}No tool calls suggested by the model.{Colors.RESET}")
                    print(f"{Colors.DIM}Model response: {response.content[:200]}...{Colors.RESET}")
                    
                    # Add assistant response even if no tool calls
                    assistant_message = Message.assistant_message(
                        content=response.content or "I don't think I need to use any tools for this.",
                        metadata=response.metadata
                    )
                    conversation_history.append(assistant_message)
                
                # 6. Debug: Show conversation history length
                print(f"{Colors.DIM}💾 Conversation history: {len(conversation_history)} messages{Colors.RESET}")
                
            except Exception as e:
                print_test(f"Error: {str(e)}", "fail")
            
            separator("─", 60)
            
        except (KeyboardInterrupt, EOFError):
            logger.status("Demo interrupted")
            break
        except Exception as e:
            print_test(f"Unexpected error: {str(e)}", "fail")


def main():
    """Main entry point."""
    try:
        # Setup project
        setup_project_path()
        
        # Show demo information
        logger.success("Starting Enterprise AI Manual Tool Validation Demo")
        logger.status("Using clean terminal output - detailed logs in file")
        
        # Run the interactive example
        asyncio.run(run_interactive_example())
        
    except KeyboardInterrupt:
        logger.status("Demo interrupted by user")
    except Exception as e:
        print_test(f"Demo failed: {str(e)}", "fail")
    finally:
        # Show debug file location
        print(f"\n{Colors.DIM}Debug logs saved to: /tmp/enterprise_ai_demo.log{Colors.RESET}")


if __name__ == "__main__":
    main()