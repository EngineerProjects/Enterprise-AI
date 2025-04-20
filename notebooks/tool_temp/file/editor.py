"""File and directory manipulation tool with sandbox support."""

from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Literal, Optional, Union, Tuple, get_args, cast

from enterprise_ai.config import get_config
from enterprise_ai.tool.core.base import BaseTool, ToolError
from enterprise_ai.tool.core.result import CLIResult, ToolResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client

# Type for command literals
Command = Literal[
    "view",
    "create",
    "str_replace",
    "insert",
    "undo_edit",
]

# Constants
SNIPPET_LINES: int = 4
MAX_RESPONSE_LEN: int = 16000
TRUNCATED_MESSAGE: str = (
    "<response clipped><NOTE>To save on context only part of this file has been shown to you. "
    "You should retry this tool after you have searched inside the file with `grep -n` "
    "in order to find the line numbers of what you are looking for.</NOTE>"
)

# Define a type for run_command results
CommandResult = Tuple[int, str, str]

# Tool description
_STR_REPLACE_EDITOR_DESCRIPTION = """Custom editing tool for viewing, creating and editing files
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
* The `new_str` parameter should contain the edited lines that should replace the `old_str`
"""


def maybe_truncate(content: str, truncate_after: Optional[int] = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length."""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE


@register_tool(category="file")
class StrReplaceEditor(BaseTool):
    """A tool for viewing, creating, and editing files with sandbox support."""

    name: str = "str_replace_editor"
    description: str = _STR_REPLACE_EDITOR_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.",
                "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                "type": "string",
            },
            "path": {
                "description": "Absolute path to file or directory.",
                "type": "string",
            },
            "file_text": {
                "description": "Required parameter of `create` command, with the content of the file to be created.",
                "type": "string",
            },
            "old_str": {
                "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                "type": "string",
            },
            "new_str": {
                "description": "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
                "type": "string",
            },
            "insert_line": {
                "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
                "type": "integer",
            },
            "view_range": {
                "description": "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                "items": {"type": "integer"},
                "type": "array",
            },
        },
        "required": ["command", "path"],
    }

    class Config:
        """Configuration for the model."""

        arbitrary_types_allowed = True

    def __init__(self) -> None:
        """Initialize the editor tool with class attributes."""
        super().__init__(name=self.name, description=self.description, parameters=self.parameters)
        self._file_history: DefaultDict[str, List[str]] = defaultdict(list)
        self._sandbox_client: Optional[BaseSandboxClient] = None

    async def _get_sandbox_client(self) -> BaseSandboxClient:
        """Get or create a sandbox client."""
        if self._sandbox_client is None:
            self._sandbox_client = create_sandbox_client()
            await self._sandbox_client.create()
        return self._sandbox_client

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a file operation command."""
        # Extract parameters from kwargs
        command = kwargs.get("command")
        if not command:
            raise ToolError("Parameter 'command' is required")

        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required")

        file_text = kwargs.get("file_text")
        view_range = kwargs.get("view_range")
        old_str = kwargs.get("old_str")
        new_str = kwargs.get("new_str")
        insert_line = kwargs.get("insert_line")

        # Get the sandbox client
        sandbox = await self._get_sandbox_client()

        # Validate path and command combination
        await self.validate_path(command, path, sandbox)

        # Execute the appropriate command
        if command == "view":
            result = await self.view(path, view_range, sandbox)
            return cast(ToolResult, result)
        elif command == "create":
            if file_text is None:
                raise ToolError("Parameter `file_text` is required for command: create")
            await sandbox.write_file(path, file_text)
            self._file_history[path].append(file_text)
            return ToolResult(output=f"File created successfully at: {path}")
        elif command == "str_replace":
            if old_str is None:
                raise ToolError("Parameter `old_str` is required for command: str_replace")
            result = await self.str_replace(path, old_str, new_str, sandbox)
            return cast(ToolResult, result)
        elif command == "insert":
            if insert_line is None:
                raise ToolError("Parameter `insert_line` is required for command: insert")
            if new_str is None:
                raise ToolError("Parameter `new_str` is required for command: insert")
            result = await self.insert(path, insert_line, new_str, sandbox)
            return cast(ToolResult, result)
        elif command == "undo_edit":
            result = await self.undo_edit(path, sandbox)
            return cast(ToolResult, result)
        else:
            # This should be caught by type checking, but we include it for safety
            raise ToolError(
                f"Unrecognized command {command}. The allowed commands are: {', '.join(get_args(Command))}"
            )

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
                cmd_result = await sandbox.run_command(
                    f"test -e {path} && echo 'exists' || echo 'not exists'"
                )

                # Safely handle the command result without unpacking
                stdout = ""
                if isinstance(cmd_result, tuple) and len(cmd_result) > 1:
                    stdout = str(cmd_result[1])

                if "not exists" in stdout:
                    raise ToolError(f"The path {path} does not exist. Please provide a valid path.")

                # Check if path is a directory
                cmd_result = await sandbox.run_command(
                    f"test -d {path} && echo 'directory' || echo 'file'"
                )

                # Safely handle the command result without unpacking
                stdout = ""
                if isinstance(cmd_result, tuple) and len(cmd_result) > 1:
                    stdout = str(cmd_result[1])

                is_dir = "directory" in stdout

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
                cmd_result = await sandbox.run_command(
                    f"test -e {path} && echo 'exists' || echo 'not exists'"
                )

                # Safely handle the command result without unpacking
                stdout = ""
                if isinstance(cmd_result, tuple) and len(cmd_result) > 1:
                    stdout = str(cmd_result[1])

                if "exists" in stdout:
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
        cmd_result = await sandbox.run_command(f"test -d {path} && echo 'directory' || echo 'file'")

        # Safely handle the command result without unpacking
        stdout = ""
        if isinstance(cmd_result, tuple) and len(cmd_result) > 1:
            stdout = str(cmd_result[1])

        is_dir = "directory" in stdout

        if is_dir:
            # Directory handling
            if view_range:
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )

            return await self._view_directory(path, sandbox)
        else:
            # File handling
            return await self._view_file(path, sandbox, view_range)

    @staticmethod
    async def _view_directory(path: str, sandbox: BaseSandboxClient) -> CLIResult:
        """Display directory contents."""
        find_cmd = f"find {path} -maxdepth 2 -not -path '*/\\.*'"

        # Execute command using the sandbox
        cmd_result = await sandbox.run_command(find_cmd)

        # Safely handle the command result without unpacking
        stdout = ""
        stderr = ""
        if isinstance(cmd_result, tuple):
            if len(cmd_result) > 1:
                stdout = str(cmd_result[1])
            if len(cmd_result) > 2:
                stderr = str(cmd_result[2])

        if not stderr:
            output = (
                f"Here's the files and directories up to 2 levels deep in {path}, "
                f"excluding hidden items:\n{stdout}\n"
            )
            return CLIResult(output=output)
        else:
            return CLIResult(error=stderr)

    async def _view_file(
        self,
        path: str,
        sandbox: BaseSandboxClient,
        view_range: Optional[List[int]] = None,
    ) -> CLIResult:
        """Display file content, optionally within a specified line range."""
        # Read file content
        file_content = await sandbox.read_file(path)
        init_line = 1

        # Apply view range if specified
        if view_range:
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                raise ToolError("Invalid `view_range`. It should be a list of two integers.")

            file_lines = file_content.split("\n")
            n_lines_file = len(file_lines)
            init_line, final_line = view_range

            # Validate view range
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be "
                    f"within the range of lines of the file: {[1, n_lines_file]}"
                )
            if final_line > n_lines_file:
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

        # Format and return result
        return CLIResult(output=self._make_output(file_content, str(path), init_line=init_line))

    async def str_replace(
        self,
        path: str,
        old_str: str,
        new_str: Optional[str] = None,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Replace a unique string in a file with a new string."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read file content and expand tabs
        file_content = await sandbox.read_file(path)
        if hasattr(file_content, "expandtabs"):
            file_content = file_content.expandtabs()
        old_str = old_str.expandtabs() if hasattr(old_str, "expandtabs") else old_str
        new_str = (
            new_str.expandtabs()
            if new_str is not None and hasattr(new_str, "expandtabs")
            else new_str or ""
        )

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
            for idx, line in enumerate(file_content_lines):
                if old_str in line:
                    lines.append(idx + 1)
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str `{old_str}` "
                f"in lines {lines}. Please ensure it is unique"
            )

        # Replace old_str with new_str
        new_file_content = file_content.replace(old_str, new_str)

        # Write the new content to the file
        await sandbox.write_file(path, new_file_content)

        # Save the original content to history
        self._file_history[path].append(file_content)

        # Create a snippet of the edited section
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        # Prepare the success message
        success_msg = f"The file {path} has been edited. "
        success_msg += self._make_output(snippet, f"a snippet of {path}", start_line + 1)
        success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

        return CLIResult(output=success_msg)

    async def insert(
        self,
        path: str,
        insert_line: int,
        new_str: str,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """Insert text at a specific line in a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        # Read and prepare content
        file_text = await sandbox.read_file(path)
        if hasattr(file_text, "expandtabs"):
            file_text = file_text.expandtabs()
        if hasattr(new_str, "expandtabs"):
            new_str = new_str.expandtabs()
        file_text_lines = file_text.split("\n")
        n_lines_file = len(file_text_lines)

        # Validate insert_line
        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"Invalid `insert_line` parameter: {insert_line}. It should be within "
                f"the range of lines of the file: {[0, n_lines_file]}"
            )

        # Perform insertion
        new_str_lines = new_str.split("\n")
        new_file_text_lines = (
            file_text_lines[:insert_line] + new_str_lines + file_text_lines[insert_line:]
        )

        # Create a snippet for preview
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )

        # Join lines and write to file
        new_file_text = "\n".join(new_file_text_lines)
        snippet = "\n".join(snippet_lines)

        await sandbox.write_file(path, new_file_text)
        self._file_history[path].append(file_text)

        # Prepare success message
        success_msg = f"The file {path} has been edited. "
        success_msg += self._make_output(
            snippet,
            "a snippet of the edited file",
            max(1, insert_line - SNIPPET_LINES + 1),
        )
        success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."

        return CLIResult(output=success_msg)

    async def undo_edit(self, path: str, sandbox: Optional[BaseSandboxClient] = None) -> CLIResult:
        """Revert the last edit made to a file."""
        if sandbox is None:
            sandbox = await self._get_sandbox_client()

        if not self._file_history[path]:
            raise ToolError(f"No edit history found for {path}.")

        old_text = self._file_history[path].pop()
        await sandbox.write_file(path, old_text)

        return CLIResult(
            output=f"Last edit to {path} undone successfully. {self._make_output(old_text, str(path))}"
        )

    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ) -> str:
        """Format file content for display with line numbers."""
        file_content = maybe_truncate(file_content)
        if expand_tabs and hasattr(file_content, "expandtabs"):
            file_content = file_content.expandtabs()

        # Add line numbers to each line
        file_content = "\n".join(
            [f"{i + init_line:6}\t{line}" for i, line in enumerate(file_content.split("\n"))]
        )

        return (
            f"Here's the result of running `cat -n` on {file_descriptor}:\n" + file_content + "\n"
        )
