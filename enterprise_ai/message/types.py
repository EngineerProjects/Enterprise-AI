"""
Message-specific type definitions and protocols for Enterprise AI.

This module extends the core type system with specialized types and protocols
for message handling, transformation, validation, and storage. It provides
type-safe definitions for various message content formats and operations
while maintaining compatibility with the core type system.
"""

from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    runtime_checkable,
)

from enterprise_ai.types import (
    MessageProtocol,
    ToolCallProtocol,
    Serializable,
    RoleType,
)
from enterprise_ai.message.constants import (
    ContentTypeValue,
    ImageFormatValue,
    MessageFormatValue,
    CONTENT_TYPE_TEXT,
    CONTENT_TYPE_IMAGE,
    CONTENT_TYPE_CODE,
    CONTENT_TYPE_MARKDOWN,
    CONTENT_TYPE_TOOL_CALL,
    CONTENT_TYPE_TOOL_RESULT,
    CONTENT_TYPE_FILE,
)

# Type variables for generic typing
T = TypeVar("T")
# Make M covariant to fix the variance error
M = TypeVar("M", bound="MessageProtocol", covariant=True)
C = TypeVar("C", bound="ContentProtocol")


# -----------------------------------------------------------------------------
# Message Content Type Definitions
# -----------------------------------------------------------------------------


class ContentType(str, Enum):
    """Types of content that can be included in a message."""

    TEXT = CONTENT_TYPE_TEXT
    IMAGE = CONTENT_TYPE_IMAGE
    CODE = CONTENT_TYPE_CODE
    MARKDOWN = CONTENT_TYPE_MARKDOWN
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = CONTENT_TYPE_FILE
    TOOL_CALL = CONTENT_TYPE_TOOL_CALL
    TOOL_RESULT = CONTENT_TYPE_TOOL_RESULT


class ImageFormat(str, Enum):
    """Image formats supported in messages."""

    PNG = "png"
    JPEG = "jpeg"
    GIF = "gif"
    WEBP = "webp"
    SVG = "svg"
    BASE64 = "base64"


class MessageFormat(str, Enum):
    """Message formatting options for different providers."""

    DEFAULT = "default"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PLAIN = "plain"


# -----------------------------------------------------------------------------
# Message Content Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class ContentProtocol(Serializable, Protocol):
    """Protocol for message content of any type."""

    content_type: ContentTypeValue

    def to_string(self) -> str:
        """Convert content to string representation."""
        ...

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        ...

    def get_content_type(self) -> ContentTypeValue:
        """Get the content type."""
        ...


@runtime_checkable
class TextContent(ContentProtocol, Protocol):
    """Protocol for text content."""

    text: str
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_TEXT


@runtime_checkable
class ImageContent(ContentProtocol, Protocol):
    """Protocol for image content."""

    data: Union[str, bytes]
    format: ImageFormatValue
    alt_text: Optional[str]
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_IMAGE


@runtime_checkable
class CodeContent(ContentProtocol, Protocol):
    """Protocol for code content."""

    code: str
    language: str
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_CODE


@runtime_checkable
class MarkdownContent(ContentProtocol, Protocol):
    """Protocol for markdown content."""

    markdown: str
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_MARKDOWN


@runtime_checkable
class ToolCallContent(ContentProtocol, Protocol):
    """Protocol for tool call content."""

    tool_calls: List[ToolCallProtocol]
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_TOOL_CALL


@runtime_checkable
class ToolResultContent(ContentProtocol, Protocol):
    """Protocol for tool result content."""

    tool_call_id: str
    result: Dict[str, Any]
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_TOOL_RESULT


@runtime_checkable
class FileContent(ContentProtocol, Protocol):
    """Protocol for file content."""

    data: bytes
    filename: str
    mime_type: str
    content_type: ContentTypeValue  # Should be CONTENT_TYPE_FILE


# -----------------------------------------------------------------------------
# Extended Message Protocols
# -----------------------------------------------------------------------------


