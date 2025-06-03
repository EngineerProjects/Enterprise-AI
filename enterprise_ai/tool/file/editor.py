"""
Advanced file editor tool for Enterprise AI.

This module provides a comprehensive tool for viewing, creating, and editing files
with local and sandbox support, regex capabilities, and edit history.
"""

import os
import re
import time
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Literal, Optional, Union, Pattern, Set, Tuple, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.file.editor")

# Constants
SNIPPET_LINES: int = 4
MAX_RESPONSE_LEN: int = 16000
TRUNCATED_MESSAGE: str = (
    "<response clipped><NOTE>To save on context only part of this file has been shown to you. "
    "You should retry this tool with line range parameters or search first.</NOTE>"
)

# Command type
Command = Literal[
    "view",  # View file or directory content
    "create",  # Create a new file
    "str_replace",  # Replace exact string
    "regex_replace",  # Replace using regex pattern
    "line_edit",  # Edit specific lines
    "insert",  # Insert content
    "insert_at",  # Insert at specific character position
    "undo_edit",  # Undo last edit
]


class RegexReplaceParams(BaseModel):
    """Parameters for regex replacement."""
    pattern: str = Field(..., description="Regex pattern to match")
    replacement: str = Field(..., description="Replacement string (can include regex groups like \\1, \\2)")
    count: int = Field(0, description="Maximum number of replacements (0 = all)")
    flags: str = Field("", description="Regex flags: i (ignore case), m (multiline), s (dot matches newline), etc.")


class LineEditParams(BaseModel):
    """Parameters for line editing operations."""
    operation: str = Field(..., description="Operation: insert, delete, replace")
    line_number: Optional[int] = Field(None, description="Line number (1-based)")
    pattern: Optional[str] = Field(None, description="Pattern to match lines")
    count: int = Field(1, description="Number of lines to affect")
    after_match: bool = Field(False, description="For pattern matching: insert after matched line")
    content: Optional[str] = Field(None, description="Content for insert/replace operations")

    @field_validator("operation")
    def validate_operation(cls, v: str) -> str:
        valid_ops = ["insert", "delete", "replace"]
        if v.lower() not in valid_ops:
            raise ValueError(f"operation must be one of: {', '.join(valid_ops)}")
        return v.lower()

    @model_validator(mode="after")
    def validate_line_number_or_pattern(self) -> "LineEditParams":
        if self.line_number is not None and self.line_number < 1:
            raise ValueError("line_number must be >= 1")
        if self.line_number is None and self.pattern is None:
            raise ValueError("Either line_number or pattern must be provided")
        return self


