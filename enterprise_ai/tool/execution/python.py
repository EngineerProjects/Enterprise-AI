"""Python code execution tool."""

import multiprocessing
import sys
import traceback
from io import StringIO
from typing import Any, Dict, Optional

from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool


@register_tool(category="execution")
class PythonExecute(BaseTool):
    """A tool for executing Python code with timeout and safety restrictions."""

    name: str = "python_execute"
    description: str = "Executes Python code string. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results."
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
                "default": 5,
            },
        },
        "required": ["code"],
    }

    def _run_code(
        self, code: str, result_dict: Dict[str, Any], safe_globals: Dict[str, Any]
    ) -> None:
        """Execute Python code in a separate process with output capturing."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        output_buffer = StringIO()
        error_buffer = StringIO()

        try:
            sys.stdout = output_buffer
            sys.stderr = error_buffer

            # Execute the code
            try:
                exec(code, safe_globals, safe_globals)
                result_dict["output"] = output_buffer.getvalue()
                error_output = error_buffer.getvalue()
                result_dict["error"] = error_output if error_output else None
                result_dict["success"] = True
            except SyntaxError as e:
                # Capture syntax errors with traceback
                error_msg = f"SyntaxError: {str(e)}\n{traceback.format_exc()}"
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_msg
                result_dict["success"] = False
            except Exception as e:
                # Capture other exceptions
                error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                result_dict["output"] = output_buffer.getvalue()
                result_dict["error"] = error_msg
                result_dict["success"] = False

        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Executes the provided Python code with a timeout.

        Args:
            **kwargs: Keyword arguments including:
                code: The Python code to execute.
                timeout: Maximum execution time in seconds (default: 5).

        Returns:
            ToolResult containing execution output or error message.
        """
        # Extract parameters from kwargs
        code = kwargs.get("code")
        if not code:
            return ToolResult(error="Code parameter is required")

        timeout = kwargs.get("timeout", 5)

        with multiprocessing.Manager() as manager:
            result = manager.dict({"output": "", "error": None, "success": False})

            # Create a safe globals dictionary
            if isinstance(__builtins__, dict):
                safe_globals = {"__builtins__": dict(__builtins__)}  # type: ignore
            else:
                # In some Python environments, __builtins__ is a module, not a dict
                safe_globals = {"__builtins__": dict(__builtins__.__dict__)}  # type: ignore

            # Execute in a separate process for isolation
            proc = multiprocessing.Process(target=self._run_code, args=(code, result, safe_globals))
            proc.start()
            proc.join(timeout)

            # Handle timeout
            if proc.is_alive():
                proc.terminate()
                proc.join(1)
                return ToolResult(error=f"Execution timeout after {timeout} seconds")

            # Return successful result
            if result["success"]:
                return ToolResult(output=result["output"])
            else:
                # Return error result
                return ToolResult(error=f"Execution error: {result['error']}")
