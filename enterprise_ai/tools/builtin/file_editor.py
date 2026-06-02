from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from enterprise_ai.schema import ToolResult
from enterprise_ai.tools.context import ToolContext
from enterprise_ai.tools.contract import BaseTool

MAX_READ_BYTES = 200_000


class FileCommand(str, Enum):
    read = "read"
    write = "write"
    create = "create"
    str_replace = "str_replace"
    insert = "insert"
    delete_range = "delete_range"
    view_dir = "view_dir"


class FileEditorInput(BaseModel):
    command: FileCommand = Field(description="Operation to perform on the file.")
    path: str = Field(description="Absolute or relative file/directory path.")
    content: Optional[str] = Field(default=None, description="Content to write (for write/create/insert).")
    old_str: Optional[str] = Field(default=None, description="Exact string to replace (for str_replace).")
    new_str: Optional[str] = Field(default=None, description="Replacement string (for str_replace).")
    insert_line: Optional[int] = Field(default=None, description="Line number to insert after (1-indexed, for insert).")
    start_line: Optional[int] = Field(default=None, description="Start line for delete_range (1-indexed).")
    end_line: Optional[int] = Field(default=None, description="End line for delete_range (1-indexed, inclusive).")


class FileEditorTool(BaseTool):
    name = "file_editor"
    description = (
        "Read, write, and edit files. Supports: read a file, write/create a file, "
        "replace an exact string in a file, insert lines, delete line ranges, or list a directory."
    )
    input_schema = FileEditorInput

    def is_concurrency_safe(self) -> bool:
        return False  # file writes must be sequential

    async def call(self, input: FileEditorInput, ctx: ToolContext) -> ToolResult:
        path = Path(input.path) if os.path.isabs(input.path) else Path(ctx.working_dir) / input.path
        try:
            if input.command == FileCommand.view_dir:
                return self._view_dir(path)
            elif input.command == FileCommand.read:
                return self._read(path)
            elif input.command in (FileCommand.write, FileCommand.create):
                return self._write(path, input.content or "")
            elif input.command == FileCommand.str_replace:
                return self._str_replace(path, input.old_str or "", input.new_str or "")
            elif input.command == FileCommand.insert:
                return self._insert(path, input.insert_line or 0, input.content or "")
            elif input.command == FileCommand.delete_range:
                return self._delete_range(path, input.start_line or 1, input.end_line or 1)
            else:
                return ToolResult.error(tool_call_id="", name=self.name, error=f"Unknown command: {input.command}")
        except Exception as e:
            return ToolResult.error(tool_call_id="", name=self.name, error=str(e))

    def _read(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult.error(tool_call_id="", name=self.name, error=f"File not found: {path}")
        size = path.stat().st_size
        if size > MAX_READ_BYTES:
            return ToolResult.error(tool_call_id="", name=self.name, error=f"File too large ({size} bytes). Read in chunks.")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        numbered = "\n".join(f"{i+1:4d}\t{line}" for i, line in enumerate(lines))
        return ToolResult.ok(tool_call_id="", name=self.name, content=numbered)

    def _write(self, path: Path, content: str) -> ToolResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"Written {len(content)} chars to {path}")

    def _str_replace(self, path: Path, old_str: str, new_str: str) -> ToolResult:
        if not path.exists():
            return ToolResult.error(tool_call_id="", name=self.name, error=f"File not found: {path}")
        text = path.read_text(encoding="utf-8")
        count = text.count(old_str)
        if count == 0:
            return ToolResult.error(tool_call_id="", name=self.name, error="old_str not found in file")
        if count > 1:
            return ToolResult.error(tool_call_id="", name=self.name, error=f"old_str found {count} times — must be unique")
        path.write_text(text.replace(old_str, new_str, 1), encoding="utf-8")
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"Replaced 1 occurrence in {path}")

    def _insert(self, path: Path, after_line: int, content: str) -> ToolResult:
        if not path.exists():
            return ToolResult.error(tool_call_id="", name=self.name, error=f"File not found: {path}")
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        lines.insert(after_line, content if content.endswith("\n") else content + "\n")
        path.write_text("".join(lines), encoding="utf-8")
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"Inserted after line {after_line} in {path}")

    def _delete_range(self, path: Path, start: int, end: int) -> ToolResult:
        if not path.exists():
            return ToolResult.error(tool_call_id="", name=self.name, error=f"File not found: {path}")
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        del lines[start - 1:end]
        path.write_text("".join(lines), encoding="utf-8")
        return ToolResult.ok(tool_call_id="", name=self.name, content=f"Deleted lines {start}-{end} from {path}")

    def _view_dir(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult.error(tool_call_id="", name=self.name, error=f"Directory not found: {path}")
        entries = []
        for item in sorted(path.iterdir()):
            prefix = "d" if item.is_dir() else "f"
            entries.append(f"[{prefix}] {item.name}")
        return ToolResult.ok(tool_call_id="", name=self.name, content="\n".join(entries) or "(empty)")
