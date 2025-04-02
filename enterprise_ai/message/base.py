"""
Enhanced message functionality for Enterprise AI.

This module implements extended message capabilities building on the core schema.Message
class. It provides enhanced message representation, creation, validation, and utility
methods while maintaining compatibility with the core message system.
"""

import base64
import copy
import json
from pathlib import Path
import uuid
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from enterprise_ai.exceptions import ConfigValueError
from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message, Role
from enterprise_ai.types import (
    MessageProtocol,
    ToolCallProtocol,
    RoleType,
)
from enterprise_ai.message.types import (
    ContentProtocol,
    ContentType,
    EnhancedMessageProtocol,
    ImageFormat,
    MessageFormat,
    MessageValidatorProtocol,
    TextContent,
    ImageContent,
    CodeContent,
    MarkdownContent,
    ToolCallContent,
    ToolResultContent,
    FileContent,
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
    IMAGE_FORMAT_BASE64,
    IMAGE_FORMAT_PNG,
    MESSAGE_FORMAT_DEFAULT,
    MESSAGE_FORMAT_OPENAI,
    MESSAGE_FORMAT_ANTHROPIC,
)

# Initialize logger
logger = get_logger("message.base")

# Type variables for generic typing
T = TypeVar("T", bound="EnhancedMessage")


# -----------------------------------------------------------------------------
# Content Implementation Classes
# -----------------------------------------------------------------------------


class BaseContent:
    """Base class for message content implementations."""

    def __init__(self, content_type: ContentTypeValue):
        self._content_type = content_type

    @property
    def content_type(self) -> ContentTypeValue:
        """Property to expose content_type as required by ContentProtocol."""
        return self._content_type

    def get_content_type(self) -> ContentTypeValue:
        """Get the content type."""
        return self._content_type

    def to_string(self) -> str:
        """Convert content to string representation."""
        raise NotImplementedError("Subclasses must implement to_string()")

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        return {"content_type": self._content_type}


class TextContentImpl(BaseContent):
    """Implementation of text content."""

    def __init__(self, text: str):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_TEXT))
        self.text = text

    def to_string(self) -> str:
        """Convert content to string representation."""
        return self.text

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()
        result["text"] = self.text
        return result


class ImageContentImpl(BaseContent):
    """Implementation of image content."""

    def __init__(
        self,
        data: Union[str, bytes],
        format: str = IMAGE_FORMAT_BASE64,
        alt_text: Optional[str] = None,
    ):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_IMAGE))
        self.data = data
        self.format = cast(ImageFormatValue, format)
        self.alt_text = alt_text

    def to_string(self) -> str:
        """Convert content to string representation."""
        if self.alt_text:
            return f"[Image: {self.alt_text}]"
        return "[Image]"

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()

        # Handle bytes vs string data appropriately
        if isinstance(self.data, bytes):
            result["data"] = base64.b64encode(self.data).decode("utf-8")
            result["encoding"] = "base64"
        else:
            result["data"] = self.data
            result["encoding"] = "string"

        result["format"] = self.format
        if self.alt_text:
            result["alt_text"] = self.alt_text

        return result

    @classmethod
    def from_base64(
        cls, base64_data: str, format: str = IMAGE_FORMAT_PNG, alt_text: Optional[str] = None
    ) -> "ImageContentImpl":
        """Create image content from base64 data."""
        return cls(base64_data, format, alt_text)

    @classmethod
    def from_bytes(
        cls, image_bytes: bytes, format: str = IMAGE_FORMAT_PNG, alt_text: Optional[str] = None
    ) -> "ImageContentImpl":
        """Create image content from bytes."""
        return cls(image_bytes, format, alt_text)


class CodeContentImpl(BaseContent):
    """Implementation of code content."""

    def __init__(self, code: str, language: str):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_CODE))
        self.code = code
        self.language = language

    def to_string(self) -> str:
        """Convert content to string representation."""
        return f"```{self.language}\n{self.code}\n```"

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()
        result["code"] = self.code
        result["language"] = self.language
        return result


