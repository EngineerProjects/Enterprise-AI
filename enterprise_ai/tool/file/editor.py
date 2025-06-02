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
from enterprise_ai.logger import get_logger

logger = get_logger("tool.file.editor")

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

    Notes:
    * Runs locally by default for better performance
    * Can optionally run in sandbox environment for security
    * Large files are automatically truncated in the display
    * Use view_range parameter to view specific portions of large files
    * Backups are automatically created before file modifications
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

    # Define tool capabilities
    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.FILE_ACCESS}

    # Tool requires explicit cleanup and initialization
    requires_initialization: bool = True

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[dict] = None,
        config: Optional[ToolConfig] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the FileEditor tool with standard parameters.

        Args:
            name: Override for tool name
            description: Override for tool description
            parameters: Override for tool parameters schema
            config: Tool configuration settings
            **kwargs: Additional keyword arguments
        """
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        # Store tool configuration
        self.config = config or ToolConfig(
            timeout=60.0,
            max_retries=2,
            sandbox_enabled=False,  # Local mode by default
        )

        # Initialize file history tracking
        self._file_history: DefaultDict[str, List[str]] = defaultdict(list)
        self._sandbox_client: Optional[BaseSandboxClient] = None
        self._local_mode = not getattr(self.config, 'sandbox_enabled', False)

        logger.debug(f"FileEditor tool initialized in {'local' if self._local_mode else 'sandbox'} mode")

    async def initialize(self, **kwargs: Any) -> bool:
        """
        Initialize the file editor.

        Args:
            **kwargs: Additional initialization parameters

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            if self._local_mode:
                # Local mode - no sandbox needed
                logger.info("FileEditor initialized in local mode")
                return True
            else:
                # Sandbox mode - create sandbox environment
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
                logger.info("FileEditor sandbox environment created")
                return True
        except Exception as e:
            logger.error(f"Failed to initialize FileEditor: {e}")
            # Fallback to local mode if sandbox fails
            self._local_mode = True
            logger.info("Falling back to local mode")
            return True

    async def _get_sandbox_client(self) -> Optional[BaseSandboxClient]:
        """
        Get sandbox client or None for local mode.

        Returns:
            Initialized sandbox client or None

        Raises:
            ToolError: If sandbox creation fails in sandbox mode
        """
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

    async def _run_local_command(self, command: str) -> str:
        """
        Run a command locally (for local mode).

        Args:
            command: Shell command to execute

        Returns:
            Command output as string
        """
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            logger.error(f"Error executing local command: {e}")
            raise ToolError(f"Error executing local command: {str(e)}")

    async def _run_sandbox_command(
        self, command: str, sandbox: Optional[BaseSandboxClient] = None
    ) -> str:
        """
        Run a command in sandbox or locally.

        Args:
            command: Shell command to execute
            sandbox: Optional sandbox client

        Returns:
            Command output as string
        """
        if self._local_mode:
            return await self._run_local_command(command)
        else:
            if sandbox is None:
                sandbox = await self._get_sandbox_client()
            try:
                result = await sandbox.run_command(command)
                return result
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                raise ToolError(f"Error executing command: {str(e)}")

    async def _read_file_local(self, path: str) -> str:
        """Read file content locally."""
        try:
            return Path(path).read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            raise ToolError(f"Could not read file {path}: {str(e)}")

    async def _write_file_local(self, path: str, content: str) -> None:
        """Write file content locally."""
        try:
            Path(path).write_text(content, encoding='utf-8')
        except Exception as e:
            raise ToolError(f"Could not write file {path}: {str(e)}")

    async def _create_backup_local(self, path: str) -> Optional[str]:
        """Create a backup of the file locally."""
        try:
            path_obj = Path(path)
            if not path_obj.exists():
                return None
                
            timestamp = int(time.time())
            backup_path = f"{path}.bak.{timestamp}"
            
            shutil.copy2(path, backup_path)
            logger.debug(f"Created local backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.warning(f"Failed to create local backup: {e}")
            return None

    async def _ensure_directory_exists(
        self, path: str, sandbox: Optional[BaseSandboxClient] = None
    ) -> None:
        """
        Ensure a directory exists, creating it if needed.

        Args:
            path: Path to file or directory
            sandbox: Optional sandbox client

        Raises:
            ToolError: If directory creation fails
        """
        # Extract directory path from file path
        dir_path = os.path.dirname(path)
        if not dir_path:
            # No directory component
            return

        try:
            if self._local_mode:
                # Local mode - use pathlib
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                logger.info(f"Directory structure created locally: {dir_path}")
            else:
                # Sandbox mode - use sandbox commands
                # Check if directory exists
                dir_exists = await self._run_sandbox_command(
                    f"[ -d '{dir_path}' ] && echo 'exists' || echo 'not_exists'", sandbox
                )

                if "not_exists" in dir_exists:
                    # Directory doesn't exist, create it
                    logger.info(f"Creating directory structure: {dir_path}")
                    await self._run_sandbox_command(f"mkdir -p '{dir_path}'", sandbox)

                    # Verify directory was created
                    check_result = await self._run_sandbox_command(
                        f"[ -d '{dir_path}' ] && echo 'created' || echo 'failed'", sandbox
                    )
                    if "failed" in check_result:
                        raise ToolError(f"Failed to create directory structure: {dir_path}")

                    logger.info(f"Directory structure created: {dir_path}")
                    
        except ToolError:
            raise
        except Exception as e:
            logger.error(f"Error ensuring directory exists: {e}")
            raise ToolError(f"Failed to create directory structure: {str(e)}")

    def _build_regex_flags(self, flags_str: str) -> int:
        """
        Build regex flags from string.

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

    async def _create_backup(self, path: str, sandbox: Optional[BaseSandboxClient] = None) -> Optional[str]:
        """
        Create a backup of the file.

        Args:
            path: Path to the file to back up
            sandbox: Sandbox client

        Returns:
            Path to the backup file or None if backup failed
        """
        try:
            if self._local_mode:
                return await self._create_backup_local(path)
            else:
                backup_path = f"{path}.bak"
                logger.debug(f"Creating backup at {backup_path}")
                # Use cp command to create backup
                await self._run_sandbox_command(f"cp {path} {backup_path}", sandbox)
                return backup_path
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
            return None

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute a file operation command.

        Args:
            **kwargs: Command parameters including:
                command: Operation to perform (view, create, str_replace, etc.)
                path: Path to target file or directory
                Additional parameters specific to each command

        Returns:
            ToolResult with operation result or error message
        """
        # Extract parameters from kwargs
        command = kwargs.get("command")
        if not command:
            logger.error("Missing required 'command' parameter")
            raise ToolError("Parameter 'command' is required")

        path = kwargs.get("path")
        if not path:
            logger.error("Missing required 'path' parameter")
            raise ToolError("Parameter 'path' is required")

        logger.info(f"Executing command: {command} on path: {path} (mode: {'local' if self._local_mode else 'sandbox'})")

        # Get the sandbox client (None for local mode)
        sandbox = await self._get_sandbox_client() if not self._local_mode else None

        # Validate path and command combination
        try:
            await self.validate_path(command, path, sandbox)
        except ToolError as e:
            logger.error(f"Path validation failed: {e}")
            return ToolResult(error=str(e))

        # Execute the appropriate command
        try:
            if command == "view":
                view_range = kwargs.get("view_range")
                logger.debug(f"Viewing file with range: {view_range}")
                result = await self.view(path, view_range, sandbox)
                return result

            elif command == "create":
                file_text = kwargs.get("file_text")
                if file_text is None:
                    logger.error("Missing required 'file_text' parameter")
                    raise ToolError("Parameter `file_text` is required for command: create")

                # Ensure directory exists before creating file
                await self._ensure_directory_exists(path, sandbox)

                logger.debug(f"Creating file at {path}")
                if self._local_mode:
                    # Local file creation
                    await self._write_file_local(path, file_text)
                else:
                    # Sandbox file creation
                    await sandbox.write_file(path, file_text)
                
                logger.info(f"File created successfully at: {path}")
                return ToolResult(output=f"File created successfully at: {path}")

            elif command == "str_replace":
                old_str = kwargs.get("old_str")
                new_str = kwargs.get("new_str")
                make_backup = kwargs.get("make_backup", True)

                if old_str is None:
                    logger.error("Missing required 'old_str' parameter")
                    raise ToolError("Parameter `old_str` is required for command: str_replace")

                logger.debug(f"Replacing string in {path}")
                return await self.str_replace(path, old_str, new_str, make_backup, sandbox)

            elif command == "regex_replace":
                regex_params = kwargs.get("regex_params")
                make_backup = kwargs.get("make_backup", True)

                if regex_params is None:
                    logger.error("Missing required 'regex_params' parameter")
                    raise ToolError("Parameter `regex_params` is required for command: regex_replace")

                # Validate and extract regex params
                validated_params = RegexReplaceParams(**regex_params)
                logger.debug(f"Performing regex replacement in {path}")
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
                    logger.error("Missing required 'line_params' parameter")
                    raise ToolError("Parameter `line_params` is required for command: line_edit")

                # Validate and extract line edit params
                line_edit_params = LineEditParams(**line_params)
                logger.debug(f"Performing line edit in {path}")
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
                    logger.error("Missing required 'insert_line' parameter")
                    raise ToolError("Parameter `insert_line` is required for command: insert")
                if new_str is None:
                    logger.error("Missing required 'new_str' parameter")
                    raise ToolError("Parameter `new_str` is required for command: insert")

                logger.debug(f"Inserting at line {insert_line} in {path}")
                return await self.insert(path, insert_line, new_str, make_backup, sandbox)

            elif command == "insert_at":
                position = kwargs.get("position")
                new_str = kwargs.get("new_str")
                make_backup = kwargs.get("make_backup", True)

                if position is None:
                    logger.error("Missing required 'position' parameter")
                    raise ToolError("Parameter `position` is required for command: insert_at")
                if new_str is None:
                    logger.error("Missing required 'new_str' parameter")
                    raise ToolError("Parameter `new_str` is required for command: insert_at")

                logger.debug(f"Inserting at position {position} in {path}")
                return await self.insert_at(path, position, new_str, make_backup, sandbox)

            elif command == "undo_edit":
                logger.debug(f"Undoing last edit for {path}")
                return await self.undo_edit(path, sandbox)

            else:
                logger.error(f"Unsupported command: {command}")
                raise ToolError(f"Unsupported command: {command}")

        except ToolError as e:
            # Pass through tool errors
            logger.error(f"Tool error during {command}: {e}")
            return ToolResult(error=str(e))
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error executing command {command}: {e}")
            return ToolResult(error=f"Error executing command {command}: {str(e)}")

    async def validate_path(self, command: str, path: str, sandbox: Optional[BaseSandboxClient]) -> None:
        """
        Validate path and command combination.

        Args:
            command: Operation to perform
            path: Path to validate
            sandbox: Sandbox client (None for local mode)

        Raises:
            ToolError: If path validation fails
        """
        path_obj = Path(path)

        # Check if path is absolute
        if not path_obj.is_absolute():
            logger.error(f"Path is not absolute: {path}")
            raise ToolError(f"The path {path} is not an absolute path")

        # Check if path exists (except for create command)
        if command != "create":
            try:
                if self._local_mode:
                    # Local mode - use pathlib
                    if not path_obj.exists():
                        if command in ["str_replace", "regex_replace", "line_edit", "insert", "insert_at"]:
                            # Check if parent directory exists
                            if not path_obj.parent.exists():
                                logger.warning(f"Parent directory does not exist: {path_obj.parent}")
                        else:
                            logger.error(f"Path does not exist: {path}")
                            raise ToolError(f"The path {path} does not exist. Please provide a valid path.")
                    
                    is_dir = path_obj.is_dir()
                else:
                    # Sandbox mode - use sandbox commands
                    exists_result = await self._run_sandbox_command(
                        f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
                    )
                    if "not exists" in exists_result:
                        if command in ["str_replace", "regex_replace", "line_edit", "insert", "insert_at"]:
                            dir_path = os.path.dirname(path)
                            if dir_path:
                                dir_exists = await self._run_sandbox_command(
                                    f"test -d {dir_path} && echo 'exists' || echo 'not exists'", sandbox
                                )
                                if "not exists" in dir_exists:
                                    logger.warning(f"Parent directory does not exist: {dir_path}")
                        else:
                            logger.error(f"Path does not exist: {path}")
                            raise ToolError(f"The path {path} does not exist. Please provide a valid path.")

                    # Check if path is a directory
                    dir_result = await self._run_sandbox_command(
                        f"test -d {path} && echo 'directory' || echo 'file'", sandbox
                    )
                    is_dir = "directory" in dir_result

                if is_dir and command != "view":
                    logger.error(f"Path is a directory but command is not 'view': {path}")
                    raise ToolError(
                        f"The path {path} is a directory and only the `view` command can be used on directories"
                    )
            except Exception as e:
                if not isinstance(e, ToolError):
                    logger.error(f"Error validating path: {e}")
                    raise ToolError(f"Error validating path: {str(e)}")
                raise

        # Check if file exists for create command
        elif command == "create":
            try:
                if self._local_mode:
                    # Local mode
                    if path_obj.exists():
                        logger.error(f"File already exists: {path}")
                        raise ToolError(f"File already exists at: {path}. Cannot overwrite files using command `create`.")
                else:
                    # Sandbox mode
                    exists_result = await self._run_sandbox_command(
                        f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
                    )
                    if "exists" in exists_result:
                        logger.error(f"File already exists: {path}")
                        raise ToolError(f"File already exists at: {path}. Cannot overwrite files using command `create`.")
            except Exception as e:
                if not isinstance(e, ToolError):
                    logger.error(f"Error checking file existence: {e}")
                    raise ToolError(f"Error checking file existence: {str(e)}")
                raise

    async def view(
        self,
        path: str,
        view_range: Optional[List[int]] = None,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """
        Display file or directory content.

        Args:
            path: Path to file or directory
            view_range: Optional line range to view [start, end]
            sandbox: Sandbox client (None for local mode)

        Returns:
            CLIResult with file or directory content
        """
        # Determine if path is a directory
        if self._local_mode:
            path_obj = Path(path)
            is_dir = path_obj.is_dir()
        else:
            is_dir_result = await self._run_sandbox_command(
                f"test -d {path} && echo 'directory' || echo 'file'", sandbox
            )
            is_dir = "directory" in is_dir_result

        if is_dir:
            # Directory handling
            if view_range:
                logger.warning("view_range parameter not allowed for directories")
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )

            if self._local_mode:
                # Local directory listing
                try:
                    path_obj = Path(path)
                    items = list(path_obj.iterdir())
                    items = sorted(items, key=lambda x: (x.is_file(), x.name))  # Dirs first, then files
                    
                    output = f"Here are the files and directories in {path}:\n"
                    for item in items[:100]:  # Limit to 100 items
                        item_type = "[DIR]" if item.is_dir() else "[FILE]"
                        output += f"{item_type} {item.name}\n"
                    
                    if len(items) > 100:
                        output += f"... and {len(items) - 100} more items\n"
                    
                    logger.info(f"Listed local directory contents: {path}")
                    return CLIResult(output=output)
                except Exception as e:
                    logger.warning(f"Failed to list local directory contents: {path}")
                    return CLIResult(error=f"Failed to list directory contents: {str(e)}")
            else:
                # Sandbox directory listing
                find_cmd = f"find {path} -maxdepth 2 -not -path '*/\\.*'"
                find_result = await self._run_sandbox_command(find_cmd, sandbox)

                if isinstance(find_result, str) and find_result:
                    output = (
                        f"Here are the files and directories up to 2 levels deep in {path}, "
                        f"excluding hidden items:\n{find_result}\n"
                    )
                    logger.info(f"Listed directory contents: {path}")
                    return CLIResult(output=output)
                else:
                    logger.warning(f"Failed to list directory contents: {path}")
                    return CLIResult(error=f"Failed to list directory contents: {path}")
        else:
            # File handling - read file content
            try:
                if self._local_mode:
                    file_content = await self._read_file_local(path)
                else:
                    file_content = await sandbox.read_file(path)
                    
                init_line = 1

                # Apply view range if specified
                if view_range:
                    if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                        logger.error(f"Invalid view_range: {view_range}")
                        raise ToolError(
                            "Invalid `view_range`. It should be a list of two integers."
                        )

                    file_lines = file_content.split("\n")
                    n_lines_file = len(file_lines)
                    init_line, final_line = view_range

                    # Validate view range
                    if init_line < 1 or init_line > n_lines_file:
                        logger.error(f"Invalid view_range start line: {init_line}")
                        raise ToolError(
                            f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be "
                            f"within the range of lines of the file: {[1, n_lines_file]}"
                        )
                    if final_line > n_lines_file and final_line != -1:
                        logger.error(f"Invalid view_range end line: {final_line}")
                        raise ToolError(
                            f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be "
                            f"smaller than the number of lines in the file: `{n_lines_file}`"
                        )
                    if final_line != -1 and final_line < init_line:
                        logger.error(f"Invalid view_range (end < start): {view_range}")
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
                logger.info(f"Viewed file content: {path}")
                return CLIResult(output=output)

            except Exception as e:
                logger.error(f"Failed to read file: {e}")
                return CLIResult(error=f"Failed to read file: {str(e)}")

    async def str_replace(
        self,
        path: str,
        old_str: str,
        new_str: Optional[str] = None,
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """
        Replace a unique string in a file with a new string.

        Args:
            path: Path to the file
            old_str: String to replace
            new_str: Replacement string
            make_backup: Whether to create a backup
            sandbox: Sandbox client

        Returns:
            CLIResult with replacement result
        """
        # Check if file exists, and create path to it if needed
        if self._local_mode:
            path_obj = Path(path)
            if not path_obj.exists():
                await self._ensure_directory_exists(path, sandbox)
                logger.error(f"File does not exist for replacement: {path}")
                raise ToolError(f"The file {path} does not exist for replacement operation.")
        else:
            exists_result = await self._run_sandbox_command(
                f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
            )
            if "not exists" in exists_result:
                await self._ensure_directory_exists(path, sandbox)
                logger.error(f"File does not exist for replacement: {path}")
                raise ToolError(f"The file {path} does not exist for replacement operation.")

        # Read file content
        if self._local_mode:
            file_content = await self._read_file_local(path)
        else:
            file_content = await sandbox.read_file(path)
            
        new_str = new_str or ""

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)
            logger.debug(f"Created backup at: {backup_path}")

        # Check if old_str is unique in the file
        occurrences = file_content.count(old_str)
        if occurrences == 0:
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.warning(f"String not found: {old_str}")
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

            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.warning(f"Multiple occurrences found: {old_str}")
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str in {path} "
                f"at lines {lines}. Please ensure it is unique or use regex_replace."
            )

        # Replace old_str with new_str
        new_file_content = file_content.replace(old_str, new_str)

        # Save the original content to history
        self._file_history[path].append(file_content)
        logger.debug(f"Added original content to history for {path}")

        # Write the new content to the file
        if self._local_mode:
            await self._write_file_local(path, new_file_content)
        else:
            await sandbox.write_file(path, new_file_content)
        logger.info(f"Successfully replaced string in {path}")

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
        """
        Replace text in a file using a regex pattern.

        Args:
            path: Path to the file
            pattern: Regex pattern to match
            replacement: Replacement string
            count: Maximum replacements (0 = all)
            flags: Regex flags
            make_backup: Whether to create a backup
            sandbox: Sandbox client

        Returns:
            CLIResult with replacement result
        """
        # Check if file exists, and create path to it if needed
        if self._local_mode:
            path_obj = Path(path)
            if not path_obj.exists():
                await self._ensure_directory_exists(path, sandbox)
                logger.error(f"File does not exist for replacement: {path}")
                raise ToolError(f"The file {path} does not exist for replacement operation.")
        else:
            exists_result = await self._run_sandbox_command(
                f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
            )
            if "not exists" in exists_result:
                await self._ensure_directory_exists(path, sandbox)
                logger.error(f"File does not exist for replacement: {path}")
                raise ToolError(f"The file {path} does not exist for replacement operation.")

        # Read file content
        if self._local_mode:
            file_content = await self._read_file_local(path)
        else:
            file_content = await sandbox.read_file(path)

        # Create backup if requested
        backup_path = None
        if make_backup:
            backup_path = await self._create_backup(path, sandbox)
            logger.debug(f"Created backup at: {backup_path}")

        # Compile the regex pattern
        try:
            regex_flags = self._build_regex_flags(flags)
            compiled_pattern = re.compile(pattern, regex_flags)
            logger.debug(f"Compiled regex pattern: {pattern} with flags: {flags}")
        except re.error as e:
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.error(f"Invalid regex pattern: {e}")
            raise ToolError(f"Invalid regex pattern: {e}")

        # Find matches
        matches = compiled_pattern.findall(file_content)
        match_count = len(matches)

        if match_count == 0:
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.warning(f"No matches found for pattern: {pattern}")
            raise ToolError(f"No matches found for pattern: {pattern}")

        # Perform replacement
        new_file_content, replacement_count = compiled_pattern.subn(
            replacement, file_content, count=count
        )

        if replacement_count == 0:
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.warning("No replacements made")
            raise ToolError("No replacements made. Pattern matched but replacement failed.")

        # Save the original content to history
        self._file_history[path].append(file_content)
        logger.debug(f"Added original content to history for {path}")

        # Write the new content to the file
        if self._local_mode:
            await self._write_file_local(path, new_file_content)
        else:
            await sandbox.write_file(path, new_file_content)
        logger.info(f"Successfully replaced {replacement_count} occurrences in {path}")

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
        """
        Find the line numbers that match a pattern.

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
        """
        Perform line-based editing operations.

        Args:
            path: Path to file
            operation: Operation type (insert, delete, replace)
            line_number: Line number to operate on (1-based)
            pattern: Pattern to match lines
            count: Number of lines to affect
            after_match: Insert after matched line
            content: Content for insert/replace
            make_backup: Whether to create backup
            sandbox: Sandbox client

        Returns:
            CLIResult with edit result
        """
        # Check if file exists, and create path to it if needed
        if self._local_mode:
            path_obj = Path(path)
            if not path_obj.exists():
                if operation == "insert":
                    await self._ensure_directory_exists(path, sandbox)
                    await self._write_file_local(path, "")
                    logger.info(f"Created empty file for insertion: {path}")
                    file_content = ""
                else:
                    logger.error(f"File does not exist for {operation} operation: {path}")
                    raise ToolError(f"The file {path} does not exist for {operation} operation.")
            else:
                file_content = await self._read_file_local(path)
        else:
            exists_result = await self._run_sandbox_command(
                f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
            )
            if "not exists" in exists_result:
                if operation == "insert":
                    await self._ensure_directory_exists(path, sandbox)
                    await sandbox.write_file(path, "")
                    logger.info(f"Created empty file for insertion: {path}")
                    file_content = ""
                else:
                    logger.error(f"File does not exist for {operation} operation: {path}")
                    raise ToolError(f"The file {path} does not exist for {operation} operation.")
            else:
                file_content = await sandbox.read_file(path)

        lines = file_content.splitlines()

        # Create backup if requested
        backup_path = None
        if make_backup and file_content:  # Only create backup if file already had content
            backup_path = await self._create_backup(path, sandbox)
            logger.debug(f"Created backup at: {backup_path}")

        # Determine which lines to operate on
        target_lines: List[int] = []
        if line_number is not None:
            # Convert 1-based to 0-based line numbering
            line_idx = line_number - 1
            if operation != "insert" and (line_idx < 0 or line_idx >= len(lines)):
                if backup_path and not self._local_mode:
                    await self._run_sandbox_command(f"rm {backup_path}", sandbox)
                elif backup_path and self._local_mode:
                    Path(backup_path).unlink(missing_ok=True)
                logger.error(f"Line number out of range: {line_number}")
                raise ToolError(f"Line number {line_number} is out of range (1-{len(lines)})")

            # For insert, allow line number at end of file
            if operation == "insert" and line_idx > len(lines):
                if backup_path and not self._local_mode:
                    await self._run_sandbox_command(f"rm {backup_path}", sandbox)
                elif backup_path and self._local_mode:
                    Path(backup_path).unlink(missing_ok=True)
                logger.error(f"Line number out of range: {line_number}")
                raise ToolError(f"Line number {line_number} is out of range (1-{len(lines) + 1})")

            # Add consecutive lines if count > 1
            for i in range(count):
                if operation == "insert" or line_idx + i < len(lines):
                    target_lines.append(line_idx + i)

        elif pattern is not None:
            # Find lines matching the pattern
            matches = self._find_line_numbers(file_content, pattern, count)
            if not matches:
                if backup_path and not self._local_mode:
                    await self._run_sandbox_command(f"rm {backup_path}", sandbox)
                elif backup_path and self._local_mode:
                    Path(backup_path).unlink(missing_ok=True)
                logger.warning(f"No lines matched pattern: {pattern}")
                raise ToolError(f"No lines matched pattern: {pattern}")
            target_lines = matches

        # Save the original content to history if file existed
        if file_content:
            self._file_history[path].append(file_content)
            logger.debug(f"Added original content to history for {path}")

        # Perform the requested operation
        modified = False
        new_lines = lines.copy()

        if operation == "delete":
            # Delete lines (starting from the end to avoid index shifting)
            for line_idx in sorted(target_lines, reverse=True):
                if 0 <= line_idx < len(new_lines):
                    logger.debug(f"Deleting line {line_idx + 1}")
                    del new_lines[line_idx]
                    modified = True

        elif operation == "replace":
            if content is None:
                if backup_path and not self._local_mode:
                    await self._run_sandbox_command(f"rm {backup_path}", sandbox)
                elif backup_path and self._local_mode:
                    Path(backup_path).unlink(missing_ok=True)
                logger.error("Missing content for replace operation")
                raise ToolError("Content must be provided for replace operation")

            # Replace content in the specified lines
            replacement_lines = content.splitlines()
            for i, line_idx in enumerate(target_lines):
                if 0 <= line_idx < len(new_lines):
                    if i < len(replacement_lines):
                        logger.debug(f"Replacing line {line_idx + 1}")
                        new_lines[line_idx] = replacement_lines[i]
                    else:
                        # If we have more target lines than replacement lines,
                        # use the last replacement line for remaining targets
                        new_lines[line_idx] = replacement_lines[-1] if replacement_lines else ""
                    modified = True

        elif operation == "insert":
            if content is None:
                if backup_path and not self._local_mode:
                    await self._run_sandbox_command(f"rm {backup_path}", sandbox)
                elif backup_path and self._local_mode:
                    Path(backup_path).unlink(missing_ok=True)
                logger.error("Missing content for insert operation")
                raise ToolError("Content must be provided for insert operation")

            insertion_lines = content.splitlines()

            if pattern is not None and after_match:
                # When using pattern matching with after_match, we insert after matched lines
                # Insert in reverse order to avoid index shifting
                for line_idx in sorted(target_lines, reverse=True):
                    # Insert after the matched line
                    insert_pos = line_idx + 1
                    if 0 <= insert_pos <= len(new_lines):  # <= to allow append at end
                        logger.debug(f"Inserting after line {line_idx + 1}")
                        for ins_line in reversed(insertion_lines):
                            new_lines.insert(insert_pos, ins_line)
                        modified = True
            else:
                # Regular insertion (before matched line)
                # Insert in reverse order to avoid index shifting
                for line_idx in sorted(target_lines, reverse=True):
                    if 0 <= line_idx <= len(new_lines):  # <= to allow append at end
                        logger.debug(f"Inserting at line {line_idx + 1}")
                        for ins_line in reversed(insertion_lines):
                            new_lines.insert(line_idx, ins_line)
                        modified = True

        # Write the modified content back to the file if changed
        if modified:
            new_content = "\n".join(new_lines)
            if file_content.endswith("\n"):  # Preserve trailing newline if it existed
                new_content += "\n"

            if self._local_mode:
                await self._write_file_local(path, new_content)
            else:
                await sandbox.write_file(path, new_content)
            logger.info(f"Successfully applied {operation} operation to {path}")

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
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.warning("No changes were made to the file")
            return CLIResult(output="No changes were made to the file.")

    async def insert(
        self,
        path: str,
        insert_line: int,
        new_str: str,
        make_backup: bool = True,
        sandbox: Optional[BaseSandboxClient] = None,
    ) -> CLIResult:
        """
        Insert text at a specific line in a file.

        Args:
            path: Path to the file
            insert_line: Line number to insert at (1-based)
            new_str: Text to insert
            make_backup: Whether to create a backup
            sandbox: Sandbox client

        Returns:
            CLIResult with insertion result
        """
        # Check if file exists, and create path to it if needed
        if self._local_mode:
            path_obj = Path(path)
            if not path_obj.exists():
                await self._ensure_directory_exists(path, sandbox)
                await self._write_file_local(path, "")
                logger.info(f"Created empty file for insertion: {path}")
                file_content = ""
                lines = []
            else:
                file_content = await self._read_file_local(path)
                lines = file_content.splitlines()
        else:
            exists_result = await self._run_sandbox_command(
                f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
            )
            if "not exists" in exists_result:
                await self._ensure_directory_exists(path, sandbox)
                await sandbox.write_file(path, "")
                logger.info(f"Created empty file for insertion: {path}")
                file_content = ""
                lines = []
            else:
                file_content = await sandbox.read_file(path)
                lines = file_content.splitlines()

        # Create backup if requested and file has content
        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path, sandbox)
            logger.debug(f"Created backup at: {backup_path}")

        # Validate insert_line
        if insert_line < 0 or insert_line > len(lines) + 1:
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.error(f"Invalid line number for insertion: {insert_line}")
            raise ToolError(
                f"Invalid line number {insert_line}. It should be within the range [1-{len(lines) + 1}]"
            )

        # Save original content to history if file had content
        if file_content:
            self._file_history[path].append(file_content)
            logger.debug(f"Added original content to history for {path}")

        # For insertion at end of file when file is empty or doesn't exist,
        # insert at position 0
        insert_pos = insert_line - 1  # Convert to 0-based
        if insert_pos > len(lines):
            insert_pos = len(lines)

        # Insert the new content
        new_str_lines = new_str.splitlines()
        new_lines = lines[:insert_pos] + new_str_lines + lines[insert_pos:]
        new_content = "\n".join(new_lines)

        # Preserve trailing newline if it existed
        if file_content.endswith("\n"):
            new_content += "\n"

        # Write the new content to the file
        if self._local_mode:
            await self._write_file_local(path, new_content)
        else:
            await sandbox.write_file(path, new_content)
        logger.info(f"Successfully inserted at line {insert_line} in {path}")

        # Create a snippet for preview
        start_line = max(0, insert_pos - SNIPPET_LINES)
        end_line = min(len(new_lines), insert_pos + len(new_str_lines) + SNIPPET_LINES)

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
        """
        Insert text at a specific character position in a file.

        Args:
            path: Path to the file
            position: Character position to insert at
            new_str: Text to insert
            make_backup: Whether to create a backup
            sandbox: Sandbox client

        Returns:
            CLIResult with insertion result
        """
        # Check if file exists, and create path to it if needed
        if self._local_mode:
            path_obj = Path(path)
            if not path_obj.exists():
                if position == 0:
                    await self._ensure_directory_exists(path, sandbox)
                    await self._write_file_local(path, "")
                    logger.info(f"Created empty file for insertion: {path}")
                    file_content = ""
                else:
                    logger.error(f"File does not exist for insert_at operation: {path}")
                    raise ToolError(f"The file {path} does not exist for insert_at operation.")
            else:
                file_content = await self._read_file_local(path)
        else:
            exists_result = await self._run_sandbox_command(
                f"test -e {path} && echo 'exists' || echo 'not exists'", sandbox
            )
            if "not exists" in exists_result:
                if position == 0:
                    await self._ensure_directory_exists(path, sandbox)
                    await sandbox.write_file(path, "")
                    logger.info(f"Created empty file for insertion: {path}")
                    file_content = ""
                else:
                    logger.error(f"File does not exist for insert_at operation: {path}")
                    raise ToolError(f"The file {path} does not exist for insert_at operation.")
            else:
                file_content = await sandbox.read_file(path)

        # Create backup if requested
        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path, sandbox)
            logger.debug(f"Created backup at: {backup_path}")

        # Validate position
        if position < 0 or position > len(file_content):
            if backup_path and not self._local_mode:
                await self._run_sandbox_command(f"rm {backup_path}", sandbox)
            elif backup_path and self._local_mode:
                Path(backup_path).unlink(missing_ok=True)
            logger.error(f"Invalid position for insertion: {position}")
            raise ToolError(
                f"Invalid position {position}. It should be within the range [0-{len(file_content)}]"
            )

        # Save original content to history if file had content
        if file_content:
            self._file_history[path].append(file_content)
            logger.debug(f"Added original content to history for {path}")

        # Insert at the specified position
        new_content = file_content[:position] + new_str + file_content[position:]

        # Write the new content to the file
        if self._local_mode:
            await self._write_file_local(path, new_content)
        else:
            await sandbox.write_file(path, new_content)
        logger.info(f"Successfully inserted at position {position} in {path}")

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
        """
        Revert the last edit made to a file.

        Args:
            path: Path to the file
            sandbox: Sandbox client

        Returns:
            CLIResult with undo result
        """
        if not self._file_history[path]:
            logger.warning(f"No edit history found for {path}")
            raise ToolError(f"No edit history found for {path}.")

        old_text = self._file_history[path].pop()
        logger.debug(f"Retrieved previous version from history for {path}")

        if self._local_mode:
            await self._write_file_local(path, old_text)
        else:
            await sandbox.write_file(path, old_text)
        logger.info(f"Successfully undid last edit to {path}")

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

    async def cleanup(self) -> None:
        """Clean up resources used by the file editor."""
        logger.info("Cleaning up file editor resources")

        # Clean up sandbox client if it exists
        if self._sandbox_client:
            try:
                # Check for cleanup method
                if hasattr(self._sandbox_client, "cleanup") and callable(
                    getattr(self._sandbox_client, "cleanup")
                ):
                    await self._sandbox_client.cleanup()
                    logger.debug("Sandbox client cleaned up")
                # Check for alternative close method
                elif hasattr(self._sandbox_client, "close") and callable(
                    getattr(self._sandbox_client, "close")
                ):
                    await self._sandbox_client.close()
                    logger.debug("Sandbox client closed")
                else:
                    logger.warning("Sandbox client does not have cleanup or close method")
            except Exception as e:
                logger.warning(f"Error closing sandbox client: {e}")
            finally:
                self._sandbox_client = None

        # Clear file history
        self._file_history = defaultdict(list)