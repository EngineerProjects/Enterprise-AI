"""
Exception classes for the Enterprise AI message system.

This module provides specialized exceptions for message-related errors, including
content validation, formatting, and processing issues. These exceptions inherit
from the core enterprise_ai.exceptions classes to maintain compatibility with
existing error handling while providing more specific error information.
"""

from typing import Any, Dict, List, Optional, Union

from enterprise_ai.exceptions import EnterpriseAIError


class MessageError(EnterpriseAIError):
    """Base class for message-related errors.

    This serves as the parent class for all message-specific exceptions.
    """

    def __init__(self, message: str = "Error in message operation") -> None:
        super().__init__(message)


class MessageValidationError(MessageError):
    """Exception raised when message validation fails.

    This occurs when a message fails to meet structural or content requirements.
    """

    def __init__(
        self,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        message: Optional[str] = None,
    ) -> None:
        self.field = field
        self.value = value
        field_info = f" for field '{field}'" if field else ""
        msg = message or f"Message validation failed{field_info}"
        super().__init__(msg)


class MessageFormatError(MessageError):
    """Exception raised when message format conversion fails.

    This happens when a message cannot be properly formatted for a specific provider.
    """

    def __init__(
        self,
        format_name: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.format_name = format_name
        format_info = f" for format '{format_name}'" if format_name else ""
        msg = message or f"Message format conversion failed{format_info}"
        super().__init__(msg)


class MessageContentError(MessageError):
    """Base class for message content-related errors.

    This is used for errors related to specific content types within messages.
    """

    def __init__(
        self,
        content_type: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.content_type = content_type
        type_info = f" for content type '{content_type}'" if content_type else ""
        msg = message or f"Message content error{type_info}"
        super().__init__(msg)


# --- Image-Specific Exceptions ---


class MessageImageError(MessageContentError):
    """Base class for image-related errors in messages.

    Parent class for all errors related to image content in messages.
    """

    def __init__(
        self,
        message: str = "Error processing image content",
        source: Optional[str] = None,
    ) -> None:
        self.source = source
        source_info = f" for {source}" if source else ""
        msg = f"{message}{source_info}"
        super().__init__("image", msg)


class InvalidImageError(MessageImageError):
    """Exception raised when an invalid image is provided.

    This occurs when an image cannot be properly parsed or is corrupted.
    """

    def __init__(
        self,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        self.reason = reason
        reason_info = f": {reason}" if reason else ""
        super().__init__(f"Invalid image{reason_info}", source)


class ImageSizeError(MessageImageError):
    """Exception raised when an image exceeds size limits.

    This happens when an image is too large for use in messages.
    """

    def __init__(
        self,
        size: Optional[int] = None,
        max_size: Optional[int] = None,
        source: Optional[str] = None,
    ) -> None:
        self.size = size
        self.max_size = max_size

        if size is not None and max_size is not None:
            msg = f"Image too large: {size} bytes (max {max_size} bytes)"
        else:
            msg = "Image exceeds maximum size limit"

        super().__init__(msg, source)


class ImageFormatError(MessageImageError):
    """Exception raised when an image has an unsupported format.

    This occurs when the image format is not supported by the system.
    """

    def __init__(
        self,
        format: Optional[str] = None,
        allowed_formats: Optional[List[str]] = None,
        source: Optional[str] = None,
    ) -> None:
        self.format = format
        self.allowed_formats = allowed_formats

        if format and allowed_formats:
            msg = (
                f"Unsupported image format: {format}. Allowed formats: {', '.join(allowed_formats)}"
            )
        elif format:
            msg = f"Unsupported image format: {format}"
        else:
            msg = "Unsupported image format"

        super().__init__(msg, source)


class ImageProcessingError(MessageImageError):
    """Exception raised when image processing fails.

    This happens during image encoding, decoding, resizing, or compression.
    """

    def __init__(
        self,
        operation: Optional[str] = None,
        error: Optional[Exception] = None,
        source: Optional[str] = None,
    ) -> None:
        self.operation = operation
        self.error = error

        operation_info = f" during {operation}" if operation else ""
        error_info = f": {error}" if error else ""
        msg = f"Image processing failed{operation_info}{error_info}"

        super().__init__(msg, source)


# --- Content Collection Exceptions ---


class ContentCollectionError(MessageError):
    """Exception raised when operating on collections of content.

    This is used for errors related to managing multiple content objects.
    """

    def __init__(
        self,
        operation: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        self.operation = operation
        operation_info = f" during {operation}" if operation else ""
        msg = message or f"Content collection error{operation_info}"
        super().__init__(msg)
