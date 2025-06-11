"""
Process management tool for Enterprise AI.

This module provides comprehensive process management capabilities including
listing, monitoring, and controlling system processes.
"""

import os
import signal
import subprocess
import time
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.execution.process")


class ProcessInfo(BaseModel):
    """Process information model."""
    pid: int
    name: str
    status: str
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_rss: Optional[int] = None
    create_time: Optional[float] = None
    command: Optional[str] = None


class SessionInfo(BaseModel):
    """Terminal session information model."""
    pid: int
    command: str
    status: str
    start_time: str
    duration: str


@register_tool(category="execution", capabilities=["process_management", "system_monitoring"])
class ProcessManagerTool(BaseTool):
    """
    Comprehensive process management tool with system monitoring capabilities.

    Key capabilities:
    * List all running processes with detailed information
    * Monitor process CPU and memory usage
    * Terminate processes by PID with safety checks
    * Manage terminal sessions created by execution tools
    * Track long-running commands and their status
    * Force terminate unresponsive processes
    * Read output from running terminal sessions
    * Support for both local and sandbox execution modes
    * Security controls to prevent system damage

    Use this tool when:
    * You need to monitor system processes and resource usage
    * You want to terminate unresponsive or runaway processes
    * You need to manage long-running commands started by other tools
    * You want to check the status of background processes
    * You need to clean up resources from previous tool executions
    * You want to read output from ongoing terminal sessions
    """

    name: str = "process_manager"
    short_description: str = "Monitor and control system processes and terminal sessions with resource usage tracking."
    description: str = """
    Comprehensive process management with monitoring and control capabilities.

    * Purpose: Monitor, control, and manage system processes and terminal sessions
    * Usage: List processes, terminate by PID, manage terminal sessions, read output
    * Features: Process monitoring, memory/CPU tracking, session management, output reading
    * Returns: Process lists, termination confirmations, session status, command output

    Provides safe process management with security controls to prevent accidental
    termination of critical system processes. Integrates with execution tools for
    comprehensive command and process lifecycle management.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "Process management operation to perform",
                "enum": [
                    "list_processes", "kill_process", "list_sessions", 
                    "read_output", "force_terminate"
                ],
                "type": "string",
            },
            "pid": {"description": "Process ID for process-specific operations", "type": "integer"},
            "timeout_ms": {"description": "Timeout for read operations in milliseconds", "type": "integer"},
            "signal_type": {"description": "Signal to send for termination (TERM, KILL, INT)", "type": "string"},
            "include_system": {"description": "Include system processes in listing", "type": "boolean"},
            "filter_name": {"description": "Filter processes by name pattern", "type": "string"},
        },
        "required": ["command"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.SHELL_ACCESS}
    requires_initialization: bool = True

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the ProcessManagerTool."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        self.config = config or ToolConfig(timeout=60.0, max_retries=2, sandbox_enabled=False)
        self._sandbox_client: Optional[BaseSandboxClient] = None
        self._local_mode = not getattr(self.config, 'sandbox_enabled', False)
        
        # Track terminal sessions created by execution tools
        self._active_sessions: Dict[int, SessionInfo] = {}
        
        logger.debug(f"ProcessManagerTool initialized in {'local' if self._local_mode else 'sandbox'} mode")

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the process manager tool."""
        try:
            if not self._local_mode:
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
                logger.info("ProcessManagerTool sandbox environment created")
            else:
                logger.info("ProcessManagerTool initialized in local mode")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ProcessManagerTool: {e}")
            self._local_mode = True
            logger.info("Falling back to local mode")
            return True

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a process management operation."""
        command = kwargs.get("command")
        
        if not command:
            raise ToolError("Parameter 'command' is required")

        logger.info(f"Executing process management command: {command}")

        try:
            if command == "list_processes":
                return await self._list_processes(kwargs)
            elif command == "kill_process":
                return await self._kill_process(kwargs)
            elif command == "list_sessions":
                return await self._list_sessions(kwargs)
            elif command == "read_output":
                return await self._read_output(kwargs)
            elif command == "force_terminate":
                return await self._force_terminate(kwargs)
            else:
                raise ToolError(f"Unsupported command: {command}")
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Error executing command {command}: {str(e)}", tool_name=self.name)

    async def _list_processes(self, kwargs: dict) -> CLIResult:
        """List running processes with detailed information."""
        include_system = kwargs.get("include_system", False)
        filter_name = kwargs.get("filter_name")

        try:
            if self._local_mode:
                processes = await self._get_local_processes(include_system, filter_name)
            else:
                processes = await self._get_sandbox_processes(include_system, filter_name)

            if not processes:
                result = "No processes found matching the criteria."
                return CLIResult.create_success(result=result, tool_name=self.name)

            # Format process list
            output = "Running Processes:\n\n"
            output += f"{'PID':<8} {'Name':<20} {'Status':<12} {'CPU%':<8} {'Memory%':<10} {'Command':<50}\n"
            output += "-" * 110 + "\n"

            for proc in processes[:50]:  # Limit to 50 processes
                cpu = f"{proc.cpu_percent:.1f}" if proc.cpu_percent is not None else "N/A"
                mem = f"{proc.memory_percent:.1f}" if proc.memory_percent is not None else "N/A"
                cmd = (proc.command[:47] + "...") if proc.command and len(proc.command) > 50 else (proc.command or "")
                
                output += f"{proc.pid:<8} {proc.name[:19]:<20} {proc.status:<12} {cpu:<8} {mem:<10} {cmd:<50}\n"

            if len(processes) > 50:
                output += f"\n... and {len(processes) - 50} more processes (use filter_name to narrow results)\n"

            return CLIResult.create_success(result=output, tool_name=self.name)

        except Exception as e:
            raise ToolError(f"Failed to list processes: {str(e)}")

    async def _get_local_processes(self, include_system: bool, filter_name: Optional[str]) -> List[ProcessInfo]:
        """Get local system processes."""
        try:
            import psutil
        except ImportError:
            # Fallback to basic ps command
            return await self._get_processes_with_ps(include_system, filter_name)

        processes = []
        current_uid = os.getuid() if hasattr(os, 'getuid') else None

        # Get process attributes list
        attrs = ['pid', 'name', 'status', 'cpu_percent', 'memory_percent', 'memory_info', 'create_time', 'cmdline', 'username']
        
        for proc in psutil.process_iter(attrs):
            try:
                proc_info = proc.info
                
                # Filter system processes if not requested
                if not include_system:
                    if current_uid is not None:
                        try:
                            # Get current user name for comparison
                            import getpass
                            current_user = getpass.getuser()
                            if proc_info.get('username') != current_user:
                                continue
                        except Exception:
                            # If we can't determine user, skip this filter
                            pass

                # Filter by name if specified
                if filter_name and filter_name.lower() not in proc_info['name'].lower():
                    continue

                command_line = ' '.join(proc_info.get('cmdline', [])) if proc_info.get('cmdline') else proc_info['name']

                # Handle memory info properly - it's a named tuple, not a dict
                memory_rss = None
                memory_info = proc_info.get('memory_info')
                if memory_info is not None:
                    # memory_info is a pmem named tuple with attributes like rss, vms, etc.
                    try:
                        memory_rss = getattr(memory_info, 'rss', None)
                    except (AttributeError, TypeError):
                        memory_rss = None

                processes.append(ProcessInfo(
                    pid=proc_info['pid'],
                    name=proc_info['name'],
                    status=proc_info.get('status', 'unknown'),
                    cpu_percent=proc_info.get('cpu_percent'),
                    memory_percent=proc_info.get('memory_percent'),
                    memory_rss=memory_rss,
                    create_time=proc_info.get('create_time'),
                    command=command_line
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                logger.debug(f"Error processing process {proc_info.get('pid', 'unknown')}: {e}")
                continue

        return sorted(processes, key=lambda x: x.cpu_percent or 0, reverse=True)

    async def _get_processes_with_ps(self, include_system: bool, filter_name: Optional[str]) -> List[ProcessInfo]:
        """Fallback process listing using ps command."""
        try:
            # Use ps command as fallback
            cmd = ["ps", "aux"] if include_system else ["ps", "ux"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise ToolError("Failed to execute ps command")

            processes = []
            lines = result.stdout.strip().split('\n')[1:]  # Skip header

            for line in lines:
                parts = line.split(None, 10)
                if len(parts) < 11:
                    continue

                name = parts[10].split()[0] if parts[10] else "unknown"
                
                # Filter by name if specified
                if filter_name and filter_name.lower() not in name.lower():
                    continue

                try:
                    processes.append(ProcessInfo(
                        pid=int(parts[1]),
                        name=os.path.basename(name),
                        status="running",  # ps doesn't easily provide status
                        cpu_percent=float(parts[2]) if parts[2] != '-' else None,
                        memory_percent=float(parts[3]) if parts[3] != '-' else None,
                        command=parts[10]
                    ))
                except (ValueError, IndexError):
                    continue

            return processes

        except Exception as e:
            raise ToolError(f"Failed to get processes with ps: {str(e)}")

    async def _get_sandbox_processes(self, include_system: bool, filter_name: Optional[str]) -> List[ProcessInfo]:
        """Get processes in sandbox environment."""
        if not self._sandbox_client:
            raise ToolError("Sandbox client not available")

        try:
            # Run ps command in sandbox
            cmd = "ps aux" if include_system else "ps ux"
            result = await self._sandbox_client.run_command(cmd)

            processes = []
            lines = result.strip().split('\n')[1:]  # Skip header

            for line in lines:
                parts = line.split(None, 10)
                if len(parts) < 11:
                    continue

                name = parts[10].split()[0] if parts[10] else "unknown"
                
                # Filter by name if specified
                if filter_name and filter_name.lower() not in name.lower():
                    continue

                try:
                    processes.append(ProcessInfo(
                        pid=int(parts[1]),
                        name=os.path.basename(name),
                        status="running",
                        cpu_percent=float(parts[2]) if parts[2] != '-' else None,
                        memory_percent=float(parts[3]) if parts[3] != '-' else None,
                        command=parts[10]
                    ))
                except (ValueError, IndexError):
                    continue

            return processes

        except Exception as e:
            raise ToolError(f"Failed to get sandbox processes: {str(e)}")

    async def _kill_process(self, kwargs: dict) -> CLIResult:
            """Terminate a process by PID."""
            pid = kwargs.get("pid")
            signal_type = kwargs.get("signal_type", "TERM")

            if not pid:
                raise ToolError("Parameter 'pid' is required for kill_process")

            # Validate PID is positive
            if not isinstance(pid, int) or pid <= 0:
                raise ToolError(f"pid must be a positive integer (got {pid})")

            # Safety check - don't allow killing critical system processes
            if pid in [1, 2] or pid == os.getpid():
                raise ToolError(f"Cannot terminate critical system process with PID {pid}")

            try:
                # Validate signal type
                valid_signals = {"TERM": signal.SIGTERM, "KILL": signal.SIGKILL, "INT": signal.SIGINT}
                if signal_type not in valid_signals:
                    raise ToolError(f"Invalid signal type: {signal_type}. Use TERM, KILL, or INT")

                sig = valid_signals[signal_type]

                if self._local_mode:
                    # Check if process exists and get info
                    proc_name = "unknown"
                    proc_status = "unknown"
                    
                    try:
                        import psutil
                        proc = psutil.Process(pid)
                        proc_name = proc.name()
                        proc_status = proc.status()
                        
                        # Handle zombie processes
                        if proc_status == psutil.STATUS_ZOMBIE:
                            status = f"Process {pid} ({proc_name}) is already terminated (zombie). Cannot send signal to zombie process."
                            # Remove from active sessions since it's dead
                            if pid in self._active_sessions:
                                del self._active_sessions[pid]
                            return CLIResult.create_success(result=status, tool_name=self.name)
                        
                        proc_cmdline = ' '.join(proc.cmdline())
                    except ImportError:
                        # Fallback without psutil
                        try:
                            # Just test if process exists
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            raise ToolError(f"No process found with PID {pid}")
                    except psutil.NoSuchProcess:
                        raise ToolError(f"No process found with PID {pid}")

                    # Send signal
                    try:
                        os.kill(pid, sig)
                        logger.info(f"Sent signal {signal_type} to process {pid} ({proc_name})")
                    except ProcessLookupError:
                        raise ToolError(f"No process found with PID {pid}")
                    
                    # Wait a moment and check if process is gone
                    time.sleep(1)
                    try:
                        if hasattr(psutil, 'Process'):
                            # Use psutil if available for better status checking
                            proc = psutil.Process(pid)
                            if proc.status() == psutil.STATUS_ZOMBIE:
                                status = f"Process {pid} ({proc_name}) terminated and became zombie"
                            else:
                                status = f"Signal {signal_type} sent to process {pid} ({proc_name}), process may still be running"
                        else:
                            # Fallback method
                            os.kill(pid, 0)  # Test if process still exists
                            status = f"Signal {signal_type} sent to process {pid} ({proc_name}), but process may still be running"
                    except (ProcessLookupError, psutil.NoSuchProcess):
                        status = f"Process {pid} ({proc_name}) terminated successfully"

                else:
                    # Sandbox mode
                    sandbox = self._sandbox_client
                    if not sandbox:
                        raise ToolError("Sandbox client not available")

                    result = await sandbox.run_command(f"kill -{signal_type} {pid}")
                    status = f"Signal {signal_type} sent to process {pid} in sandbox"

                # Remove from active sessions if it was one of ours
                if pid in self._active_sessions:
                    del self._active_sessions[pid]

                return CLIResult.create_success(result=status, tool_name=self.name)

            except PermissionError:
                raise ToolError(f"Permission denied: cannot terminate process {pid}")
            except ProcessLookupError:
                raise ToolError(f"No process found with PID {pid}")
            except Exception as e:
                raise ToolError(f"Failed to terminate process {pid}: {str(e)}")

    async def _list_sessions(self, kwargs: dict) -> CLIResult:
        """List active terminal sessions."""
        if not self._active_sessions:
            result = "No active terminal sessions found."
            return CLIResult.create_success(result=result, tool_name=self.name)

        output = "Active Terminal Sessions:\n\n"
        output += f"{'PID':<8} {'Command':<30} {'Status':<12} {'Duration':<15}\n"
        output += "-" * 67 + "\n"

        for pid, session in self._active_sessions.items():
            # Check if process is still running
            try:
                if self._local_mode:
                    os.kill(pid, 0)  # Test if process exists
                    status = "running"
                else:
                    # For sandbox, assume running if in our list
                    status = session.status
            except ProcessLookupError:
                status = "terminated"

            cmd = (session.command[:27] + "...") if len(session.command) > 30 else session.command
            output += f"{pid:<8} {cmd:<30} {status:<12} {session.duration:<15}\n"

        return CLIResult.create_success(result=output, tool_name=self.name)

    async def _read_output(self, kwargs: dict) -> CLIResult:
        """Read output from a running terminal session."""
        pid = kwargs.get("pid")
        timeout_ms = kwargs.get("timeout_ms", 5000)

        if not pid:
            raise ToolError("Parameter 'pid' is required for read_output")

        if pid not in self._active_sessions:
            raise ToolError(f"No active session found with PID {pid}")

        try:
            if self._local_mode:
                # For local mode, we'd need to implement process output reading
                # This is complex and would require capturing stdout/stderr from the original process
                result = f"Output reading from PID {pid} not fully implemented in local mode. Use process logs or redirect output to files."
            else:
                # Sandbox mode - read from the sandbox session
                sandbox = self._sandbox_client
                if not sandbox:
                    raise ToolError("Sandbox client not available")

                # This would depend on the sandbox implementation
                result = await sandbox.read_session_output(pid, timeout_ms)

            return CLIResult.create_success(result=result, tool_name=self.name)

        except Exception as e:
            raise ToolError(f"Failed to read output from PID {pid}: {str(e)}")

    async def _force_terminate(self, kwargs: dict) -> CLIResult:
        """Force terminate a process with SIGKILL."""
        pid = kwargs.get("pid")

        if not pid:
            raise ToolError("Parameter 'pid' is required for force_terminate")

        # Use kill_process with KILL signal
        kwargs["signal_type"] = "KILL"
        return await self._kill_process(kwargs)

    def register_session(self, pid: int, command: str) -> None:
        """Register a new terminal session (called by execution tools)."""
        self._active_sessions[pid] = SessionInfo(
            pid=pid,
            command=command,
            status="running",
            start_time=time.strftime("%Y-%m-%d %H:%M:%S"),
            duration="0s"
        )
        logger.info(f"Registered terminal session PID {pid}: {command}")

    def update_session_status(self, pid: int, status: str) -> None:
        """Update session status (called by execution tools)."""
        if pid in self._active_sessions:
            self._active_sessions[pid].status = status
            logger.debug(f"Updated session PID {pid} status to: {status}")

    async def cleanup(self) -> None:
        """Clean up resources and terminate any remaining sessions."""
        logger.info("Cleaning up ProcessManagerTool resources")

        # Terminate any remaining sessions
        for pid, session in list(self._active_sessions.items()):
            try:
                if self._local_mode:
                    os.kill(pid, signal.SIGTERM)
                else:
                    if self._sandbox_client:
                        await self._sandbox_client.run_command(f"kill -TERM {pid}")
                logger.info(f"Terminated session PID {pid}")
            except (ProcessLookupError, Exception) as e:
                logger.debug(f"Session PID {pid} already terminated or error: {e}")

        self._active_sessions.clear()

        if self._sandbox_client:
            try:
                if hasattr(self._sandbox_client, "cleanup") and callable(getattr(self._sandbox_client, "cleanup")):
                    await self._sandbox_client.cleanup()
                elif hasattr(self._sandbox_client, "close") and callable(getattr(self._sandbox_client, "close")):
                    await self._sandbox_client.close()
            except Exception as e:
                logger.warning(f"Error closing sandbox client: {e}")
            finally:
                self._sandbox_client = None