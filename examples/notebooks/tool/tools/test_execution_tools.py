#!/usr/bin/env python3
"""
Execution Tools Testing Script

Tests bash and python execution tools individually with configurable LLM support.
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path

from examples.notebooks.utils import print_header, print_test, print_chat, Timer, run_async
from enterprise_ai.tool.execution.bash import Bash
from enterprise_ai.tool.execution.python import PythonExecute
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.config import get_config


class ExecutionToolsTester:
    """Comprehensive execution tools tester with LLM configuration support."""
    
    def __init__(self):
        self.bash_tool = None
        self.python_tool = None
        self.test_dir = None
        self.test_files = {}
    
    async def show_current_config(self):
        """Show current configuration."""
        print_header("Current Configuration", "single")
        
        # LLM Configuration
        provider = get_config("llm.default_provider", "not configured")
        model = get_config("llm.default_model", "not configured")
        print_test(f"LLM Provider: {provider}", "pass")
        print_test(f"LLM Model: {model}", "pass")
        
        # Test directory
        print_test(f"Test Directory: {self.test_dir}", "pass" if self.test_dir else "warn")

    async def show_tool_descriptions(self):
        """Show the tool descriptions and capabilities."""
        print_header("Execution Tools Description", "double")
        
        if self.bash_tool:
            print_chat("tool", f"Tool Name: {self.bash_tool.name}")
            print_chat("tool", f"Description: {self.bash_tool.description.strip()}")
            
            # Show capabilities
            if hasattr(self.bash_tool, 'capabilities'):
                caps = [str(cap) for cap in self.bash_tool.capabilities]
                print_chat("tool", f"Bash Capabilities: {', '.join(caps)}")
        
        if self.python_tool:
            print_chat("tool", f"Tool Name: {self.python_tool.name}")
            print_chat("tool", f"Description: {self.python_tool.description.strip()}")
            
            # Show capabilities
            if hasattr(self.python_tool, 'capabilities'):
                caps = [str(cap) for cap in self.python_tool.capabilities]
                print_chat("tool", f"Python Capabilities: {', '.join(caps)}")

    async def setup(self, llm_provider=None, llm_model=None):
        """Initialize execution tools with optional LLM configuration."""
        print_header("Execution Tools Test Suite", "double")
        
        # Create temporary test directory
        self.test_dir = tempfile.mkdtemp(prefix="execution_test_")
        print_test(f"Created test directory: {self.test_dir}", "pass")
        
        # Show current config
        await self.show_current_config()
        
        print_test("Setting up execution tools", "running")
        
        # Create tools with working directory
        kwargs = {}
        if llm_provider:
            kwargs['llm_provider'] = llm_provider
            print_test(f"Using LLM Provider Override: {llm_provider}", "pass")
        if llm_model:
            kwargs['llm_model'] = llm_model
            print_test(f"Using LLM Model Override: {llm_model}", "pass")
        
        # Pass working directory to bash tool
        self.bash_tool = Bash(working_dir=self.test_dir, **kwargs)
        self.python_tool = PythonExecute(**kwargs)
        
        bash_success = await self.bash_tool.initialize()
        python_success = await self.python_tool.initialize()
        
        if bash_success and python_success:
            print_test("Execution tools initialized", "pass")
            await self.show_tool_descriptions()
            return True
        else:
            print_test("Execution tools initialization failed", "fail")
            return False
    
    async def test_operation(self, tool, description: str, expect_success: bool = True, 
                           show_content: bool = True, **kwargs):
        """Test a single tool operation."""
        print_test(f"Testing: {description}", "running")
        
        try:
            with Timer(f"Operation: {description}"):
                result = await tool.execute(**kwargs)
            
            # For execution tools, check if result has meaningful output or expected error
            is_success = isinstance(result, ToolResult) and result.success
            
            # For error cases, check if we got the expected error
            if not expect_success:
                # We expect this to fail, so success=False OR success=True with error details is acceptable
                if not is_success or (is_success and hasattr(result, 'result') and 
                                    isinstance(result.result, dict) and result.result.get('error')):
                    print_test(f"{description}: EXPECTED ERROR", "pass")
                    if hasattr(result, 'result') and result.result and show_content:
                        output = str(result.result)
                        if len(output) <= 1000:
                            print_chat("tool", output)
                        else:
                            print_chat("tool", output[:1000] + "...")
                    return result, True
                else:
                    print_test(f"{description}: UNEXPECTED SUCCESS (expected failure)", "warn")
                    return result, False
            
            # For success cases
            if expect_success and is_success:
                print_test(f"{description}: SUCCESS", "pass")
                
                # Show result content
                if hasattr(result, 'result') and result.result and show_content:
                    output = str(result.result)
                    if len(output) <= 1000:
                        print_chat("tool", output)
                    else:
                        print_chat("tool", output[:1000] + "...")
                
                return result, True
            elif expect_success and not is_success:
                error_msg = getattr(result, 'error', 'Unknown error')
                print_test(f"{description}: UNEXPECTED FAILURE - {error_msg}", "fail")
                if hasattr(result, 'result') and result.result:
                    print_chat("tool", f"Result: {result.result}")
                return result, False
                
        except Exception as e:
            if expect_success:
                print_test(f"{description}: EXCEPTION - {e}", "fail")
                return None, False
            else:
                print_test(f"{description}: EXPECTED EXCEPTION - {e}", "pass")
                return None, True
    
    def _get_test_file_path(self, filename: str) -> str:
        """Get full path for test file."""
        return os.path.join(self.test_dir, filename)
    
    async def run_bash_tests(self):
        """Test bash tool operations."""
        print_header("Bash Tool Tests", "single")
        
        # Test safe commands (should run locally)
        await self.test_operation(
            self.bash_tool,
            "Simple Echo Command",
            expect_success=True,
            command="echo 'Hello from bash!'",
            sandbox_mode="local"  # Force local for simple commands
        )
        
        await self.test_operation(
            self.bash_tool,
            "List Current Directory",
            expect_success=True,
            command="ls -la",
            sandbox_mode="local"
        )
        
        await self.test_operation(
            self.bash_tool,
            "Show Current Working Directory",
            expect_success=True,
            command="pwd",
            sandbox_mode="local"
        )
        
        # Test file operations
        await self.test_operation(
            self.bash_tool,
            "Create File with Echo",
            expect_success=True,
            command="echo 'Hello from bash file!' > bash_test.txt",
            sandbox_mode="local"
        )
        
        await self.test_operation(
            self.bash_tool,
            "Read File Content",
            expect_success=True,
            command="cat bash_test.txt",
            sandbox_mode="local"
        )
        
        # Test potentially dangerous command (should use sandbox)
        await self.test_operation(
            self.bash_tool,
            "Complex Command with Pipe",
            expect_success=True,
            command="echo 'test data' | wc -l",
            sandbox_mode="auto"  # This should trigger sandbox
        )
        
        # Test error handling
        await self.test_operation(
            self.bash_tool,
            "Non-existent Command",
            expect_success=False,
            command="nonexistentcommand12345",
            sandbox_mode="local"
        )
        
        # Test session restart
        await self.test_operation(
            self.bash_tool,
            "Restart Session",
            expect_success=True,
            command="",
            restart=True
        )
    
    async def run_python_tests(self):
        """Test python tool operations."""
        print_header("Python Tool Tests", "single")
        
        # Test simple safe operations (should run locally)
        await self.test_operation(
            self.python_tool,
            "Simple Print Statement",
            expect_success=True,
            code="print('Hello from Python!')",
            sandbox_mode="local"  # Force local for simple operations
        )
        
        await self.test_operation(
            self.python_tool,
            "Basic Math Operations",
            expect_success=True,
            code="""
