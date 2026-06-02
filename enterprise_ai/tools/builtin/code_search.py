from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool

MAX_MATCHES = 50
CONTEXT_LINES = 2


class CodeSearchInput(BaseModel):
    pattern: str = Field(description="Text or regex pattern to search for.")
    path: str = Field(default=".", description="Directory or file to search in.")
    glob: Optional[str] = Field(default=None, description="File glob filter, e.g. '*.py', '*.ts'.")
    case_sensitive: bool = Field(default=True, description="Case-sensitive search.")


class CodeSearchTool(BaseTool):
    name = "code_search"
    description = (
        "Search for a pattern in source code files. Returns matching lines with file path, "
        "line number, and surrounding context. Use to find function definitions, usages, imports, etc."
    )
    input_schema = CodeSearchInput

    async def call(self, input: CodeSearchInput, ctx: ToolContext) -> ToolResult:
        search_path = Path(input.path) if os.path.isabs(input.path) else Path(ctx.working_dir) / input.path
        if not search_path.exists():
            return ToolResult.error(tool_call_id="", name=self.name, error=f"Path not found: {search_path}")

        args = ["grep", "-rn", "--include=" + (input.glob or "*")]
        if not input.case_sensitive:
            args.append("-i")
        args += [f"-A{CONTEXT_LINES}", f"-B{CONTEXT_LINES}", input.pattern, str(search_path)]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            output = stdout.decode(errors="replace").strip()
        except asyncio.TimeoutError:
            return ToolResult.error(tool_call_id="", name=self.name, error="Search timed out")
        except FileNotFoundError:
            return ToolResult.error(tool_call_id="", name=self.name, error="grep not available on this system")

        if not output:
            return ToolResult.ok(tool_call_id="", name=self.name, content=f"No matches found for: {input.pattern!r}")

        lines = output.splitlines()
        if len(lines) > MAX_MATCHES * (CONTEXT_LINES * 2 + 2):
            lines = lines[: MAX_MATCHES * (CONTEXT_LINES * 2 + 2)]
            output = "\n".join(lines) + f"\n\n... (truncated to {MAX_MATCHES} matches)"

        return ToolResult.ok(tool_call_id="", name=self.name, content=output)
