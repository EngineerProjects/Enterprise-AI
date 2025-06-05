"""
Optimized file editor tool for Enterprise AI with improved modularity and maintainability.

This module provides a comprehensive tool for editing files with regex capabilities,
edit history, sandbox support, fuzzy matching analytics, and advanced error reporting.
"""

import os
import re
import time
import shutil
import subprocess
import json
import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Literal, Optional, Union, Pattern, Set, Tuple, cast
from datetime import datetime
from dataclasses import dataclass, asdict

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
    "You should retry this tool with line range parameters or use FileSystemTool for viewing.</NOTE>"
)
FUZZY_THRESHOLD: float = 0.7

# Command type
Command = Literal[
    "str_replace",
    "regex_replace", 
    "line_edit",
    "insert",
    "insert_at",
    "undo_edit",
]


# ANALYTICS SERVICE (Extracted from main tool)
@dataclass
class FuzzySearchLogEntry:
    """Log entry for fuzzy search analytics."""
    timestamp: datetime
    search_text: str
    found_text: str
    similarity: float
    execution_time: float
    exact_match_count: int
    expected_replacements: int
    fuzzy_threshold: float
    below_threshold: bool
    diff: str
    search_length: int
    found_length: int
    file_extension: str
    character_codes: str
    unique_character_count: int
    diff_length: int