def maybe_truncate(content: str, truncate_after: Optional[int] = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length."""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE


@register_tool(category="file")
class FileEditor(BaseTool):
    """
    Advanced file editor with comprehensive file manipulation capabilities.

    Key capabilities:
    * View file and directory contents with line range control
    * Create new files with specified content
    * Edit files using exact string or regex pattern replacement
    * Perform line-based operations (insert, delete, replace)
    * Insert content at specific character positions
    * Track edit history with undo functionality
    * Create automatic backups before edits
    * Local and sandbox execution modes

    Use this tool when:
    * You need to inspect file or directory contents
    * You need to create or modify files
    * You need to perform complex search and replace operations
    * You need precise control over file edits with line numbers
    * You want to make changes with the ability to undo them
    """

    name: str = "file_editor"
    description: str = """
    Comprehensive file editor with local and sandbox support for secure file operations.

    * Purpose: View, create, and edit files with precision and safety
    * Usage: Manipulate files with various editing operations and pattern matching
    * Features: View files/directories, create files, string/regex replacement, line operations, undo
    * Returns: Operation results with file content previews and confirmation messages

    The editor supports multiple editing modes including exact string replacement, regex patterns,
    line-based editing, and character position insertion. Runs locally by default for performance,
    with optional sandbox mode for enhanced security.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The command to run",
                "enum": ["view", "create", "str_replace", "regex_replace", "line_edit", "insert", "insert_at", "undo_edit"],
                "type": "string",
            },
            "path": {"description": "Absolute path to file or directory", "type": "string"},
            "file_text": {"description": "Content for file creation", "type": "string"},
            "old_str": {"description": "String to replace (for str_replace)", "type": "string"},
            "new_str": {"description": "Replacement string (for str_replace or insert)", "type": "string"},
            "regex_params": {"description": "Parameters for regex replacement", "type": "object"},
            "line_params": {"description": "Parameters for line editing", "type": "object"},
            "insert_line": {"description": "Line number for insertion (1-based)", "type": "integer"},
            "position": {"description": "Position for insertion (character offset)", "type": "integer"},
            "view_range": {"description": "Line range for viewing [start, end]", "items": {"type": "integer"}, "type": "array"},
            "make_backup": {"description": "Whether to create a backup file", "type": "boolean"},
        },
        "required": ["command", "path"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.FILE_ACCESS}
    requires_initialization: bool = True

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the FileEditor tool with standard parameters."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        self.config = config or ToolConfig(timeout=60.0, max_retries=2, sandbox_enabled=False)
        self._file_history: DefaultDict[str, List[str]] = defaultdict(list)
        self._sandbox_client: Optional[BaseSandboxClient] = None
        self._local_mode = not getattr(self.config, 'sandbox_enabled', False)

        logger.debug(f"FileEditor tool initialized in {'local' if self._local_mode else 'sandbox'} mode")

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the file editor."""
        try:
            if not self._local_mode:
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
                logger.info("FileEditor sandbox environment created")
            else:
                logger.info("FileEditor initialized in local mode")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize FileEditor: {e}")
            self._local_mode = True
            logger.info("Falling back to local mode")
            return True

    # OPTIMIZED HELPER METHODS
    async def _get_sandbox_client(self) -> Optional[BaseSandboxClient]:
        """Get sandbox client or None for local mode."""
        if self._local_mode:
            return None
        if self._sandbox_client is None:
            try:
                logger.info("Creating new sandbox client")
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
            except Exception as e:
                logger.error(f"Failed to create sandbox client: {e}")
                raise ToolError(f"Failed to initialize sandbox environment: {str(e)}")
        return self._sandbox_client

    async def _read_file(self, path: str) -> str:
        """Unified file reading for both local and sandbox modes."""
        if self._local_mode:
            try:
                return Path(path).read_text(encoding='utf-8', errors='replace')
            except Exception as e:
                raise ToolError(f"Could not read file {path}: {str(e)}")
        else:
            sandbox = await self._get_sandbox_client()
            return await sandbox.read_file(path)

    async def _write_file(self, path: str, content: str) -> None:
        """Unified file writing for both local and sandbox modes."""
        if self._local_mode:
            try:
                Path(path).write_text(content, encoding='utf-8')
            except Exception as e:
                raise ToolError(f"Could not write file {path}: {str(e)}")
        else:
            sandbox = await self._get_sandbox_client()
            await sandbox.write_file(path, content)

    async def _file_exists(self, path: str) -> bool:
        """Check if file exists in both local and sandbox modes."""
        if self._local_mode:
            return Path(path).exists()
        else:
            sandbox = await self._get_sandbox_client()
            result = await self._run_sandbox_command(f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox)
            return "exists" in result

    async def _is_directory(self, path: str) -> bool:
        """Check if path is a directory in both local and sandbox modes."""
        if self._local_mode:
            return Path(path).is_dir()
        else:
            sandbox = await self._get_sandbox_client()
            result = await self._run_sandbox_command(f"test -d {path} && echo 'directory' || echo 'file'", sandbox)
            return "directory" in result

    async def _ensure_directory_exists(self, path: str) -> None:
        """Ensure directory exists for file path."""
        dir_path = os.path.dirname(path)
        if not dir_path:
            return

        if self._local_mode:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory structure created locally: {dir_path}")
        else:
            sandbox = await self._get_sandbox_client()
            dir_exists = await self._run_sandbox_command(f"[ -d '{dir_path}' ] && echo 'exists' || echo 'not_exists'", sandbox)
            if "not_exists" in dir_exists:
                await self._run_sandbox_command(f"mkdir -p '{dir_path}'", sandbox)
                logger.info(f"Directory structure created: {dir_path}")

    async def _create_backup(self, path: str) -> Optional[str]:
        """Create backup file."""
        if not await self._file_exists(path):
            return None

        try:
            if self._local_mode:
                timestamp = int(time.time())
                backup_path = f"{path}.bak.{timestamp}"
                shutil.copy2(path, backup_path)
                logger.debug(f"Created local backup: {backup_path}")
                return backup_path
            else:
                sandbox = await self._get_sandbox_client()
                backup_path = f"{path}.bak"
                await self._run_sandbox_command(f"cp {path} {backup_path}", sandbox)
                return backup_path
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
            return None

    async def _run_sandbox_command(self, command: str, sandbox: Optional[BaseSandboxClient] = None) -> str:
        """Run command in sandbox or locally."""
        if self._local_mode:
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
                return result.stdout if result.returncode == 0 else result.stderr
            except Exception as e:
                raise ToolError(f"Error executing local command: {str(e)}")
        else:
            if sandbox is None:
                sandbox = await self._get_sandbox_client()
            try:
                return await sandbox.run_command(command)
            except Exception as e:
                raise ToolError(f"Error executing command: {str(e)}")

    def _validate_path_format(self, path: str) -> None:
        """Validate path format."""
        if not Path(path).is_absolute():
            raise ToolError(f"The path {path} is not an absolute path")

    async def _validate_file_operation(self, command: str, path: str) -> None:
        """Validate file operation requirements."""
        self._validate_path_format(path)
        
        if command == "create":
            if await self._file_exists(path):
                raise ToolError(f"File already exists at: {path}. Cannot overwrite files using command `create`.")
        elif command != "view":
            if not await self._file_exists(path):
                if command in ["str_replace", "regex_replace", "line_edit", "insert", "insert_at"]:
                    dir_path = os.path.dirname(path)
                    if dir_path and not await self._file_exists(dir_path):
                        logger.warning(f"Parent directory does not exist: {dir_path}")
                else:
                    raise ToolError(f"The path {path} does not exist. Please provide a valid path.")
            elif await self._is_directory(path):
                raise ToolError(f"The path {path} is a directory and only the `view` command can be used on directories")

    def _create_snippet(self, content: str, line_number: int, num_lines: int = SNIPPET_LINES) -> str:
        """Create a numbered snippet around a specific line."""
        lines = content.split("\n")
        start_line = max(0, line_number - num_lines)
        end_line = min(len(lines), line_number + num_lines + 1)
        
        snippet_lines = lines[start_line:end_line]
        return "\n".join([f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)])

    # MAIN EXECUTION METHOD
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a file operation command."""
        command = kwargs.get("command")
        path = kwargs.get("path")
        
        if not command:
            raise ToolError("Parameter 'command' is required")
        if not path:
            raise ToolError("Parameter 'path' is required")

        logger.info(f"Executing command: {command} on path: {path} (mode: {'local' if self._local_mode else 'sandbox'})")

        try:
            await self._validate_file_operation(command, path)
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)

        # Route to appropriate command handler
        try:
            if command == "view":
                return await self._handle_view(path, kwargs.get("view_range"))
            elif command == "create":
                return await self._handle_create(path, kwargs.get("file_text"))
            elif command == "str_replace":
                return await self._handle_str_replace(path, kwargs.get("old_str"), kwargs.get("new_str"), kwargs.get("make_backup", True))
            elif command == "regex_replace":
                return await self._handle_regex_replace(path, kwargs.get("regex_params"), kwargs.get("make_backup", True))
            elif command == "line_edit":
                return await self._handle_line_edit(path, kwargs.get("line_params"), kwargs.get("make_backup", True))
            elif command == "insert":
                return await self._handle_insert(path, kwargs.get("insert_line"), kwargs.get("new_str"), kwargs.get("make_backup", True))
            elif command == "insert_at":
                return await self._handle_insert_at(path, kwargs.get("position"), kwargs.get("new_str"), kwargs.get("make_backup", True))
            elif command == "undo_edit":
                return await self._handle_undo_edit(path)
            else:
                raise ToolError(f"Unsupported command: {command}")
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Error executing command {command}: {str(e)}", tool_name=self.name)

    # COMMAND HANDLERS
    async def _handle_view(self, path: str, view_range: Optional[List[int]] = None) -> CLIResult:
        """Handle view command."""
        if await self._is_directory(path):
            if view_range:
                raise ToolError("The `view_range` parameter is not allowed when `path` points to a directory.")
            return await self._view_directory(path)
        else:
            return await self._view_file(path, view_range)

    async def _view_directory(self, path: str) -> CLIResult:
        """View directory contents."""
        if self._local_mode:
            try:
                path_obj = Path(path)
                items = sorted(path_obj.iterdir(), key=lambda x: (x.is_file(), x.name))
                output = f"Here are the files and directories in {path}:\n"
                for item in items[:100]:
                    item_type = "[DIR]" if item.is_dir() else "[FILE]"
                    output += f"{item_type} {item.name}\n"
                if len(items) > 100:
                    output += f"... and {len(items) - 100} more items\n"
                return CLIResult.create_success(result=output, tool_name=self.name)
            except Exception as e:
                return CLIResult.create_error(error=f"Failed to list directory contents: {str(e)}", tool_name=self.name)
        else:
            sandbox = await self._get_sandbox_client()
            find_cmd = f"find {path} -maxdepth 2 -not -path '*/\\.*'"
            find_result = await self._run_sandbox_command(find_cmd, sandbox)
            if find_result:
                output = f"Here are the files and directories up to 2 levels deep in {path}, excluding hidden items:\n{find_result}\n"
                return CLIResult.create_success(result=output, tool_name=self.name)
            else:
                return CLIResult.create_error(error=f"Failed to list directory contents: {path}", tool_name=self.name)

    async def _view_file(self, path: str, view_range: Optional[List[int]] = None) -> CLIResult:
        """View file contents."""
        try:
            file_content = await self._read_file(path)
            init_line = 1

            if view_range:
                if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                    raise ToolError("Invalid `view_range`. It should be a list of two integers.")
                
                file_lines = file_content.split("\n")
                n_lines_file = len(file_lines)
                init_line, final_line = view_range

                if init_line < 1 or init_line > n_lines_file:
                    raise ToolError(f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within the range of lines of the file: {[1, n_lines_file]}")
                if final_line > n_lines_file and final_line != -1:
                    raise ToolError(f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be smaller than the number of lines in the file: `{n_lines_file}`")
                if final_line != -1 and final_line < init_line:
                    raise ToolError(f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be larger or equal than its first `{init_line}`")

                if final_line == -1:
                    file_content = "\n".join(file_lines[init_line - 1 :])
                else:
                    file_content = "\n".join(file_lines[init_line - 1 : final_line])

            file_content = maybe_truncate(file_content)
            if hasattr(file_content, "expandtabs"):
                file_content = file_content.expandtabs()

            numbered_content = "\n".join([f"{i + init_line:6}\t{line}" for i, line in enumerate(file_content.split("\n"))])
            output = f"Here's the content of {path} with line numbers:\n{numbered_content}\n"
            
            return CLIResult.create_success(result=output, tool_name=self.name)
        except Exception as e:
            return CLIResult.create_error(error=f"Failed to read file: {str(e)}", tool_name=self.name)

    async def _handle_create(self, path: str, file_text: Optional[str]) -> ToolResult:
        """Handle create command."""
        if file_text is None:
            raise ToolError("Parameter `file_text` is required for command: create")
        
        await self._ensure_directory_exists(path)
        await self._write_file(path, file_text)
        logger.info(f"File created successfully at: {path}")
        return ToolResult.create_success(result=f"File created successfully at: {path}", tool_name=self.name)

    async def _handle_str_replace(self, path: str, old_str: Optional[str], new_str: Optional[str], make_backup: bool) -> CLIResult:
        """Handle string replacement."""
        if old_str is None:
            raise ToolError("Parameter `old_str` is required for command: str_replace")
        
        if not await self._file_exists(path):
            await self._ensure_directory_exists(path)
            raise ToolError(f"The file {path} does not exist for replacement operation.")

        file_content = await self._read_file(path)
        new_str = new_str or ""

        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path)

        occurrences = file_content.count(old_str)
        if occurrences == 0:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}.")
        elif occurrences > 1:
            if backup_path:
                await self._cleanup_backup(backup_path)
            
            file_lines = file_content.split("\n")
            lines = [i + 1 for i, line in enumerate(file_lines) if old_str in line]
            raise ToolError(f"No replacement was performed. Multiple occurrences of old_str in {path} at lines {lines}. Please ensure it is unique or use regex_replace.")

        new_file_content = file_content.replace(old_str, new_str)
        self._file_history[path].append(file_content)
        await self._write_file(path, new_file_content)

        replacement_line = file_content.split(old_str)[0].count("\n")
        snippet = self._create_snippet(new_file_content, replacement_line)

        success_msg = f"The file {path} has been edited.\nHere's a snippet of the edited section:\n{snippet}\n"
        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_regex_replace(self, path: str, regex_params: Optional[dict], make_backup: bool) -> CLIResult:
        """Handle regex replacement."""
        if regex_params is None:
            raise ToolError("Parameter `regex_params` is required for command: regex_replace")

        if not await self._file_exists(path):
            await self._ensure_directory_exists(path)
            raise ToolError(f"The file {path} does not exist for replacement operation.")

        validated_params = RegexReplaceParams(**regex_params)
        file_content = await self._read_file(path)

        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path)

        try:
            regex_flags = self._build_regex_flags(validated_params.flags)
            compiled_pattern = re.compile(validated_params.pattern, regex_flags)
        except re.error as e:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"Invalid regex pattern: {e}")

        matches = compiled_pattern.findall(file_content)
        if not matches:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"No matches found for pattern: {validated_params.pattern}")

        new_file_content, replacement_count = compiled_pattern.subn(
            validated_params.replacement, file_content, count=validated_params.count
        )

        if replacement_count == 0:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError("No replacements made. Pattern matched but replacement failed.")

        self._file_history[path].append(file_content)
        await self._write_file(path, new_file_content)

        # Find first match line for snippet
        file_lines = file_content.split("\n")
        match_line = 0
        for i, line in enumerate(file_lines):
            if compiled_pattern.search(line):
                match_line = i
                break

        snippet = self._create_snippet(new_file_content, match_line)
        success_msg = f"The file {path} has been edited.\nPattern: {validated_params.pattern}\nReplacements made: {replacement_count}\nHere's a snippet around the first match:\n{snippet}\n"
        
        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_line_edit(self, path: str, line_params: Optional[dict], make_backup: bool) -> CLIResult:
        """Handle line editing operations."""
        if line_params is None:
            raise ToolError("Parameter `line_params` is required for command: line_edit")

        line_edit_params = LineEditParams(**line_params)
        
        # Handle file creation for insert operations
        if not await self._file_exists(path):
            if line_edit_params.operation == "insert":
                await self._ensure_directory_exists(path)
                await self._write_file(path, "")
                file_content = ""
            else:
                raise ToolError(f"The file {path} does not exist for {line_edit_params.operation} operation.")
        else:
            file_content = await self._read_file(path)

        lines = file_content.splitlines()

        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path)

        # Determine target lines
        target_lines: List[int] = []
        if line_edit_params.line_number is not None:
            line_idx = line_edit_params.line_number - 1
            if line_edit_params.operation != "insert" and (line_idx < 0 or line_idx >= len(lines)):
                if backup_path:
                    await self._cleanup_backup(backup_path)
                raise ToolError(f"Line number {line_edit_params.line_number} is out of range (1-{len(lines)})")
            
            if line_edit_params.operation == "insert" and line_idx > len(lines):
                if backup_path:
                    await self._cleanup_backup(backup_path)
                raise ToolError(f"Line number {line_edit_params.line_number} is out of range (1-{len(lines) + 1})")

            for i in range(line_edit_params.count):
                if line_edit_params.operation == "insert" or line_idx + i < len(lines):
                    target_lines.append(line_idx + i)

        elif line_edit_params.pattern is not None:
            matches = self._find_line_numbers(file_content, line_edit_params.pattern, line_edit_params.count)
            if not matches:
                if backup_path:
                    await self._cleanup_backup(backup_path)
                raise ToolError(f"No lines matched pattern: {line_edit_params.pattern}")
            target_lines = matches

        if file_content:
            self._file_history[path].append(file_content)

        # Perform operation
        new_lines = lines.copy()
        modified = False

        if line_edit_params.operation == "delete":
            for line_idx in sorted(target_lines, reverse=True):
                if 0 <= line_idx < len(new_lines):
                    del new_lines[line_idx]
                    modified = True

        elif line_edit_params.operation == "replace":
            if line_edit_params.content is None:
                if backup_path:
                    await self._cleanup_backup(backup_path)
                raise ToolError("Content must be provided for replace operation")
            
            replacement_lines = line_edit_params.content.splitlines()
            for i, line_idx in enumerate(target_lines):
                if 0 <= line_idx < len(new_lines):
                    if i < len(replacement_lines):
                        new_lines[line_idx] = replacement_lines[i]
                    else:
                        new_lines[line_idx] = replacement_lines[-1] if replacement_lines else ""
                    modified = True

        elif line_edit_params.operation == "insert":
            if line_edit_params.content is None:
                if backup_path:
                    await self._cleanup_backup(backup_path)
                raise ToolError("Content must be provided for insert operation")
            
            insertion_lines = line_edit_params.content.splitlines()
            
            if line_edit_params.pattern is not None and line_edit_params.after_match:
                for line_idx in sorted(target_lines, reverse=True):
                    insert_pos = line_idx + 1
                    if 0 <= insert_pos <= len(new_lines):
                        for ins_line in reversed(insertion_lines):
                            new_lines.insert(insert_pos, ins_line)
                        modified = True
            else:
                for line_idx in sorted(target_lines, reverse=True):
                    if 0 <= line_idx <= len(new_lines):
                        for ins_line in reversed(insertion_lines):
                            new_lines.insert(line_idx, ins_line)
                        modified = True

        if modified:
            new_content = "\n".join(new_lines)
            if file_content.endswith("\n"):
                new_content += "\n"

            await self._write_file(path, new_content)

            if target_lines:
                first_line = min(target_lines)
                snippet = self._create_snippet("\n".join(new_lines), first_line)
                success_msg = f"The file {path} has been edited using operation: {line_edit_params.operation}\nLines affected: {sorted([i + 1 for i in target_lines])}\nHere's a snippet of the edited section:\n{snippet}\n"
                if backup_path:
                    success_msg += f"Backup created at: {backup_path}\n"
                return CLIResult.create_success(result=success_msg, tool_name=self.name)
            else:
                return CLIResult.create_success(result=f"File {path} was modified but no snippet is available to display.", tool_name=self.name)
        else:
            if backup_path:
                await self._cleanup_backup(backup_path)
            return CLIResult.create_success(result="No changes were made to the file.", tool_name=self.name)

    async def _handle_insert(self, path: str, insert_line: Optional[int], new_str: Optional[str], make_backup: bool) -> CLIResult:
        """Handle line insertion."""
        if insert_line is None:
            raise ToolError("Parameter `insert_line` is required for command: insert")
        if new_str is None:
            raise ToolError("Parameter `new_str` is required for command: insert")

        if not await self._file_exists(path):
            await self._ensure_directory_exists(path)
            await self._write_file(path, "")
            file_content = ""
            lines = []
        else:
            file_content = await self._read_file(path)
            lines = file_content.splitlines()

        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path)

        if insert_line < 0 or insert_line > len(lines) + 1:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"Invalid line number {insert_line}. It should be within the range [1-{len(lines) + 1}]")

        if file_content:
            self._file_history[path].append(file_content)

        insert_pos = insert_line - 1
        if insert_pos > len(lines):
            insert_pos = len(lines)

        new_str_lines = new_str.splitlines()
        new_lines = lines[:insert_pos] + new_str_lines + lines[insert_pos:]
        new_content = "\n".join(new_lines)

        if file_content.endswith("\n"):
            new_content += "\n"

        await self._write_file(path, new_content)

        snippet = self._create_snippet("\n".join(new_lines), insert_pos)
        success_msg = f"The file {path} has been edited with insertion at line {insert_line}\nInserted {len(new_str_lines)} line(s)\nHere's a snippet of the edited section:\n{snippet}\n"
        
        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_insert_at(self, path: str, position: Optional[int], new_str: Optional[str], make_backup: bool) -> CLIResult:
        """Handle character position insertion."""
        if position is None:
            raise ToolError("Parameter `position` is required for command: insert_at")
        if new_str is None:
            raise ToolError("Parameter `new_str` is required for command: insert_at")

        if not await self._file_exists(path):
            if position == 0:
                await self._ensure_directory_exists(path)
                await self._write_file(path, "")
                file_content = ""
            else:
                raise ToolError(f"The file {path} does not exist for insert_at operation.")
        else:
            file_content = await self._read_file(path)

        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path)

        if position < 0 or position > len(file_content):
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"Invalid position {position}. It should be within the range [0-{len(file_content)}]")

        if file_content:
            self._file_history[path].append(file_content)

        new_content = file_content[:position] + new_str + file_content[position:]
        await self._write_file(path, new_content)

        prefix = file_content[:position]
        line_number = prefix.count("\n") + 1
        line_index = prefix.count("\n")

        snippet = self._create_snippet(new_content, line_index)
        success_msg = f"The file {path} has been edited with insertion at position {position}\n(around line {line_number})\nInserted: '{new_str}'\nHere's a snippet of the edited section:\n{snippet}\n"
        
        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_undo_edit(self, path: str) -> CLIResult:
        """Handle undo operation."""
        if not self._file_history[path]:
            raise ToolError(f"No edit history found for {path}.")

        old_text = self._file_history[path].pop()
        await self._write_file(path, old_text)

        lines = old_text.splitlines()
        preview_lines = lines[: min(10, len(lines))]
        numbered_preview = "\n".join([f"{i + 1:6}\t{line}" for i, line in enumerate(preview_lines)])

        success_msg = f"Last edit to {path} was undone successfully.\n"
        if preview_lines:
            success_msg += f"Here's the beginning of the file after undo:\n{numbered_preview}\n"
            if len(lines) > 10:
                success_msg += "(File continues...)\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    # UTILITY METHODS
    def _build_regex_flags(self, flags_str: str) -> int:
        """Build regex flags from string."""
        flag_map = {
            "i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL,
            "x": re.VERBOSE, "a": re.ASCII, "l": re.LOCALE, "u": re.UNICODE,
        }
        result = 0
        for flag in flags_str.lower():
            if flag in flag_map:
                result |= flag_map[flag]
        return result

    def _find_line_numbers(self, content: str, pattern: str, count: int = 1) -> List[int]:
        """Find line numbers that match a pattern."""
        lines = content.splitlines()
        result_matches: List[int] = []

        try:
            regex = re.compile(pattern)
            for i, line in enumerate(lines):
                if regex.search(line) and (count <= 0 or len(result_matches) < count):
                    result_matches.append(i)
        except re.error:
            for i, line in enumerate(lines):
                if pattern in line and (count <= 0 or len(result_matches) < count):
                    result_matches.append(i)

        return result_matches

    async def _cleanup_backup(self, backup_path: str) -> None:
        """Clean up backup file."""
        try:
            if self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            else:
                sandbox = await self._get_sandbox_client()
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
        except Exception as e:
            logger.warning(f"Failed to clean up backup {backup_path}: {e}")

    async def cleanup(self) -> None:
        """Clean up resources used by the file editor."""
        logger.info("Cleaning up file editor resources")

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

        self._file_history = defaultdict(list)