@runtime_checkable
class EnhancedMessageProtocol(MessageProtocol, Protocol):
    """Extended protocol for enhanced messages with additional capabilities."""

    id: str
    created_at: datetime
    updated_at: Optional[datetime]
    version: int
    content_objects: List[ContentProtocol]

    def add_content(self, content: ContentProtocol) -> None:
        """Add content to the message."""
        ...

    def get_content_by_type(self, content_type: ContentTypeValue) -> List[ContentProtocol]:
        """Get content by type."""
        ...

    def has_content_type(self, content_type: ContentTypeValue) -> bool:
        """Check if message has content of specified type."""
        ...

    def transform(self, format: MessageFormatValue) -> Dict[str, Any]:
        """Transform message to specified format."""
        ...


@runtime_checkable
class MessageTransformerProtocol(Protocol):
    """Protocol for message transformation between formats."""

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to the target format."""
        ...

    def transform_batch(
        self, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to the target format."""
        ...

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format."""
        ...


@runtime_checkable
class MessageValidatorProtocol(Protocol):
    """Protocol for message validation."""

    def validate(self, message: MessageProtocol) -> Tuple[bool, Optional[str]]:
        """Validate a message.

        Returns:
            Tuple of (is_valid, error_message)
        """
        ...

    def validate_content(self, content: ContentProtocol) -> Tuple[bool, Optional[str]]:
        """Validate message content.

        Returns:
            Tuple of (is_valid, error_message)
        """
        ...


@runtime_checkable
class MessageFactoryProtocol(Protocol[M]):
    """Protocol for message factories that create specialized messages."""

    def create_user_message(self, content: str, **kwargs: Any) -> M:
        """Create a user message."""
        ...

    def create_system_message(self, content: str, **kwargs: Any) -> M:
        """Create a system message."""
        ...

    def create_assistant_message(self, content: Optional[str] = None, **kwargs: Any) -> M:
        """Create an assistant message."""
        ...

    def create_tool_message(self, content: str, name: str, tool_call_id: str, **kwargs: Any) -> M:
        """Create a tool message."""
        ...

    def create_agent_message(self, content: str, name: str, **kwargs: Any) -> M:
        """Create an agent message."""
        ...

    def create_from_dict(self, data: Dict[str, Any]) -> M:
        """Create a message from a dictionary."""
        ...


@runtime_checkable
class MessageStorageProtocol(Protocol):
    """Protocol for message storage and retrieval."""

    def store(self, message: MessageProtocol) -> str:
        """Store a message and return its ID."""
        ...

    def retrieve(self, message_id: str) -> Optional[MessageProtocol]:
        """Retrieve a message by ID."""
        ...

    def update(self, message: MessageProtocol) -> bool:
        """Update a stored message."""
        ...

    def delete(self, message_id: str) -> bool:
        """Delete a message by ID."""
        ...

    def list(self, filter_criteria: Optional[Dict[str, Any]] = None) -> List[MessageProtocol]:
        """List messages matching filter criteria."""
        ...


# -----------------------------------------------------------------------------
# Generic Message Collections
# -----------------------------------------------------------------------------


class MessageFilterCriteria(Dict[str, Any]):
    """Type for message filter criteria."""

    pass


@runtime_checkable
class MessageCollectionProtocol(Protocol):
    """Protocol for collections of messages with filtering and sorting."""

    def add(self, message: MessageProtocol) -> None:
        """Add a message to the collection."""
        ...

    def remove(self, message_id: str) -> bool:
        """Remove a message from the collection."""
        ...

    def get(self, message_id: str) -> Optional[MessageProtocol]:
        """Get a message by ID."""
        ...

    def filter(self, criteria: MessageFilterCriteria) -> List[MessageProtocol]:
        """Filter messages based on criteria."""
        ...

    def sort(
        self, key: Callable[[MessageProtocol], Any], reverse: bool = False
    ) -> List[MessageProtocol]:
        """Sort messages based on key function."""
        ...

    def clear(self) -> None:
        """Clear all messages from the collection."""
        ...

    def count(self) -> int:
        """Count messages in the collection."""
        ...