class MarkdownContentImpl(BaseContent):
    """Implementation of markdown content."""

    def __init__(self, markdown: str):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_MARKDOWN))
        self.markdown = markdown

    def to_string(self) -> str:
        """Convert content to string representation."""
        return self.markdown

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()
        result["markdown"] = self.markdown
        return result


class ToolCallContentImpl(BaseContent):
    """Implementation of tool call content."""

    def __init__(self, tool_calls: List[ToolCallProtocol]):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_TOOL_CALL))
        self.tool_calls = tool_calls

    def to_string(self) -> str:
        """Convert content to string representation."""
        calls = []
        for call in self.tool_calls:
            calls.append(f"Call to {call.function.name}({call.function.arguments})")
        return "\n".join(calls)

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()
        result["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        return result


class ToolResultContentImpl(BaseContent):
    """Implementation of tool result content."""

    def __init__(self, tool_call_id: str, result: Dict[str, Any]):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_TOOL_RESULT))
        self.tool_call_id = tool_call_id
        self.result = result

    def to_string(self) -> str:
        """Convert content to string representation."""
        return f"Tool result for call {self.tool_call_id}: {json.dumps(self.result)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()
        result["tool_call_id"] = self.tool_call_id
        result["result"] = self.result
        return result


class FileContentImpl(BaseContent):
    """Implementation of file content."""

    def __init__(self, data: bytes, filename: str, mime_type: str):
        super().__init__(cast(ContentTypeValue, CONTENT_TYPE_FILE))
        self.data = data
        self.filename = filename
        self.mime_type = mime_type

    def to_string(self) -> str:
        """Convert content to string representation."""
        return f"[File: {self.filename} ({self.mime_type})]"

    def to_dict(self) -> Dict[str, Any]:
        """Convert content to dictionary representation."""
        result = super().to_dict()
        result["filename"] = self.filename
        result["mime_type"] = self.mime_type
        result["data"] = base64.b64encode(self.data).decode("utf-8")
        result["encoding"] = "base64"
        return result


# -----------------------------------------------------------------------------
# Message Implementation
# -----------------------------------------------------------------------------


