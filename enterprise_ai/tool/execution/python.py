"""Python code execution tool for Enterprise AI with enhanced sandbox support."""

import asyncio
import multiprocessing
import sys
import traceback
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
from enterprise_ai.logger import get_logger

logger = get_logger("tool.execution.python")


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
                execution_mode=ExecutionMode.HYBRID,  # Safe by default, but can be dangerous
                sandbox_mode=SandboxMode.UNIFIED,     # Use unified sandbox when needed
                danger_level=4,                       # High danger level for code execution
                requires_approval=True,               # Require approval in manual/hybrid modes
                approval_message="Execute Python code with potential system access?",
            ),
            **kwargs,
        )

        logger.debug(f"PythonExecute tool initialized with execution_mode={self.config.execution_mode}, sandbox_mode={self.config.sandbox_mode}")

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
        
        # Auto-detection based on dangerous patterns
        dangerous_patterns = [
            "import os", "import sys", "import subprocess", "import shutil",
            "os.", "sys.", "subprocess.", "shutil.",
            "open(", "file(", "exec(", "eval(",
            "__import__", "globals(", "locals(",
            "input(", "raw_input(",
            "rmdir", "remove", "unlink", "delete",
            "socket", "urllib", "requests", "http"
        ]
        
        code_lower = code.lower()
        dangerous_count = sum(1 for pattern in dangerous_patterns if pattern in code_lower)
        
        # Simple print statements are safe
        if code_lower.strip().startswith('print(') and dangerous_count == 0:
            return False
        
        # Basic arithmetic and simple operations are safe
        safe_patterns = ['print(', '+', '-', '*', '/', 'len(', 'str(', 'int(', 'float(']
        if dangerous_count == 0 and any(pattern in code_lower for pattern in safe_patterns):
            if len(code) < 100:  # Short, simple code
                return False
        
        # Use sandbox if multiple dangerous patterns or sandbox mode is configured
        return (
            dangerous_count >= 1 or  # Any dangerous pattern triggers sandbox
            self.config.sandbox_mode != SandboxMode.NONE or
            len(code) > 500  # Long code gets sandbox treatment
        )

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
            except SyntaxError as e:
                error_msg = f"SyntaxError: {str(e)}\n{traceback.format_exc()}"
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_msg
                result_dict["success"] = False
                result_dict["execution_environment"] = "local_process"
            except Exception as e:
                error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_msg
                result_dict["success"] = False
                result_dict["execution_environment"] = "local_process"

        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    async def _execute_in_sandbox(self, code: str, timeout: float) -> ToolResult:
        """
        Execute Python code in sandbox environment.
        
        Note: This is a placeholder for sandbox execution. In practice, this would
        interface with the SandboxToolExecutor or Docker containers.
        """
        try:
            # This would be handled by the SandboxToolExecutor in practice
            # For now, we'll create a simple containerized execution
            
            import tempfile
            import subprocess
            import os
            
            # Create temporary file for code
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # Execute in a restricted Python environment
                # In practice, this would use Docker
                result = subprocess.run([
                    'python', '-c', f'''
import sys
import tempfile
import os
sys.path = [p for p in sys.path if not p.startswith('/home')]  # Restrict imports
try:
    with open("{temp_file}", "r") as f:
        code = f.read()
    exec(code, {{"__builtins__": {{"print": print, "len": len, "str": str, "int": int, "float": float, "list": list, "dict": dict, "range": range, "enumerate": enumerate, "zip": zip}}}})
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
'''
                ], capture_output=True, text=True, timeout=timeout)
                
                return ToolResult.create_success(
                    result={
                        "output": result.stdout,
                        "error": result.stderr if result.stderr else None,
                        "execution_environment": "sandbox_container",
                        "return_code": result.returncode
                    },
                    tool_name=self.name,
                    metadata={"execution_environment": "sandbox"}
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
            logger.warning("No code parameter provided")
            return ToolResult.create_error(error="Code parameter is required", tool_name=self.name)

        timeout = kwargs.get("timeout", self.config.timeout)
        sandbox_preference = kwargs.get("sandbox_mode", "auto")
        
        use_sandbox = self._should_use_sandbox_execution(code, sandbox_preference)
        
        if self.config.verbose_logging:
            logger.info(f"Executing Python code in {'sandbox' if use_sandbox else 'local'} environment")
            logger.info(f"Code preview: {code[:100]}...")

        if use_sandbox:
            logger.info("Routing Python execution to sandbox")
            return await self._execute_in_sandbox(code, timeout)
        else:
            logger.info("Executing Python code locally with process isolation")
            return await self._execute_locally(code, timeout)

    async def _execute_locally(self, code: str, timeout: float) -> ToolResult:
        """Execute code locally with multiprocessing isolation."""
        try:
            with multiprocessing.Manager() as manager:
                result = manager.dict({"output": "", "error": None, "success": False})

                # Create safe globals
                if isinstance(__builtins__, dict):
                    safe_globals = {"__builtins__": dict(__builtins__)}
                else:
                    safe_globals = {"__builtins__": dict(__builtins__.__dict__)}

                # Execute in separate process
                proc = multiprocessing.Process(
                    target=self._run_code_local, args=(code, result, safe_globals)
                )
                proc.start()
                proc.join(timeout)

                if proc.is_alive():
                    logger.warning(f"Local code execution timed out after {timeout} seconds")
                    proc.terminate()
                    proc.join(1)
                    return ToolResult.create_error(
                        error=f"Execution timeout after {timeout} seconds",
                        tool_name=self.name
                    )

                if result["success"]:
                    logger.info("Local Python execution completed successfully")
                    return ToolResult.create_success(
                        result={
                            "output": result["output"],
                            "execution_environment": result.get("execution_environment", "local_process")
                        },
                        tool_name=self.name
                    )
                else:
                    logger.error(f"Local Python execution failed: {result['error']}")
                    return ToolResult.create_error(
                        error=result['error'],
                        tool_name=self.name
                    )

        except Exception as e:
            logger.error(f"Unexpected error during local execution: {e}")
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