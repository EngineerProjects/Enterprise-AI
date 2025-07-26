"""
Comprehensive file system operations tool for Enterprise AI.

This module provides essential file system operations including reading, writing,
directory management, file searching, metadata retrieval, URL fetching, and advanced security.
"""

import os
import shutil
import time
import asyncio
import aiohttp
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.sandbox.client import BaseSandboxClient, create_sandbox_client
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.file.filesystem")

class FileInfo(BaseModel):
    """File information model."""
    path: str
    size: int
    created: str
    modified: str
    accessed: str
    is_directory: bool
    is_file: bool
    permissions: str
    line_count: Optional[int] = None
    last_line: Optional[int] = None
    append_position: Optional[int] = None

class MultiFileResult(BaseModel):
    """Result for multiple file operations."""
    path: str
    content: Optional[str] = None
    mime_type: Optional[str] = None
    is_image: Optional[bool] = None
    error: Optional[str] = None

class FileResult(BaseModel):
    """Enhanced file result with metadata."""
    content: str
    mime_type: str
    is_image: bool
    size: Optional[int] = None
    encoding: Optional[str] = None

class PathSecurityValidator:
    """Advanced path validation with security checks like Desktop Commander."""
    
    def __init__(self, allowed_directories: Optional[List[str]] = None):
        self.allowed_directories = allowed_directories or []
        # If empty list, allow full access (like Desktop Commander)
        self.full_access = len(self.allowed_directories) == 0
    
    def expand_home(self, filepath: str) -> str:
        """Expand home directory paths."""
        if filepath.startswith('~/') or filepath == '~':
            return str(Path.home() / filepath[1:].lstrip('/'))
        return filepath
    
    def normalize_path(self, path_str: str) -> str:
        """Normalize all paths consistently."""
        expanded = self.expand_home(path_str)
        return str(Path(expanded).resolve())
    
    async def validate_path(self, requested_path: str, timeout_seconds: float = 10.0) -> str:
        """
        Validate a path with timeout like Desktop Commander.
        
        Args:
            requested_path: The path to validate
            timeout_seconds: Timeout for validation operation
            
        Returns:
            The validated path
            
        Raises:
            ToolError: If path is not allowed or validation fails
        """
        async def validation_operation():
            # Expand and normalize path
            normalized_path = self.normalize_path(requested_path)
            
            # Check if path is allowed
            if not self.is_path_allowed(normalized_path):
                allowed_dirs_str = ', '.join(self.allowed_directories) if self.allowed_directories else "full system access"
                raise ToolError(f"Path not allowed: {requested_path}. Must be within: {allowed_dirs_str}")
            
            # Check if path exists, if not validate parent directories
            try:
                if Path(normalized_path).exists():
                    return str(Path(normalized_path).resolve())
                else:
                    # Validate parent directories exist
                    if await self._validate_parent_directories(normalized_path):
                        return normalized_path
                    return normalized_path  # Return anyway for creation operations
            except Exception as e:
                logger.warning(f"Path validation warning for {requested_path}: {e}")
                return normalized_path
        
        try:
            return await asyncio.wait_for(validation_operation(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise ToolError(f"Path validation timed out for: {requested_path}")
    
    def is_path_allowed(self, path_to_check: str) -> bool:
        """Check if a path is within allowed directories."""
        if self.full_access:
            return True
        
        normalized_path = self.normalize_path(path_to_check).lower()
        
        for allowed_dir in self.allowed_directories:
            normalized_allowed = self.normalize_path(allowed_dir).lower()
            
            # Check if path is exactly the allowed directory
            if normalized_path == normalized_allowed:
                return True
            
            # Check if path is a subdirectory
            if normalized_path.startswith(normalized_allowed + os.sep):
                return True
        
        return False
    
    async def _validate_parent_directories(self, directory_path: str) -> bool:
        """Recursively validate parent directories exist."""
        parent_dir = str(Path(directory_path).parent)
        
        # Base case: reached root or same directory
        if parent_dir == directory_path or parent_dir == str(Path(parent_dir).parent):
            return False
        
        try:
            # Check if parent exists
            if Path(parent_dir).exists():
                return True
            else:
                # Recursively check parent's parent
                return await self._validate_parent_directories(parent_dir)
        except Exception:
            return False

class MimeTypeDetector:
    """Advanced MIME type detection like Desktop Commander."""
    
    # Extended mappings from Desktop Commander
    MIME_MAPPINGS = {
        # Images
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        
        # Text files
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.py': 'text/x-python',
        '.js': 'text/javascript',
        '.ts': 'text/typescript',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.css': 'text/css',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.yml': 'application/x-yaml',
        '.yaml': 'application/x-yaml',
        '.csv': 'text/csv',
        '.log': 'text/plain',
        '.ini': 'text/plain',
        '.cfg': 'text/plain',
        '.conf': 'text/plain',
        
        # Code files
        '.c': 'text/x-c',
        '.cpp': 'text/x-c++',
        '.h': 'text/x-c',
        '.hpp': 'text/x-c++',
        '.java': 'text/x-java',
        '.php': 'text/x-php',
        '.rb': 'text/x-ruby',
        '.go': 'text/x-go',
        '.rs': 'text/x-rust',
        '.sh': 'text/x-shellscript',
        '.bash': 'text/x-shellscript',
        '.ps1': 'text/x-powershell',
        
        # Documents
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xls': 'application/vnd.ms-excel',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        
        # Archives
        '.zip': 'application/zip',
        '.rar': 'application/x-rar-compressed',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip',
        '.7z': 'application/x-7z-compressed',
        
        # Media
        '.mp3': 'audio/mpeg',
        '.wav': 'audio/wav',
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
    }
    
    IMAGE_EXTENSIONS = {
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', 
        '.tiff', '.tif', '.svg', '.ico'
    }
    
    def get_mime_type(self, file_path: str) -> str:
        """Get MIME type for a file based on extension."""
        ext = Path(file_path).suffix.lower()
        return self.MIME_MAPPINGS.get(ext, 'application/octet-stream')
    
    def is_image_file(self, mime_type_or_path: str) -> bool:
        """Check if MIME type or file path represents an image."""
        if '/' in mime_type_or_path:
            # It's a MIME type
            return mime_type_or_path.startswith('image/')
        else:
            # It's a file path
            ext = Path(mime_type_or_path).suffix.lower()
            return ext in self.IMAGE_EXTENSIONS

class FileSystemTool(BaseTool):
    """
    Comprehensive file system operations tool with Desktop Commander enhancements.

    Key capabilities:
    * Read single or multiple files with offset and length control
    * Read content from URLs with timeout and error handling
    * Write files with append/rewrite modes and automatic directory creation
    * Create and manage directories with proper validation
    * List directory contents with file type information and size details
    * Move and rename files and directories with path validation
    * Search for files by name patterns with timeout control
    * Retrieve detailed file metadata and information including line counts
    * Advanced path security validation with configurable allowed directories
    * Support for both local and sandbox execution modes
    * Handle binary files and images with automatic base64 encoding
    * Enhanced MIME type detection for better file classification
    * Timeout handling for all operations to prevent hangs
    * Comprehensive error reporting with detailed context

    Use this tool when:
    * You need to perform basic file system operations with advanced security
    * You want to read content from URLs or local files efficiently
    * You need to read multiple files simultaneously with error handling
    * You need to search for files by name patterns with performance control
    * You require detailed file metadata (size, permissions, line counts)
    * You need to manage directories and file organization safely
    * You want secure file operations with configurable access control
    * You need cross-platform file operations with proper encoding
    
    Enhanced Features from Desktop Commander:
    * URL content fetching with timeout and proper error handling
    * Advanced path security validation with recursive parent checking
    * Enhanced MIME type detection with comprehensive file type support
    * Timeout control for all operations to prevent system hangs
    * Better error reporting with detailed context and suggestions
    * Cross-platform path handling with proper normalization
    """

    name: str = "filesystem"
    short_description: str = "Perform file operations including reading, writing, moving, and searching with security controls."
    description: str = """
    Comprehensive file system operations with Desktop Commander enhancements for security and performance.

    * Purpose: Perform essential file and directory operations safely and efficiently with advanced features
    * Usage: Read, write, create, move, search files and directories, fetch URL content
    * Features: Multi-file operations, URL fetching, metadata retrieval, pattern searching, sandbox support, advanced security
    * Returns: File contents, operation confirmations, file lists, detailed metadata, and comprehensive error information

    Enhanced with URL content fetching, advanced path security validation, comprehensive MIME type detection,
    timeout control for all operations, and detailed error reporting. Supports both text and binary files
    with automatic encoding detection and base64 encoding for images. Provides robust error handling and 
    path validation for security across local and sandbox environments.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The file system operation to perform",
                "enum": [
                    "read_file", "read_multiple_files", "write_file", 
                    "create_directory", "list_directory", "move_file", 
                    "search_files", "get_file_info"
                ],
                "type": "string",
            },
            "path": {"description": "File or directory path", "type": "string"},
            "paths": {"description": "List of file paths (for read_multiple_files)", "items": {"type": "string"}, "type": "array"},
            "content": {"description": "Content to write to file", "type": "string"},
            "mode": {"description": "Write mode: rewrite or append", "enum": ["rewrite", "append"], "type": "string"},
            "source": {"description": "Source path for move operation", "type": "string"},
            "destination": {"description": "Destination path for move operation", "type": "string"},
            "pattern": {"description": "Search pattern for file names", "type": "string"},
            "is_url": {"description": "Whether path is a URL", "type": "boolean"},
            "offset": {"description": "Starting line number to read from", "type": "integer"},
            "length": {"description": "Maximum number of lines to read", "type": "integer"},
            "timeout_ms": {"description": "Timeout in milliseconds for operations", "type": "integer"},
            "allowed_directories": {"description": "List of allowed directories for security", "items": {"type": "string"}, "type": "array"},
        },
        "required": ["command"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.FILE_ACCESS}
    requires_initialization: bool = True

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the Enhanced FileSystemTool."""
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
        
        # Enhanced components
        self._mime_detector = MimeTypeDetector()
        self._path_validator = PathSecurityValidator()

        logger.debug(f"Enhanced FileSystemTool initialized in {'local' if self._local_mode else 'sandbox'} mode")

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the enhanced file system tool."""
        try:
            if not self._local_mode:
                self._sandbox_client = create_sandbox_client()
                await self._sandbox_client.create()
                logger.info("Enhanced FileSystemTool sandbox environment created")
            else:
                logger.info("Enhanced FileSystemTool initialized in local mode")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced FileSystemTool: {e}")
            self._local_mode = True
            logger.info("Falling back to local mode")
            return True

    def _validate_path(self, path: str) -> str:
        """Basic path validation for backward compatibility."""
        if not path:
            raise ToolError("Path cannot be empty")
        
        # Convert to absolute path
        abs_path = str(Path(path).resolve())
        
        # Basic security check - prevent access to sensitive directories
        sensitive_dirs = ["/etc", "/sys", "/proc", "/dev"] if os.name != 'nt' else ["C:\\Windows\\System32"]
        if any(abs_path.startswith(sensitive) for sensitive in sensitive_dirs):
            raise ToolError(f"Access to sensitive directory not allowed: {path}")
        
        return abs_path

    async def _validate_path_advanced(self, path: str, allowed_dirs: Optional[List[str]] = None, 
                                    timeout_ms: int = 10000) -> str:
        """Advanced path validation using Desktop Commander style security."""
        if allowed_dirs is not None:
            self._path_validator = PathSecurityValidator(allowed_dirs)
        
        try:
            return await self._path_validator.validate_path(path, timeout_ms / 1000.0)
        except Exception as e:
            # Fallback to basic validation
            logger.warning(f"Advanced path validation failed, using basic validation: {e}")
            return self._validate_path(path)

    def _detect_mime_type(self, file_path: str) -> Tuple[str, bool]:
        """Detect MIME type and determine if file is an image using enhanced detector."""
        mime_type = self._mime_detector.get_mime_type(file_path)
        is_image = self._mime_detector.is_image_file(mime_type)
        return mime_type, is_image

    async def _read_file_from_url(self, url: str, timeout_ms: int = 30000) -> FileResult:
        """Read file content from URL with enhanced error handling like Desktop Commander."""
        timeout_seconds = timeout_ms / 1000.0
        
        # Validate URL format
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ToolError(f"Invalid URL format: {url}")
        
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_seconds)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ToolError(f"HTTP error {response.status} fetching URL: {url}")
                    
                    content_type = response.headers.get('content-type', 'text/plain')
                    content_length = response.headers.get('content-length')
                    is_image = self._mime_detector.is_image_file(content_type)
                    
                    if is_image:
                        # For images, read as bytes and encode as base64
                        content_bytes = await response.read()
                        content = base64.b64encode(content_bytes).decode('utf-8')
                        
                        return FileResult(
                            content=content,
                            mime_type=content_type,
                            is_image=True,
                            size=len(content_bytes),
                            encoding='base64'
                        )
                    else:
                        # For text content
                        content = await response.text()
                        
                        return FileResult(
                            content=content,
                            mime_type=content_type,
                            is_image=False,
                            size=int(content_length) if content_length else len(content.encode()),
                            encoding='utf-8'
                        )
                        
        except asyncio.TimeoutError:
            raise ToolError(f"URL fetch timed out after {timeout_seconds}s: {url}")
        except aiohttp.ClientError as e:
            raise ToolError(f"Network error fetching URL {url}: {str(e)}")
        except Exception as e:
            raise ToolError(f"Failed to fetch URL {url}: {str(e)}")

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a file system operation with enhanced features."""
        command = kwargs.get("command")
        
        if not command:
            raise ToolError("Parameter 'command' is required")

        logger.info(f"Executing enhanced filesystem command: {command}")

        try:
            if command == "read_file":
                return await self._read_file(kwargs)
            elif command == "read_multiple_files":
                return await self._read_multiple_files(kwargs)
            elif command == "write_file":
                return await self._write_file(kwargs)
            elif command == "create_directory":
                return await self._create_directory(kwargs)
            elif command == "list_directory":
                return await self._list_directory(kwargs)
            elif command == "move_file":
                return await self._move_file(kwargs)
            elif command == "search_files":
                return await self._search_files(kwargs)
            elif command == "get_file_info":
                return await self._get_file_info(kwargs)
            else:
                raise ToolError(f"Unsupported command: {command}")
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Error executing command {command}: {str(e)}", tool_name=self.name)

    async def _read_file(self, kwargs: dict) -> CLIResult:
        """Read a single file with enhanced URL support and path validation."""
        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required for read_file")

        is_url = kwargs.get("is_url", False)
        offset = kwargs.get("offset", 0)
        length = kwargs.get("length", 1000)
        timeout_ms = kwargs.get("timeout_ms", 30000)
        allowed_dirs = kwargs.get("allowed_directories")

        if is_url:
            file_result = await self._read_file_from_url(path, timeout_ms)
            
            if file_result.is_image:
                result = (f"Image from URL: {path}\n"
                         f"Content-Type: {file_result.mime_type}\n"
                         f"Size: {file_result.size} bytes\n"
                         f"Encoding: {file_result.encoding}\n"
                         f"Base64 content: {file_result.content[:100]}...")
            else:
                content_preview = file_result.content[:2000] + ('...' if len(file_result.content) > 2000 else '')
                result = (f"Content from URL: {path}\n"
                         f"Content-Type: {file_result.mime_type}\n"
                         f"Size: {file_result.size} bytes\n"
                         f"Encoding: {file_result.encoding}\n\n"
                         f"{content_preview}")
            
            return CLIResult.create_success(result=result, tool_name=self.name)
        
        # Local file reading with enhanced validation
        validated_path = await self._validate_path_advanced(path, allowed_dirs, timeout_ms)
        
        if not Path(validated_path).exists():
            raise ToolError(f"File does not exist: {path}")

        if Path(validated_path).is_dir():
            raise ToolError(f"Path is a directory, not a file: {path}")

        try:
            mime_type, is_image = self._detect_mime_type(validated_path)
            
            if is_image:
                # Read binary file and encode as base64
                with open(validated_path, 'rb') as f:
                    content_bytes = f.read()
                    encoded_content = base64.b64encode(content_bytes).decode('utf-8')
                
                result = (f"Image file: {path}\n"
                         f"MIME Type: {mime_type}\n"
                         f"Size: {len(content_bytes)} bytes\n"
                         f"Base64 content: {encoded_content[:100]}...")
                return CLIResult.create_success(result=result, tool_name=self.name)
            else:
                # Read text file with line-based offset and length
                with open(validated_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                
                total_lines = len(lines)
                start_line = min(offset, total_lines)
                end_line = min(start_line + length, total_lines)
                
                if start_line >= total_lines and offset > 0:
                    # Show last few lines instead
                    last_lines_count = min(10, total_lines)
                    start_line = max(0, total_lines - last_lines_count)
                    end_line = total_lines
                
                selected_lines = lines[start_line:end_line]
                
                info_header = ""
                if offset > 0 or end_line < total_lines:
                    info_header = f"[Reading {end_line - start_line} lines from line {start_line + 1} of {total_lines} total lines]\n\n"
                
                numbered_content = "\n".join([
                    f"{i + start_line + 1:6}\t{line.rstrip()}" 
                    for i, line in enumerate(selected_lines)
                ])
                
                result = (f"File: {path}\n"
                         f"MIME Type: {mime_type}\n"
                         f"Total Lines: {total_lines}\n"
                         f"{info_header}Content:\n{numbered_content}")
                
                return CLIResult.create_success(result=result, tool_name=self.name)
                
        except Exception as e:
            raise ToolError(f"Failed to read file {path}: {str(e)}")

    async def _read_multiple_files(self, kwargs: dict) -> CLIResult:
        """Read multiple files simultaneously with enhanced error handling."""
        paths = kwargs.get("paths")
        if not paths:
            raise ToolError("Parameter 'paths' is required for read_multiple_files")

        allowed_dirs = kwargs.get("allowed_directories")
        timeout_ms = kwargs.get("timeout_ms", 30000)

        results = []
        for file_path in paths:
            try:
                validated_path = await self._validate_path_advanced(file_path, allowed_dirs, timeout_ms)
                
                if not Path(validated_path).exists():
                    results.append(MultiFileResult(path=file_path, error="File does not exist"))
                    continue
                
                if Path(validated_path).is_dir():
                    results.append(MultiFileResult(path=file_path, error="Path is a directory"))
                    continue

                mime_type, is_image = self._detect_mime_type(validated_path)
                
                if is_image:
                    with open(validated_path, 'rb') as f:
                        content_bytes = f.read()
                        encoded_content = base64.b64encode(content_bytes).decode('utf-8')
                    
                    results.append(MultiFileResult(
                        path=file_path,
                        content=f"[Image file - {len(content_bytes)} bytes] {encoded_content[:100]}...",
                        mime_type=mime_type,
                        is_image=True
                    ))
                else:
                    with open(validated_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    
                    preview_content = content[:1000] + ('...' if len(content) > 1000 else '')
                    results.append(MultiFileResult(
                        path=file_path,
                        content=preview_content,
                        mime_type=mime_type,
                        is_image=False
                    ))
                    
            except Exception as e:
                results.append(MultiFileResult(path=file_path, error=str(e)))

        # Format results
        output = "Multiple file read results:\n\n"
        for result in results:
            output += f"=== {result.path} ===\n"
            if result.error:
                output += f"ERROR: {result.error}\n"
            else:
                output += f"MIME Type: {result.mime_type}\n"
                if result.is_image:
                    output += f"Image Content: {result.content}\n"
                else:
                    output += f"Content:\n{result.content}\n"
            output += "\n"

        return CLIResult.create_success(result=output, tool_name=self.name)

    async def _write_file(self, kwargs: dict) -> CLIResult:
        """Write content to a file with enhanced validation."""
        path = kwargs.get("path")
        content = kwargs.get("content")
        mode = kwargs.get("mode", "rewrite")
        allowed_dirs = kwargs.get("allowed_directories")
        timeout_ms = kwargs.get("timeout_ms", 30000)

        if not path:
            raise ToolError("Parameter 'path' is required for write_file")
        if content is None:
            raise ToolError("Parameter 'content' is required for write_file")

        validated_path = await self._validate_path_advanced(path, allowed_dirs, timeout_ms)
        
        # Ensure parent directory exists
        parent_dir = Path(validated_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        try:
            if mode == "append":
                with open(validated_path, 'a', encoding='utf-8') as f:
                    f.write(content)
            else:  # rewrite
                with open(validated_path, 'w', encoding='utf-8') as f:
                    f.write(content)

            file_size = Path(validated_path).stat().st_size
            line_count = content.count('\n') + 1 if content else 0
            
            result = (f"File written successfully: {path}\n"
                     f"Mode: {mode}\n"
                     f"Size: {file_size} bytes\n"
                     f"Lines: {line_count}")
            return CLIResult.create_success(result=result, tool_name=self.name)
            
        except Exception as e:
            raise ToolError(f"Failed to write file {path}: {str(e)}")

    async def _create_directory(self, kwargs: dict) -> CLIResult:
        """Create a directory with enhanced validation."""
        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required for create_directory")

        allowed_dirs = kwargs.get("allowed_directories")
        timeout_ms = kwargs.get("timeout_ms", 10000)
        
        validated_path = await self._validate_path_advanced(path, allowed_dirs, timeout_ms)

        try:
            Path(validated_path).mkdir(parents=True, exist_ok=True)
            result = f"Directory created successfully: {path}"
            return CLIResult.create_success(result=result, tool_name=self.name)
        except Exception as e:
            raise ToolError(f"Failed to create directory {path}: {str(e)}")

    async def _list_directory(self, kwargs: dict) -> CLIResult:
        """List directory contents with enhanced details."""
        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required for list_directory")

        allowed_dirs = kwargs.get("allowed_directories")
        timeout_ms = kwargs.get("timeout_ms", 30000)
        
        validated_path = await self._validate_path_advanced(path, allowed_dirs, timeout_ms)

        if not Path(validated_path).exists():
            raise ToolError(f"Directory does not exist: {path}")

        if not Path(validated_path).is_dir():
            raise ToolError(f"Path is not a directory: {path}")

        try:
            entries = sorted(Path(validated_path).iterdir(), key=lambda x: (x.is_file(), x.name))
            
            output = f"Directory contents of {path}:\n\n"
            for entry in entries[:100]:  # Limit to 100 entries
                entry_type = "[DIR]" if entry.is_dir() else "[FILE]"
                size_info = ""
                mime_info = ""
                
                if entry.is_file():
                    try:
                        size = entry.stat().st_size
                        size_info = f" ({size:,} bytes)"
                        
                        # Add MIME type for files
                        mime_type, is_image = self._detect_mime_type(str(entry))
                        if is_image:
                            mime_info = f" [IMAGE: {mime_type}]"
                        elif mime_type != 'application/octet-stream':
                            mime_info = f" [{mime_type}]"
                    except:
                        size_info = " (size unknown)"
                
                output += f"{entry_type} {entry.name}{size_info}{mime_info}\n"
            
            if len(entries) > 100:
                output += f"\n... and {len(entries) - 100} more items"
            
            return CLIResult.create_success(result=output, tool_name=self.name)
            
        except Exception as e:
            raise ToolError(f"Failed to list directory {path}: {str(e)}")

    async def _move_file(self, kwargs: dict) -> CLIResult:
        """Move or rename a file/directory with enhanced validation."""
        source = kwargs.get("source")
        destination = kwargs.get("destination")
        allowed_dirs = kwargs.get("allowed_directories")
        timeout_ms = kwargs.get("timeout_ms", 30000)

        if not source:
            raise ToolError("Parameter 'source' is required for move_file")
        if not destination:
            raise ToolError("Parameter 'destination' is required for move_file")

        validated_source = await self._validate_path_advanced(source, allowed_dirs, timeout_ms)
        validated_destination = await self._validate_path_advanced(destination, allowed_dirs, timeout_ms)

        if not Path(validated_source).exists():
            raise ToolError(f"Source does not exist: {source}")

        try:
            # Ensure destination parent directory exists
            parent_dir = Path(validated_destination).parent
            parent_dir.mkdir(parents=True, exist_ok=True)
            
            shutil.move(validated_source, validated_destination)
            result = f"Successfully moved: {source} -> {destination}"
            return CLIResult.create_success(result=result, tool_name=self.name)
            
        except Exception as e:
            raise ToolError(f"Failed to move {source} to {destination}: {str(e)}")

    async def _search_files(self, kwargs: dict) -> CLIResult:
        """Search for files by name pattern with enhanced timeout control."""
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")
        timeout_ms = kwargs.get("timeout_ms", 30000)
        allowed_dirs = kwargs.get("allowed_directories")

        if not path:
            raise ToolError("Parameter 'path' is required for search_files")
        if not pattern:
            raise ToolError("Parameter 'pattern' is required for search_files")

        validated_path = await self._validate_path_advanced(path, allowed_dirs, timeout_ms)

        if not Path(validated_path).exists():
            raise ToolError(f"Search path does not exist: {path}")

        try:
            results = []
            start_time = time.time()
            timeout_seconds = timeout_ms / 1000.0

            async def search_recursive(current_path: Path, depth: int = 0):
                if time.time() - start_time > timeout_seconds:
                    return
                
                if depth > 15:  # Prevent deep recursion
                    return
                
                try:
                    for entry in current_path.iterdir():
                        if time.time() - start_time > timeout_seconds:
                            break
                            
                        if pattern.lower() in entry.name.lower():
                            entry_type = "DIR" if entry.is_dir() else "FILE"
                            size_info = ""
                            
                            if entry.is_file():
                                try:
                                    size = entry.stat().st_size
                                    size_info = f" ({size:,} bytes)"
                                except:
                                    pass
                            
                            results.append(f"[{entry_type}] {entry}{size_info}")
                        
                        if entry.is_dir() and len(results) < 1000:  # Limit results
                            await search_recursive(entry, depth + 1)
                            
                except PermissionError:
                    pass  # Skip directories we can't read

            await search_recursive(Path(validated_path))

            execution_time = time.time() - start_time
            output = f"File search results for pattern '{pattern}' in {path}:\n"
            output += f"Search completed in {execution_time:.2f}s\n\n"
            
            if results:
                output += "\n".join(results[:100])  # Limit display
                if len(results) > 100:
                    output += f"\n\n... and {len(results) - 100} more matches"
            else:
                output += "No files found matching the pattern."

            return CLIResult.create_success(result=output, tool_name=self.name)
            
        except Exception as e:
            raise ToolError(f"Failed to search files in {path}: {str(e)}")

    async def _get_file_info(self, kwargs: dict) -> CLIResult:
        """Get detailed file information with enhanced metadata."""
        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required for get_file_info")

        allowed_dirs = kwargs.get("allowed_directories")
        timeout_ms = kwargs.get("timeout_ms", 10000)
        
        validated_path = await self._validate_path_advanced(path, allowed_dirs, timeout_ms)

        if not Path(validated_path).exists():
            raise ToolError(f"File does not exist: {path}")

        try:
            path_obj = Path(validated_path)
            stat = path_obj.stat()
            
            info = FileInfo(
                path=str(path_obj),
                size=stat.st_size,
                created=time.ctime(stat.st_ctime),
                modified=time.ctime(stat.st_mtime),
                accessed=time.ctime(stat.st_atime),
                is_directory=path_obj.is_dir(),
                is_file=path_obj.is_file(),
                permissions=oct(stat.st_mode)[-3:],
            )

            # Enhanced metadata
            mime_type = "N/A"
            is_image = False
            
            # For files, get MIME type and line count
            if info.is_file and info.size < 10 * 1024 * 1024:  # Limit to 10MB
                try:
                    mime_type, is_image = self._detect_mime_type(validated_path)
                    
                    if not is_image and mime_type.startswith('text/'):
                        with open(validated_path, 'r', encoding='utf-8', errors='replace') as f:
                            content = f.read()
                            line_count = content.count('\n') + 1
                            info.line_count = line_count
                            info.last_line = line_count - 1
                            info.append_position = line_count
                except:
                    pass  # Skip line counting for binary files

            # Format output
            output = f"File Information: {path}\n\n"
            output += f"Size: {info.size:,} bytes\n"
            output += f"Type: {'Directory' if info.is_directory else 'File'}\n"
            if not info.is_directory:
                output += f"MIME Type: {mime_type}\n"
                if is_image:
                    output += f"Image: Yes\n"
            output += f"Permissions: {info.permissions}\n"
            output += f"Created: {info.created}\n"
            output += f"Modified: {info.modified}\n"
            output += f"Accessed: {info.accessed}\n"
            
            if info.line_count is not None:
                output += f"Lines: {info.line_count}\n"
                output += f"Last Line: {info.last_line}\n"
                output += f"Append Position: {info.append_position}\n"
                output += f"Append Position: {info.append_position}\n"

            return CLIResult.create_success(result=output, tool_name=self.name)
            
        except Exception as e:
            raise ToolError(f"Failed to get file info for {path}: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up Enhanced FileSystemTool resources")
        
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