class EnhancedMessage(Message):
    """Enhanced message implementation with additional capabilities.

    This class implements all methods and properties defined in EnhancedMessageProtocol
    without directly inheriting from it to avoid metaclass conflicts.
    """

    def __init__(
        self,
        role: RoleType,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCallProtocol]] = None,
        name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        base64_image: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        version: int = 1,
        content_objects: Optional[List[ContentProtocol]] = None,
    ):
        # Initialize base Message class
        super().__init__(
            role=role,
            content=content,
            tool_calls=tool_calls,
            name=name,
            tool_call_id=tool_call_id,
            base64_image=base64_image,
            timestamp=timestamp or datetime.now(),
            metadata=metadata or {},
        )

        # Additional EnhancedMessage attributes
        self.id = id or str(uuid.uuid4())
        self.created_at = self.timestamp or datetime.now()
        self.updated_at: Optional[datetime] = None
        self.version = version
        self.content_objects: List[ContentProtocol] = (
            [] if content_objects is None else content_objects
        )

        # Initialize content objects from base attributes if not provided
        if not content_objects:
            self._initialize_content_objects()

    def _initialize_content_objects(self) -> None:
        """Initialize content objects from base attributes."""
        # Add text content if available
        if self.content is not None:
            self.add_content(cast(ContentProtocol, TextContentImpl(self.content)))

        # Add image content if available
        if self.base64_image is not None:
            self.add_content(cast(ContentProtocol, ImageContentImpl.from_base64(self.base64_image)))

        # Add tool calls if available
        if self.tool_calls is not None:
            self.add_content(cast(ContentProtocol, ToolCallContentImpl(self.tool_calls)))

    def add_content(self, content: ContentProtocol) -> None:
        """Add content to the message."""
        self.content_objects.append(content)
        self.updated_at = datetime.now()
        self.version += 1

        # Update base attributes for backward compatibility
        content_type = content.get_content_type()

        if content_type == CONTENT_TYPE_TEXT:
            text_content = cast(TextContent, content)
            self.content = text_content.to_string()

        elif content_type == CONTENT_TYPE_IMAGE:
            image_content = cast(ImageContent, content)
            if isinstance(image_content.data, str):
                self.base64_image = image_content.data
            elif isinstance(image_content.data, bytes):
                self.base64_image = base64.b64encode(image_content.data).decode("utf-8")

        elif content_type == CONTENT_TYPE_TOOL_CALL:
            tool_call_content = cast(ToolCallContent, content)
            self.tool_calls = tool_call_content.tool_calls

    def add_image(
        self,
        image_data: Union[str, bytes, Path],
        alt_text: Optional[str] = None,
        optimize: bool = True,
    ) -> None:
        """Add an image to the message using ImageHelper.

        Args:
            image_data: Image as a file path, bytes, or base64 string
            alt_text: Optional alternative text for the image
            optimize: Whether to automatically optimize the image if needed
        """
        # Import here to avoid circular imports
        from enterprise_ai.message.image_helper import process_image_for_message

        # Process the image using ImageHelper
        image_content = process_image_for_message(image=image_data, alt_text=alt_text)

        # Add the processed image content
        self.add_content(cast(ContentProtocol, image_content))

        # Update base attributes for backward compatibility
        if isinstance(image_content, ImageContent):
            if isinstance(image_content.data, str):
                self.base64_image = image_content.data
            elif isinstance(image_content.data, bytes):
                self.base64_image = base64.b64encode(image_content.data).decode("utf-8")

    def get_content_by_type(self, content_type: ContentTypeValue) -> List[ContentProtocol]:
        """Get content by type."""
        return [c for c in self.content_objects if c.get_content_type() == content_type]

    def has_content_type(self, content_type: ContentTypeValue) -> bool:
        """Check if message has content of specified type."""
        return any(c.get_content_type() == content_type for c in self.content_objects)

    def transform(self, format: MessageFormatValue) -> Dict[str, Any]:
        """Transform message to specified format."""
        # Standard format is the same as to_dict
        if format == MESSAGE_FORMAT_DEFAULT:
            return self.to_dict()

        # For other formats, delegate to specialized transformers
        transformer = MessageTransformerRegistry.get_transformer(format)
        if transformer:
            return transformer.transform(self, format)

        # Fallback to default format
        logger.warning(f"No transformer found for format {format}, using default")
        return self.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format with enhanced attributes."""
        # Start with base message serialization
        result = super().to_dict()

        # Add enhanced attributes
        result["id"] = self.id
        result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
        result["version"] = self.version

        # Add content objects
        if self.content_objects:
            result["content_objects"] = [c.to_dict() for c in self.content_objects]

        return result

    @classmethod
    def from_message(cls, message: MessageProtocol) -> "EnhancedMessage":
        """Create an EnhancedMessage from a standard Message."""
        if isinstance(message, EnhancedMessage):
            return copy.deepcopy(message)

        # Extract attributes from the message
        return cls(
            role=message.role,
            content=message.content,
            tool_calls=message.tool_calls,
            name=message.name,
            tool_call_id=message.tool_call_id,
            base64_image=message.base64_image,
            timestamp=message.timestamp,
            metadata=message.metadata if message.metadata else {},
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancedMessage":
        """Create an EnhancedMessage from a dictionary."""
        # Extract basic message attributes
        role = cast(RoleType, data.get("role"))
        content = data.get("content")
        tool_calls = data.get("tool_calls")
        name = data.get("name")
        tool_call_id = data.get("tool_call_id")
        base64_image = data.get("base64_image")

        # Convert timestamps if provided
        timestamp = None
        if "timestamp" in data:
            timestamp_str = data["timestamp"]
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str)

        # Extract enhanced attributes
        id = data.get("id")
        version = data.get("version", 1)
        metadata = data.get("metadata", {})

        # Create content objects if provided
        content_objects: List[ContentProtocol] = []
        if "content_objects" in data:
            for content_data in data["content_objects"]:
                content_type = content_data.get("content_type")
                if content_type == CONTENT_TYPE_TEXT:
                    content_objects.append(
                        cast(ContentProtocol, TextContentImpl(content_data["text"]))
                    )
                elif content_type == CONTENT_TYPE_IMAGE:
                    format = content_data.get("format", IMAGE_FORMAT_BASE64)
                    alt_text = content_data.get("alt_text")
                    image_data = content_data["data"]
                    content_objects.append(
                        cast(ContentProtocol, ImageContentImpl(image_data, format, alt_text))
                    )
                elif content_type == CONTENT_TYPE_CODE:
                    content_objects.append(
                        cast(
                            ContentProtocol,
                            CodeContentImpl(content_data["code"], content_data["language"]),
                        )
                    )
                elif content_type == CONTENT_TYPE_MARKDOWN:
                    content_objects.append(
                        cast(ContentProtocol, MarkdownContentImpl(content_data["markdown"]))
                    )
                # Additional content types can be handled here

        # Create and return the enhanced message
        return cls(
            role=role,
            content=content,
            tool_calls=tool_calls,
            name=name,
            tool_call_id=tool_call_id,
            base64_image=base64_image,
            timestamp=timestamp,
            metadata=metadata,
            id=id,
            version=version,
            content_objects=content_objects,
        )


# -----------------------------------------------------------------------------
# Message Factory
# -----------------------------------------------------------------------------


class MessageFactory:
    """Factory for creating enhanced messages."""

    @classmethod
    def user_message(
        cls, content: str, base64_image: Optional[str] = None, **kwargs: Any
    ) -> EnhancedMessage:
        """Create a user message with enhanced capabilities."""
        message = EnhancedMessage(
            role=cast(RoleType, Role.USER),
            content=content,
            base64_image=base64_image,
            **kwargs,
        )

        return message

    @classmethod
    def system_message(cls, content: str, **kwargs: Any) -> EnhancedMessage:
        """Create a system message with enhanced capabilities."""
        return EnhancedMessage(
            role=cast(RoleType, Role.SYSTEM),
            content=content,
            **kwargs,
        )

    @classmethod
    def assistant_message(
        cls,
        content: Optional[str] = None,
        tool_calls: Optional[List[ToolCallProtocol]] = None,
        base64_image: Optional[str] = None,
        **kwargs: Any,
    ) -> EnhancedMessage:
        """Create an assistant message with enhanced capabilities."""
        return EnhancedMessage(
            role=cast(RoleType, Role.ASSISTANT),
            content=content,
            tool_calls=tool_calls,
            base64_image=base64_image,
            **kwargs,
        )

    @classmethod
    def tool_message(
        cls,
        content: str,
        name: str,
        tool_call_id: str,
        base64_image: Optional[str] = None,
        **kwargs: Any,
    ) -> EnhancedMessage:
        """Create a tool message with enhanced capabilities."""
        return EnhancedMessage(
            role=cast(RoleType, Role.TOOL),
            content=content,
            name=name,
            tool_call_id=tool_call_id,
            base64_image=base64_image,
            **kwargs,
        )

    @classmethod
    def agent_message(
        cls,
        content: str,
        name: str,
        base64_image: Optional[str] = None,
        **kwargs: Any,
    ) -> EnhancedMessage:
        """Create an agent message with enhanced capabilities."""
        return EnhancedMessage(
            role=cast(RoleType, Role.AGENT),
            content=content,
            name=name,
            base64_image=base64_image,
            **kwargs,
        )

    @classmethod
    def with_processed_image(
        cls,
        role: RoleType,
        text_content: str,
        image_data: Union[str, bytes, Path],
        alt_text: Optional[str] = None,
        **kwargs: Any,
    ) -> EnhancedMessage:
        """Create a message with optimized image content."""
        # Create basic message
        message = (
            cls.user_message(text_content, **kwargs)
            if role == Role.USER
            else cls.assistant_message(text_content, **kwargs)
        )

        # Use ImageHelper to process and add the image
        message.add_image(image_data, alt_text)

        return message

    @classmethod
    def with_code(
        cls,
        role: RoleType,
        text_content: str,
        code: str,
        language: str,
        **kwargs: Any,
    ) -> EnhancedMessage:
        """Create a message with both text and code content."""
        # Create basic message with the given role
        if role == Role.USER:
            message = cls.user_message(text_content, **kwargs)
        elif role == Role.ASSISTANT:
            message = cls.assistant_message(text_content, **kwargs)
        elif role == Role.SYSTEM:
            message = cls.system_message(text_content, **kwargs)
        elif role == Role.TOOL:
            if "name" not in kwargs or "tool_call_id" not in kwargs:
                raise ConfigValueError(
                    "name and tool_call_id",
                    None,
                    "Tool messages require name and tool_call_id parameters",
                )
            message = cls.tool_message(
                text_content, kwargs.pop("name"), kwargs.pop("tool_call_id"), **kwargs
            )
        elif role == Role.AGENT:
            if "name" not in kwargs:
                raise ConfigValueError("name", None, "Agent messages require name parameter")
            message = cls.agent_message(text_content, kwargs.pop("name"), **kwargs)
        else:
            raise ConfigValueError("role", role, f"Invalid role: {role}")

        # Add code content
        message.add_content(cast(ContentProtocol, CodeContentImpl(code, language)))

        return message

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EnhancedMessage:
        """Create a message from a dictionary."""
        return EnhancedMessage.from_dict(data)


# -----------------------------------------------------------------------------
# Message Validation
# -----------------------------------------------------------------------------


class MessageValidator(MessageValidatorProtocol):
    """Implementation of message validation."""

    def validate(self, message: MessageProtocol) -> Tuple[bool, Optional[str]]:
        """Validate a message."""
        # Check required fields
        if not message.role:
            return False, "Message role is required"

        # Validate role-specific requirements
        if message.role == Role.TOOL:
            if not message.name:
                return False, "Tool message requires a name"
            if not message.tool_call_id:
                return False, "Tool message requires a tool_call_id"

        if message.role == Role.AGENT and not message.name:
            return False, "Agent message requires a name"

        # Validate content
        if isinstance(message, EnhancedMessage) and message.content_objects:
            for content_obj in message.content_objects:
                valid, error = self.validate_content(content_obj)
                if not valid:
                    return False, f"Invalid content: {error}"
        elif not message.content and not message.tool_calls and not message.base64_image:
            return False, "Message must have content, tool_calls, or base64_image"

        return True, None

    def validate_content(self, content: ContentProtocol) -> Tuple[bool, Optional[str]]:
        """Validate message content."""
        content_type = content.get_content_type()

        if content_type == CONTENT_TYPE_TEXT:
            text_content = cast(TextContent, content)
            if not text_content.text:
                return False, "Text content cannot be empty"

        elif content_type == CONTENT_TYPE_IMAGE:
            image_content = cast(ImageContent, content)
            if not image_content.data:
                return False, "Image data cannot be empty"

        elif content_type == CONTENT_TYPE_CODE:
            code_content = cast(CodeContent, content)
            if not code_content.code:
                return False, "Code content cannot be empty"
            if not code_content.language:
                return False, "Code language must be specified"

        elif content_type == CONTENT_TYPE_TOOL_CALL:
            tool_call_content = cast(ToolCallContent, content)
            if not tool_call_content.tool_calls or len(tool_call_content.tool_calls) == 0:
                return False, "Tool call content must have at least one tool call"

        elif content_type == CONTENT_TYPE_TOOL_RESULT:
            tool_result_content = cast(ToolResultContent, content)
            if not tool_result_content.tool_call_id:
                return False, "Tool result must have a tool_call_id"

        elif content_type == CONTENT_TYPE_FILE:
            file_content = cast(FileContent, content)
            if not file_content.data:
                return False, "File data cannot be empty"
            if not file_content.filename:
                return False, "File must have a filename"
            if not file_content.mime_type:
                return False, "File must have a mime_type"

        return True, None


# -----------------------------------------------------------------------------
# Message Transformation
# -----------------------------------------------------------------------------


class BaseMessageTransformer:
    """Base class for message transformers."""

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to the target format."""
        # Default implementation returns standard dictionary format
        if isinstance(message, dict):
            return message  # type: ignore
        return message.to_dict()

    def transform_batch(
        self, messages: List[MessageProtocol], target_format: MessageFormatValue
    ) -> List[Dict[str, Any]]:
        """Transform a batch of messages to the target format."""
        return [self.transform(m, target_format) for m in messages]

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format."""
        return format == MESSAGE_FORMAT_DEFAULT


class OpenAIMessageTransformer(BaseMessageTransformer):
    """Transformer for OpenAI API format."""

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format."""
        return format == MESSAGE_FORMAT_OPENAI

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to OpenAI API format."""
        result: Dict[str, Any] = {"role": message.role}

        # Handle content
        if message.content is not None:
            result["content"] = message.content

        # Handle name for function messages
        if message.name is not None:
            result["name"] = message.name

        # Handle tool calls
        if message.tool_calls is not None:
            result["tool_calls"] = [tc.to_dict() for tc in message.tool_calls]

        # Handle function results (tool messages in OpenAI format)
        if message.role == Role.TOOL:
            result["role"] = "function"  # OpenAI uses "function" instead of "tool"
            if message.tool_call_id:
                result["function_call_id"] = message.tool_call_id

        # Handle images - OpenAI uses a specific content format for images
        if message.base64_image is not None:
            if "content" not in result or not result["content"]:
                result["content"] = []
            elif isinstance(result["content"], str):
                # Convert string content to array format
                result["content"] = [{"type": "text", "text": result["content"]}]

            # Add image content
            result["content"].append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{message.base64_image}",
                        "detail": "auto",
                    },
                }
            )

        return result


class AnthropicMessageTransformer(BaseMessageTransformer):
    """Transformer for Anthropic API format."""

    def supports_format(self, format: MessageFormatValue) -> bool:
        """Check if the transformer supports the specified format."""
        return format == MESSAGE_FORMAT_ANTHROPIC

    def transform(
        self, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to Anthropic API format."""
        result: Dict[str, Any] = {"role": message.role}

        # Anthropic uses "assistant" instead of "system"
        if message.role == "system":
            result["role"] = "assistant"

        # Handle content
        if message.content is not None:
            result["content"] = message.content

        # Handle images - Anthropic uses a specific content format for images
        if message.base64_image is not None:
            # Convert to Anthropic's content format
            if "content" not in result:
                result["content"] = []
            elif isinstance(result["content"], str):
                # Convert string content to array format
                result["content"] = [{"type": "text", "text": result["content"]}]

            # Add image content
            result["content"].append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": message.base64_image,
                    },
                }
            )

        # Handle tool calls (Anthropic has tool_use)
        if message.tool_calls is not None:
            if "content" not in result:
                result["content"] = []
            elif isinstance(result["content"], str):
                result["content"] = [{"type": "text", "text": result["content"]}]

            for tool_call in message.tool_calls:
                result["content"].append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "input": json.loads(tool_call.function.arguments),
                    }
                )

        # Handle tool results (Anthropic has tool_result)
        if message.role == Role.TOOL:
            if "content" not in result:
                result["content"] = []
            elif isinstance(result["content"], str):
                result["content"] = [{"type": "text", "text": result["content"]}]

            result["content"].append(
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content,
                }
            )

        return result


