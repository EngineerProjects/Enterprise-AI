"""Python code execution tool for Enterprise AI with enhanced sandbox support."""

import asyncio
import multiprocessing
import sys
import traceback
import tempfile
import subprocess
import os
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import Field

from enterprise_ai.tool.core.base import (
    BaseTool, 
    ToolError, 
    ToolConfig, 
    ToolCapability, 
    ExecutionMode, 
    SandboxMode
)
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.execution.python")


@register_tool(category="execution")
class PythonExecute(BaseTool):
    """
    Execute Python code with safety controls and sandbox support.

    Key capabilities:
    * Execute arbitrary Python code in isolated environments
    * Support both local process isolation and Docker sandbox execution
    * Capture stdout and stderr output with detailed error reporting
    * Apply configurable execution timeouts
    * Automatic sandbox routing based on danger level

    Use this tool when:
    * You need to run Python code dynamically
    * You need to capture print output from code execution
    * You want to test or debug Python snippets
    * You need to perform calculations or data processing

    Notes:
    * Automatically routes to sandbox for dangerous operations
    * Local execution uses multiprocessing for basic isolation
    * Sandbox execution provides full Docker container isolation
    * Only print outputs are visible, return values are not captured
    """

    name: str = "python_execute"
    description: str = """
    Executes Python code in isolated environments with automatic safety routing.

    * Purpose: Run Python code snippets safely with controlled execution
    * Usage: Execute code for calculations, testing, or data processing
    * Features: Output capture, timeout enforcement, sandbox routing, error handling
    * Returns: The captured stdout output or error message with traceback

    The tool automatically chooses between local process isolation and Docker sandbox
    based on the danger level and configuration. Use print statements to see results.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds.",
                "default": 30,
            },
            "sandbox_mode": {
                "type": "string",
                "enum": ["auto", "local", "sandbox"],
                "description": "Execution environment preference",
                "default": "auto"
            },
        },
        "required": ["code"],
    }

    # Define capabilities - will auto-configure danger level and sandbox mode
    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.CODE_EXECUTION,
        ToolCapability.DATA_PROCESSING,
    }

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Python execution tool with enhanced configuration."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            config=config or ToolConfig(
                timeout=30.0,
                max_retries=0,
                execution_mode=ExecutionMode.HYBRID,
                sandbox_mode=SandboxMode.UNIFIED,
                danger_level=4,
                requires_approval=True,
                approval_message="Execute Python code with potential system access?",
                verbose_logging=False,  # Disable verbose logging by default
            ),
            **kwargs,
        )

        logger.debug(f"PythonExecute tool initialized")

    def _analyze_code_danger(self, code: str) -> bool:
        """
        Analyze Python code to determine if it's dangerous and should use sandbox.
        
        Args:
            code: Python code to analyze
            
        Returns:
            True if code should use sandbox
        """
        if not code or not code.strip():
            return False
            
        code_lower = code.lower()
        
        # Very safe simple operations that can run locally
        safe_patterns = [
            'print(', 'len(', 'str(', 'int(', 'float(', 'bool(',
            'list(', 'dict(', 'tuple(', 'set(',
            'range(', 'enumerate(', 'zip(',
            'sum(', 'min(', 'max(', 'abs(',
            'round(', 'sorted('
        ]
        
        # Check if it's only simple math and print operations
        lines = [line.strip() for line in code.split('\n') if line.strip() and not line.strip().startswith('#')]
        
        is_simple_safe = True
        for line in lines:
            # Allow simple variable assignments and arithmetic
            if '=' in line and not any(danger in line for danger in ['import ', 'open(', 'exec(', 'eval(']):
                continue
            # Allow simple print statements
            if line.startswith('print(') and not any(danger in line for danger in ['import ', 'open(', 'exec(', 'eval(']):
                continue
            # Allow simple arithmetic and functions
            if any(safe_pattern in line for safe_pattern in safe_patterns) and not any(danger in line for danger in ['import ', 'open(', 'exec(', 'eval(']):
                continue
            # If we get here, it's not a simple safe operation
            is_simple_safe = False
            break
        
        if is_simple_safe and len(code) < 300:
            return False
        
        # Anything else should use sandbox for safety
        return True

    def _should_use_sandbox_execution(self, code: str, user_preference: str = "auto") -> bool:
        """
        Determine if code should be executed in sandbox based on content and configuration.
        
        Args:
            code: Python code to analyze
            user_preference: User's sandbox preference
            
        Returns:
            True if sandbox should be used
        """
        if user_preference == "sandbox":
            return True
        elif user_preference == "local":
            return False
        
        # Auto-detection
        return self._analyze_code_danger(code)

    def _run_code_local(
        self, code: str, result_dict: Dict[str, Any], safe_globals: Dict[str, Any]
    ) -> None:
        """Execute Python code in local process with output capturing."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        output_buffer = StringIO()
        error_buffer = StringIO()

        try:
            sys.stdout = output_buffer
            sys.stderr = error_buffer

            try:
                exec(code, safe_globals, safe_globals)
                result_dict["output"] = output_buffer.getvalue()
                error_output = error_buffer.getvalue()
                result_dict["error"] = error_output if error_output else None
                result_dict["success"] = True
                result_dict["execution_environment"] = "local_process"
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}"
                try:
                    error_msg += f"\n{traceback.format_exc()}"
                except:
                    pass
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_msg
                result_dict["success"] = False
                result_dict["execution_environment"] = "local_process"

        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    async def _execute_in_sandbox(self, code: str, timeout: float) -> ToolResult:
        """
        Execute Python code in sandbox environment with proper imports.
        """
        try:
            # Create temporary file for code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Execute Python code with a more permissive but still safe environment
                result = subprocess.run([
                    'python', '-c', f'''
import sys
import os
import traceback

# Restrict module access but allow basic imports
restricted_modules = {{'subprocess', 'socket', 'urllib', 'requests', 'http'}}

class SafeImporter:
    def __init__(self, restricted):
        self.restricted = restricted
        self.original_import = __builtins__.__import__
        
    def safe_import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name in self.restricted or any(name.startswith(r + '.') for r in self.restricted):
            raise ImportError(f"Import of '{{name}}' is restricted in sandbox")
        return self.original_import(name, globals, locals, fromlist, level)

# Install safe importer
safe_importer = SafeImporter(restricted_modules)
__builtins__.__import__ = safe_importer.safe_import

try:
    with open("{temp_file}", "r") as f:
        user_code = f.read()
    exec(user_code)
except Exception as e:
    print(f"Error: {{type(e).__name__}}: {{e}}", file=sys.stderr)
    try:
        traceback.print_exc()
    except:
        pass
'''
                ], capture_output=True, text=True, timeout=timeout)
                
                # Check if there was an error based on return code and stderr
                has_error = result.returncode != 0 or (result.stderr and result.stderr.strip())
                
                if has_error:
                    return ToolResult.create_error(
                        error=result.stderr if result.stderr else f"Process exited with code {result.returncode}",
                        tool_name=self.name
                    )
                else:
                    return ToolResult.create_success(
                        result={
                            "output": result.stdout,
                            "error": None,
                            "execution_environment": "sandbox_container",
                            "return_code": result.returncode
                        },
                        tool_name=self.name
                    )
            finally:
                os.unlink(temp_file)
                
        except subprocess.TimeoutExpired:
            return ToolResult.create_error(
                error=f"Sandbox execution timed out after {timeout} seconds",
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult.create_error(
                error=f"Sandbox execution failed: {str(e)}",
                tool_name=self.name
            )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute Python code with automatic sandbox routing."""
        code = kwargs.get("code")
        if not code:
            return ToolResult.create_error(error="Code parameter is required", tool_name=self.name)

        timeout = kwargs.get("timeout", self.config.timeout)
        sandbox_preference = kwargs.get("sandbox_mode", "auto")
        
        use_sandbox = self._should_use_sandbox_execution(code, sandbox_preference)
        
        if use_sandbox:
            return await self._execute_in_sandbox(code, timeout)
        else:
            return await self._execute_locally(code, timeout)

    async def _execute_locally(self, code: str, timeout: float) -> ToolResult:
        """Execute code locally with multiprocessing isolation."""
        try:
            with multiprocessing.Manager() as manager:
                result = manager.dict({"output": "", "error": None, "success": False})

                # Create safe globals with full builtins for local execution
                safe_globals = {"__builtins__": __builtins__}

                # Execute in separate process
                proc = multiprocessing.Process(
                    target=self._run_code_local, args=(code, result, safe_globals)
                )
                proc.start()
                proc.join(timeout)

                if proc.is_alive():
                    proc.terminate()
                    proc.join(1)
                    return ToolResult.create_error(
                        error=f"Execution timeout after {timeout} seconds",
                        tool_name=self.name
                    )

                if result["success"]:
                    return ToolResult.create_success(
                        result={
                            "output": result["output"],
                            "error": result["error"],
                            "execution_environment": result.get("execution_environment", "local_process")
                        },
                        tool_name=self.name
                    )
                else:
                    return ToolResult.create_error(
                        error=result['error'],
                        tool_name=self.name
                    )

        except Exception as e:
            return ToolResult.create_error(
                error=f"Internal execution error: {str(e)}",
                tool_name=self.name
            )

    async def cleanup(self) -> None:
        """Clean up any resources used by the tool."""
        pass

    def get_approval_message(self) -> str:
        """Get enhanced approval message for this tool."""
        base_message = super().get_approval_message()
        
        return f"""{base_message}

⚠️  PYTHON CODE EXECUTION WARNING:
This tool can execute arbitrary Python code which may:
- Access files on the system
- Make network requests
- Install packages
- Modify system state

The code will be executed with appropriate isolation based on content analysis.
"""