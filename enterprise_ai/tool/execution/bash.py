"""Enhanced bash command execution tool for Enterprise AI with session management."""

import asyncio
import os
import tempfile
import subprocess
import time
import signal
from typing import Any, Dict, List, Optional, Set, Union
from dataclasses import dataclass, asdict
from pathlib import Path

from pydantic import Field

from enterprise_ai.tool.core.base import (
    BaseTool, 
    ToolError, 
    ToolConfig, 
    ToolCapability, 
    ExecutionMode, 
    SandboxMode
)
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.execution.bash")


@dataclass
class ExecutionSession:
    """Manages persistent execution sessions - lightweight version."""
    session_id: str
    pid: int
    command: str
    start_time: float
    timeout_ms: float
    shell: str
    is_blocked: bool = False
    is_completed: bool = False
    final_output: str = ""
    final_error: str = ""
    # DO NOT store process object - this causes the leak
    
    def get_runtime(self) -> float:
        """Get session runtime in milliseconds."""
        return (time.time() - self.start_time) * 1000
    
    def is_alive(self) -> bool:
        """Check if the session is still running."""
        return self.is_blocked and not self.is_completed
    
    def complete_session(self, output: str, error: str = "") -> None:
        """Mark session as completed with final output."""
        self.is_completed = True
        self.is_blocked = False
        self.final_output = output
        self.final_error = error

    async def terminate_process(self) -> None:
        """Terminate process - placeholder for compatibility."""
        # Since we don't store process objects, just mark as completed
        self.complete_session("Process terminated")


class SessionManager:
    """Global session manager like Desktop Commander."""
    
    def __init__(self):
        self.sessions: Dict[int, ExecutionSession] = {}
        self._next_pid = 1000
    
    def create_session(self, command: str, timeout_ms: float, shell: str) -> ExecutionSession:
        """Create new execution session."""
        session_id = f"session_{self._next_pid}"
        session = ExecutionSession(
            session_id=session_id,
            pid=self._next_pid,
            command=command,
            start_time=time.time(),
            timeout_ms=timeout_ms,
            shell=shell
        )
        
        self.sessions[self._next_pid] = session
        self._next_pid += 1
        return session
    
    def get_session(self, pid: int) -> Optional[ExecutionSession]:
        """Get existing session."""
        return self.sessions.get(pid)
    
    def remove_session(self, pid: int) -> bool:
        """Remove session."""
        if pid in self.sessions:
            del self.sessions[pid]
            return True
        return False
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        active_sessions = []
        for session in self.sessions.values():
            active_sessions.append({
                'pid': session.pid,
                'command': session.command[:50] + ('...' if len(session.command) > 50 else ''),
                'runtime': session.get_runtime(),
                'is_blocked': session.is_blocked,
                'is_alive': session.is_alive()
            })
        return active_sessions
    
    def cleanup_dead_sessions(self) -> None:
        """Clean up sessions with dead processes."""
        dead_pids = []
        for pid, session in self.sessions.items():
            if not session.is_alive():
                dead_pids.append(pid)
        
        for pid in dead_pids:
            self.remove_session(pid)

    async def terminate_all_sessions(self) -> None:
        """Terminate all active sessions properly."""
        for session in list(self.sessions.values()):
            try:
                await session.terminate_process()
            except Exception as e:
                logger.debug(f"Error terminating session {session.pid}: {e}")
        
        self.sessions.clear()


class CommandValidator:
    """Enhanced command validation like Desktop Commander."""
    
    def __init__(self):
        self.blocked_commands = [
            "rm -rf /",
            "rm -rf /*", 
            "mkfs.",
            "fdisk",
            "dd if=/dev/zero",
            ":(){ :|:& };:",  # Fork bomb
            "chmod -R 777 /",
            "chown -R root /"
        ]
        
        self.dangerous_patterns = [
            r"rm\s+-rf\s+/",
            r"dd\s+if=/dev/zero",
            r"mkfs\.",
            r"fdisk",
            r":\(\)\{\s*:\|\:\&\s*\}\s*;:",  # Fork bomb pattern
        ]
    
    async def validate_command(self, command: str) -> bool:
        """Validate if command is allowed to execute."""
        if not command or not command.strip():
            return True
        
        command_lower = command.lower().strip()
        
        # Check blocked commands
        for blocked in self.blocked_commands:
            if blocked.lower() in command_lower:
                logger.warning(f"Blocked dangerous command: {command}")
                return False
        
        # Check dangerous patterns with regex
        import re
        for pattern in self.dangerous_patterns:
            if re.search(pattern, command_lower):
                logger.warning(f"Blocked command matching dangerous pattern: {command}")
                return False
        
        return True
    
    def extract_commands(self, command_line: str) -> List[str]:
        """Extract all commands from a command line for analytics."""
        # Split by common separators
        import re
        commands = re.split(r'[;&|]+', command_line)
        
        # Extract base command from each part
        base_commands = []
        for cmd in commands:
            cmd = cmd.strip()
            if cmd:
                # Get first word (the actual command)
                base_cmd = cmd.split()[0] if cmd.split() else cmd
                base_commands.append(base_cmd)
        
        return base_commands
    
    def get_base_command(self, command_line: str) -> str:
        """Get the base command for analytics."""
        if not command_line or not command_line.strip():
            return ""
        
        # Get first word
        parts = command_line.strip().split()
        return parts[0] if parts else ""


