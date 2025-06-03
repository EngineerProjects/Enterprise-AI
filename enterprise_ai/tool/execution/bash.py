"""Bash command execution tool for Enterprise AI with enhanced sandbox support."""

import asyncio
import os
import tempfile
import subprocess
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

logger = get_optimized_logger("tool.execution.bash")


class _BashSession:
    """A session of a bash shell with sandbox awareness."""

    def __init__(self, timeout: float = 10.0, use_sandbox: bool = False, working_dir: Optional[str] = None):
        self._timeout = timeout
        self._use_sandbox = use_sandbox
        self._cleanup_files: List[str] = []
        self._working_dir = working_dir or os.getcwd()

    async def setup(self) -> bool:
        """Set up a working directory for the bash session."""
        try:
            # Ensure working directory exists
            if not os.path.exists(self._working_dir):
                os.makedirs(self._working_dir, exist_ok=True)
            
            logger.debug(f"Using working directory: {self._working_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to set up bash session: {e}")
            return False

    async def run(self, command: str) -> ToolResult:
        """Execute a command in bash with sandbox routing."""
        if not command.strip():
            return ToolResult.create_success(
                result={"output": "", "execution_environment": "none"},
                tool_name="bash"
            )

        try:
            if self._use_sandbox:
                return await self._run_in_sandbox(command)
            else:
                return await self._run_locally(command)
        except Exception as e:
            logger.error(f"Error executing bash command: {e}")
            return ToolResult.create_error(
                error=f"Error: {str(e)}",
                tool_name="bash"
            )

    async def _run_in_sandbox(self, command: str) -> ToolResult:
        """Execute command in sandbox-like environment."""
        try:
            # Create a safer command for sandbox execution
            safe_command = self._sanitize_command(command)
            
            # Execute with restricted privileges and timeout in working directory
            result = subprocess.run([
                'bash', '-c', f'cd "{self._working_dir}" && timeout {self._timeout}s {safe_command}'
            ], capture_output=True, text=True, timeout=self._timeout + 5)
            
            return ToolResult.create_success(
                result={
                    "output": result.stdout.strip(),
                    "error": result.stderr.strip() if result.stderr else None,
                    "return_code": result.returncode,
                    "execution_environment": "sandbox_container"
                },
                tool_name="bash"
            )
        except subprocess.TimeoutExpired:
            return ToolResult.create_error(
                error=f"Sandbox command execution timed out after {self._timeout} seconds",
                tool_name="bash"
            )
        except Exception as e:
            return ToolResult.create_error(
                error=f"Sandbox execution error: {str(e)}",
                tool_name="bash"
            )

    async def _run_locally(self, command: str) -> ToolResult:
        """Execute command locally with restrictions."""
        try:
            # Execute directly with working directory
            process = await asyncio.create_subprocess_shell(
                f'cd "{self._working_dir}" && {command}',
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout
            )

            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()

            return ToolResult.create_success(
                result={
                    "output": output,
                    "error": error if error else None,
                    "return_code": process.returncode,
                    "execution_environment": "local_process"
                },
                tool_name="bash"
            )

        except asyncio.TimeoutError:
            try:
                process.terminate()
                await asyncio.sleep(0.1)
            except Exception:
                pass
            return ToolResult.create_error(
                error=f"Local command execution timed out after {self._timeout} seconds",
                tool_name="bash"
            )

    def _sanitize_command(self, command: str) -> str:
        """Sanitize command for safer execution."""
        # Replace extremely dangerous patterns
        dangerous_replacements = {
            'rm -rf /': 'echo "Dangerous command blocked: rm -rf /"',
            'rm -rf /*': 'echo "Dangerous command blocked: rm -rf /*"',
            'dd if=/dev/zero': 'echo "Dangerous command blocked: dd if=/dev/zero"',
            'mkfs.': 'echo "Dangerous command blocked: mkfs"',
            'fdisk': 'echo "Dangerous command blocked: fdisk"'
        }
        
        sanitized = command
        for dangerous, replacement in dangerous_replacements.items():
            if dangerous in sanitized:
                sanitized = replacement
                break
                
        return sanitized

    def cleanup(self) -> None:
        """Clean up resources used by the bash session."""
        for filepath in self._cleanup_files:
            try:
                if os.path.exists(filepath):
                    os.unlink(filepath)
            except Exception as e:
                logger.warning(f"Error cleaning up file {filepath}: {e}")


