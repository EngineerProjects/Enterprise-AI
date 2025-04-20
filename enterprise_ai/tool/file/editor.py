"""
Advanced file editor tool for Enterprise AI.

This module provides a comprehensive tool for viewing, creating, and editing files
with sandbox support, regex capabilities, and edit history.
"""

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Literal, Optional, Union, Pattern, Set, Tuple, cast

from pydantic import BaseModel, Field, validator

from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client


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
    replacement: str = Field(
        ..., description="Replacement string (can include regex groups like \\1, \\2)"
    )
    count: int = Field(0, description="Maximum number of replacements (0 = all)")
    flags: str = Field(
        "", description="Regex flags: i (ignore case), m (multiline), s (dot matches newline), etc."
    )


class LineEditParams(BaseModel):
    """Parameters for line editing operations."""

    operation: str = Field(..., description="Operation: insert, delete, replace")
    line_number: Optional[int] = Field(None, description="Line number (1-based)")
    pattern: Optional[str] = Field(None, description="Pattern to match lines")
    count: int = Field(1, description="Number of lines to affect")
    after_match: bool = Field(False, description="For pattern matching: insert after matched line")
    content: Optional[str] = Field(None, description="Content for insert/replace operations")

    @validator("operation")
    def validate_operation(cls, v: str) -> str:
        valid_ops = ["insert", "delete", "replace"]
        if v.lower() not in valid_ops:
            raise ValueError(f"operation must be one of: {', '.join(valid_ops)}")
        return v.lower()

    @validator("line_number")
    def validate_line_number(cls, v: Optional[int], values: Dict[str, Any]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("line_number must be >= 1")

        # Ensure we have either line_number or pattern
        if v is None and "pattern" in values and values["pattern"] is None:
            raise ValueError("Either line_number or pattern must be provided")

        return v


def maybe_truncate(content: str, truncate_after: Optional[int] = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length."""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE


@register_tool(category="file")
class FileEditor(BaseTool):
    """Advanced tool for viewing, creating, and editing files with sandbox support."""

    def __init__(self) -> None:
        """Initialize the editor tool with explicit attributes."""
        # Define values explicitly in __init__
        name = "file_editor"
        description = """Comprehensive file editor with sandbox support. Capabilities include:
    * Viewing files and directories
    * Creating new files
    * String replacement (exact matches)
    * Regex pattern replacement
    * Line-based operations (insert, delete, replace)
    * Insert at specific positions including character offsets
    * Undo functionality with edit history

    Notes:
    * All operations run in a secure sandbox environment
    * Files can be edited using exact string matches or regex patterns
    * Line operations can target specific line numbers or line patterns
    * Backups can be created automatically before edits
    * Undo capability for all edit operations
    """
        parameters = {
            "type": "object",
            "properties": {
                "command": {
                    "description": "The command to run",
                    "enum": [
                        "view",
                        "create",
                        "str_replace",
                        "regex_replace",
                        "line_edit",
                        "insert",
                        "insert_at",
                        "undo_edit",
                    ],
                    "type": "string",
                },
                "path": {
                    "description": "Absolute path to file or directory",
                    "type": "string",
                },
                # Include all other parameters here...
                "file_text": {
                    "description": "Content for file creation",
                    "type": "string",
                },
                "old_str": {
                    "description": "String to replace (for str_replace)",
                    "type": "string",
                },
                "new_str": {
                    "description": "Replacement string (for str_replace or insert)",
                    "type": "string",
                },
                "regex_params": {
                    "description": "Parameters for regex replacement",
                    "type": "object",
                },
                "line_params": {
                    "description": "Parameters for line editing",
                    "type": "object",
                },
                "insert_line": {
                    "description": "Line number for insertion (1-based)",
                    "type": "integer",
                },
                "position": {
                    "description": "Position for insertion (character offset)",
                    "type": "integer",
                },
                "view_range": {
                    "description": "Line range for viewing [start, end]",
                    "items": {"type": "integer"},
                    "type": "array",
                },
                "make_backup": {
                    "description": "Whether to create a backup file",
                    "type": "boolean",
                },
            },
            "required": ["command", "path"],
        }

        super().__init__(name=name, description=description, parameters=parameters)
        self._file_history: DefaultDict[str, List[str]] = defaultdict(list)
        self._sandbox_client: Optional[BaseSandboxClient] = None

    async def _get_sandbox_client(self) -> BaseSandboxClient:
        """Get or create a sandbox client."""
        if self._sandbox_client is None:
            self._sandbox_client = create_sandbox_client()
            await self._sandbox_client.create()
        return self._sandbox_client

    def _build_regex_flags(self, flags_str: str) -> int:
        """Build regex flags from string.

        Args:
            flags_str: String representation of flags (e.g., 'im' for re.I | re.M)

        Returns:
            Integer flags for re module
        """
        flag_map = {
            "i": re.IGNORECASE,
            "m": re.MULTILINE,
            "s": re.DOTALL,
            "x": re.VERBOSE,
            "a": re.ASCII,
            "l": re.LOCALE,
            "u": re.UNICODE,
        }

        result = 0
        for flag in flags_str.lower():
            if flag in flag_map:
                result |= flag_map[flag]

        return result

    async def _create_backup(self, path: str, sandbox: BaseSandboxClient) -> Optional[str]:
        """Create a backup of the file.

        Args:
            path: Path to the file to back up
            sandbox: Sandbox client

        Returns:
            Path to the backup file or None if backup failed
        """
        try:
            backup_path = f"{path}.bak"
            # Use cp command to create backup
            await sandbox.run_command(f"cp {path} {backup_path}")
            return backup_path
        except Exception as _:
            return None

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a file operation command."""
        # Extract parameters from kwargs
        command = kwargs.get("command")
        if not command:
            raise ToolError("Parameter 'command' is required")

        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required")

        # Get the sandbox client
        sandbox = await self._get_sandbox_client()

        # Validate path and command combination
        await self.validate_path(command, path, sandbox)

        # Execute the appropriate command
        try:
            if command == "view":
                view_range = kwargs.get("view_range")
                result = await self.view(path, view_range, sandbox)
                return result

            elif command == "create":
                file_text = kwargs.get("file_text")
                if file_text is None:
                    raise ToolError("Parameter `file_text` is required for command: create")
                await sandbox.write_file(path, file_text)
                return ToolResult(output=f"File created successfully at: {path}")

            elif command == "str_replace":
                old_str = kwargs.get("old_str")
                new_str = kwargs.get("new_str")
                make_backup = kwargs.get("make_backup", True)

                if old_str is None:
                    raise ToolError("Parameter `old_str` is required for command: str_replace")

                return await self.str_replace(path, old_str, new_str, make_backup, sandbox)

            elif command == "regex_replace":
                regex_params = kwargs.get("regex_params")
                make_backup = kwargs.get("make_backup", True)

                if regex_params is None:
                    raise ToolError(
                        "Parameter `regex_params` is required for command: regex_replace"
                    )

                # Validate and extract regex params
                validated_params = RegexReplaceParams(**regex_params)
                return await self.regex_replace(
                    path,
                    validated_params.pattern,
                    validated_params.replacement,
                    validated_params.count,
                    validated_params.flags,
                    make_backup,
                    sandbox,
                )

            elif command == "line_edit":
                line_params = kwargs.get("line_params")
                make_backup = kwargs.get("make_backup", True)

                if line_params is None:
                    raise ToolError("Parameter `line_params` is required for command: line_edit")

                # Validate and extract line edit params
                line_edit_params = LineEditParams(**line_params)
                return await self.line_edit(
                    path,
                    line_edit_params.operation,
                    line_edit_params.line_number,
                    line_edit_params.pattern,
                    line_edit_params.count,
                    line_edit_params.after_match,
                    line_edit_params.content,
                    make_backup,
                    sandbox,
                )

            elif command == "insert":
                insert_line = kwargs.get("insert_line")
                new_str = kwargs.get("new_str")
                make_backup = kwargs.get("make_backup", True)

                if insert_line is None:
                    raise ToolError("Parameter `insert_line` is required for command: insert")
                if new_str is None:
                    raise ToolError("Parameter `new_str` is required for command: insert")

                return await self.insert(path, insert_line, new_str, make_backup, sandbox)

            elif command == "insert_at":
                position = kwargs.get("position")
                new_str = kwargs.get("new_str")
                make_backup = kwargs.get("make_backup", True)

                if position is None:
                    raise ToolError("Parameter `position` is required for command: insert_at")
                if new_str is None:
                    raise ToolError("Parameter `new_str` is required for command: insert_at")

                return await self.insert_at(path, position, new_str, make_backup, sandbox)

            elif command == "undo_edit":
                return await self.undo_edit(path, sandbox)

            else:
                raise ToolError(f"Unsupported command: {command}")

        except Exception as e:
            if isinstance(e, ToolError):
                raise
            raise ToolError(f"Error executing command {command}: {str(e)}")

    async def validate_path(self, command: str, path: str, sandbox: BaseSandboxClient) -> None:
        """Validate path and command combination."""
        path_obj = Path(path)

        # Check if path is absolute
        if not path_obj.is_absolute():
            raise ToolError(f"The path {path} is not an absolute path")

        # Check if path exists (except for create command)
        if command != "create":
            try:
                # Check if path exists by running a command in the sandbox
                exists_result = await sandbox.run_command(
                    f"test -e {path} && echo 'exists' || echo 'not exists'"
                )
                if "not exists" in exists_result:
                    raise ToolError(f"The path {path} does not exist. Please provide a valid path.")

                # Check if path is a directory
                dir_result = await sandbox.run_command(
                    f"test -d {path} && echo 'directory' || echo 'file'"
                )
                is_dir = "directory" in dir_result

                if is_dir and command != "view":
                    raise ToolError(
                        f"The path {path} is a directory and only the `view` command can be used on directories"
                    )
            except Exception as e:
                if not isinstance(e, ToolError):
                    raise ToolError(f"Error validating path: {str(e)}")
                raise

        # Check if file exists for create command
        elif command == "create":
            try:
                exists_result = await sandbox.run_command(
                    f"test -e {path} && echo 'exists' || echo 'not exists'"
                )
                if "exists" in exists_result:
                    raise ToolError(
                        f"File already exists at: {path}. Cannot overwrite files using command `create`."
                    )
            except Exception as e:
                if not isinstance(e, ToolError):
                    raise ToolError(f"Error checking file existence: {str(e)}")
                raise

    async def view(
        self,
        path: str,
        view_range: Optional[List[int]] = None,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Display file or directory content."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Determine if path is a directory
        is_dir_result = await sandbox.run_command(
            f"test -d {path} && echo 'directory' || echo 'file'"
        )
        is_dir = "directory" in is_dir_result

        if is_dir:
            # Directory handling
            if view_range:
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )

            # List directory contents
            find_cmd = f"find {path} -maxdepth 2 -not -path '*/\\.*'"
            find_result = await sandbox.run_command(find_cmd)

            if isinstance(find_result, str) and find_result:
                output = (
                    f"Here are the files and directories up to 2 levels deep in {path}, "
                    f"excluding hidden items:\n{find_result}\n"
                )
                return CLIResult(output=output)
            else:
                return CLIResult(error=f"Failed to list directory contents: {path}")
        else:
            # File handling - read file content
            try:
                file_content = await sandbox.read_file(path)
                init_line = 1

                # Apply view range if specified
                if view_range:
                    if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                        raise ToolError(
                            "Invalid `view_range`. It should be a list of two integers."
                        )

                    file_lines = file_content.split("\n")
                    n_lines_file = len(file_lines)
                    init_line, final_line = view_range

                    # Validate view range
                    if init_line < 1 or init_line > n_lines_file:
                        raise ToolError(
                            f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be "
                            f"within the range of lines of the file: {[1, n_lines_file]}"
                        )
                    if final_line > n_lines_file and final_line != -1:
                        raise ToolError(
                            f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be "
                            f"smaller than the number of lines in the file: `{n_lines_file}`"
                        )
                    if final_line != -1 and final_line < init_line:
                        raise ToolError(
                            f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be "
                            f"larger or equal than its first `{init_line}`"
                        )

                    # Apply range
                    if final_line == -1:
                        file_content = "\n".join(file_lines[init_line - 1 :])
                    else:
                        file_content = "\n".join(file_lines[init_line - 1 : final_line])

                # Format the output with line numbers
                file_content = maybe_truncate(file_content)
                if hasattr(file_content, "expandtabs"):
                    file_content = file_content.expandtabs()

                # Add line numbers to each line
                numbered_content = "\n".join(
                    [
                        f"{i + init_line:6}\t{line}"
                        for i, line in enumerate(file_content.split("\n"))
                    ]
                )

                output = f"Here's the content of {path} with line numbers:\n{numbered_content}\n"
                return CLIResult(output=output)

            except Exception as e:
                return CLIResult(error=f"Failed to read file: {str(e)}")

    async def str_replace(
        self,
        path: str,
        old_str: str,
        new_str: Optional[str] = None,
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Replace a unique string in a file with a new string."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content
        file_content = await sandbox.read_file(path)
        new_str = new_str or ""

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)

        # Check if old_str is unique in the file
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            raise ToolError(
                f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}."
            )
        elif occurrences > 1:
            # Find line numbers of occurrences
            file_content_lines = file_content.split("\n")
            lines = []
            line_num = 1
            for line in file_content_lines:
                if old_str in line:
                    lines.append(line_num)
                line_num += 1

            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str in {path} "
                f"at lines {lines}. Please ensure it is unique or use regex_replace."
            )

        # Replace old_str with new_str
        new_file_content = file_content.replace(old_str, new_str)

        # Save the original content to history
        self._file_history[path].append(file_content)

        # Write the new content to the file
        await sandbox.write_file(path, new_file_content)

        # Create a snippet of the edited section
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")

        # Get snippet lines
        snippet_lines = new_file_content.split("\n")[start_line : end_line + 1]
        # Add line numbers
        numbered_snippet = "\n".join(
            [f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)]
        )

        # Prepare the success message
        success_msg = f"The file {path} has been edited.\n"
        success_msg += f"Here's a snippet of the edited section:\n{numbered_snippet}\n"

        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult(output=success_msg)

    async def regex_replace(
        self,
        path: str,
        pattern: str,
        replacement: str,
        count: int = 0,
        flags: str = "",
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Replace text in a file using a regex pattern."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content
        file_content = await sandbox.read_file(path)

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)

        # Compile the regex pattern
        try:
            regex_flags = self._build_regex_flags(flags)
            compiled_pattern = re.compile(pattern, regex_flags)
        except re.error as e:
            if backup_path:
                # Clean up backup if not needed
                await sandbox.run_command(f"rm {backup_path}")
            raise ToolError(f"Invalid regex pattern: {e}")

        # Find matches
        matches = compiled_pattern.findall(file_content)
        match_count = len(matches)

        if match_count == 0:
            if backup_path:
                # Clean up backup if not needed
                await sandbox.run_command(f"rm {backup_path}")
            raise ToolError(f"No matches found for pattern: {pattern}")

        # Perform replacement
        new_file_content, replacement_count = compiled_pattern.subn(
            replacement, file_content, count=count
        )

        if replacement_count == 0:
            if backup_path:
                # Clean up backup if not needed
                await sandbox.run_command(f"rm {backup_path}")
            raise ToolError("No replacements made. Pattern matched but replacement failed.")

        # Save the original content to history
        self._file_history[path].append(file_content)

        # Write the new content to the file
        await sandbox.write_file(path, new_file_content)

        # Find line numbers of matches (for reporting)
        file_lines = file_content.split("\n")
        match_lines: List[int] = []
        for i, line in enumerate(file_lines):
            if compiled_pattern.search(line):
                match_lines.append(i + 1)  # 1-based line numbers

        # Get snippet around first match
        if match_lines:
            first_match = match_lines[0]
            start_line = max(0, first_match - SNIPPET_LINES - 1)  # -1 to convert to 0-based
            end_line = min(
                len(file_lines), first_match + SNIPPET_LINES - 1
            )  # -1 to convert to 0-based

            # Get snippet lines from new content
            new_lines = new_file_content.split("\n")
            snippet_lines = new_lines[start_line:end_line]

            # Add line numbers
            numbered_snippet = "\n".join(
                [f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)]
            )
        else:
            numbered_snippet = "(No snippet available)"

        # Prepare the success message
        success_msg = f"The file {path} has been edited.\n"
        success_msg += f"Pattern: {pattern}\n"
        success_msg += f"Replacements made: {replacement_count}\n"
        # Format match lines - only show first 10 if there are many
        if len(match_lines) <= 10:
            match_lines_str = str(match_lines)
        else:
            match_lines_str = str(match_lines[:10]) + " and more..."
        success_msg += f"Match lines: {match_lines_str}\n"
        success_msg += f"Here's a snippet around the first match:\n{numbered_snippet}\n"

        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult(output=success_msg)

    def _find_line_numbers(self, content: str, pattern: str, count: int = 1) -> List[int]:
        """Find the line numbers that match a pattern.

        Args:
            content: File content as string
            pattern: Pattern to match
            count: Maximum number of matches to find

        Returns:
            List of line numbers (0-based)
        """
        lines = content.splitlines()
        result_matches: List[int] = []

        try:
            # Try to use regex pattern
            regex = re.compile(pattern)
            for i, line in enumerate(lines):
                if regex.search(line) and (count <= 0 or len(result_matches) < count):
                    result_matches.append(i)
        except re.error:
            # If regex fails, fall back to simple string matching
            for i, line in enumerate(lines):
                if pattern in line and (count <= 0 or len(result_matches) < count):
                    result_matches.append(i)

        return result_matches

    async def line_edit(
        self,
        path: str,
        operation: str,
        line_number: Optional[int] = None,
        pattern: Optional[str] = None,
        count: int = 1,
        after_match: bool = False,
        content: Optional[str] = None,
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Perform line-based editing operations."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content
        file_content = await sandbox.read_file(path)
        lines = file_content.splitlines()

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)

        # Determine which lines to operate on
        target_lines: List[int] = []
        if line_number is not None:
            # Convert 1-based to 0-based line numbering
            line_idx = line_number - 1
            if line_idx < 0 or line_idx >= len(lines):
                if backup_path:
                    await sandbox.run_command(f"rm {backup_path}")
                raise ToolError(f"Line number {line_number} is out of range (1-{len(lines)})")

            # Add consecutive lines if count > 1
            for i in range(count):
                if line_idx + i < len(lines):
                    target_lines.append(line_idx + i)

        elif pattern is not None:
            # Find lines matching the pattern
            matches = self._find_line_numbers(file_content, pattern, count)
            if not matches:
                if backup_path:
                    await sandbox.run_command(f"rm {backup_path}")
                raise ToolError(f"No lines matched pattern: {pattern}")
            target_lines = matches

        # Save the original content to history
        self._file_history[path].append(file_content)

        # Perform the requested operation
        modified = False
        new_lines = lines.copy()

        if operation == "delete":
            # Delete lines (starting from the end to avoid index shifting)
            for line_idx in sorted(target_lines, reverse=True):
                if 0 <= line_idx < len(new_lines):
                    del new_lines[line_idx]
                    modified = True

        elif operation == "replace":
            if content is None:
                if backup_path:
                    await sandbox.run_command(f"rm {backup_path}")
                raise ToolError("Content must be provided for replace operation")

            # Replace content in the specified lines
            replacement_lines = content.splitlines()
            for i, line_idx in enumerate(target_lines):
                if 0 <= line_idx < len(new_lines):
                    if i < len(replacement_lines):
                        new_lines[line_idx] = replacement_lines[i]
                    else:
                        # If we have more target lines than replacement lines,
                        # use the last replacement line for remaining targets
                        new_lines[line_idx] = replacement_lines[-1] if replacement_lines else ""
                    modified = True

        elif operation == "insert":
            if content is None:
                if backup_path:
                    await sandbox.run_command(f"rm {backup_path}")
                raise ToolError("Content must be provided for insert operation")

            insertion_lines = content.splitlines()

            if pattern is not None and after_match:
                # When using pattern matching with after_match, we insert after matched lines
                # Insert in reverse order to avoid index shifting
                for line_idx in sorted(target_lines, reverse=True):
                    # Insert after the matched line
                    insert_pos = line_idx + 1
                    if 0 <= insert_pos <= len(new_lines):  # <= to allow append at end
                        for ins_line in reversed(insertion_lines):
                            new_lines.insert(insert_pos, ins_line)
                        modified = True
            else:
                # Regular insertion (before matched line)
                # Insert in reverse order to avoid index shifting
                for line_idx in sorted(target_lines, reverse=True):
                    if 0 <= line_idx <= len(new_lines):  # <= to allow append at end
                        for ins_line in reversed(insertion_lines):
                            new_lines.insert(line_idx, ins_line)
                        modified = True

        # Write the modified content back to the file if changed
        if modified:
            new_content = "\n".join(new_lines)
            if file_content.endswith("\n"):  # Preserve trailing newline if it existed
                new_content += "\n"

            await sandbox.write_file(path, new_content)

            # Create snippet for preview around the modified lines
            if target_lines:
                first_line = min(target_lines)
                last_line = max(target_lines)
                start_line = max(0, first_line - SNIPPET_LINES)
                end_line = min(len(new_lines), last_line + SNIPPET_LINES + 1)

                # Get snippet lines
                snippet_lines = new_lines[start_line:end_line]
                # Add line numbers
                numbered_snippet = "\n".join(
                    [f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)]
                )

                success_msg = f"The file {path} has been edited using operation: {operation}\n"
                success_msg += f"Lines affected: {sorted([i + 1 for i in target_lines])}\n"
                success_msg += f"Here's a snippet of the edited section:\n{numbered_snippet}\n"

                if backup_path:
                    success_msg += f"Backup created at: {backup_path}\n"

                return CLIResult(output=success_msg)
            else:
                return CLIResult(
                    output=f"File {path} was modified but no snippet is available to display."
                )
        else:
            # No changes made
            if backup_path:
                await sandbox.run_command(f"rm {backup_path}")

            return CLIResult(output="No changes were made to the file.")

    async def insert(
        self,
        path: str,
        insert_line: int,
        new_str: str,
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Insert text at a specific line in a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content
        file_content = await sandbox.read_file(path)
        lines = file_content.splitlines()

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)

        # Validate insert_line
        if insert_line < 0 or insert_line > len(lines):
            if backup_path:
                await sandbox.run_command(f"rm {backup_path}")
            raise ToolError(
                f"Invalid line number {insert_line}. It should be within the range [0-{len(lines)}]"
            )

        # Save original content to history
        self._file_history[path].append(file_content)

        # Insert the new content
        new_str_lines = new_str.splitlines()
        new_lines = lines[:insert_line] + new_str_lines + lines[insert_line:]
        new_content = "\n".join(new_lines)

        # Preserve trailing newline if it existed
        if file_content.endswith("\n"):
            new_content += "\n"

        # Write the new content to the file
        await sandbox.write_file(path, new_content)

        # Create a snippet for preview
        start_line = max(0, insert_line - SNIPPET_LINES)
        end_line = min(len(new_lines), insert_line + len(new_str_lines) + SNIPPET_LINES)

        # Get snippet lines
        snippet_lines = new_lines[start_line:end_line]
        # Add line numbers
        numbered_snippet = "\n".join(
            [f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)]
        )

        success_msg = f"The file {path} has been edited with insertion at line {insert_line}\n"
        success_msg += f"Inserted {len(new_str_lines)} line(s)\n"
        success_msg += f"Here's a snippet of the edited section:\n{numbered_snippet}\n"

        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult(output=success_msg)

    async def insert_at(
        self,
        path: str,
        position: int,
        new_str: str,
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Insert text at a specific character position in a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content
        file_content = await sandbox.read_file(path)

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)

        # Validate position
        if position < 0 or position > len(file_content):
            if backup_path:
                await sandbox.run_command(f"rm {backup_path}")
            raise ToolError(
                f"Invalid position {position}. It should be within the range [0-{len(file_content)}]"
            )

        # Save original content to history
        self._file_history[path].append(file_content)

        # Insert at the specified position
        new_content = file_content[:position] + new_str + file_content[position:]

        # Write the new content to the file
        await sandbox.write_file(path, new_content)

        # Determine the line number where the insertion occurred for better context
        prefix = file_content[:position]
        line_number = prefix.count("\n") + 1  # 1-based line number

        # Create a snippet for preview
        lines = new_content.splitlines()
        # Find the line index (0-based) containing the insertion
        line_index = prefix.count("\n")

        start_line = max(0, line_index - SNIPPET_LINES)
        end_line = min(len(lines), line_index + SNIPPET_LINES + 1)

        # Get snippet lines
        snippet_lines = lines[start_line:end_line]
        # Add line numbers
        numbered_snippet = "\n".join(
            [f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)]
        )

        success_msg = f"The file {path} has been edited with insertion at position {position}\n"
        success_msg += f"(around line {line_number})\n"
        success_msg += f"Inserted: '{new_str}'\n"
        success_msg += f"Here's a snippet of the edited section:\n{numbered_snippet}\n"

        if backup_path:
            success_msg += f"Backup created at: {backup_path}\n"

        return CLIResult(output=success_msg)

    async def undo_edit(self, path: str, sandbox: Optional[BaseSandboxClient] = None) -> CLIResult:
        """Revert the last edit made to a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        if not self._file_history[path]:
            raise ToolError(f"No edit history found for {path}.")

        old_text = self._file_history[path].pop()
        await sandbox.write_file(path, old_text)

        # Create a snippet of the first few lines for preview
        lines = old_text.splitlines()
        preview_lines = lines[: min(10, len(lines))]

        # Add line numbers
        numbered_preview = "\n".join([f"{i + 1:6}\t{line}" for i, line in enumerate(preview_lines)])

        success_msg = f"Last edit to {path} was undone successfully.\n"
        if preview_lines:
            success_msg += f"Here's the beginning of the file after undo:\n{numbered_preview}\n"
            if len(lines) > 10:
                success_msg += "(File continues...)\n"

        return CLIResult(output=success_msg)
