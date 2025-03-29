"""
Message module constants for Enterprise AI.

This module defines constants related to message handling, including content types,
formats, and other message-specific values. These constants are used throughout
the message module to ensure consistency and type safety.
"""

import re
from typing import Dict, Final, Literal, Set

# -----------------------------------------------------------------------------
# Content Type Constants
# -----------------------------------------------------------------------------

# Content types for message content
CONTENT_TYPE_TEXT: Final[str] = "text"
CONTENT_TYPE_IMAGE: Final[str] = "image"
CONTENT_TYPE_CODE: Final[str] = "code"
CONTENT_TYPE_MARKDOWN: Final[str] = "markdown"
CONTENT_TYPE_HTML: Final[str] = "html"
CONTENT_TYPE_JSON: Final[str] = "json"
CONTENT_TYPE_CSV: Final[str] = "csv"
CONTENT_TYPE_XML: Final[str] = "xml"
CONTENT_TYPE_AUDIO: Final[str] = "audio"
CONTENT_TYPE_VIDEO: Final[str] = "video"
CONTENT_TYPE_FILE: Final[str] = "file"
CONTENT_TYPE_TOOL_CALL: Final[str] = "tool_call"
CONTENT_TYPE_TOOL_RESULT: Final[str] = "tool_result"

# Set of all supported content types
SUPPORTED_CONTENT_TYPES: Final[Set[str]] = {
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_MARKDOWN,
    CONTENT_TYPE_HTML,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_CSV,
    CONTENT_TYPE_XML,
    CONTENT_TYPE_AUDIO,
    CONTENT_TYPE_VIDEO,
    CONTENT_TYPE_FILE,
    CONTENT_TYPE_TOOL_CALL,
    CONTENT_TYPE_TOOL_RESULT,
}

# Literal type for content types
ContentTypeValue = Literal[
    "text",
    "image",
    "code",
    "markdown",
    "html",
    "json",
    "csv",
    "xml",
    "audio",
    "video",
    "file",
    "tool_call",
    "tool_result",
]

# -----------------------------------------------------------------------------
# Image Format Constants
# -----------------------------------------------------------------------------

# Image formats supported in messages
IMAGE_FORMAT_PNG: Final[str] = "png"
IMAGE_FORMAT_JPEG: Final[str] = "jpeg"
IMAGE_FORMAT_GIF: Final[str] = "gif"
IMAGE_FORMAT_WEBP: Final[str] = "webp"
IMAGE_FORMAT_SVG: Final[str] = "svg"
IMAGE_FORMAT_BASE64: Final[str] = "base64"

# Set of all supported image formats
SUPPORTED_IMAGE_FORMATS: Final[Set[str]] = {
    IMAGE_FORMAT_PNG,
    IMAGE_FORMAT_JPEG,
    IMAGE_FORMAT_GIF,
    IMAGE_FORMAT_WEBP,
    IMAGE_FORMAT_SVG,
    IMAGE_FORMAT_BASE64,
}

# Literal type for image formats
ImageFormatValue = Literal["png", "jpeg", "gif", "webp", "svg", "base64"]

# MIME types for image formats
IMAGE_MIME_TYPES: Final[Dict[str, str]] = {
    IMAGE_FORMAT_PNG: "image/png",
    IMAGE_FORMAT_JPEG: "image/jpeg",
    IMAGE_FORMAT_GIF: "image/gif",
    IMAGE_FORMAT_WEBP: "image/webp",
    IMAGE_FORMAT_SVG: "image/svg+xml",
}


MAX_IMAGE_SIZE_BYTES = 4 * 1024 * 1024  # 4MB default maximum
DEFAULT_IMAGE_FORMAT = IMAGE_FORMAT_PNG
DEFAULT_JPEG_QUALITY = 85
DEFAULT_IMAGE_WIDTH = 1024  # Default width for resizing
SVG_HEADER = b'<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
SVG_TAG_PATTERN = re.compile(r"<svg\s.*?>.*?</svg>", re.DOTALL)
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
JPEG_HEADER = b"\xff\xd8\xff"
GIF_HEADER = b"GIF8"
WEBP_HEADER = b"RIFF....WEBP"  # .... represents 4 variable bytes

# Provider-specific image size limits
PROVIDER_IMAGE_LIMITS = {
    "openai": 20 * 1024 * 1024,  # 20MB for OpenAI
    "anthropic": 5 * 1024 * 1024,  # 5MB for Anthropic
    "ollama": 10 * 1024 * 1024,  # 10MB for Ollama
    "default": MAX_IMAGE_SIZE_BYTES,
}

