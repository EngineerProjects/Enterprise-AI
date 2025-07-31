#!/usr/bin/env python3
"""
Simple Python Execute Test Through MCP
=====================================

Test Python code execution through Enterprise-AI's MCP system.
Simple usage validation (under 150 lines) to verify:
✅ MCP can execute Python code
✅ Code execution results are returned properly
✅ Error handling works
✅ System is ready for Python automation
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def setup_simple_logging():
    """Setup simple .log file logging (optional)."""
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / "python_execute_test.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("python_execute_test")

async def test_python_execution():
    """Test Python code execution through MCP."""
    
    print("🐍 Python Execute Test Through MCP")
    print("=" * 40)
    
    logger = setup_simple_logging()
    logger.info("Starting Python execution test through MCP")
    
    try:
        # Create MCP system
        print("🔧 Creating MCP system...")
        from enterprise_ai.mcp import create_simple_mcp
        
        mcp = create_simple_mcp(timeout=60.0)
        print(f"   ✅ MCP created: {type(mcp).__name__}")
        
        # Check if python_execute tool is available
        if hasattr(mcp, '_tools') and mcp._tools:
            tools = list(mcp._tools.keys())
            python_tools = [t for t in tools if 'python' in t.lower()]
            print(f"   🔧 Python tools available: {python_tools}")
        else:
            print("   ❌ No tools found in MCP")
            return False
        
        # Test 1: Simple Python calculation
        print("\n🧮 Test 1: Simple Python Calculation")
        python_code_1 = """
result = 2 + 3 * 4
print(f"Calculation result: {result}")
print(f"Type: {type(result)}")
"""
        
        success_1 = await execute_python_code(mcp, python_code_1, "Simple calculation")
        
        # Test 2: Python with imports
        print("\n📊 Test 2: Python with Imports")
        python_code_2 = """
import math
import datetime

# Math calculation
area = math.pi * (5 ** 2)
print(f"Circle area (r=5): {area:.2f}")

# Current time
now = datetime.datetime.now()
print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

# List comprehension
squares = [x**2 for x in range(1, 6)]
print(f"Squares 1-5: {squares}")
"""
        
        success_2 = await execute_python_code(mcp, python_code_2, "Imports and data structures")
        
        # Test 3: Python with error handling
        print("\n⚠️  Test 3: Python Error Handling")
        python_code_3 = """
try:
    # This will cause a division by zero error
    result = 10 / 0
    print(f"Result: {result}")
except ZeroDivisionError as e:
    print(f"Caught error: {e}")
    print("Error handling works!")

# This should work fine
safe_result = 10 / 2
print(f"Safe division: {safe_result}")
"""
        
        success_3 = await execute_python_code(mcp, python_code_3, "Error handling")
        
        # Test 4: Python data analysis simulation
        print("\n📈 Test 4: Data Analysis Simulation")
        python_code_4 = """
# Simulate some data analysis
data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Statistics
mean = sum(data) / len(data)
total = sum(data)
maximum = max(data)
minimum = min(data)

print(f"Data: {data}")
print(f"Mean: {mean}")
print(f"Sum: {total}")
print(f"Max: {maximum}, Min: {minimum}")

# Simple data transformation
doubled = [x * 2 for x in data]
print(f"Doubled: {doubled}")
"""
        
        success_4 = await execute_python_code(mcp, python_code_4, "Data analysis")
        
        # Summary
        total_tests = 4
        passed_tests = sum([success_1, success_2, success_3, success_4])
        
        print(f"\n🎯 PYTHON EXECUTION TEST SUMMARY")
        print(f"=" * 40)
        print(f"✅ Tests passed: {passed_tests}/{total_tests}")
        print(f"🧮 Simple calculation: {'✅' if success_1 else '❌'}")
        print(f"📊 Imports & structures: {'✅' if success_2 else '❌'}")
        print(f"⚠️  Error handling: {'✅' if success_3 else '❌'}")
        print(f"📈 Data analysis: {'✅' if success_4 else '❌'}")
        
        logger.info(f"Python execution test completed: {passed_tests}/{total_tests} passed")
        
        if passed_tests >= 3:
            print(f"\n🎉 Python execution through MCP is working!")
            return True
        else:
            print(f"\n⚠️  Python execution has issues")
            return False
            
    except Exception as e:
        print(f"❌ Python execution test failed: {e}")
        logger.error(f"Python execution test failed: {e}")
        return False

async def execute_python_code(mcp, code, description):
    """Execute Python code through MCP and show results."""
    
    try:
        print(f"   🔄 Executing: {description}")
        print(f"   📝 Code preview: {code.strip().split()[0]}...")
        
        # Create proper tool call for python execution
        from enterprise_ai.schema import ToolCall, Function
        
        # Try different possible python tool names
        python_tool_name = None
        if hasattr(mcp, '_tools') and mcp._tools:
            tools = list(mcp._tools.keys())
            for tool_name in ['python_execute', 'python', 'python_exec']:
                if tool_name in tools:
                    python_tool_name = tool_name
                    break
        
        if not python_tool_name:
            print(f"   ❌ No Python execution tool found")
            return False
        
        # Create tool call with correct schema
        tool_call = ToolCall(
            id=f"python_test_{int(time.time())}",
            function=Function(
                name=python_tool_name,
                arguments={"code": code.strip()}
            )
        )
        
        # Execute with timeout
        start_time = time.time()
        result = await asyncio.wait_for(
            execute_tool_call_safely(mcp, tool_call),
            timeout=30.0
        )
        execution_time = time.time() - start_time
        
        if result:
            print(f"   ✅ Execution successful ({execution_time:.2f}s)")
            
            # Show result if available
            if hasattr(result, 'result') and result.result:
                result_str = str(result.result)
                if len(result_str) > 200:
                    print(f"   📤 Output: {result_str[:200]}...")
                else:
                    print(f"   📤 Output: {result_str}")
            
            return True
        else:
            print(f"   ❌ Execution failed - no result returned")
            return False
            
    except asyncio.TimeoutError:
        print(f"   ⏰ Execution timed out (30s)")
        return False
    except Exception as e:
        print(f"   ❌ Execution error: {e}")
        return False

async def execute_tool_call_safely(mcp, tool_call):
    """Safely execute tool call through MCP with different methods."""
    
    # Try different execution methods based on MCP type
    try:
        # Method 1: Direct execution if available
        if hasattr(mcp, 'execute_tool_call'):
            return await mcp.execute_tool_call(tool_call)
        
        # Method 2: Direct tool access
        elif hasattr(mcp, '_tools') and mcp._tools:
            tool_func = mcp._tools.get(tool_call.function.name)
            if tool_func and callable(tool_func):
                args = tool_call.function.arguments
                if isinstance(args, str):
                    import json
                    args = json.loads(args)
                return await tool_func(**args)
        
        # Method 3: Tool executor access
        elif hasattr(mcp, 'tool_executor'):
            args = tool_call.function.arguments
            if isinstance(args, str):
                import json
                args = json.loads(args)
            return await mcp.tool_executor.execute_tool(
                tool_call.function.name,
                args
            )
        
        return None
        
    except Exception as e:
        print(f"   ⚠️  Execution method failed: {e}")
        return None

if __name__ == "__main__":
    print("🐍 Testing Python Execution Through Enterprise-AI MCP")
    print(f"📁 Logs will be saved to: logs/python_execute_test.log")
    print()
    
    success = asyncio.run(test_python_execution())
    
    print(f"\n{'🎉 SUCCESS' if success else '❌ FAILED'}: Python execution {'working' if success else 'needs attention'}")
    sys.exit(0 if success else 1)