result = 10 + 20 * 3
print(f"Math result: {result}")
print(f"Square root of 16: {16 ** 0.5}")
""",
            sandbox_mode="local"
        )
        
        await self.test_operation(
            self.python_tool,
            "List Operations",
            expect_success=True,
            code="""
numbers = [1, 2, 3, 4, 5]
squared = [x**2 for x in numbers]
print(f"Original: {numbers}")
print(f"Squared: {squared}")
print(f"Sum of squares: {sum(squared)}")
""",
            sandbox_mode="local"
        )
        
        # Test potentially dangerous code (should use sandbox)
        await self.test_operation(
            self.python_tool,
            "File System Access",
            expect_success=True,
            code="""
import os
print("Current directory:", os.getcwd())
print("Directory contents:")
for item in os.listdir('.'):
    print(f"  {item}")
""",
            sandbox_mode="auto"  # This should trigger sandbox
        )
        
        # Test error handling
        await self.test_operation(
            self.python_tool,
            "Syntax Error",
            expect_success=False,
            code="print('missing quote)",
            sandbox_mode="local"
        )
        
        await self.test_operation(
            self.python_tool,
            "Runtime Error",
            expect_success=False,
            code="""
numbers = [1, 2, 3]
print(numbers[10])  # Index error
""",
            sandbox_mode="local"
        )
        
        # Test forced sandbox mode
        await self.test_operation(
            self.python_tool,
            "Forced Sandbox Execution",
            expect_success=True,
            code="print('This will run in sandbox')",
            sandbox_mode="sandbox"
        )
        
        # Test forced local mode
        await self.test_operation(
            self.python_tool,
            "Forced Local Execution",
            expect_success=True,
            code="print('This will run locally')",
            sandbox_mode="local"
        )
    
    async def run_integration_tests(self):
        """Test integration between bash and python tools."""
        print_header("Integration Tests", "single")
        
        # Create a data file with bash, then process with python
        data_file = "data.txt"
        
        # Create data with printf instead of echo -e for better compatibility
        await self.test_operation(
            self.bash_tool,
            "Create Data File",
            expect_success=True,
            command=f"printf '1\\n2\\n3\\n4\\n5\\n' > {data_file}",
            sandbox_mode="local"
        )
        
        # Verify file was created
        await self.test_operation(
            self.bash_tool,
            "Verify Data File",
            expect_success=True,
            command=f"cat {data_file}",
            sandbox_mode="local"
        )
        
        # Process data with python
        full_data_path = self._get_test_file_path(data_file)
        await self.test_operation(
            self.python_tool,
            "Process Data File",
            expect_success=True,
            code=f"""
