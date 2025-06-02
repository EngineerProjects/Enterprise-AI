#!/usr/bin/env python3
"""
Deep Tool Discovery - Find out why tools aren't loading
"""

import asyncio
import traceback
from pathlib import Path
import sys

# Setup project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from examples.notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async, Style
)

# Enterprise AI imports
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.tool.core.llm_adapter import get_llm_tools, get_llm_tool_definitions, get_adapter


async def main():
    """Deep discovery to find issues"""
    setup_project_path()
    
    print_header("🔍 Deep Tool Discovery", "double")
    
    # 1. Registry Analysis
    print_header("Registry Analysis", "box")
    registry = get_registry()
    
    all_tools = registry.get_all_tool_classes()
    categories = registry.get_all_category_names()
    
    print_test(f"Registry tools: {len(all_tools)}", "pass")
    print_test(f"Categories: {categories}", "pass")
    
    # Show each tool's category
    print(f"\n{Style.CYAN}Tools by Category:{Style.RESET}")
    for category in categories:
        tools_in_cat = registry.get_tools_by_category(category)
        print(f"\n{Style.YELLOW}{category}:{Style.RESET}")
        for tool_cls in tools_in_cat:
            tool_name = getattr(tool_cls, 'name', tool_cls.__name__)
            print(f"   • {tool_name} ({tool_cls.__name__})")
    
    # 2. Individual Tool Registration Test
    print_header("Individual Tool Registration", "box")
    
    adapter = get_adapter()
    
    for tool_name, tool_cls in all_tools.items():
        print(f"\n{Style.YELLOW}Testing: {tool_name}{Style.RESET}")
        
        try:
            # Try to register individual tool
            registered_name = await adapter.register_tool_class(tool_cls, initialize=True)
            print_test(f"Registration: {registered_name}", "pass")
            
        except Exception as e:
            print_test(f"Registration failed: {str(e)}", "fail")
            print(f"   {Style.RED}Error:{Style.RESET} {str(e)}")
            
            # Show full traceback for debugging
            print(f"   {Style.RED}Traceback:{Style.RESET}")
            for line in traceback.format_exc().split('\n')[-10:]:
                if line.strip():
                    print(f"     {line}")
    
    # 3. Category-specific Registration
    print_header("Category Registration Test", "box")
    
    for category in categories:
        print(f"\n{Style.YELLOW}--- {category.upper()} ---{Style.RESET}")
        
        try:
            # Fresh adapter for each category
            from enterprise_ai.tool.core.llm_adapter import LLMToolAdapter
            fresh_adapter = LLMToolAdapter()
            
            # Register tools from this category only
            registered = await fresh_adapter.register_all_tools(categories=[category])
            
            print_test(f"Registered {len(registered)} tools", "pass")
            
            for class_name, function_name in registered.items():
                print(f"   ✓ {class_name} → {function_name}")
            
            # Get the actual functions
            functions = fresh_adapter.get_tool_functions()
            definitions = fresh_adapter.get_tool_definitions()
            
            print(f"   Functions: {list(functions.keys())}")
            print(f"   Definitions: {len(definitions)}")
            
        except Exception as e:
            print_test(f"Category {category} failed: {str(e)}", "fail")
            print(f"   {Style.RED}Error:{Style.RESET} {str(e)}")
    
    # 4. Global Adapter State
    print_header("Global Adapter State", "box")
    
    global_adapter = get_adapter()
    
    print(f"Global adapter tools: {len(global_adapter._tool_instances)}")
    print(f"Global adapter functions: {len(global_adapter._function_tools)}")
    
    print(f"\n{Style.CYAN}Registered instances:{Style.RESET}")
    for name in global_adapter._tool_instances.keys():
        print(f"   • {name}")
    
    print(f"\n{Style.CYAN}Function tools:{Style.RESET}")
    for name in global_adapter._function_tools.keys():
        print(f"   • {name}")
    
    # 5. Direct Tool Creation Test
    print_header("Direct Tool Creation Test", "box")
    
    # Test creating tools directly
    for tool_name, tool_cls in list(all_tools.items())[:3]:  # Test first 3
        print(f"\n{Style.YELLOW}Creating: {tool_name}{Style.RESET}")
        
        try:
            # Create tool instance directly
            tool_instance = tool_cls()
            print_test(f"Instance created", "pass")
            
            # Check if it needs initialization
            if tool_instance.requires_initialization:
                print_test(f"Requires initialization", "warn")
                success = await tool_instance.initialize()
                print_test(f"Initialization: {'success' if success else 'failed'}", 
                          "pass" if success else "fail")
            else:
                print_test(f"No initialization needed", "pass")
            
        except Exception as e:
            print_test(f"Creation failed: {str(e)}", "fail")
            print(f"   {Style.RED}Error:{Style.RESET} {str(e)}")
    
    # 6. Try get_llm_tools without categories
    print_header("Test get_llm_tools", "box")
    
    try:
        print("Testing get_llm_tools() without categories...")
        all_tools_llm = await get_llm_tools()
        print_test(f"Got {len(all_tools_llm)} tools without categories", "pass")
        
        for name in all_tools_llm.keys():
            print(f"   • {name}")
            
    except Exception as e:
        print_test(f"get_llm_tools() failed: {str(e)}", "fail")
        print(f"   {Style.RED}Error:{Style.RESET} {str(e)}")
    
    try:
        print("\nTesting get_llm_tools() with force_refresh...")
        all_tools_fresh = await get_llm_tools(force_refresh=True)
        print_test(f"Got {len(all_tools_fresh)} tools with refresh", "pass")
        
        for name in all_tools_fresh.keys():
            print(f"   • {name}")
            
    except Exception as e:
        print_test(f"get_llm_tools(force_refresh) failed: {str(e)}", "fail")
        print(f"   {Style.RED}Error:{Style.RESET} {str(e)}")
    
    print(f"\n{Style.GREEN}🎯 Deep Discovery Complete!{Style.RESET}")
    print(f"\n{Style.CYAN}Summary:{Style.RESET}")
    print("- Check individual tool registration errors above")
    print("- Look for initialization failures")
    print("- Check if global adapter is caching incorrectly")


if __name__ == "__main__":
    run_async(main())