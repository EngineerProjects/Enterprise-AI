from __future__ import annotations

import asyncio
import os
import signal

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool


class BashInput(BaseModel):
    command: str = Field(description="The shell command to execute.")
    timeout: float = Field(default=30.0, description="Max execution time in seconds.", ge=1.0, le=300.0)


class BashTool(BaseTool):
    name = "bash"
    description = (
        "Execute a shell command in the working directory. "
        "Use for running scripts, installing packages, running tests, or any system operation. "
        "Commands run in an isolated process. Output is captured and returned."
    )
    input_schema = BashInput

    def is_concurrency_safe(self) -> bool:
        return False  # bash commands modify state — run sequentially

    async def call(self, input: BashInput, ctx: ToolContext) -> ToolResult:
        if ctx.sandbox is not None:
            result = await ctx.sandbox.exec(input.command, timeout=input.timeout)
            return ToolResult.ok(tool_call_id="", name=self.name, content=result.output) if not result.error \
                else ToolResult.error(tool_call_id="", name=self.name, error=result.output)

        return await self._exec_local(input.command, input.timeout, ctx.working_dir)

    async def _exec_local(self, command: str, timeout: float, cwd: str) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=cwd,
                preexec_fn=os.setsid,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                await proc.wait()
                return ToolResult.error(tool_call_id="", name=self.name, error=f"Command timed out after {timeout}s")

            output = stdout.decode(errors="replace").strip()
            if proc.returncode != 0:
                return ToolResult.error(tool_call_id="", name=self.name, error=output or f"Exit code {proc.returncode}")
            return ToolResult.ok(tool_call_id="", name=self.name, content=output or "(no output)")
        except Exception as e:
            return ToolResult.error(tool_call_id="", name=self.name, error=str(e))