# -----------------------------------------------------------------------------
# Message Format Constants
# -----------------------------------------------------------------------------

# Message formatting options for different providers
MESSAGE_FORMAT_DEFAULT: Final[str] = "default"
MESSAGE_FORMAT_OPENAI: Final[str] = "openai"
MESSAGE_FORMAT_ANTHROPIC: Final[str] = "anthropic"
MESSAGE_FORMAT_OLLAMA: Final[str] = "ollama"
MESSAGE_FORMAT_MARKDOWN: Final[str] = "markdown"
MESSAGE_FORMAT_HTML: Final[str] = "html"
MESSAGE_FORMAT_JSON: Final[str] = "json"
MESSAGE_FORMAT_PLAIN: Final[str] = "plain"

# Set of all supported message formats
SUPPORTED_MESSAGE_FORMATS: Final[Set[str]] = {
    MESSAGE_FORMAT_DEFAULT,
    MESSAGE_FORMAT_OPENAI,
    MESSAGE_FORMAT_ANTHROPIC,
    MESSAGE_FORMAT_OLLAMA,
    MESSAGE_FORMAT_MARKDOWN,
    MESSAGE_FORMAT_HTML,
    MESSAGE_FORMAT_JSON,
    MESSAGE_FORMAT_PLAIN,
}

# Literal type for message formats
MessageFormatValue = Literal[
    "default", "openai", "anthropic", "ollama", "markdown", "html", "json", "plain"
]

# -----------------------------------------------------------------------------
# Message Collection Constants
# -----------------------------------------------------------------------------

# Default values for message collections
DEFAULT_MAX_MESSAGES: Final[int] = 100
DEFAULT_MEMORY_RETENTION: Final[int] = 10  # Number of recent messages to keep by default

# -----------------------------------------------------------------------------
# Message Validation Constants
# -----------------------------------------------------------------------------

# Maximum lengths for different message components
MAX_MESSAGE_CONTENT_LENGTH: Final[int] = 100000
MAX_MESSAGE_NAME_LENGTH: Final[int] = 64
MAX_MESSAGE_ROLE_LENGTH: Final[int] = 32

# Maximum number of tool calls in a single message
MAX_TOOL_CALLS_PER_MESSAGE: Final[int] = 20

# Maximum number of content objects in a single message
MAX_CONTENT_OBJECTS_PER_MESSAGE: Final[int] = 50

# -----------------------------------------------------------------------------
# Content Format Markers
# -----------------------------------------------------------------------------

# Markers for formatted content
CODE_BLOCK_START: Final[str] = "```"
CODE_BLOCK_END: Final[str] = "```"
BOLD_MARKER: Final[str] = "**"
ITALIC_MARKER: Final[str] = "*"
STRIKETHROUGH_MARKER: Final[str] = "~~"
HEADING_MARKER: Final[str] = "#"
UNORDERED_LIST_MARKER: Final[str] = "- "
ORDERED_LIST_MARKER: Final[str] = "1. "
BLOCKQUOTE_MARKER: Final[str] = "> "
LINK_FORMAT: Final[str] = "[{text}]({url})"
IMAGE_FORMAT: Final[str] = "![{alt_text}]({url})"

# HTML special characters for escaping
HTML_SPECIAL_CHARS: Final[Dict[str, str]] = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}

# Maximum allowed length for different message components (in characters)
MAX_CONTENT_LENGTH: Final[int] = 100000
MAX_NAME_LENGTH: Final[int] = 64
MAX_TOOL_NAME_LENGTH: Final[int] = 64
MAX_SYSTEM_PROMPT_LENGTH: Final[int] = 32000

# Special tokens or markers for message processing
SYSTEM_PROMPT_MARKER: Final[str] = "<system>"
SYSTEM_PROMPT_END_MARKER: Final[str] = "</system>"
USER_PROMPT_MARKER: Final[str] = "<user>"
USER_PROMPT_END_MARKER: Final[str] = "</user>"
ASSISTANT_RESPONSE_MARKER: Final[str] = "<assistant>"
ASSISTANT_RESPONSE_END_MARKER: Final[str] = "</assistant>"
TOOL_RESPONSE_MARKER: Final[str] = "<tool>"
TOOL_RESPONSE_END_MARKER: Final[str] = "</tool>"
