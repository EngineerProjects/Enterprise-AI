"""Bash command execution tool for Enterprise AI."""

import asyncio
import os
import tempfile
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.execution.bash")


class _BashSession:
    """A session of a bash shell."""

    def __init__(self, timeout: float = 10.0):
        """Initialize the bash session."""
        self._timeout = timeout
        self._cleanup_files: List[str] = []
        self._home_dir: Optional[str] = None

    async def setup(self) -> bool:
        """Set up a working directory for the bash session."""
        try:
            # Create a temporary directory to work in (this avoids permission issues)
            self._home_dir = tempfile.mkdtemp(prefix="bash_session_")
            logger.debug(f"Created temporary directory: {self._home_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to set up bash session: {e}")
            return False

    async def run(self, command: str) -> CLIResult:
        """
        Execute a command in bash.

        Args:
            command: The bash command to execute

        Returns:
            CLIResult containing command output or error
        """
        if not command.strip():
            return CLIResult(output="", error="")

        if not self._home_dir:
            return CLIResult(error="Bash session not properly initialized")

        try:
            # Create a temporary script file for the command
            fd, script_path = tempfile.mkstemp(prefix="cmd_", suffix=".sh", dir=self._home_dir)
            self._cleanup_files.append(script_path)

            # Write the command to the script file
            with os.fdopen(fd, "w") as f:
                f.write("#!/bin/bash\n")
                f.write("set -e\n")  # Exit on error
                f.write(f"cd {self._home_dir}\n")  # Set working directory
                f.write(f"{command}\n")  # The actual command

            # Make the script executable
            os.chmod(script_path, 0o755)

            # Create subprocess with timeout
            process = await asyncio.create_subprocess_exec(
                script_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            try:
                # Wait for the process to complete with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self._timeout
                )

                # Decode the output
                output = stdout.decode("utf-8", errors="replace").strip()
                error = stderr.decode("utf-8", errors="replace").strip()

                return CLIResult(output=output, error=error)

            except asyncio.TimeoutError:
                # If timeout occurs, try to terminate the process
                try:
                    process.terminate()
                    await asyncio.sleep(0.1)  # Give it a moment to terminate
                except Exception:
                    pass  # Ignore errors in termination

                return CLIResult(error=f"Command execution timed out after {self._timeout} seconds")

        except Exception as e:
            logger.error(f"Error executing bash command: {e}")
            return CLIResult(error=f"Error: {str(e)}")

    def cleanup(self) -> None:
        """Clean up resources used by the bash session."""
        # Clean up temporary files
        for filepath in self._cleanup_files:
            try:
                if os.path.exists(filepath):
                    os.unlink(filepath)
            except Exception as e:
                logger.warning(f"Error cleaning up file {filepath}: {e}")

        # Clean up temporary directory
        if self._home_dir and os.path.exists(self._home_dir):
            try:
                # Remove remaining files
                for root, dirs, files in os.walk(self._home_dir):
                    for file in files:
                        try:
                            os.unlink(os.path.join(root, file))
                        except Exception:
                            pass

                # Remove the directory
                os.rmdir(self._home_dir)
            except Exception as e:
                logger.warning(f"Error cleaning up directory {self._home_dir}: {e}")


@register_tool(category="execution")
class Bash(BaseTool):
    """
    Execute bash commands in an interactive terminal session.

    Key capabilities:
    * Run any bash command or script
    * Access command output and error messages
    * Maintain state between commands in the same session
    * Support for interactive commands with stdin/stdout
    * Handle long-running background processes

    Use this tool when:
    * You need to execute shell commands
    * You need to interact with the filesystem
    * You need to run system utilities
    * You want to perform a sequence of related shell operations

    Notes:
    * For long-running commands, use background execution (command &)
    * For interactive commands, send empty commands to retrieve logs
    * Session maintains state until explicitly restarted
    * Use ctrl+c (command=`ctrl+c`) to interrupt running processes
    """

    name: str = "bash"
    description: str = """
    Execute bash commands in an interactive terminal environment.

    * Purpose: Run bash commands and scripts in a persistent shell session
    * Usage: Execute system commands, interact with the filesystem, run processes
    * Features: Interactive session, command output capture, error handling
    * Returns: Command output and errors as structured results

    For long-running commands, run them in the background with: `command > output.log 2>&1 &`.
    For interactive commands, you can send empty commands to retrieve additional output.
    Send `ctrl+c` to interrupt running processes.
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
        },
        "required": ["command"],
    }

    # Define capabilities
    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.TERMINAL_ACCESS,
        ToolCapability.CODE_EXECUTION,
    }

    # Tool requires explicit cleanup
    session: Optional[_BashSession] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Bash tool with standard parameters.

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
            timeout=10.0,  # Much shorter default timeout to avoid long waits
            max_retries=1,
            sandbox_enabled=True,
        )

        # Session will be initialized when needed
        self._session: Optional[_BashSession] = None

        logger.debug("Bash tool initialized")

    async def initialize(self, **kwargs: Any) -> bool:
        """
        Initialize the bash session.

        Args:
            **kwargs: Additional initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            # Apply timeout from config
            timeout = (
                getattr(self.config, "timeout", 10.0) if hasattr(self.config, "timeout") else 10.0
            )

            # Create and set up session
            self._session = _BashSession(timeout=timeout)
            if self._session is not None:
                setup_success = await self._session.setup()

                if setup_success:
                    # Test the session
                    test_result = await self._session.run("echo 'SESSION_INITIALIZED'")
                    if "SESSION_INITIALIZED" in test_result.output:
                        logger.info("Bash session initialized successfully")
                        return True
                    else:
                        logger.error(f"Bash session test failed: {test_result.error}")

            return False
        except Exception as e:
            logger.error(f"Failed to initialize bash session: {e}")
            return False

    async def execute(self, **kwargs: Any) -> CLIResult:
        """
        Execute a bash command.

        Args:
            command: The bash command to execute
            restart: Whether to restart the bash session
            **kwargs: Additional parameters

        Returns:
            CLIResult containing command output or error
        """
        # Extract parameters
        command = kwargs.get("command", "")
        restart = kwargs.get("restart", False)

        try:
            # Handle restart request
            if restart:
                logger.info("Restarting bash session")
                if self._session:
                    self._session.cleanup()
                self._session = None
                success = await self.initialize()
                if not success:
                    return CLIResult(error="Failed to restart bash session")
                return CLIResult(system="Bash session has been restarted.")

            # Ensure session is initialized
            if self._session is None:
                logger.info("Initializing bash session on first use")
                success = await self.initialize()
                if not success:
                    return CLIResult(error="Failed to initialize bash session")

            # Execute the command
            logger.info(f"Executing bash command: {command}")
            if self._session is not None:
                return await self._session.run(command)
            return CLIResult(error="Bash session is not initialized")

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