with open('{full_data_path}', 'r') as f:
    numbers = [int(line.strip()) for line in f.readlines() if line.strip()]

print(f"Numbers: {{numbers}}")
print(f"Sum: {{sum(numbers)}}")
print(f"Average: {{sum(numbers) / len(numbers)}}")
""",
            sandbox_mode="local"
        )
        
        self.test_files["data"] = full_data_path
    
    async def run_llm_integration_tests(self):
        """Test LLM integration with real usage scenarios."""
        print_header("LLM Integration Tests", "single")
        
        print_chat("user", "I want to create a Python script that analyzes some data, then run it with bash")
        print_chat("user", "Steps:")
        print_chat("user", "1. Create a Python script that reads numbers and calculates statistics")
        print_chat("user", "2. Create sample data file")
        print_chat("user", "3. Run the Python script using bash")
        
        # Create Python script using bash
        script_content = '''#!/usr/bin/env python3
import sys

def analyze_numbers(filename):
    """Analyze numbers from a file."""
    try:
        with open(filename, 'r') as f:
            numbers = [float(line.strip()) for line in f.readlines() if line.strip()]
        
        if not numbers:
            print("No numbers found in file")
            return
        
        print(f"Data Analysis Results:")
        print(f"  Count: {len(numbers)}")
        print(f"  Sum: {sum(numbers)}")
        print(f"  Average: {sum(numbers) / len(numbers):.2f}")
        print(f"  Min: {min(numbers)}")
        print(f"  Max: {max(numbers)}")
        print(f"  Range: {max(numbers) - min(numbers)}")
        
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
    except ValueError as e:
        print(f"Error: Invalid number in file - {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python analyze_data.py <data_file>")
        sys.exit(1)
    
    analyze_numbers(sys.argv[1])
'''
        
        # Write script using bash
        await self.test_operation(
            self.bash_tool,
            "Create Analysis Script",
            expect_success=True,
            command=f"cat > analyze_data.py << 'EOF'\n{script_content}EOF",
            sandbox_mode="local"
        )
        
        await self.test_operation(
            self.bash_tool,
            "Make Script Executable",
            expect_success=True,
            command="chmod +x analyze_data.py",
            sandbox_mode="local"
        )
        
        # Create sample data using printf instead of echo -e
        await self.test_operation(
            self.bash_tool,
            "Create Sample Data",
            expect_success=True,
            command="printf '10.5\\n20.3\\n15.7\\n8.2\\n12.9\\n18.4\\n22.1\\n' > sample_numbers.txt",
            sandbox_mode="local"
        )
        
        # Run the analysis script
        await self.test_operation(
            self.bash_tool,
            "Run Analysis Script",
            expect_success=True,
            command="python analyze_data.py sample_numbers.txt",
            sandbox_mode="local"
        )
        
        # Verify the script content with python
        script_path = self._get_test_file_path("analyze_data.py")
        sample_path = self._get_test_file_path("sample_numbers.txt")
        await self.test_operation(
            self.python_tool,
            "Verify Script Exists",
            expect_success=True,
            code=f"""