class MessageTransformerRegistry:
    """Registry for message transformers."""

    _transformers: Dict[MessageFormatValue, BaseMessageTransformer] = {
        cast(MessageFormatValue, MESSAGE_FORMAT_DEFAULT): BaseMessageTransformer(),
        cast(MessageFormatValue, MESSAGE_FORMAT_OPENAI): OpenAIMessageTransformer(),
        cast(MessageFormatValue, MESSAGE_FORMAT_ANTHROPIC): AnthropicMessageTransformer(),
    }

    @classmethod
    def register_transformer(
        cls, format: MessageFormatValue, transformer: BaseMessageTransformer
    ) -> None:
        """Register a transformer for a specific format."""
        cls._transformers[format] = transformer

    @classmethod
    def get_transformer(cls, format: MessageFormatValue) -> Optional[BaseMessageTransformer]:
        """Get a transformer for a specific format."""
        return cls._transformers.get(format)

    @classmethod
    def transform(
        cls, message: MessageProtocol, target_format: MessageFormatValue
    ) -> Dict[str, Any]:
        """Transform a message to the target format."""
        transformer = cls.get_transformer(target_format)
        if transformer:
            return transformer.transform(message, target_format)

        # Fallback to default format
        logger.warning(f"No transformer found for format {target_format}, using default")
        return message.to_dict()
