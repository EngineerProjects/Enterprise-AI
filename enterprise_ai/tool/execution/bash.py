"""Bash command execution tool for Enterprise AI."""

import asyncio
import os
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_logger

logger = get_logger("tool.execution.bash")


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # seconds
    _timeout: float = 120.0  # seconds
    _sentinel: str = "<<exit>>"

    def __init__(self) -> None:
        """Initialize the bash session."""
        self._started = False
        self._timed_out = False

    async def start(self) -> None:
        """Start the bash shell."""
        if self._started:
            return

        self._process = await asyncio.create_subprocess_shell(
            self.command,
            shell=True,
            bufsize=0,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True
        logger.debug("Bash session started")

    def stop(self) -> None:
        """Terminate the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return

        logger.debug("Terminating bash session")
        self._process.terminate()

    async def run(self, command: str) -> CLIResult:
        """
        Execute a command in the bash shell.

        Args:
            command: The bash command to execute

        Returns:
            CLIResult containing command output or error

        Raises:
            ToolError: If the session has timed out or is not started
        """
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return CLIResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            )

        logger.debug(f"Running bash command: {command}")

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # send command to the process
        self._process.stdin.write(command.encode() + f"; echo '{self._sentinel}'\n".encode())
        await self._process.stdin.drain()

        # read output from the process, until the sentinel is found
        try:
            async with asyncio.timeout(self._timeout):
                output = ""
                while True:
                    await asyncio.sleep(self._output_delay)

                    # Read from stdout - safer approach that works with most Python versions
                    chunk = await self._process.stdout.read(1024)
                    if not chunk:
                        break

                    output += chunk.decode()

                    if self._sentinel in output:
                        # strip the sentinel and break
                        output = output[: output.index(self._sentinel)]
                        break

                # Read any error output
                error_bytes = await self._process.stderr.read(1024)
                error = error_bytes.decode() if error_bytes else ""
        except asyncio.TimeoutError:
            self._timed_out = True
            logger.warning(f"Command timed out after {self._timeout} seconds")
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            ) from None

        if output.endswith("\n"):
            output = output[:-1]

        if error.endswith("\n"):
            error = error[:-1]

        logger.debug("Command execution completed")
        return CLIResult(output=output, error=error)


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
        super().__init__(
            name=name or self.name,
            description=description or self.description,
            parameters=parameters or self.parameters,
        )

        # Store tool configuration
        self.config = config or ToolConfig(
            timeout=120.0,  # Default timeout for bash commands
            max_retries=0,  # Bash commands should not be automatically retried
            sandbox_enabled=True,  # Run in sandbox environment by default
        )

        # Session will be initialized when needed
        self._session = None

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
            if self._session is None:
                self._session = _BashSession()
                await self._session.start()
                logger.info("Bash session initialized")

            return True
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
        command = kwargs.get("command")
        restart = kwargs.get("restart", False)

        # Apply timeout from config
        timeout = self.config.timeout if hasattr(self.config, "timeout") else 120.0

        try:
            # Handle restart request
            if restart:
                logger.info("Restarting bash session")
                if self._session:
                    self._session.stop()
                self._session = _BashSession()
                # Configure timeout from tool config
                self._session._timeout = timeout
                await self._session.start()

                return CLIResult(system="Bash session has been restarted.")

            # Ensure session is initialized
            if self._session is None:
                logger.info("Initializing bash session on first use")
                self._session = _BashSession()
                # Configure timeout from tool config
                self._session._timeout = timeout
                await self._session.start()

            # Validate command
            if command is not None:
                logger.info(f"Executing bash command: {command}")
                return await self._session.run(command)
            else:
                logger.warning("No command provided")
                return CLIResult(error="No command provided.")

        except ToolError as e:
            logger.error(f"Bash tool error: {e}")
            return CLIResult(error=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in bash execution: {e}")
            return CLIResult(error=f"Error executing bash command: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up the bash session."""
        if self._session:
            logger.info("Cleaning up bash session")
            try:
                self._session.stop()
                self._session = None
            except Exception as e:
                logger.warning(f"Error during bash session cleanup: {e}")