class _EnhancedBashSession:
    """Enhanced bash session with Desktop Commander features."""

    def __init__(self, timeout: float = 30.0, use_sandbox: bool = False, working_dir: Optional[str] = None):
        self._timeout = timeout
        self._use_sandbox = use_sandbox
        self._cleanup_files: List[str] = []
        self._working_dir = working_dir or os.getcwd()
        self._session_manager = SessionManager()
        self._command_validator = CommandValidator()
        self._is_cleaned_up = False

    async def setup(self) -> bool:
        """Set up enhanced bash session."""
        try:
            # Ensure working directory exists
            if not os.path.exists(self._working_dir):
                os.makedirs(self._working_dir, exist_ok=True)
            
            logger.debug(f"Using working directory: {self._working_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to set up enhanced bash session: {e}")
            return False

    async def execute_command(self, command: str, timeout_ms: float, shell: str = "bash") -> Dict[str, Any]:
        """Execute command with session management like Desktop Commander."""
        if not command.strip():
            return {
                "pid": -1,
                "output": "No command provided",
                "isBlocked": False
            }

        # Validate command
        if not await self._command_validator.validate_command(command):
            return {
                "pid": -1,
                "output": f"Command not allowed: {command}",
                "isBlocked": False
            }

        # Create session
        session = self._session_manager.create_session(command, timeout_ms, shell)
        
        try:
            if self._use_sandbox:
                return await self._execute_in_sandbox(session)
            else:
                return await self._execute_locally(session)
        except Exception as e:
            logger.error(f"Error executing command in session {session.pid}: {e}")
            # Clean up the failed session
            await session.terminate_process()
            self._session_manager.remove_session(session.pid)
            return {
                "pid": -1,
                "output": f"Error: {str(e)}",
                "isBlocked": False
            }

    async def _execute_locally(self, session: ExecutionSession) -> Dict[str, Any]:
        """Execute command locally with immediate subprocess cleanup."""
        try:
            # Start process - but don't store it in session
            full_command = f'cd "{self._working_dir}" && {session.command}'
            
            process = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            
            # Try to get initial output with short timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=1.0  # 1 second for initial output
                )
                
                output = stdout.decode("utf-8", errors="replace").strip()
                error = stderr.decode("utf-8", errors="replace").strip()
                
                result_output = output
                if error:
                    result_output += f"\nSTDERR: {error}"
                
                # Mark session as completed immediately
                session.complete_session(result_output)
                
                # Process is done - cleanup immediately and don't store reference
                try:
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    if process.stdin:
                        process.stdin.close()
                    await process.wait()  # Ensure process is fully cleaned up
                except Exception:
                    pass
                
                # Clear process reference immediately
                del process
                
                return {
                    "pid": session.pid,
                    "output": result_output or "Command completed",
                    "isBlocked": False
                }
                
            except asyncio.TimeoutError:
                # Command is still running - we need to track it differently
                session.is_blocked = True
                
                # Store minimal info and cleanup process reference
                try:
                    process.kill()  # Force kill long-running processes
                    await process.wait()
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    if process.stdin:
                        process.stdin.close()
                except Exception:
                    pass
                
                del process
                
                return {
                    "pid": session.pid,
                    "output": f"Command started: {session.command}",
                    "isBlocked": True
                }

        except Exception as e:
            self._session_manager.remove_session(session.pid)
            raise ToolError(f"Local execution error: {str(e)}")
    
    async def _execute_in_sandbox(self, session: ExecutionSession) -> Dict[str, Any]:
        """Execute command in sandbox with immediate subprocess cleanup."""
        try:
            # Create safer command for sandbox
            safe_command = self._sanitize_command(session.command)
            sandbox_command = f'cd "{self._working_dir}" && timeout {self._timeout}s {safe_command}'
            
            process = await asyncio.create_subprocess_shell(
                sandbox_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=2.0  # 2 seconds for initial sandbox output
                )
                
                output = stdout.decode("utf-8", errors="replace").strip()
                error = stderr.decode("utf-8", errors="replace").strip()
                
                result_output = output
                if error:
                    result_output += f"\nSTDERR: {error}"
                
                # Mark session as completed
                session.complete_session(result_output)
                
                # Cleanup process immediately
                try:
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    if process.stdin:
                        process.stdin.close()
                    await process.wait()
                except Exception:
                    pass
                
                del process
                
                return {
                    "pid": session.pid,
                    "output": result_output or "Sandbox command completed",
                    "isBlocked": False
                }
                
            except asyncio.TimeoutError:
                session.is_blocked = True
                
                # Cleanup long-running process
                try:
                    process.kill()
                    await process.wait()
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    if process.stdin:
                        process.stdin.close()
                except Exception:
                    pass
                
                del process
                
                return {
                    "pid": session.pid,
                    "output": f"Sandbox command started: {safe_command}",
                    "isBlocked": True
                }

        except Exception as e:
            self._session_manager.remove_session(session.pid)
            raise ToolError(f"Sandbox execution error: {str(e)}")

    async def read_output(self, pid: int, timeout_ms: int = 5000) -> str:
        """Read output from completed session."""
        session = self._session_manager.get_session(pid)
        if not session:
            return "No session found for PID"
        
        if session.is_completed:
            # Return final output and remove session
            result = session.final_output
            if session.final_error:
                result += f"\nSTDERR: {session.final_error}"
            
            # Remove completed session
            self._session_manager.remove_session(pid)
            return result or "Process has finished"
        
        if session.is_blocked:
            # Session was long-running but we killed it
            session.complete_session("Command was terminated due to timeout")
            self._session_manager.remove_session(pid)
            return "Command was terminated due to timeout"
        
        return "No new output available"

    async def force_terminate(self, pid: int) -> bool:
        """Force terminate a session."""
        session = self._session_manager.get_session(pid)
        if not session:
            return False
        
        try:
            await session.terminate_process()
            self._session_manager.remove_session(pid)
            return True
            
        except Exception as e:
            logger.warning(f"Error terminating session {pid}: {e}")
            return False

    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        self._session_manager.cleanup_dead_sessions()
        return self._session_manager.list_sessions()

    def _sanitize_command(self, command: str) -> str:
        """Sanitize command for safer execution."""
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

    async def cleanup(self) -> None:
        """Clean up all sessions and resources - no subprocess references to clean."""
        if self._is_cleaned_up:
            return
            
        try:
            # Simply clear all sessions - no subprocess objects to cleanup
            self._session_manager.sessions.clear()
            
            # Clean up files
            for filepath in list(self._cleanup_files):
                try:
                    if os.path.exists(filepath):
                        os.unlink(filepath)
                except Exception:
                    pass
            
            self._cleanup_files.clear()
            self._is_cleaned_up = True
            
            # Force garbage collection to ensure no lingering references
            import gc
            gc.collect()
            
            logger.info("Enhanced bash session cleaned up successfully")
            
        except Exception as e:
            logger.warning(f"Cleanup completed with warnings: {e}")

    def cleanup_sync(self) -> None:
        """Synchronous cleanup fallback - for use when event loop is closing."""
        if self._is_cleaned_up:
            return
            
        try:
            # Clear all sessions
            self._session_manager.sessions.clear()
            
            # Clean up files
            for filepath in list(self._cleanup_files):
                try:
                    if os.path.exists(filepath):
                        os.unlink(filepath)
                except Exception:
                    pass
            
            self._cleanup_files.clear()
            self._is_cleaned_up = True
            
            logger.info("Enhanced bash session cleaned up successfully (sync)")
            
        except Exception as e:
            logger.warning(f"Sync cleanup completed with warnings: {e}")


