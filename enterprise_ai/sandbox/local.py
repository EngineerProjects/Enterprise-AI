from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

from enterprise_ai.sandbox.base import ExecResult, Sandbox

BLOCKED_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    ":(){ :|:& };:",
    "mkfs",
    "> /dev/sda",
    "dd if=/dev/zero of=/dev/",
]


class LocalSandbox(Sandbox):
    """
    Executes commands locally with constraints:
    - Strict timeout with process group kill (no zombie processes)
    - Blocked dangerous patterns
    - Bounded working directory
    """

    def __init__(self, working_dir: str = ".", max_output_bytes: int = 512_000) -> None:
        self._working_dir = str(Path(working_dir).resolve())
        self._max_output_bytes = max_output_bytes
        self._started = False

    async def start(self) -> None:
        Path(self._working_dir).mkdir(parents=True, exist_ok=True)
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def exec(self, command: str, timeout: float = 30.0) -> ExecResult:
        blocked = self._check_blocked(command)
        if blocked:
            return ExecResult(output=f"Blocked: {blocked}", exit_code=1)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self._working_dir,
                preexec_fn=os.setsid,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
                return ExecResult(
                    output=f"Command timed out after {timeout}s",
                    exit_code=124,
                    timed_out=True,
                )

            output = stdout[: self._max_output_bytes].decode(errors="replace").strip()
            if len(stdout) > self._max_output_bytes:
                output += f"\n\n[... output truncated at {self._max_output_bytes} bytes]"

            return ExecResult(output=output or "(no output)", exit_code=proc.returncode or 0)

        except Exception as e:
            return ExecResult(output=str(e), exit_code=1)

    async def write_file(self, path: str, content: str) -> None:
        target = Path(path) if os.path.isabs(path) else Path(self._working_dir) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    async def read_file(self, path: str) -> str:
        target = Path(path) if os.path.isabs(path) else Path(self._working_dir) / path
        return target.read_text(encoding="utf-8", errors="replace")

    def _check_blocked(self, command: str) -> str:
        lower = command.lower()
        for pattern in BLOCKED_PATTERNS:
            if pattern.lower() in lower:
                return f"dangerous pattern '{pattern}'"
        return ""

    @property
    def working_dir(self) -> str:
        return self._working_dir
