"""Python code execution tool for Enterprise AI."""

import asyncio
import multiprocessing
import sys
import traceback
from io import StringIO
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.execution.python")


@register_tool(category="execution")
class PythonExecute(BaseTool):
    """
    Execute Python code with safety controls and output capture.

    Key capabilities:
    * Execute arbitrary Python code in a sandboxed environment
    * Capture stdout and stderr output
    * Apply configurable execution timeouts
    * Provide detailed error reporting with traceback
    * Execute in isolated process for safety

    Use this tool when:
    * You need to run Python code dynamically
    * You need to capture print output from code execution
    * You want to test or debug Python snippets
    * You need to perform calculations or data processing

    Notes:
    * Only print outputs are visible, return values are not captured
    * Use print() statements to see calculation results
    * Execution happens in a separate process for isolation
    * Timeout will terminate long-running code
    """

    name: str = "python_execute"
    description: str = """
    Executes Python code in an isolated environment with output capture.

    * Purpose: Run Python code snippets safely with controlled execution
    * Usage: Execute code for calculations, testing, or data processing
    * Features: Output capture, timeout enforcement, error handling
    * Returns: The captured stdout output or error message with traceback

    Note: Only print outputs are visible, function return values are not captured.
    Use print statements to see results of your code execution.
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
                "default": 5,
            },
        },
        "required": ["code"],
    }

    # Define capabilities
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
        """
        Initialize the Python execution tool with standard parameters.

        Args:
            name: Override for tool name
            description: Override for tool description
            parameters: Override for tool parameters schema
            config: Tool configuration settings
            **kwargs: Additional keyword arguments
        """
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        # Store tool configuration
        self.config = config or ToolConfig(
            timeout=5.0,  # Default timeout for code execution
            max_retries=0,  # Code execution should not be automatically retried
            sandbox_enabled=True,  # Always run in sandbox environment
        )

        logger.debug("PythonExecute tool initialized")

    def _run_code(
        self, code: str, result_dict: Dict[str, Any], safe_globals: Dict[str, Any]
    ) -> None:
        """
        Execute Python code in a separate process with output capturing.

        Args:
            code: Python code to execute
            result_dict: Shared dictionary to store execution results
            safe_globals: Safe globals dictionary for execution
        """
        # Save original stdout and stderr
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        output_buffer = StringIO()
        error_buffer = StringIO()

        try:
            # Redirect output
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
            # Restore original stdout and stderr
            sys.stdout = original_stdout
            sys.stderr = original_stderr

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Executes the provided Python code with a timeout.

        Args:
            **kwargs: Keyword arguments including:
                code: The Python code to execute
                timeout: Maximum execution time in seconds (default: 5)

        Returns:
            ToolResult containing execution output or error message
        """
        # Extract parameters from kwargs
        code = kwargs.get("code")
        if not code:
            logger.warning("No code parameter provided")
            return ToolResult(error="Code parameter is required")

        # Get timeout from parameters or config
        param_timeout = kwargs.get("timeout")
        config_timeout = self.config.timeout if hasattr(self.config, "timeout") else 5
        timeout = param_timeout or config_timeout

        logger.info(f"Executing Python code with timeout: {timeout}s")
        logger.debug(f"Code to execute:\n{code}")

        try:
            with multiprocessing.Manager() as manager:
                # Create shared result dictionary
                result = manager.dict({"output": "", "error": None, "success": False})

                # Create a safe globals dictionary
                if isinstance(__builtins__, dict):
                    safe_globals = {"__builtins__": dict(__builtins__)}  # type: ignore
                else:
                    # In some Python environments, __builtins__ is a module, not a dict
                    safe_globals = {"__builtins__": dict(__builtins__.__dict__)}  # type: ignore

                # Execute in a separate process for isolation
                proc = multiprocessing.Process(
                    target=self._run_code, args=(code, result, safe_globals)
                )
                proc.start()
                proc.join(timeout)

                # Handle timeout
                if proc.is_alive():
                    logger.warning(f"Code execution timed out after {timeout} seconds")
                    proc.terminate()
                    proc.join(1)
                    return ToolResult(error=f"Execution timeout after {timeout} seconds")

                # Return successful result
                if result["success"]:
                    logger.info("Code execution completed successfully")
                    return ToolResult(output=result["output"])
                else:
                    # Return error result
                    logger.error(f"Code execution failed: {result['error']}")
                    return ToolResult(error=f"Execution error: {result['error']}")

        except Exception as e:
            logger.error(f"Unexpected error during code execution: {e}")
            return ToolResult(error=f"Internal execution error: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up any resources used by the tool."""
        # No persistent resources to clean up for this tool
        pass
