"""
Message handling system for Enterprise AI.

This module provides a comprehensive framework for working with messages in the
Enterprise AI platform. It includes enhanced message types, content objects,
formatting utilities, validation, and specialized image handling capabilities.

The message system serves as a foundation for agent-to-agent communication and
LLM interactions throughout the platform.
"""

# Version information
__version__ = "0.1.0"

# First import basic types and constants to avoid circular imports
from enterprise_ai.message.constants import (
    # Content type constants
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
    SUPPORTED_CONTENT_TYPES,
    # Image format constants
    IMAGE_FORMAT_PNG,
    IMAGE_FORMAT_JPEG,
    IMAGE_FORMAT_GIF,
    IMAGE_FORMAT_WEBP,
    IMAGE_FORMAT_SVG,
    IMAGE_FORMAT_BASE64,
    SUPPORTED_IMAGE_FORMATS,
    # Message format constants
    MESSAGE_FORMAT_DEFAULT,
    MESSAGE_FORMAT_OPENAI,
    MESSAGE_FORMAT_ANTHROPIC,
    MESSAGE_FORMAT_OLLAMA,
    MESSAGE_FORMAT_MARKDOWN,
    MESSAGE_FORMAT_HTML,
    MESSAGE_FORMAT_JSON,
    MESSAGE_FORMAT_PLAIN,
    SUPPORTED_MESSAGE_FORMATS,
)

# Import type definitions
from enterprise_ai.message.types import (
    # Content type enums
    ContentType,
    ImageFormat,
    MessageFormat,
    # Content protocols
    ContentProtocol,
    TextContent,
    ImageContent,
    CodeContent,
    MarkdownContent,
    ToolCallContent,
    ToolResultContent,
    FileContent,
    # Enhanced message protocols
    EnhancedMessageProtocol,
    MessageTransformerProtocol,
    MessageValidatorProtocol,
    MessageFactoryProtocol,
    MessageStorageProtocol,
    MessageCollectionProtocol,
)

# Import exceptions
from enterprise_ai.message.exceptions import (
    MessageError,
    MessageValidationError,
    MessageFormatError,
    MessageContentError,
    MessageImageError,
    InvalidImageError,
    ImageSizeError,
    ImageFormatError,
    ImageProcessingError,
    ContentCollectionError,
)

# Import base module for enhanced message functionality
from enterprise_ai.message.base import (
    EnhancedMessage,
    MessageFactory,
    MessageTransformerRegistry,
    MessageValidator,
)

# Import image processing capabilities
from enterprise_ai.message.image import (
    is_base64,
    encode_image_to_base64,
    decode_base64_to_image,
    detect_image_format,
    validate_image,
    resize_image,
    compress_image,
    create_image_content,
    prepare_image_for_provider,
    ImageResizeMode,
)

# Import high-level image helper
from enterprise_ai.message.image_helper import (
    ImageHelper,
    process_image_for_message,
    optimize_image_for_message,
)

# Import formatting utilities
from enterprise_ai.message.formatter import (
    MessageFormatter,
    PlainTextFormatter,
    MarkdownFormatter,
    HTMLFormatter,
    ConsoleFormatter,
    FormatterRegistry,
    format_message,
    format_messages,
    get_formatter,
    register_formatter,
    message_to_html,
    message_to_markdown,
    conversation_to_html,
)

# Import validation utilities
from enterprise_ai.message.validation import (
    BaseValidator,
    StrictValidator,
    ValidatorRegistry,
    validate_messages,
    is_valid_message,
    get_validation_error,
)

# Import message utilities
from enterprise_ai.message.utils import (
    extract_code_blocks,
    extract_text_without_code_blocks,
    get_message_summary,
    format_message_for_display,
    message_to_dict,
    messages_to_dict_list,
    dict_to_message,
    contains_image,
    contains_code,
    get_message_type,
    filter_messages_by_role,
    filter_messages_by_timestamp,
    search_messages,
    extract_structured_content,
    normalize_message_content,
    get_conversation_summary,
    merge_consecutive_messages,
)

