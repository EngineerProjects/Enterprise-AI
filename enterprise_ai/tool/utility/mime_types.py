"""
MIME type detection and handling utilities for Enterprise AI.

This module provides comprehensive MIME type detection and file type
classification capabilities for various file formats.
"""

import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, Field

from enterprise_ai.tool.core.base import BaseTool, ToolError, ToolConfig, ToolCapability
from enterprise_ai.tool.core.result import ToolResult, CLIResult
from enterprise_ai.logger import get_optimized_logger

logger = get_optimized_logger("tool.utility.mime_types")

class FileTypeInfo(BaseModel):
    """File type information model."""
    path: str
    mime_type: str
    file_type: str
    category: str
    is_text: bool
    is_binary: bool
    is_image: bool
    is_executable: bool
    extensions: List[str]
    description: str

class MimeTypeTool(BaseTool):
    """
    MIME type detection and file classification tool.

    Key capabilities:
    * Detect MIME types from file extensions and content
    * Classify files into categories (text, binary, image, executable, etc.)
    * Support for hundreds of file formats and extensions
    * Content-based detection for files without extensions
    * Batch processing of multiple files
    * Custom MIME type registration and overrides
    * File signature (magic number) detection
    * Integration with system MIME type databases

    Use this tool when:
    * You need to determine file types and MIME types programmatically
    * You want to classify files for processing or filtering
    * You need to validate file types before operations
    * You're working with files without extensions
    * You want to ensure proper content-type headers for web applications
    * You need to identify potentially dangerous file types
    """

    name: str = "mime_type_detector"
    short_description: str = "Detect file types and classify files based on extensions, content, and signatures."
    description: str = """
    Comprehensive MIME type detection and file classification.

    * Purpose: Detect and classify file types using extensions, content, and signatures
    * Usage: Identify MIME types, categorize files, validate file types, batch processing
    * Features: Extension-based detection, content analysis, magic number detection, custom types
    * Returns: MIME types, file categories, detailed type information, batch results

    Provides accurate file type detection using multiple methods including file extensions,
    content analysis, and magic number detection. Supports custom type registration and
    comprehensive file classification for security and processing purposes.
    """

    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "MIME type operation to perform",
                "enum": [
                    "detect_type", "classify_file", "batch_detect", 
                    "list_types", "register_type", "validate_type"
                ],
                "type": "string",
            },
            "path": {"description": "File path for type detection", "type": "string"},
            "paths": {"description": "List of file paths for batch processing", "items": {"type": "string"}, "type": "array"},
            "content_sample": {"description": "Content sample for type detection", "type": "string"},
            "extension": {"description": "File extension to check", "type": "string"},
            "mime_type": {"description": "MIME type to validate or register", "type": "string"},
            "use_content": {"description": "Use content analysis in addition to extension", "type": "boolean"},
            "include_magic": {"description": "Include magic number detection", "type": "boolean"},
            "category_filter": {"description": "Filter results by category", "type": "string"},
        },
        "required": ["command"],
    }

    capabilities: Set[Union[str, ToolCapability]] = {ToolCapability.FILE_ACCESS}
    requires_initialization: bool = True

    def __init__(self, name: Optional[str] = None, description: Optional[str] = None, 
                 parameters: Optional[dict] = None, config: Optional[ToolConfig] = None, **kwargs: Any) -> None:
        """Initialize the MimeTypeTool."""
        model_fields = self.__class__.model_fields
        super().__init__(
            name=name or model_fields["name"].default,
            description=description or model_fields["description"].default,
            parameters=parameters or model_fields["parameters"].default,
            **kwargs,
        )

        self.config = config or ToolConfig(timeout=30.0, max_retries=2, sandbox_enabled=False)
        
        # Initialize MIME types database
        mimetypes.init()
        
        # Extended MIME type mappings
        self._custom_types = {
            # Programming languages
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.ts': 'text/typescript',
            '.jsx': 'text/jsx',
            '.tsx': 'text/tsx',
            '.vue': 'text/x-vue',
            '.go': 'text/x-go',
            '.rs': 'text/x-rust',
            '.swift': 'text/x-swift',
            '.kt': 'text/x-kotlin',
            '.scala': 'text/x-scala',
            '.rb': 'text/x-ruby',
            '.php': 'text/x-php',
            '.java': 'text/x-java-source',
            '.c': 'text/x-c',
            '.cpp': 'text/x-c++',
            '.cc': 'text/x-c++',
            '.cxx': 'text/x-c++',
            '.h': 'text/x-c-header',
            '.hpp': 'text/x-c++-header',
            '.cs': 'text/x-csharp',
            '.vb': 'text/x-vb',
            '.fs': 'text/x-fsharp',
            '.r': 'text/x-r',
            '.R': 'text/x-r',
            '.m': 'text/x-matlab',
            '.pl': 'text/x-perl',
            '.sh': 'text/x-shellscript',
            '.bash': 'text/x-shellscript',
            '.zsh': 'text/x-shellscript',
            '.fish': 'text/x-shellscript',
            '.ps1': 'text/x-powershell',
            '.bat': 'text/x-batch',
            '.cmd': 'text/x-batch',
            
            # Configuration files
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml',
            '.toml': 'text/toml',
            '.ini': 'text/x-ini',
            '.cfg': 'text/x-config',
            '.conf': 'text/x-config',
            '.env': 'text/x-env',
            '.dockerfile': 'text/x-dockerfile',
            '.gitignore': 'text/x-gitignore',
            '.gitattributes': 'text/x-gitattributes',
            
            # Data formats
            '.jsonl': 'application/jsonlines',
            '.ndjson': 'application/x-ndjson',
            '.parquet': 'application/x-parquet',
            '.avro': 'application/x-avro',
            '.protobuf': 'application/x-protobuf',
            '.proto': 'text/x-proto',
            
            # Documentation
            '.md': 'text/markdown',
            '.markdown': 'text/markdown',
            '.rst': 'text/x-rst',
            '.asciidoc': 'text/x-asciidoc',
            '.adoc': 'text/x-asciidoc',
            '.tex': 'text/x-latex',
            '.bib': 'text/x-bibtex',
            
            # Web technologies
            '.scss': 'text/x-scss',
            '.sass': 'text/x-sass',
            '.less': 'text/x-less',
            '.stylus': 'text/x-stylus',
            '.coffee': 'text/x-coffeescript',
            '.handlebars': 'text/x-handlebars',
            '.hbs': 'text/x-handlebars',
            '.mustache': 'text/x-mustache',
            '.pug': 'text/x-pug',
            '.jade': 'text/x-jade',
            
            # Archives and packages
            '.tar.gz': 'application/x-tar-gz',
            '.tar.bz2': 'application/x-tar-bz2',
            '.tar.xz': 'application/x-tar-xz',
            '.deb': 'application/x-debian-package',
            '.rpm': 'application/x-rpm',
            '.dmg': 'application/x-apple-diskimage',
            '.pkg': 'application/x-installer',
            '.msi': 'application/x-msi',
            '.appimage': 'application/x-appimage',
            '.snap': 'application/x-snap',
            '.flatpak': 'application/x-flatpak',
            
            # Database files
            '.db': 'application/x-sqlite3',
            '.sqlite': 'application/x-sqlite3',
            '.sqlite3': 'application/x-sqlite3',
            '.dbf': 'application/x-dbf',
            '.mdb': 'application/x-msaccess',
            '.accdb': 'application/x-msaccess',
            
            # Log files
            '.log': 'text/x-log',
            '.out': 'text/x-log',
            '.err': 'text/x-log',
            
            # System files
            '.service': 'text/x-systemd-service',
            '.socket': 'text/x-systemd-socket',
            '.timer': 'text/x-systemd-timer',
            '.mount': 'text/x-systemd-mount',
            '.desktop': 'text/x-desktop-entry',
            
            # Development files
            '.lock': 'text/x-lockfile',
            '.pid': 'text/x-pid',
            '.tmp': 'application/x-temp',
            '.bak': 'application/x-backup',
            '.orig': 'text/x-original',
            '.patch': 'text/x-patch',
            '.diff': 'text/x-diff',
        }
        
        # File categories
        self._categories = {
            'text': ['text/', 'application/json', 'application/xml', 'application/yaml'],
            'image': ['image/'],
            'video': ['video/'],
            'audio': ['audio/'],
            'archive': ['application/zip', 'application/x-tar', 'application/x-gzip', 'application/x-rar'],
            'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats'],
            'executable': ['application/x-executable', 'application/x-msdos-program', 'application/x-msdownload'],
            'code': ['text/x-python', 'text/javascript', 'text/x-java-source', 'text/x-c'],
            'data': ['application/x-sqlite3', 'text/csv', 'application/x-parquet'],
            'config': ['text/x-config', 'text/yaml', 'text/x-ini'],
        }
        
        # Magic numbers for content-based detection
        self._magic_numbers = {
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'\xff\xd8\xff': 'image/jpeg',
            b'GIF87a': 'image/gif',
            b'GIF89a': 'image/gif',
            b'RIFF': 'audio/wav',  # Could also be video/avi
            b'\x00\x00\x01\x00': 'image/x-icon',
            b'BM': 'image/bmp',
            b'%PDF': 'application/pdf',
            b'PK\x03\x04': 'application/zip',
            b'PK\x05\x06': 'application/zip',
            b'PK\x07\x08': 'application/zip',
            b'\x1f\x8b': 'application/gzip',
            b'\x42\x5a\x68': 'application/x-bzip2',
            b'\xfd7zXZ\x00': 'application/x-xz',
            b'\x7fELF': 'application/x-executable',
            b'MZ': 'application/x-msdos-program',
            b'\xca\xfe\xba\xbe': 'application/x-mach-binary',
            b'\xfe\xed\xfa\xce': 'application/x-mach-binary',
            b'\xfe\xed\xfa\xcf': 'application/x-mach-binary',
            b'\xce\xfa\xed\xfe': 'application/x-mach-binary',
            b'\xcf\xfa\xed\xfe': 'application/x-mach-binary',
        }

        logger.debug("MimeTypeTool initialized with extended type database")

    async def initialize(self, **kwargs: Any) -> bool:
        """Initialize the MIME type tool."""
        try:
            # Register custom types with system
            for ext, mime_type in self._custom_types.items():
                mimetypes.add_type(mime_type, ext)
            
            logger.info(f"MimeTypeTool initialized with {len(self._custom_types)} custom types")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MimeTypeTool: {e}")
            return False

    def _detect_from_extension(self, file_path: str) -> Optional[str]:
        """Detect MIME type from file extension."""
        # Try custom types first
        ext = Path(file_path).suffix.lower()
        if ext in self._custom_types:
            return self._custom_types[ext]
        
        # Handle compound extensions
        if file_path.endswith('.tar.gz'):
            return 'application/x-tar-gz'
        elif file_path.endswith('.tar.bz2'):
            return 'application/x-tar-bz2'
        elif file_path.endswith('.tar.xz'):
            return 'application/x-tar-xz'
        
        # Use system MIME types
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type

    def _detect_from_content(self, content: bytes) -> Optional[str]:
        """Detect MIME type from file content using magic numbers."""
        if not content:
            return None
        
        # Check magic numbers
        for magic, mime_type in self._magic_numbers.items():
            if content.startswith(magic):
                # Special handling for RIFF files
                if magic == b'RIFF' and len(content) > 8:
                    if content[8:12] == b'WAVE':
                        return 'audio/wav'
                    elif content[8:12] == b'AVI ':
                        return 'video/avi'
                    elif content[8:12] == b'WEBP':
                        return 'image/webp'
                return mime_type
        
        # Text vs binary heuristic
        try:
            content.decode('utf-8')
            # If we can decode as UTF-8, it's likely text
            return 'text/plain'
        except UnicodeDecodeError:
            # Check for common text encodings
            try:
                content.decode('ascii')
                return 'text/plain'
            except UnicodeDecodeError:
                pass
            
            try:
                content.decode('latin-1')
                # Could be text in latin-1 encoding
                return 'text/plain'
            except UnicodeDecodeError:
                pass
        
        # Default to binary
        return 'application/octet-stream'

    def _classify_file(self, mime_type: str, file_path: Optional[str] = None) -> Tuple[str, str, bool, bool, bool, bool]:
        """Classify file based on MIME type."""
        category = 'unknown'
        file_type = 'unknown'
        is_text = False
        is_binary = True
        is_image = False
        is_executable = False
        
        # Determine category
        for cat, prefixes in self._categories.items():
            for prefix in prefixes:
                if mime_type.startswith(prefix) or mime_type == prefix:
                    category = cat
                    break
            if category != 'unknown':
                break
        
        # Determine properties
        if mime_type.startswith('text/') or mime_type in ['application/json', 'application/xml', 'application/yaml']:
            is_text = True
            is_binary = False
            file_type = 'text'
        elif mime_type.startswith('image/'):
            is_image = True
            file_type = 'image'
        elif mime_type in ['application/x-executable', 'application/x-msdos-program', 'application/x-msdownload']:
            is_executable = True
            file_type = 'executable'
        elif mime_type.startswith('video/'):
            file_type = 'video'
        elif mime_type.startswith('audio/'):
            file_type = 'audio'
        elif 'zip' in mime_type or 'tar' in mime_type or 'archive' in mime_type:
            file_type = 'archive'
        elif mime_type in ['application/pdf', 'application/msword']:
            file_type = 'document'
        else:
            file_type = 'binary'
        
        return category, file_type, is_text, is_binary, is_image, is_executable

    def _get_file_description(self, mime_type: str, file_path: Optional[str] = None) -> str:
        """Get human-readable description of file type."""
        descriptions = {
            'text/plain': 'Plain text file',
            'text/html': 'HTML document',
            'text/css': 'Cascading Style Sheet',
            'text/javascript': 'JavaScript source code',
            'text/x-python': 'Python source code',
            'text/x-java-source': 'Java source code',
            'text/x-c': 'C source code',
            'text/x-c++': 'C++ source code',
            'application/json': 'JSON data file',
            'application/xml': 'XML document',
            'text/yaml': 'YAML configuration file',
            'image/png': 'PNG image',
            'image/jpeg': 'JPEG image',
            'image/gif': 'GIF image',
            'image/svg+xml': 'SVG vector image',
            'video/mp4': 'MP4 video',
            'audio/mpeg': 'MP3 audio',
            'application/pdf': 'PDF document',
            'application/zip': 'ZIP archive',
            'application/x-tar': 'TAR archive',
            'application/x-executable': 'Executable file',
            'application/octet-stream': 'Binary data file',
        }
        
        if mime_type in descriptions:
            return descriptions[mime_type]
        
        # Generate description from MIME type
        parts = mime_type.split('/')
        if len(parts) == 2:
            main_type, sub_type = parts
            sub_type = sub_type.replace('x-', '').replace('-', ' ').title()
            return f"{main_type.title()} file ({sub_type})"
        
        return f"File of type {mime_type}"

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a MIME type operation."""
        command = kwargs.get("command")
        
        if not command:
            raise ToolError("Parameter 'command' is required")

        logger.info(f"Executing MIME type command: {command}")

        try:
            if command == "detect_type":
                return await self._detect_type(kwargs)
            elif command == "classify_file":
                return await self._classify_file_command(kwargs)
            elif command == "batch_detect":
                return await self._batch_detect(kwargs)
            elif command == "list_types":
                return await self._list_types(kwargs)
            elif command == "register_type":
                return await self._register_type(kwargs)
            elif command == "validate_type":
                return await self._validate_type(kwargs)
            else:
                raise ToolError(f"Unsupported command: {command}")
        except ToolError as e:
            return ToolResult.create_error(error=str(e), tool_name=self.name)
        except Exception as e:
            return ToolResult.create_error(error=f"Error executing command {command}: {str(e)}", tool_name=self.name)

    async def _detect_type(self, kwargs: dict) -> CLIResult:
        """Detect MIME type for a single file."""
        path = kwargs.get("path")
        content_sample = kwargs.get("content_sample")
        use_content = kwargs.get("use_content", True)
        include_magic = kwargs.get("include_magic", True)

        if not path and not content_sample:
            raise ToolError("Either 'path' or 'content_sample' is required for detect_type")

        # Check if file exists when path is provided
        if path and not Path(path).exists():
            raise ToolError(f"File does not exist: {path}")

        # Detect from extension
        extension_mime = None
        if path:
            extension_mime = self._detect_from_extension(path)

        # Detect from content
        content_mime = None
        if use_content:
            if path and Path(path).exists():
                try:
                    with open(path, 'rb') as f:
                        content = f.read(1024)  # Read first 1KB
                    if include_magic:
                        content_mime = self._detect_from_content(content)
                except Exception as e:
                    logger.warning(f"Failed to read file content: {e}")
            elif content_sample:
                content_bytes = content_sample.encode('utf-8')
                if include_magic:
                    content_mime = self._detect_from_content(content_bytes)

        # Determine final MIME type
        final_mime = extension_mime or content_mime or 'application/octet-stream'

        # Get classification
        category, file_type, is_text, is_binary, is_image, is_executable = self._classify_file(final_mime, path)
        description = self._get_file_description(final_mime, path)

        # Format result
        result = f"MIME Type Detection Results:\n\n"
        result += f"File: {path or 'content sample'}\n"
        result += f"MIME Type: {final_mime}\n"
        result += f"Category: {category}\n"
        result += f"File Type: {file_type}\n"
        result += f"Description: {description}\n\n"
        
        result += "Properties:\n"
        result += f"  Text file: {is_text}\n"
        result += f"  Binary file: {is_binary}\n"
        result += f"  Image: {is_image}\n"
        result += f"  Executable: {is_executable}\n\n"
        
        if extension_mime and content_mime and extension_mime != content_mime:
            result += "Note: Extension and content detection results differ:\n"
            result += f"  Extension suggests: {extension_mime}\n"
            result += f"  Content suggests: {content_mime}\n"
            result += f"  Using: {final_mime}\n"

        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _classify_file_command(self, kwargs: dict) -> CLIResult:
        """Classify a file with detailed information."""
        path = kwargs.get("path")
        if not path:
            raise ToolError("Parameter 'path' is required for classify_file")

        if not Path(path).exists():
            raise ToolError(f"File does not exist: {path}")

        # Get file stats
        file_path = Path(path)
        file_size = file_path.stat().st_size
        
        # Detect MIME type
        mime_type = self._detect_from_extension(path)
        
        # Try content detection if needed
        if not mime_type or mime_type == 'application/octet-stream':
            try:
                with open(path, 'rb') as f:
                    content = f.read(1024)
                content_mime = self._detect_from_content(content)
                if content_mime:
                    mime_type = content_mime
            except Exception:
                pass
        
        if not mime_type:
            mime_type = 'application/octet-stream'

        # Classify
        category, file_type, is_text, is_binary, is_image, is_executable = self._classify_file(mime_type, path)
        description = self._get_file_description(mime_type, path)

        # Get all extensions for this MIME type
        extensions = []
        for ext, mt in self._custom_types.items():
            if mt == mime_type:
                extensions.append(ext)

        # Create result
        file_info = FileTypeInfo(
            path=str(file_path),
            mime_type=mime_type,
            file_type=file_type,
            category=category,
            is_text=is_text,
            is_binary=is_binary,
            is_image=is_image,
            is_executable=is_executable,
            extensions=extensions,
            description=description
        )

        # Format output
        result = f"File Classification Report:\n\n"
        result += f"Path: {file_info.path}\n"
        result += f"Size: {file_size:,} bytes\n"
        result += f"MIME Type: {file_info.mime_type}\n"
        result += f"Category: {file_info.category}\n"
        result += f"Type: {file_info.file_type}\n"
        result += f"Description: {file_info.description}\n\n"
        
        result += "Properties:\n"
        result += f"  Text: {file_info.is_text}\n"
        result += f"  Binary: {file_info.is_binary}\n"
        result += f"  Image: {file_info.is_image}\n"
        result += f"  Executable: {file_info.is_executable}\n\n"
        
        if file_info.extensions:
            result += f"Common extensions: {', '.join(file_info.extensions)}\n"

        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _batch_detect(self, kwargs: dict) -> CLIResult:
        """Detect MIME types for multiple files."""
        paths = kwargs.get("paths")
        if not paths:
            raise ToolError("Parameter 'paths' is required for batch_detect")

        category_filter = kwargs.get("category_filter")
        use_content = kwargs.get("use_content", False)  # Disabled by default for performance

        results = []
        for file_path in paths:
            try:
                if not Path(file_path).exists():
                    results.append({
                        'path': file_path,
                        'error': 'File does not exist'
                    })
                    continue

                # Detect MIME type
                mime_type = self._detect_from_extension(file_path)
                
                if use_content and (not mime_type or mime_type == 'application/octet-stream'):
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read(512)  # Smaller sample for batch
                        content_mime = self._detect_from_content(content)
                        if content_mime:
                            mime_type = content_mime
                    except Exception:
                        pass
                
                if not mime_type:
                    mime_type = 'application/octet-stream'

                # Classify
                category, file_type, is_text, is_binary, is_image, is_executable = self._classify_file(mime_type, file_path)
                
                # Apply category filter
                if category_filter and category != category_filter:
                    continue

                results.append({
                    'path': file_path,
                    'mime_type': mime_type,
                    'category': category,
                    'file_type': file_type,
                    'is_text': is_text,
                    'is_image': is_image,
                    'is_executable': is_executable
                })

            except Exception as e:
                results.append({
                    'path': file_path,
                    'error': str(e)
                })

        # Format results
        result = f"Batch MIME Type Detection Results:\n"
        result += f"Processed {len(paths)} files, {len(results)} results\n\n"

        if category_filter:
            result += f"Filtered by category: {category_filter}\n\n"

        # Group by category
        by_category = {}
        errors = []
        
        for item in results:
            if 'error' in item:
                errors.append(item)
            else:
                category = item['category']
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(item)

        # Display by category
        for category in sorted(by_category.keys()):
            items = by_category[category]
            result += f"=== {category.upper()} ({len(items)} files) ===\n"
            for item in items[:10]:  # Limit display
                result += f"  {item['file_type']:<12} {item['mime_type']:<30} {Path(item['path']).name}\n"
            if len(items) > 10:
                result += f"  ... and {len(items) - 10} more files\n"
            result += "\n"

        # Display errors
        if errors:
            result += f"=== ERRORS ({len(errors)} files) ===\n"
            for error in errors[:5]:
                result += f"  {error['path']}: {error['error']}\n"
            if len(errors) > 5:
                result += f"  ... and {len(errors) - 5} more errors\n"

        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _list_types(self, kwargs: dict) -> CLIResult:
        """List available MIME types and categories."""
        category_filter = kwargs.get("category_filter")

        result = "Available MIME Types and Categories:\n\n"

        if category_filter:
            # Show specific category
            if category_filter not in self._categories:
                raise ToolError(f"Unknown category: {category_filter}")
            
            result += f"Category: {category_filter.upper()}\n"
            result += f"Patterns: {', '.join(self._categories[category_filter])}\n\n"
            
            # Find matching types
            matching_types = []
            for ext, mime_type in self._custom_types.items():
                for pattern in self._categories[category_filter]:
                    if mime_type.startswith(pattern) or mime_type == pattern:
                        matching_types.append((ext, mime_type))
                        break
            
            result += f"Extensions ({len(matching_types)}):\n"
            for ext, mime_type in sorted(matching_types)[:50]:
                result += f"  {ext:<15} {mime_type}\n"
            
            if len(matching_types) > 50:
                result += f"  ... and {len(matching_types) - 50} more\n"
        
        else:
            # Show all categories
            result += "=== CATEGORIES ===\n"
            for category, patterns in self._categories.items():
                count = sum(1 for mt in self._custom_types.values() 
                          for pattern in patterns 
                          if mt.startswith(pattern) or mt == pattern)
                result += f"{category:<12} {count:>3} types  {', '.join(patterns[:2])}\n"
            
            result += f"\n=== STATISTICS ===\n"
            result += f"Total custom types: {len(self._custom_types)}\n"
            result += f"Magic signatures: {len(self._magic_numbers)}\n"
            result += f"Categories: {len(self._categories)}\n"
            
            # Most common types
            type_counts = {}
            for mime_type in self._custom_types.values():
                main_type = mime_type.split('/')[0]
                type_counts[main_type] = type_counts.get(main_type, 0) + 1
            
            result += f"\nMost common main types:\n"
            for main_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                result += f"  {main_type}: {count} types\n"

        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _register_type(self, kwargs: dict) -> CLIResult:
        """Register a custom MIME type."""
        extension = kwargs.get("extension")
        mime_type = kwargs.get("mime_type")

        if not extension:
            raise ToolError("Parameter 'extension' is required for register_type")
        if not mime_type:
            raise ToolError("Parameter 'mime_type' is required for register_type")

        # Normalize extension
        if not extension.startswith('.'):
            extension = '.' + extension
        extension = extension.lower()

        # Validate MIME type format
        if '/' not in mime_type:
            raise ToolError("MIME type must be in format 'type/subtype'")

        # Check if already exists
        existing = self._custom_types.get(extension)
        if existing:
            result = f"Updated MIME type registration:\n"
            result += f"Extension: {extension}\n"
            result += f"Old type: {existing}\n"
            result += f"New type: {mime_type}\n"
        else:
            result = f"Registered new MIME type:\n"
            result += f"Extension: {extension}\n"
            result += f"MIME type: {mime_type}\n"

        # Register the type
        self._custom_types[extension] = mime_type
        mimetypes.add_type(mime_type, extension)

        logger.info(f"Registered MIME type: {extension} -> {mime_type}")

        return CLIResult.create_success(result=result, tool_name=self.name)

    async def _validate_type(self, kwargs: dict) -> CLIResult:
        """Validate a MIME type or file type detection."""
        path = kwargs.get("path")
        mime_type = kwargs.get("mime_type")

        if path:
            # Validate file type detection
            if not Path(path).exists():
                raise ToolError(f"File does not exist: {path}")

            detected_mime = self._detect_from_extension(path)
            
            # Also check content
            try:
                with open(path, 'rb') as f:
                    content = f.read(1024)
                content_mime = self._detect_from_content(content)
            except Exception:
                content_mime = None

            result = f"File Type Validation:\n\n"
            result += f"File: {path}\n"
            result += f"Extension detection: {detected_mime or 'Unknown'}\n"
            result += f"Content detection: {content_mime or 'Unknown'}\n"
            
            if detected_mime and content_mime:
                if detected_mime == content_mime:
                    result += f"✅ Extension and content agree: {detected_mime}\n"
                else:
                    result += f"⚠️  Extension and content disagree\n"
                    result += f"   Recommended: Use content-based detection\n"
            elif detected_mime:
                result += f"ℹ️  Only extension detection available\n"
            elif content_mime:
                result += f"ℹ️  Only content detection available\n"
            else:
                result += f"❌ Unable to determine file type\n"

        elif mime_type:
            # Validate MIME type format
            if '/' not in mime_type:
                result = f"❌ Invalid MIME type format: {mime_type}\n"
                result += f"   Must be in format 'type/subtype'\n"
            else:
                parts = mime_type.split('/')
                if len(parts) != 2:
                    result = f"❌ Invalid MIME type format: {mime_type}\n"
                else:
                    main_type, sub_type = parts
                    result = f"✅ Valid MIME type: {mime_type}\n"
                    result += f"   Main type: {main_type}\n"
                    result += f"   Sub type: {sub_type}\n"
                    
                    # Check if we know about this type
                    known_extensions = [ext for ext, mt in self._custom_types.items() if mt == mime_type]
                    if known_extensions:
                        result += f"   Known extensions: {', '.join(known_extensions)}\n"
                    
                    category, file_type, is_text, is_binary, is_image, is_executable = self._classify_file(mime_type)
                    result += f"   Category: {category}\n"
                    result += f"   File type: {file_type}\n"
        else:
            raise ToolError("Either 'path' or 'mime_type' is required for validate_type")

        return CLIResult.create_success(result=result, tool_name=self.name)

    async def cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up MimeTypeTool resources")