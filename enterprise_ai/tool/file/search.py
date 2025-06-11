"""
Advanced code and text search tool for Enterprise AI.

This module provides powerful text search capabilities within files using
pattern matching, regex support, and context-aware results.
"""

import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple

from pydantic import BaseModel, Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.tool.core.registry import register_tool
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.file.search")


class SearchResult(BaseModel):
    """Search result model."""
    file: str
    line: int
    match: str
    context_before: Optional[List[str]] = None
    context_after: Optional[List[str]] = None


@register_tool(category="file", capabilities=["file_access", "code_search"])
class CodeSearchTool(BaseTool):
    """
    Advanced code and text search tool with pattern matching and context support.

    Key capabilities:
    * Search for text patterns within files using regex or plain text
    * Filter searches by file patterns (e.g., *.py, *.js)
    * Case-sensitive and case-insensitive search modes
    * Context lines before and after matches for better understanding
    * Limit results to prevent overwhelming output
    * Include or exclude hidden files from search
    * High-performance search using ripgrep when available
    * Fallback to native Python implementation when needed
    * Support for both local and sandbox execution

    Use this tool when:
    * You need to find specific code patterns or text in files
    * You want to search across multiple files in a directory tree
    * You need context around matches to understand code structure
    * You're looking for function definitions, variable usage, or specific patterns
    * You want to filter searches to specific file types
    * You need fast search across large codebases
    """

    name: str = "code_search"
    short_description: str = "Find text patterns in LOCAL code and text files. CANNOT search the web or internet."
    description: str = """
    Advanced code and text search with pattern matching and context support.

    * Purpose: Search for text patterns within files with advanced filtering and context
    * Usage: Find code patterns, text matches, function definitions across file trees
    * Features: Regex support, file filtering, context lines, case-insensitive search
    * Returns: Matching lines with file locations, line numbers, and optional context

    Uses high-performance ripgrep when available, with intelligent fallback to native
    Python implementation. Provides detailed search results with configurable context.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "path": {"description": "Root directory path to search in", "type": "string"},
            "pattern": {"description": "Text or regex pattern to search for", "type": "string"},
            "file_pattern": {"description": "File pattern filter (e.g., '*.py', '*.js')", "type": "string"},
            "ignore_case": {"description": "Perform case-insensitive search", "type": "boolean"},
            "max_results": {"description": "Maximum number of results to return", "type": "integer"},
            "include_hidden": {"description": "Include hidden files in search", "type": "boolean"},
            "context_lines": {"description": "Number of context lines before and after matches", "type": "integer"},
            "timeout_ms": {"description": "Search timeout in milliseconds", "type": "integer"},
            "use_regex": {"description": "Treat pattern as regular expression", "type": "boolean"},
            "exclude_dirs": {"description": "Directories to exclude from search", "items": {"type": "string"}, "type": "array"},
        },
        "required": ["path", "pattern"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.FILE_ACCESS}
    requires_initialization: bool = True

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the CodeSearchTool."""
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

        logger.debug(f"CodeSearchTool initialized in {'local' if self._local_mode else 'sandbox'} mode")

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the code search tool."""
        try:
            if not self._local_mode:
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
                logger.info("CodeSearchTool sandbox environment created")
            else:
                logger.info("CodeSearchTool initialized in local mode")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize CodeSearchTool: {e}")
            self._local_mode = True
            logger.info("Falling back to local mode")
            return True

    def _validate_path(self, path: str) -> str:
        """Validate and normalize path."""
        if not path:
            raise ToolError("Path cannot be empty")
        
        abs_path = str(Path(path).resolve())
        
        if not Path(abs_path).exists():
            raise ToolError(f"Search path does not exist: {path}")
        
        if not Path(abs_path).is_dir():
            raise ToolError(f"Search path must be a directory: {path}")
        
        return abs_path

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a code search operation."""
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")
        
        if not path:
            raise ToolError("Parameter 'path' is required")
        if not pattern:
            raise ToolError("Parameter 'pattern' is required")

        # Extract parameters with defaults
        file_pattern = kwargs.get("file_pattern")
        ignore_case = kwargs.get("ignore_case", True)
        max_results = kwargs.get("max_results", 1000)
        include_hidden = kwargs.get("include_hidden", False)
        context_lines = kwargs.get("context_lines", 0)
        timeout_ms = kwargs.get("timeout_ms", 30000)
        use_regex = kwargs.get("use_regex", False)
        exclude_dirs = kwargs.get("exclude_dirs", ["node_modules", ".git", "dist", "__pycache__"])

        logger.info(f"Searching for pattern '{pattern}' in {path}")

        try:
            validated_path = self._validate_path(path)
            
            # Try high-performance search first
            try:
                results = await self._ripgrep_search(
                    validated_path, pattern, file_pattern, ignore_case, 
                    max_results, include_hidden, context_lines, timeout_ms, use_regex
                )
            except Exception as e:
                logger.warning(f"Ripgrep search failed: {e}, falling back to native search")
                results = await self._native_search(
                    validated_path, pattern, file_pattern, ignore_case,
                    max_results, exclude_dirs, context_lines, timeout_ms, use_regex, include_hidden
                )

            return await self._format_results(results, pattern, validated_path, max_results)
            
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Search failed: {str(e)}", tool_name=self.name)

    async def _ripgrep_search(self, root_path: str, pattern: str, file_pattern: Optional[str], 
                            ignore_case: bool, max_results: int, include_hidden: bool, 
                            context_lines: int, timeout_ms: int, use_regex: bool) -> List[SearchResult]:
        """High-performance search using ripgrep."""
        # Check if ripgrep is available
        try:
            subprocess.run(["rg", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ToolError("Ripgrep not available")

        # Build ripgrep command
        cmd = ["rg", "--json", "--line-number"]
        
        if ignore_case:
            cmd.append("-i")
        
        if max_results:
            cmd.extend(["-m", str(max_results)])
        
        if include_hidden:
            cmd.append("--hidden")
        
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        
        if file_pattern:
            cmd.extend(["-g", file_pattern])
        
        if not use_regex:
            cmd.append("--fixed-strings")
        
        cmd.extend([pattern, root_path])

        try:
            # Run ripgrep with timeout
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout_ms / 1000.0
            )
            
            results = []
            if process.stdout:
                import json
                for line in process.stdout.strip().split('\n'):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get("type") == "match":
                            match_data = data["data"]
                            for submatch in match_data.get("submatches", []):
                                results.append(SearchResult(
                                    file=match_data["path"]["text"],
                                    line=match_data["line_number"],
                                    match=submatch["match"]["text"]
                                ))
                        elif data.get("type") == "context" and context_lines > 0:
                            context_data = data["data"]
                            results.append(SearchResult(
                                file=context_data["path"]["text"],
                                line=context_data["line_number"],
                                match=context_data["lines"]["text"].strip()
                            ))
                    except json.JSONDecodeError:
                        continue
            
            return results
            
        except subprocess.TimeoutExpired:
            raise ToolError(f"Search timed out after {timeout_ms}ms")
        except Exception as e:
            raise ToolError(f"Ripgrep search failed: {str(e)}")

    async def _native_search(self, root_path: str, pattern: str, file_pattern: Optional[str],
                           ignore_case: bool, max_results: int, exclude_dirs: List[str], 
                           context_lines: int, timeout_ms: int, use_regex: bool, include_hidden: bool) -> List[SearchResult]:
        """Fallback native Python search implementation."""
        results = []
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000.0
        
        # Compile pattern
        if use_regex:
            try:
                regex_flags = re.IGNORECASE if ignore_case else 0
                compiled_pattern = re.compile(pattern, regex_flags)
            except re.error as e:
                raise ToolError(f"Invalid regex pattern: {e}")
        else:
            compiled_pattern = None

        # File pattern matching
        if file_pattern:
            import fnmatch
            def matches_file_pattern(filename: str) -> bool:
                return fnmatch.fnmatch(filename, file_pattern)
        else:
            def matches_file_pattern(filename: str) -> bool:
                return True

        async def search_directory(dir_path: Path, depth: int = 0):
            if time.time() - start_time > timeout_seconds:
                return
            
            if depth > 20:  # Prevent deep recursion
                return
            
            try:
                for entry in dir_path.iterdir():
                    if time.time() - start_time > timeout_seconds:
                        break
                    
                    if len(results) >= max_results:
                        break
                    
                    if entry.is_dir():
                        if entry.name not in exclude_dirs and not entry.name.startswith('.'):
                            await search_directory(entry, depth + 1)
                    elif entry.is_file():
                        if not matches_file_pattern(entry.name):
                            continue
                        
                        # Skip hidden files unless requested
                        if not include_hidden and entry.name.startswith('.'):
                            continue
                        
                        # Search in file
                        try:
                            with open(entry, 'r', encoding='utf-8', errors='replace') as f:
                                lines = f.readlines()
                            
                            for line_num, line_content in enumerate(lines, 1):
                                if use_regex:
                                    if compiled_pattern.search(line_content):
                                        match_text = line_content.strip()
                                    else:
                                        continue
                                else:
                                    if ignore_case:
                                        if pattern.lower() in line_content.lower():
                                            match_text = line_content.strip()
                                        else:
                                            continue
                                    else:
                                        if pattern in line_content:
                                            match_text = line_content.strip()
                                        else:
                                            continue
                                
                                # Add context lines if requested
                                context_before = []
                                context_after = []
                                
                                if context_lines > 0:
                                    start_idx = max(0, line_num - context_lines - 1)
                                    end_idx = min(len(lines), line_num + context_lines)
                                    
                                    context_before = [lines[i].strip() for i in range(start_idx, line_num - 1)]
                                    context_after = [lines[i].strip() for i in range(line_num, end_idx)]
                                
                                results.append(SearchResult(
                                    file=str(entry),
                                    line=line_num,
                                    match=match_text,
                                    context_before=context_before if context_before else None,
                                    context_after=context_after if context_after else None
                                ))
                                
                                if len(results) >= max_results:
                                    return
                        
                        except (UnicodeDecodeError, PermissionError):
                            continue  # Skip binary files or files we can't read
                            
            except PermissionError:
                pass  # Skip directories we can't read

        await search_directory(Path(root_path))
        return results

    async def _format_results(self, results: List[SearchResult], pattern: str, 
                            search_path: str, max_results: int) -> CLIResult:
        """Format search results for output."""
        if not results:
            result_text = f"No matches found for pattern '{pattern}' in {search_path}"
            return CLIResult.create_success(result=result_text, tool_name=self.name)

        output = f"Search results for pattern '{pattern}' in {search_path}:\n"
        output += f"Found {len(results)} match(es)\n\n"

        displayed_results = results[:max_results] if len(results) > max_results else results
        
        current_file = None
        for result in displayed_results:
            # Group by file for better readability
            if result.file != current_file:
                current_file = result.file
                output += f"\n=== {result.file} ===\n"
            
            output += f"Line {result.line}: {result.match}\n"
            
            # Add context if available
            if result.context_before:
                for i, ctx_line in enumerate(result.context_before):
                    ctx_line_num = result.line - len(result.context_before) + i
                    output += f"    {ctx_line_num}: {ctx_line}\n"
            
            if result.context_after:
                for i, ctx_line in enumerate(result.context_after):
                    ctx_line_num = result.line + i + 1
                    output += f"    {ctx_line_num}: {ctx_line}\n"

        if len(results) > max_results:
            output += f"\n... and {len(results) - max_results} more matches (increase max_results to see more)\n"

        return CLIResult.create_success(result=output, tool_name=self.name)

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up CodeSearchTool resources")
        
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