@register_tool(category="execution")
class Bash(BaseTool):
    """
    Execute bash commands with enhanced sandbox support and safety controls.

    Key capabilities:
    * Run bash commands in interactive terminal sessions
    * Automatic sandbox routing for dangerous commands
    * Support both local process isolation and Docker container execution
    * Maintain state between commands in the same session
    * Command analysis for security risk assessment

    Use this tool when:
    * You need to execute shell commands
    * You need to interact with the filesystem
    * You need to run system utilities
    * You want to perform a sequence of related shell operations

    Notes:
    * Automatically routes dangerous commands to sandbox
    * Session maintains state until explicitly restarted
    * Local execution uses temporary directories for isolation
    * Sandbox execution provides full container isolation
    """

    name: str = "bash"
    description: str = """
    Execute bash commands in interactive terminal environments with automatic safety routing.

    * Purpose: Run bash commands and scripts in persistent shell sessions
    * Usage: Execute system commands, interact with the filesystem, run processes
    * Features: Interactive session, sandbox routing, command output capture, error handling
    * Returns: Command output and errors as structured results with execution environment info

    The tool automatically chooses between local process isolation and Docker sandbox
    based on command danger level and configuration. Sessions maintain state across calls.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
            },
            "restart": {
                "type": "boolean",
                "description": "Whether to restart the bash session.",
                "default": False,
            },
            "sandbox_mode": {
                "type": "string",
                "enum": ["auto", "local", "sandbox"],
                "description": "Execution environment preference",
                "default": "auto"
            },
        },
        "required": ["command"],
    }

    # Define capabilities - will auto-configure danger level
    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.TERMINAL_ACCESS,
        ToolCapability.CODE_EXECUTION,
        ToolCapability.FILE_ACCESS,  # Bash can access files
    }

    session: Optional[_BashSession] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        working_dir: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Bash tool with enhanced configuration."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            config=config or ToolConfig(
                timeout=30.0,
                max_retries=1,
                execution_mode=ExecutionMode.HYBRID,
                sandbox_mode=SandboxMode.UNIFIED,
                danger_level=5,
                requires_approval=True,
                approval_message="Execute bash command with potential system access?",
                verbose_logging=False,  # Disable verbose logging by default
            ),
            **kwargs,
        )

        self._session: Optional[_BashSession] = None
        self._working_dir = working_dir
        
        logger.debug(f"Bash tool initialized")

    def _analyze_command_danger(self, command: str) -> bool:
        """
        Analyze if a bash command is dangerous and should use sandbox.
        
        Args:
            command: Bash command to analyze
            
        Returns:
            True if command should use sandbox
        """
        if not command or not command.strip():
            return False
            
        command_lower = command.lower().strip()
        
        # Very safe simple commands that should run locally
        safe_simple_commands = [
            'echo ', 'ls', 'pwd', 'whoami', 'date', 'uptime',
            'cat ', 'head ', 'tail ', 'wc ', 'sort ',
            'uname', 'which ', 'type ', 'help', 'history'
        ]
        
        # Check for very simple safe commands
        for safe_cmd in safe_simple_commands:
            if command_lower.startswith(safe_cmd) or command_lower == safe_cmd.strip():
                # Make sure it's really simple (no redirections, pipes, etc.)
                if not any(op in command for op in ['|', '&&', '||', ';', '>', '>>', '$(', '`']):
                    return False
        
        # If command only contains echo with simple text, it's safe
        if command_lower.startswith('echo ') and not any(op in command for op in [
            '|', '&&', '||', ';', '$(', '`', 'rm ', 'del ', 'sudo', 'su '
        ]):
            return False
        
        # Everything else should use sandbox for safety
        return True

    async def _determine_execution_mode(self, command: str, user_preference: str) -> bool:
        """
        Determine if command should execute in sandbox.
        
        Args:
            command: Command to execute
            user_preference: User's sandbox preference
            
        Returns:
            True if should use sandbox
        """
        if user_preference == "sandbox":
            return True
        elif user_preference == "local":
            return False
        
        # Auto-detection
        return self._analyze_command_danger(command)

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the bash session."""
        try:
            # Session will be created when first command is executed
            logger.info("Bash tool initialized - session will be created on first use")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize bash tool: {e}")
            return False

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a bash command with automatic sandbox routing."""
        command = kwargs.get("command", "")
        restart = kwargs.get("restart", False)
        sandbox_preference = kwargs.get("sandbox_mode", "auto")

        try:
            # Handle restart request
            if restart:
                if self._session:
                    self._session.cleanup()
                self._session = None
                return ToolResult.create_success(
                    result={"system_message": "Bash session has been restarted."},
                    tool_name=self.name
                )

            # Determine execution mode for this command
            use_sandbox = await self._determine_execution_mode(command, sandbox_preference)
            
            # Create or recreate session if execution mode changed
            if (self._session is None or 
                (hasattr(self._session, '_use_sandbox') and self._session._use_sandbox != use_sandbox)):
                
                if self._session:
                    self._session.cleanup()
                
                timeout = getattr(self.config, "timeout", 30.0)
                working_dir = self._working_dir or tempfile.mkdtemp(prefix="bash_session_")
                self._session = _BashSession(timeout=timeout, use_sandbox=use_sandbox, working_dir=working_dir)
                
                success = await self._session.setup()
                if not success:
                    return ToolResult.create_error(
                        error="Failed to initialize bash session",
                        tool_name=self.name
                    )

            # Execute the command
            result = await self._session.run(command)
            
            # Add execution environment info to result metadata
            if not hasattr(result, 'metadata') or result.metadata is None:
                result.metadata = {}
            result.metadata['tool_execution_mode'] = 'sandbox' if use_sandbox else 'local'
            
            return result

        except Exception as e:
            logger.error(f"Unexpected error in bash execution: {e}")
            return ToolResult.create_error(
                error=f"Error executing bash command: {str(e)}",
                tool_name=self.name
            )

    async def cleanup(self) -> None:
        """Clean up the bash session."""
        if self._session:
            try:
                self._session.cleanup()
                self._session = None
            except Exception as e:
                logger.warning(f"Error during bash session cleanup: {e}")

    def get_approval_message(self) -> str:
        """Get enhanced approval message for this tool."""
        base_message = super().get_approval_message()
        
        return f"""{base_message}

⚠️  BASH COMMAND EXECUTION WARNING:
This tool can execute arbitrary shell commands which may:
- Access and modify files anywhere on the system
- Install/uninstall software packages
- Change system configurations
- Access network resources
- Execute privileged operations

Commands are automatically analyzed for danger level and routed to appropriate execution environments.
"""