import os
print(f"Script exists: {{os.path.exists('{script_path}')}}")
print(f"Data file exists: {{os.path.exists('{sample_path}')}}")
if os.path.exists('{script_path}'):
    with open('{script_path}', 'r') as f:
        lines = f.readlines()
    print(f"Script has {{len(lines)}} lines")
""",
            sandbox_mode="local"
        )
        
        print_test("LLM Integration setup complete", "pass")
        print_test("Files ready for LLM editing:", "pass")
        print_test(f"  Python script: {script_path}", "pass") 
        print_test(f"  Sample data: {sample_path}", "pass")
    
    async def cleanup(self):
        """Clean up test resources."""
        print_header("Cleanup", "single")
        
        if self.bash_tool:
            print_test("Cleaning up bash tool", "running")
            await self.bash_tool.cleanup()
            print_test("Bash tool cleanup complete", "pass")
        
        if self.python_tool:
            print_test("Cleaning up python tool", "running")
            await self.python_tool.cleanup()
            print_test("Python tool cleanup complete", "pass")
        
        if self.test_dir and os.path.exists(self.test_dir):
            print_test("Removing test directory", "running")
            shutil.rmtree(self.test_dir)
            print_test("Test directory removed", "pass")


async def main():
    """Run all execution tool tests with comprehensive coverage."""
    tester = ExecutionToolsTester()
    
    # Setup with default configuration
    if not await tester.setup():
        print_test("Setup failed, exiting", "fail")
        return 1
    
    try:
        # Run core test suites
        await tester.run_bash_tests()
        await tester.run_python_tests() 
        await tester.run_integration_tests()
        await tester.run_llm_integration_tests()
        
        print_header("All Execution Tool Tests Complete!", "double")
        print_test("You can now test the execution tools with your LLM", "pass")
        print_test(f"Test files available in: {tester.test_dir}", "pass")
        
    except KeyboardInterrupt:
        print_test("Tests interrupted by user", "warn")
    except Exception as e:
        print_test(f"Unexpected error: {e}", "fail")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup()
    
    return 0


if __name__ == "__main__":
    exit_code = run_async(main())
    sys.exit(exit_code)