# Import memory module for conversation history management
from enterprise_ai.message.memory import (
    EnhancedMemory,
    ConversationMemory,
    ShortTermMemory,
    LongTermMemory,
    create_conversation_memory,
    create_short_term_memory,
    create_long_term_memory,
)

# Define the public API for this module
__all__ = [
    # Message classes and factory
    "EnhancedMessage",
    "MessageFactory",
    "MessageTransformerRegistry",
    "MessageValidator",
    # Core content type constants
    "CONTENT_TYPE_TEXT",
    "CONTENT_TYPE_IMAGE",
    "CONTENT_TYPE_CODE",
    "CONTENT_TYPE_MARKDOWN",
    "CONTENT_TYPE_TOOL_CALL",
    "CONTENT_TYPE_TOOL_RESULT",
    "CONTENT_TYPE_FILE",
    "SUPPORTED_CONTENT_TYPES",
    # Image format constants
    "IMAGE_FORMAT_PNG",
    "IMAGE_FORMAT_JPEG",
    "IMAGE_FORMAT_GIF",
    "IMAGE_FORMAT_WEBP",
    "IMAGE_FORMAT_SVG",
    "IMAGE_FORMAT_BASE64",
    "SUPPORTED_IMAGE_FORMATS",
    # Message format constants
    "MESSAGE_FORMAT_DEFAULT",
    "MESSAGE_FORMAT_OPENAI",
    "MESSAGE_FORMAT_ANTHROPIC",
    "MESSAGE_FORMAT_MARKDOWN",
    "MESSAGE_FORMAT_HTML",
    "MESSAGE_FORMAT_JSON",
    "MESSAGE_FORMAT_PLAIN",
    "SUPPORTED_MESSAGE_FORMATS",
    # Type enums
    "ContentType",
    "ImageFormat",
    "MessageFormat",
    # Content protocols
    "ContentProtocol",
    "TextContent",
    "ImageContent",
    "CodeContent",
    "MarkdownContent",
    "ToolCallContent",
    "ToolResultContent",
    "FileContent",
    # Message protocols
    "EnhancedMessageProtocol",
    "MessageTransformerProtocol",
    "MessageValidatorProtocol",
    "MessageFactoryProtocol",
    "MessageStorageProtocol",
    "MessageCollectionProtocol",
    # Message exceptions
    "MessageError",
    "MessageValidationError",
    "MessageFormatError",
    "MessageContentError",
    "MessageImageError",
    "InvalidImageError",
    "ImageSizeError",
    "ImageFormatError",
    "ImageProcessingError",
    "ContentCollectionError",
    # Image processing
    "is_base64",
    "encode_image_to_base64",
    "decode_base64_to_image",
    "detect_image_format",
    "validate_image",
    "resize_image",
    "compress_image",
    "create_image_content",
    "prepare_image_for_provider",
    "ImageResizeMode",
    # Image helper
    "ImageHelper",
    "process_image_for_message",
    "optimize_image_for_message",
    # Formatters
    "MessageFormatter",
    "PlainTextFormatter",
    "MarkdownFormatter",
    "HTMLFormatter",
    "ConsoleFormatter",
    "FormatterRegistry",
    "format_message",
    "format_messages",
    "get_formatter",
    "register_formatter",
    "message_to_html",
    "message_to_markdown",
    "conversation_to_html",
    # Validators
    "BaseValidator",
    "StrictValidator",
    "ValidatorRegistry",
    "validate_messages",
    "is_valid_message",
    "get_validation_error",
    # Utilities
    "extract_code_blocks",
    "extract_text_without_code_blocks",
    "get_message_summary",
    "format_message_for_display",
    "message_to_dict",
    "messages_to_dict_list",
    "dict_to_message",
    "contains_image",
    "contains_code",
    "get_message_type",
    "filter_messages_by_role",
    "filter_messages_by_timestamp",
    "search_messages",
    "extract_structured_content",
    "normalize_message_content",
    "get_conversation_summary",
    "merge_consecutive_messages",
    # Memory module
    "EnhancedMemory",
    "ConversationMemory",
    "ShortTermMemory",
    "LongTermMemory",
    "create_conversation_memory",
    "create_short_term_memory",
    "create_long_term_memory",
]