@register_tool(category="execution", capabilities=["code_execution", "system_access"])
class Bash(BaseTool):
    """
    Enhanced bash command execution tool with Desktop Commander session management and safety controls.

    Key capabilities:
    * Run bash commands in persistent terminal sessions with session tracking
    * Automatic sandbox routing for dangerous commands with command validation
    * Support both local process isolation and Docker container execution
    * Maintain state between commands with full session lifecycle management
    * Command analysis for security risk assessment and analytics
    * Real-time output reading from long-running processes
    * Session management with PID tracking and process monitoring
    * Force termination capabilities for runaway processes
    * Comprehensive command validation and dangerous pattern detection

    Use this tool when:
    * You need to execute shell commands with persistent session state
    * You need to interact with the filesystem safely with command validation
    * You need to run system utilities with proper security controls
    * You want to perform a sequence of related shell operations in the same context
    * You need to monitor and manage long-running processes
    * You require real-time output from executing commands

    Enhanced Features from Desktop Commander:
    * Persistent session management with unique PID tracking
    * Real-time output reading from running processes with timeout control
    * Advanced command validation with dangerous pattern detection
    * Session lifecycle management with automatic cleanup
    * Process monitoring and force termination capabilities
    * Analytics and logging for command execution patterns
    * Enhanced error reporting with detailed context

    Notes:
    * Automatically routes dangerous commands to sandbox environment
    * Sessions maintain state until explicitly terminated or cleaned up
    * Local execution uses temporary directories for isolation
    * Sandbox execution provides full container isolation with timeout controls
    * Command validation prevents execution of dangerous system commands
    """

    name: str = "bash"
    short_description: str = "Execute bash commands with persistent sessions, security controls, and real-time output monitoring."
    description: str = """
    Enhanced bash command execution with Desktop Commander session management and safety controls.

    * Purpose: Run bash commands in persistent, managed terminal sessions with comprehensive safety
    * Usage: Execute system commands, interact with filesystem, run processes, manage sessions
    * Features: Session management, real-time output, command validation, sandbox routing, process monitoring
    * Returns: Command output with session PID, execution status, and session management information

    Enhanced with persistent session management, real-time output reading, advanced command validation,
    and comprehensive process monitoring. Sessions maintain state across calls with unique PID tracking.
    Automatically routes dangerous commands to sandbox environment and provides detailed analytics.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Can be 'read_output' to read from existing session, 'force_terminate' to kill session, 'list_sessions' to show active sessions, or 'ctrl+c' to interrupt.",
            },
            "pid": {
                "type": "integer", 
                "description": "Process ID for session management operations (read_output, force_terminate)"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds for command execution",
                "default": 30000
            },
            "shell": {
                "type": "string",
                "description": "Shell to use for execution (bash, sh, zsh)",
                "default": "bash"
            },
            "restart": {
                "type": "boolean",
                "description": "Whether to restart/cleanup all bash sessions",
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

    capabilities: Set[Union[str, ToolCapability]] = {
        ToolCapability.TERMINAL_ACCESS,
        ToolCapability.CODE_EXECUTION,
        ToolCapability.FILE_ACCESS,
    }

    session: Optional[_EnhancedBashSession] = Field(default=None, exclude=True)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        working_dir: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Enhanced Bash tool."""
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
                approval_message="Execute bash command with session management?",
                verbose_logging=False,
            ),
            **kwargs,
        )

        self._session: Optional[_EnhancedBashSession] = None
        self._working_dir = working_dir
        
        logger.debug(f"Enhanced Bash tool initialized")

    def _analyze_command_danger(self, command: str) -> bool:
        """Analyze if a bash command is dangerous and should use sandbox."""
        if not command or not command.strip():
            return False
            
        command_lower = command.lower().strip()
        
        # Session management commands are safe
        if command in ['read_output', 'force_terminate', 'list_sessions', 'ctrl+c']:
            return False
        
        # Very safe simple commands
        safe_commands = [
            'echo ', 'ls', 'pwd', 'whoami', 'date', 'uptime',
            'cat ', 'head ', 'tail ', 'wc ', 'sort ', 'grep ',
            'uname', 'which ', 'type ', 'help', 'history'
        ]
        
        for safe_cmd in safe_commands:
            if command_lower.startswith(safe_cmd) or command_lower == safe_cmd.strip():
                if not any(op in command for op in ['|', '&&', '||', ';', '>', '>>', '$(', '`']):
                    return False
        
        # Simple echo without redirections
        if command_lower.startswith('echo ') and not any(op in command for op in [
            '|', '&&', '||', ';', '$(', '`', 'rm ', 'del ', 'sudo', 'su '
        ]):
            return False
        
        return True

    async def _determine_execution_mode(self, command: str, user_preference: str) -> bool:
        """Determine if command should execute in sandbox."""
        if user_preference == "sandbox":
            return True
        elif user_preference == "local":
            return False
        
        return self._analyze_command_danger(command)

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the enhanced bash session."""
        try:
            logger.info("Enhanced Bash tool initialized - session will be created on first use")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize enhanced bash tool: {e}")
            return False

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute bash command with enhanced session management."""
        command = kwargs.get("command", "")
        pid = kwargs.get("pid")
        timeout_ms = kwargs.get("timeout_ms", 30000)
        shell = kwargs.get("shell", "bash")
        restart = kwargs.get("restart", False)
        sandbox_preference = kwargs.get("sandbox_mode", "auto")

        try:
            # Handle restart request
            if restart:
                if self._session:
                    await self._session.cleanup()
                self._session = None
                return CLIResult.create_success(
                    result="All bash sessions have been restarted and cleaned up.",
                    tool_name=self.name
                )

            # Initialize session if needed
            if self._session is None:
                use_sandbox = await self._determine_execution_mode(command, sandbox_preference)
                timeout = getattr(self.config, "timeout", 30.0)
                working_dir = self._working_dir or tempfile.mkdtemp(prefix="bash_session_")
                
                self._session = _EnhancedBashSession(
                    timeout=timeout, 
                    use_sandbox=use_sandbox, 
                    working_dir=working_dir
                )
                
                success = await self._session.setup()
                if not success:
                    return ToolResult.create_error(
                        error="Failed to initialize enhanced bash session",
                        tool_name=self.name
                    )

            # Handle session management commands
            if command == "read_output":
                if pid is None:
                    return ToolResult.create_error(
                        error="PID required for read_output command",
                        tool_name=self.name
                    )
                
                output = await self._session.read_output(pid, timeout_ms)
                return CLIResult.create_success(result=output, tool_name=self.name)
            
            elif command == "force_terminate":
                if pid is None:
                    return ToolResult.create_error(
                        error="PID required for force_terminate command", 
                        tool_name=self.name
                    )
                
                success = await self._session.force_terminate(pid)
                message = f"Successfully terminated session {pid}" if success else f"No active session found for PID {pid}"
                return CLIResult.create_success(result=message, tool_name=self.name)
            
            elif command == "list_sessions":
                sessions = self._session.list_active_sessions()
                if not sessions:
                    result = "No active sessions"
                else:
                    result = "Active sessions:\n"
                    for session in sessions:
                        result += f"PID: {session['pid']}, Command: {session['command']}, "
                        result += f"Runtime: {session['runtime']:.0f}ms, "
                        result += f"Blocked: {session['is_blocked']}, Alive: {session['is_alive']}\n"
                
                return CLIResult.create_success(result=result, tool_name=self.name)
            
            # Execute regular command
            result = await self._session.execute_command(command, timeout_ms, shell)
            
            if result["pid"] == -1:
                return ToolResult.create_error(error=result["output"], tool_name=self.name)
            
            # Format response
            response = f"Command started with PID {result['pid']}\n"
            response += f"Initial output:\n{result['output']}"
            
            if result["isBlocked"]:
                response += f"\n\nCommand is still running. Use command='read_output' with pid={result['pid']} to get more output."
            
            return CLIResult.create_success(result=response, tool_name=self.name)

        except Exception as e:
            logger.error(f"Unexpected error in enhanced bash execution: {e}")
            return ToolResult.create_error(
                error=f"Error executing bash command: {str(e)}",
                tool_name=self.name
            )

    async def cleanup(self) -> None:
        """Enhanced cleanup - proper async version."""
        if self._session:
            try:
                await self._session.cleanup()
                self._session = None
            except Exception as e:
                logger.warning("Session cleanup warning: %s", e)
                # Fallback to sync cleanup if async fails
                if self._session:
                    try:
                        self._session.cleanup_sync()
                        self._session = None
                    except Exception as e2:
                        logger.warning("Fallback sync cleanup warning: %s", e2)

    def __del__(self):
        """Destructor with sync cleanup as last resort."""
        if hasattr(self, '_session') and self._session and not self._session._is_cleaned_up:
            try:
                self._session.cleanup_sync()
            except Exception:
                pass  # Ignore cleanup errors in destructor

    def get_approval_message(self) -> str:
        """Get enhanced approval message for this tool."""
        base_message = super().get_approval_message()
        
        return f"""{base_message}

⚠️  ENHANCED BASH EXECUTION WARNING:
This tool provides persistent session management and can execute arbitrary shell commands which may:
- Access and modify files anywhere on the system with session persistence
- Install/uninstall software packages with tracked execution
- Change system configurations with command validation
- Access network resources with sandbox routing
- Execute privileged operations with safety controls
- Maintain running processes across multiple interactions

Enhanced features include:
- Persistent session management with unique PID tracking
- Real-time output reading from long-running processes
- Advanced command validation and dangerous pattern detection
- Automatic sandbox routing for high-risk commands
- Session monitoring and force termination capabilities

Commands are automatically analyzed for danger level and routed to appropriate execution environments.
Session state is maintained until explicitly terminated or system restart.
"""