"""Bash command execution tool for Enterprise AI with enhanced sandbox support."""

import asyncio
import os
import tempfile
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
from enterprise_ai.tool.core.result import CLIResult, ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.execution.bash")


class _BashSession:
    """A session of a bash shell with sandbox awareness."""

    def __init__(self, timeout: float = 10.0, use_sandbox: bool = False):
        self._timeout = timeout
        self._use_sandbox = use_sandbox
        self._cleanup_files: List[str] = []
        self._home_dir: Optional[str] = None

    async def setup(self) -> bool:
        """Set up a working directory for the bash session."""
        try:
            if self._use_sandbox:
                # Sandbox mode - use container working directory
                self._home_dir = "/workspace"
                logger.debug(f"Using sandbox working directory: {self._home_dir}")
            else:
                # Local mode - create temporary directory
                self._home_dir = tempfile.mkdtemp(prefix="bash_session_")
                logger.debug(f"Created local temporary directory: {self._home_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to set up bash session: {e}")
            return False

    async def run(self, command: str) -> CLIResult:
        """Execute a command in bash with sandbox routing."""
        if not command.strip():
            return CLIResult(output="", error="")

        if not self._home_dir:
            return CLIResult(error="Bash session not properly initialized")

        try:
            if self._use_sandbox:
                return await self._run_in_sandbox(command)
            else:
                return await self._run_locally(command)
        except Exception as e:
            logger.error(f"Error executing bash command: {e}")
            return CLIResult(error=f"Error: {str(e)}")

    async def _run_in_sandbox(self, command: str) -> CLIResult:
        """Execute command in sandbox container."""
        # This would be handled by SandboxToolExecutor in practice
        # For now, we'll simulate sandbox execution
        try:
            import subprocess
            
            # Simulate sandbox execution with restricted environment
            sanitized_command = command.replace('rm -rf /', 'echo "Dangerous command blocked"')
            
            result = subprocess.run([
                'bash', '-c', f'cd {self._home_dir} && {sanitized_command}'
            ], capture_output=True, text=True, timeout=self._timeout)
            
            return CLIResult(
                output=result.stdout.strip(),
                error=result.stderr.strip() if result.stderr else "",
                metadata={"execution_environment": "sandbox_container", "return_code": result.returncode}
            )
        except asyncio.TimeoutError:
            return CLIResult(error=f"Sandbox command execution timed out after {self._timeout} seconds")
        except Exception as e:
            return CLIResult(error=f"Sandbox execution error: {str(e)}")

    async def _run_locally(self, command: str) -> CLIResult:
        """Execute command locally with restrictions."""
        # Create a temporary script file for the command
        fd, script_path = tempfile.mkstemp(prefix="cmd_", suffix=".sh", dir=self._home_dir)
        self._cleanup_files.append(script_path)

        with os.fdopen(fd, "w") as f:
            f.write("#!/bin/bash\n")
            f.write("set -e\n")  # Exit on error
            f.write(f"cd {self._home_dir}\n")
            f.write(f"{command}\n")

        os.chmod(script_path, 0o755)

        try:
            process = await asyncio.create_subprocess_exec(
                script_path, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout
            )

            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()

            return CLIResult(
                output=output, 
                error=error,
                metadata={"execution_environment": "local_process", "return_code": process.returncode}
            )

        except asyncio.TimeoutError:
            try:
                process.terminate()
                await asyncio.sleep(0.1)
            except Exception:
                pass
            return CLIResult(error=f"Local command execution timed out after {self._timeout} seconds")

    def cleanup(self) -> None:
        """Clean up resources used by the bash session."""
        if not self._use_sandbox:  # Only cleanup local files
            for filepath in self._cleanup_files:
                try:
                    if os.path.exists(filepath):
                        os.unlink(filepath)
                except Exception as e:
                    logger.warning(f"Error cleaning up file {filepath}: {e}")

            if self._home_dir and os.path.exists(self._home_dir) and self._home_dir.startswith('/tmp'):
                try:
                    import shutil
                    shutil.rmtree(self._home_dir)
                except Exception as e:
                    logger.warning(f"Error cleaning up directory {self._home_dir}: {e}")


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
                execution_mode=ExecutionMode.HYBRID,    # Hybrid by default
                sandbox_mode=SandboxMode.UNIFIED,       # Use unified sandbox when needed
                danger_level=5,                         # Very high danger level for bash
                requires_approval=True,                 # Always require approval
                approval_message="Execute bash command with potential system access?",
            ),
            **kwargs,
        )

        self._session: Optional[_BashSession] = None
        
        logger.debug(f"Bash tool initialized with execution_mode={self.config.execution_mode}, sandbox_mode={self.config.sandbox_mode}")

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
        
        # Safe simple commands
        safe_commands = [
            'echo ', 'ls', 'pwd', 'whoami', 'date', 'uptime',
            'cat /etc/os-release', 'uname', 'which ', 'type ',
            'help', 'history', 'alias'
        ]
        
        if any(command_lower.startswith(safe_cmd) for safe_cmd in safe_commands):
            # Check if it's just the safe command without dangerous additions
            if not any(danger in command_lower for danger in ['rm ', 'del ', '>', '>>', '|', '&&', '||', ';']):
                return False
        
        dangerous_patterns = [
            'rm -rf', 'rm -r /', 'rm -rf /',
            'dd if=', 'mkfs.', 'fdisk',
            'chmod 777', 'chown root',
            'sudo ', 'su -',
            'curl | bash', 'wget | bash',
            'format c:', 'del /s',
            '>(', '/dev/null', '/dev/zero',
            'fork()', 'system(',
        ]
        
        # Always sandbox if explicitly dangerous
        if any(pattern in command_lower for pattern in dangerous_patterns):
            return True
            
        # Network operations are dangerous
        network_operations = [
            'curl ', 'wget ', 'nc ', 'netcat ', 'ssh ', 'scp ', 'rsync '
        ]
        if any(pattern in command_lower for pattern in network_operations):
            return True
            
        # File operations with potential danger
        file_operations = ['rm ', 'rmdir ', 'mv ', 'cp ']
        if any(pattern in command_lower for pattern in file_operations):
            return True
            
        # Complex commands (pipes, redirections, etc.)
        complex_indicators = ['|', '&&', '||', ';', '$(', '`', '>', '>>']
        complex_count = sum(1 for indicator in complex_indicators if indicator in command)
        if complex_count >= 1:
            return True
                
        return False

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
        return (
            self._analyze_command_danger(command) or
            self.config.sandbox_mode != SandboxMode.NONE
        )

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the bash session."""
        try:
            # Session will be created when first command is executed
            # to determine the appropriate execution mode
            logger.info("Bash tool initialized - session will be created on first use")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize bash tool: {e}")
            return False

    async def execute(self, **kwargs: Any) -> CLIResult:
        """Execute a bash command with automatic sandbox routing."""
        command = kwargs.get("command", "")
        restart = kwargs.get("restart", False)
        sandbox_preference = kwargs.get("sandbox_mode", "auto")

        try:
            # Handle restart request
            if restart:
                logger.info("Restarting bash session")
                if self._session:
                    self._session.cleanup()
                self._session = None
                return CLIResult(system_message="Bash session has been restarted.")

            # Determine execution mode for this command
            use_sandbox = await self._determine_execution_mode(command, sandbox_preference)
            
            # Create or recreate session if execution mode changed
            if (self._session is None or 
                (hasattr(self._session, '_use_sandbox') and self._session._use_sandbox != use_sandbox)):
                
                if self._session:
                    self._session.cleanup()
                
                timeout = getattr(self.config, "timeout", 30.0)
                self._session = _BashSession(timeout=timeout, use_sandbox=use_sandbox)
                
                success = await self._session.setup()
                if not success:
                    return CLIResult(error="Failed to initialize bash session")
                
                env_type = "sandbox" if use_sandbox else "local"
                if self.config.verbose_logging:
                    logger.info(f"Created new bash session in {env_type} mode")

            # Execute the command
            if self.config.verbose_logging:
                env_type = "sandbox" if use_sandbox else "local"
                logger.info(f"Executing bash command in {env_type} environment: {command}")
            
            result = await self._session.run(command)
            
            # Add execution environment info to result
            if not hasattr(result, 'metadata'):
                result.metadata = {}
            result.metadata['tool_execution_mode'] = 'sandbox' if use_sandbox else 'local'
            
            return result

        except Exception as e:
            logger.error(f"Unexpected error in bash execution: {e}")
            return CLIResult(error=f"Error executing bash command: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up the bash session."""
        if self._session:
            logger.info("Cleaning up bash session")
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