class FuzzySearchAnalytics:
    """Separated analytics service for fuzzy search operations."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "fuzzy_search_analytics.jsonl"
    
    async def log_fuzzy_search(self, entry: FuzzySearchLogEntry) -> None:
        """Log a fuzzy search entry."""
        try:
            log_data = asdict(entry)
            log_data['timestamp'] = entry.timestamp.isoformat()
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_data) + '\n')
        except Exception as e:
            logger.warning(f"Failed to log fuzzy search entry: {e}")
    
    def get_log_path(self) -> str:
        """Get path to log file."""
        return str(self.log_file.absolute())


# UTILITY CLASSES (Extracted for better organization)
class LineEndingHandler:
    """Handle different line ending styles."""
    
    @staticmethod
    def detect_line_ending(content: str) -> str:
        """Detect the line ending style used in content."""
        if '\r\n' in content:
            return '\r\n'
        elif '\n' in content:
            return '\n'
        elif '\r' in content:
            return '\r'
        return '\n'
    
    @staticmethod
    def normalize_line_endings(text: str, target_ending: str) -> str:
        """Normalize line endings in text to match target style."""
        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        if target_ending != '\n':
            normalized = normalized.replace('\n', target_ending)
        return normalized


class DiffAnalyzer:
    """Handle diff analysis and character code analysis."""
    
    @staticmethod
    def highlight_differences(expected: str, actual: str) -> str:
        """Generate a character-level diff using standard {-removed-}{+added+} format."""
        prefix_length = 0
        min_length = min(len(expected), len(actual))

        while prefix_length < min_length and expected[prefix_length] == actual[prefix_length]:
            prefix_length += 1

        suffix_length = 0
        while (suffix_length < min_length - prefix_length and 
               expected[len(expected) - 1 - suffix_length] == actual[len(actual) - 1 - suffix_length]):
            suffix_length += 1
        
        common_prefix = expected[:prefix_length]
        common_suffix = expected[len(expected) - suffix_length:] if suffix_length > 0 else ""

        expected_diff = expected[prefix_length:len(expected) - suffix_length if suffix_length > 0 else len(expected)]
        actual_diff = actual[prefix_length:len(actual) - suffix_length if suffix_length > 0 else len(actual)]

        return f"{common_prefix}{{-{expected_diff}-}}{{+{actual_diff}+}}{common_suffix}"
    
    @staticmethod
    def get_character_codes_report(expected: str, actual: str) -> Tuple[str, int, int]:
        """Extract character code data from diff."""
        # Simplified version focusing on core functionality
        character_codes: Dict[int, int] = {}
        full_diff = expected + actual
        
        for char in full_diff:
            char_code = ord(char)
            character_codes[char_code] = character_codes.get(char_code, 0) + 1
        
        char_code_report = []
        for code, count in sorted(character_codes.items()):
            char = chr(code)
            char_display = f"\\x{code:02x}" if code < 32 or code > 126 else char
            char_code_report.append(f"{code}:{count}[{char_display}]")
        
        return (','.join(char_code_report), len(character_codes), len(full_diff))


class FuzzyMatcher:
    """Handle fuzzy matching operations."""
    
    @staticmethod
    def get_similarity_ratio(str1: str, str2: str) -> float:
        """Calculate similarity ratio between two strings."""
        import difflib
        return difflib.SequenceMatcher(None, str1, str2).ratio()
    
    @classmethod
    def recursive_fuzzy_search(cls, content: str, search_text: str) -> Dict[str, Any]:
        """Perform recursive fuzzy search to find the best match."""
        best_match = ""
        best_similarity = 0.0
        best_start = -1
        best_end = -1
        
        search_len = len(search_text)
        content_len = len(content)
        
        for window_factor in [1.0, 1.2, 0.8, 1.5, 0.6]:
            window_size = max(search_len, int(search_len * window_factor))
            
            for start in range(0, content_len - window_size + 1, max(1, window_size // 4)):
                end = min(start + window_size, content_len)
                candidate = content[start:end]
                
                similarity = cls.get_similarity_ratio(search_text, candidate)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = candidate
                    best_start = start
                    best_end = end
        
        return {
            'value': best_match,
            'similarity': best_similarity,
            'start': best_start,
            'end': best_end,
            'distance': abs(len(search_text) - len(best_match))
        }


# PARAMETER MODELS
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


# MAIN TOOL CLASS (Significantly simplified and modularized)
@register_tool(category="file", capabilities=["file_access", "text_editing"])
class FileEditor(BaseTool):
    """
    Optimized file editor with modular design and improved maintainability.

    Key capabilities:
    * Edit files using exact string or regex pattern replacement
    * Perform line-based operations with pattern matching
    * Insert content at specific character positions
    * Track edit history with undo functionality
    * Advanced fuzzy matching with similarity analysis
    * Comprehensive analytics logging
    * Line ending normalization handling
    * Enhanced error reporting
    * Local and sandbox execution modes
    """

    name: str = "file_editor"
    description: str = """
    Optimized file editor for precise editing operations with comprehensive validation.

    * Purpose: Edit files with precision using various editing modes
    * Usage: String/regex replacement, line operations, character insertion, undo
    * Features: Pattern matching, edit history, backups, fuzzy matching, validation
    * Returns: Edit confirmations with content previews and operation summaries

    Specialized for file editing operations with automatic file creation when needed.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The editing command to run",
                "enum": ["str_replace", "regex_replace", "line_edit", "insert", "insert_at", "undo_edit"],
                "type": "string",
            },
            "path": {"description": "Absolute path to file", "type": "string"},
            "old_str": {"description": "String to replace (for str_replace)", "type": "string"},
            "new_str": {"description": "Replacement string (for str_replace or insert)", "type": "string"},
            "regex_params": {"description": "Parameters for regex replacement", "type": "object"},
            "line_params": {"description": "Parameters for line editing", "type": "object"},
            "insert_line": {"description": "Line number for insertion (1-based)", "type": "integer"},
            "position": {"description": "Position for insertion (character offset)", "type": "integer"},
            "make_backup": {"description": "Whether to create a backup file", "type": "boolean"},
            "expected_replacements": {"description": "Expected number of replacements", "type": "integer"},
            "create_if_missing": {"description": "Create file if it doesn't exist", "type": "boolean"},
            "enable_fuzzy_matching": {"description": "Enable fuzzy matching for failed exact matches", "type": "boolean"},
            "fuzzy_threshold": {"description": "Similarity threshold for fuzzy matching (0.0-1.0)", "type": "number"},
        },
        "required": ["command", "path"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.FILE_ACCESS}
    requires_initialization: bool = True

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the optimized FileEditor tool."""
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
        
        # Initialize utility services
        self._analytics = FuzzySearchAnalytics()
        self._line_handler = LineEndingHandler()
        self._diff_analyzer = DiffAnalyzer()
        self._fuzzy_matcher = FuzzyMatcher()

        logger.debug(f"Optimized FileEditor initialized in {'local' if self._local_mode else 'sandbox'} mode")

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

    # UNIFIED FILE OPERATIONS
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
        """Check if path is a directory."""
        if self._local_mode:
            return Path(path).is_dir()
        else:
            sandbox = await self._get_sandbox_client()
            result = await self._run_sandbox_command(f"test -d {path} && echo 'directory' || echo 'file'", sandbox)
            return "directory" in result

    # VALIDATION AND SETUP
    def _validate_path_format(self, path: str) -> None:
        """Validate path format."""
        if not Path(path).is_absolute():
            raise ToolError(f"The path {path} is not an absolute path")

    async def _ensure_directory_exists(self, path: str) -> None:
        """Ensure directory exists for file path."""
        dir_path = os.path.dirname(path)
        if not dir_path:
            return

        if self._local_mode:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        else:
            sandbox = await self._get_sandbox_client()
            dir_exists = await self._run_sandbox_command(f"[ -d '{dir_path}' ] && echo 'exists' || echo 'not_exists'", sandbox)
            if "not_exists" in dir_exists:
                await self._run_sandbox_command(f"mkdir -p '{dir_path}'", sandbox)

    async def _validate_file_operation(self, command: str, path: str, create_if_missing: bool = True) -> None:
        """Validate file operation requirements."""
        self._validate_path_format(path)
        
        file_exists = await self._file_exists(path)
        is_directory = file_exists and await self._is_directory(path)
        
        if file_exists:
            if is_directory:
                raise ToolError(f"The path {path} is a directory. Use FileSystemTool for directory operations.")
            return
        else:
            if create_if_missing and command in ["str_replace", "regex_replace", "line_edit", "insert", "insert_at"]:
                await self._ensure_directory_exists(path)
                await self._write_file(path, "")
                logger.info(f"Created empty file for editing: {path}")
                return
            elif command == "undo_edit":
                raise ToolError(f"Cannot undo edit on non-existent file: {path}")
            else:
                raise ToolError(f"The path {path} does not exist. Set create_if_missing=true to create it automatically.")

    # BACKUP AND HISTORY MANAGEMENT
    async def _create_backup(self, path: str) -> Optional[str]:
        """Create backup file with timestamp."""
        if not await self._file_exists(path):
            return None

        try:
            timestamp = int(time.time())
            backup_path = f"{path}.bak.{timestamp}"
            
            if self._local_mode:
                shutil.copy2(path, backup_path)
            else:
                sandbox = await self._get_sandbox_client()
                await self._run_sandbox_command(f"cp {path} {backup_path}", sandbox)
            
            logger.debug(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
            return None

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

    # FUZZY MATCHING AND ANALYTICS
    async def _perform_fuzzy_analysis(self, content: str, search_text: str, file_path: str, 
                                    expected_replacements: int) -> FuzzySearchLogEntry:
        """Perform comprehensive fuzzy analysis with logging."""
        start_time = time.time()
        
        file_extension = Path(file_path).suffix.lower()
        fuzzy_result = self._fuzzy_matcher.recursive_fuzzy_search(content, search_text)
        similarity = fuzzy_result['similarity']
        execution_time = time.time() - start_time
        
        found_text = fuzzy_result['value']
        diff = self._diff_analyzer.highlight_differences(search_text, found_text)
        char_codes, unique_count, diff_length = self._diff_analyzer.get_character_codes_report(search_text, found_text)
        
        log_entry = FuzzySearchLogEntry(
            timestamp=datetime.now(),
            search_text=search_text,
            found_text=found_text,
            similarity=similarity,
            execution_time=execution_time,
            exact_match_count=0,
            expected_replacements=expected_replacements,
            fuzzy_threshold=FUZZY_THRESHOLD,
            below_threshold=similarity < FUZZY_THRESHOLD,
            diff=diff,
            search_length=len(search_text),
            found_length=len(found_text),
            file_extension=file_extension,
            character_codes=char_codes,
            unique_character_count=unique_count,
            diff_length=diff_length
        )
        
        await self._analytics.log_fuzzy_search(log_entry)
        return log_entry

    # UTILITY METHODS
    def _create_snippet(self, content: str, line_number: int, num_lines: int = SNIPPET_LINES) -> str:
        """Create a numbered snippet around a specific line."""
        lines = content.split("\n")
        start_line = max(0, line_number - num_lines)
        end_line = min(len(lines), line_number + num_lines + 1)
        
        snippet_lines = lines[start_line:end_line]
        return "\n".join([f"{i + start_line + 1:6}\t{line}" for i, line in enumerate(snippet_lines)])

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

    # SANDBOX UTILITIES
    async def _get_sandbox_client(self) -> Optional[BaseSandboxClient]:
        """Get sandbox client or None for local mode."""
        if self._local_mode:
            return None
        if self._sandbox_client is None:
            try:
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
            except Exception as e:
                raise ToolError(f"Failed to initialize sandbox environment: {str(e)}")
        return self._sandbox_client

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

    # MAIN EXECUTION METHOD
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a file editing command."""
        command = kwargs.get("command")
        path = kwargs.get("path")
        create_if_missing = kwargs.get("create_if_missing", True)
        
        if not command:
            raise ToolError("Parameter 'command' is required")
        if not path:
            raise ToolError("Parameter 'path' is required")

        logger.info(f"Executing editing command: {command} on path: {path}")

        try:
            await self._validate_file_operation(command, path, create_if_missing)
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)

        # Route to appropriate command handler
        try:
            if command == "str_replace":
                return await self._handle_str_replace(path, kwargs)
            elif command == "regex_replace":
                return await self._handle_regex_replace(path, kwargs)
            elif command == "line_edit":
                return await self._handle_line_edit(path, kwargs)
            elif command == "insert":
                return await self._handle_insert(path, kwargs)
            elif command == "insert_at":
                return await self._handle_insert_at(path, kwargs)
            elif command == "undo_edit":
                return await self._handle_undo_edit(path)
            else:
                raise ToolError(f"Unsupported command: {command}")
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Error executing command {command}: {str(e)}", tool_name=self.name)

    # COMMAND HANDLERS (Simplified and focused)
    async def _handle_str_replace(self, path: str, kwargs: Dict[str, Any]) -> CLIResult:
        """Handle string replacement with fuzzy matching."""
        old_str = kwargs.get("old_str")
        new_str = kwargs.get("new_str", "")
        make_backup = kwargs.get("make_backup", True)
        expected_replacements = kwargs.get("expected_replacements", 1)
        enable_fuzzy = kwargs.get("enable_fuzzy_matching", True)
        fuzzy_threshold = kwargs.get("fuzzy_threshold", FUZZY_THRESHOLD)
        
        if old_str is None:
            raise ToolError("Parameter `old_str` is required for command: str_replace")
        if old_str == "":
            raise ToolError("Empty search strings are not allowed")

        file_content = await self._read_file(path)
        file_line_ending = self._line_handler.detect_line_ending(file_content)
        normalized_search = self._line_handler.normalize_line_endings(old_str, file_line_ending)

        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path)

        # Check exact match
        occurrences = file_content.count(normalized_search)
        
        if occurrences == 0:
            if backup_path:
                await self._cleanup_backup(backup_path)
            
            if enable_fuzzy:
                fuzzy_entry = await self._perform_fuzzy_analysis(
                    file_content, old_str, path, expected_replacements
                )
                
                if fuzzy_entry.similarity >= fuzzy_threshold:
                    error_msg = (
                        f"No exact match found, but found similar text with {fuzzy_entry.similarity:.1%} similarity:\n"
                        f"Differences: {fuzzy_entry.diff}\n"
                        f"Character codes: {fuzzy_entry.character_codes}\n"
                        f"Analytics logged to: {self._analytics.get_log_path()}"
                    )
                else:
                    error_msg = (
                        f"No exact match found. Closest match has {fuzzy_entry.similarity:.1%} similarity, "
                        f"below the {fuzzy_threshold:.1%} threshold.\n"
                        f"Analytics logged to: {self._analytics.get_log_path()}"
                    )
            else:
                error_msg = f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}."
            
            raise ToolError(error_msg)
            
        elif occurrences != expected_replacements:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"Found {occurrences} occurrences but expected {expected_replacements}")

        # Perform replacement
        normalized_replacement = self._line_handler.normalize_line_endings(new_str, file_line_ending)
        new_file_content = file_content.replace(normalized_search, normalized_replacement)
        self._file_history[path].append(file_content)
        await self._write_file(path, new_file_content)

        # Create result with snippet
        replacement_line = file_content.split(normalized_search)[0].count("\n")
        snippet = self._create_snippet(new_file_content, replacement_line)

        success_msg = f"File {path} edited. Applied {expected_replacements} replacement(s).\nSnippet:\n{snippet}\n"
        if backup_path:
            success_msg += f"Backup: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_regex_replace(self, path: str, kwargs: Dict[str, Any]) -> CLIResult:
        """Handle regex replacement."""
        regex_params = kwargs.get("regex_params")
        make_backup = kwargs.get("make_backup", True)
        
        if regex_params is None:
            raise ToolError("Parameter `regex_params` is required for command: regex_replace")

        validated_params = RegexReplaceParams(**regex_params)
        file_content = await self._read_file(path)
        file_line_ending = self._line_handler.detect_line_ending(file_content)

        backup_path = None
        if make_backup and file_content:
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

        normalized_replacement = self._line_handler.normalize_line_endings(
            validated_params.replacement, file_line_ending
        )

        new_file_content, replacement_count = compiled_pattern.subn(
            normalized_replacement, file_content, count=validated_params.count
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
        success_msg = f"File {path} edited.\nPattern: {validated_params.pattern}\nReplacements: {replacement_count}\nSnippet:\n{snippet}\n"
        
        if backup_path:
            success_msg += f"Backup: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_line_edit(self, path: str, kwargs: Dict[str, Any]) -> CLIResult:
        """Handle line editing operations."""
        line_params = kwargs.get("line_params")
        make_backup = kwargs.get("make_backup", True)
        
        if line_params is None:
            raise ToolError("Parameter `line_params` is required for command: line_edit")

        line_edit_params = LineEditParams(**line_params)
        file_content = await self._read_file(path)
        file_line_ending = self._line_handler.detect_line_ending(file_content)
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
                raise ToolError(f"Line number {line_edit_params.line_number} is out of range")

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
        modified = self._apply_line_operation(new_lines, line_edit_params, target_lines, file_line_ending)

        if modified:
            new_content = file_line_ending.join(new_lines)
            if file_content.endswith(file_line_ending):
                new_content += file_line_ending

            await self._write_file(path, new_content)

            if target_lines:
                first_line = min(target_lines)
                snippet = self._create_snippet(file_line_ending.join(new_lines), first_line)
                success_msg = f"File {path} edited using operation: {line_edit_params.operation}\nLines affected: {sorted([i + 1 for i in target_lines])}\nSnippet:\n{snippet}\n"
                if backup_path:
                    success_msg += f"Backup: {backup_path}\n"
                return CLIResult.create_success(result=success_msg, tool_name=self.name)
            else:
                return CLIResult.create_success(result=f"File {path} was modified.", tool_name=self.name)
        else:
            if backup_path:
                await self._cleanup_backup(backup_path)
            return CLIResult.create_success(result="No changes were made to the file.", tool_name=self.name)

    def _apply_line_operation(self, new_lines: List[str], params: LineEditParams, 
                            target_lines: List[int], file_line_ending: str) -> bool:
        """Apply line operation to the lines list."""
        modified = False

        if params.operation == "delete":
            for line_idx in sorted(target_lines, reverse=True):
                if 0 <= line_idx < len(new_lines):
                    del new_lines[line_idx]
                    modified = True

        elif params.operation == "replace":
            if params.content is None:
                raise ToolError("Content must be provided for replace operation")
            
            normalized_content = self._line_handler.normalize_line_endings(params.content, file_line_ending)
            replacement_lines = normalized_content.splitlines()
            
            for i, line_idx in enumerate(target_lines):
                if 0 <= line_idx < len(new_lines):
                    if i < len(replacement_lines):
                        new_lines[line_idx] = replacement_lines[i]
                    else:
                        new_lines[line_idx] = replacement_lines[-1] if replacement_lines else ""
                    modified = True

        elif params.operation == "insert":
            if params.content is None:
                raise ToolError("Content must be provided for insert operation")
            
            normalized_content = self._line_handler.normalize_line_endings(params.content, file_line_ending)
            insertion_lines = normalized_content.splitlines()
            
            if params.pattern is not None and params.after_match:
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

        return modified

    async def _handle_insert(self, path: str, kwargs: Dict[str, Any]) -> CLIResult:
        """Handle line insertion."""
        insert_line = kwargs.get("insert_line")
        new_str = kwargs.get("new_str")
        make_backup = kwargs.get("make_backup", True)
        
        if insert_line is None:
            raise ToolError("Parameter `insert_line` is required for command: insert")
        if new_str is None:
            raise ToolError("Parameter `new_str` is required for command: insert")

        file_content = await self._read_file(path)
        file_line_ending = self._line_handler.detect_line_ending(file_content)
        lines = file_content.splitlines()

        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path)

        if insert_line < 0 or insert_line > len(lines) + 1:
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"Invalid line number {insert_line}. Range: [1-{len(lines) + 1}]")

        if file_content:
            self._file_history[path].append(file_content)

        insert_pos = insert_line - 1
        if insert_pos > len(lines):
            insert_pos = len(lines)

        normalized_new_str = self._line_handler.normalize_line_endings(new_str, file_line_ending)
        new_str_lines = normalized_new_str.splitlines()
        new_lines = lines[:insert_pos] + new_str_lines + lines[insert_pos:]
        new_content = file_line_ending.join(new_lines)

        if file_content.endswith(file_line_ending):
            new_content += file_line_ending

        await self._write_file(path, new_content)

        snippet = self._create_snippet(file_line_ending.join(new_lines), insert_pos)
        success_msg = f"File {path} edited with insertion at line {insert_line}\nInserted {len(new_str_lines)} line(s)\nSnippet:\n{snippet}\n"
        
        if backup_path:
            success_msg += f"Backup: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_insert_at(self, path: str, kwargs: Dict[str, Any]) -> CLIResult:
        """Handle character position insertion."""
        position = kwargs.get("position")
        new_str = kwargs.get("new_str")
        make_backup = kwargs.get("make_backup", True)
        
        if position is None:
            raise ToolError("Parameter `position` is required for command: insert_at")
        if new_str is None:
            raise ToolError("Parameter `new_str` is required for command: insert_at")

        file_content = await self._read_file(path)
        file_line_ending = self._line_handler.detect_line_ending(file_content)

        backup_path = None
        if make_backup and file_content:
            backup_path = await self._create_backup(path)

        if position < 0 or position > len(file_content):
            if backup_path:
                await self._cleanup_backup(backup_path)
            raise ToolError(f"Invalid position {position}. Range: [0-{len(file_content)}]")

        if file_content:
            self._file_history[path].append(file_content)

        normalized_new_str = self._line_handler.normalize_line_endings(new_str, file_line_ending)
        new_content = file_content[:position] + normalized_new_str + file_content[position:]
        await self._write_file(path, new_content)

        prefix = file_content[:position]
        line_number = prefix.count("\n") + 1
        line_index = prefix.count("\n")

        snippet = self._create_snippet(new_content, line_index)
        success_msg = f"File {path} edited with insertion at position {position} (line {line_number})\nInserted: '{new_str}'\nSnippet:\n{snippet}\n"
        
        if backup_path:
            success_msg += f"Backup: {backup_path}\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    async def _handle_undo_edit(self, path: str) -> CLIResult:
        """Handle undo operation."""
        if not self._file_history[path]:
            raise ToolError(f"No edit history found for {path}.")

        old_text = self._file_history[path].pop()
        await self._write_file(path, old_text)

        lines = old_text.splitlines()
        preview_lines = lines[:min(10, len(lines))]
        numbered_preview = "\n".join([f"{i + 1:6}\t{line}" for i, line in enumerate(preview_lines)])

        success_msg = f"Last edit to {path} was undone successfully.\n"
        if preview_lines:
            success_msg += f"File preview:\n{numbered_preview}\n"
            if len(lines) > 10:
                success_msg += "(File continues... Use FileSystemTool to view complete file)\n"

        return CLIResult.create_success(result=success_msg, tool_name=self.name)

    # CLEANUP
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


def maybe_truncate(content: str, truncate_after: Optional[int] = MAX_RESPONSE_LEN) -> str:
    """Truncate content and append a notice if content exceeds the specified length."""
    if not truncate_after or len(content) <= truncate_after:
        return content
    return content[:truncate_after] + TRUNCATED_MESSAGE