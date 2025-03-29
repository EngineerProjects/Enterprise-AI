"""
Image processing utilities for Enterprise AI messages.

This module provides comprehensive image handling capabilities for messages,
including encoding/decoding, format detection, validation, and conversion.
It supports the creation and manipulation of image content objects compatible
with the Enterprise AI message system.
"""

# Standard library imports
import base64
import io
import mimetypes
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

# Third-party imports (optional)
try:
    from PIL import Image as PILImage

    HAS_PIL = True
except ImportError:
    PILImage = None  # type: ignore
    HAS_PIL = False

# Local application/library imports
from enterprise_ai.exceptions import ConfigValueError, ImageProcessingError
from enterprise_ai.logger import get_logger
from enterprise_ai.message.base import ImageContentImpl
from enterprise_ai.message.constants import (
    CONTENT_TYPE_IMAGE,
    DEFAULT_JPEG_QUALITY,
    GIF_HEADER,
    JPEG_HEADER,
    MAX_IMAGE_SIZE_BYTES,
    PNG_HEADER,
    PROVIDER_IMAGE_LIMITS,
    SVG_TAG_PATTERN,
    WEBP_HEADER,
    ContentTypeValue,
    IMAGE_FORMAT_BASE64,
    IMAGE_FORMAT_GIF,
    IMAGE_FORMAT_JPEG,
    IMAGE_FORMAT_PNG,
    IMAGE_FORMAT_SVG,
    IMAGE_FORMAT_WEBP,
    IMAGE_MIME_TYPES,
    ImageFormatValue,
)
from enterprise_ai.message.types import ContentProtocol, ImageContent

# Initialize logger
logger = get_logger("message.image")

# Define PIL-related constants
LANCZOS: Any = None
if HAS_PIL:
    # Get appropriate resampling filter based on PIL version
    if hasattr(PILImage, "Resampling"):
        # PIL 9.1.0 and newer
        LANCZOS = PILImage.Resampling.LANCZOS
    elif hasattr(PILImage, "LANCZOS"):
        # PIL 7.0.0 to 9.0.x
        LANCZOS = PILImage.LANCZOS
    else:
        # Very old versions of PIL (remove ANTIALIAS fallback)
        raise ValueError("Unsupported Pillow version detected.")


class ImageResizeMode(str, Enum):
    """Resize modes for image processing."""

    FIT = "fit"  # Preserve aspect ratio, fit within dimensions
    FILL = "fill"  # Preserve aspect ratio, fill dimensions (may crop)
    STRETCH = "stretch"  # Ignore aspect ratio, stretch to dimensions
    NONE = "none"  # Don't resize


def is_base64(s: str) -> bool:
    """Check if a string is valid base64.

    Args:
        s: String to check

    Returns:
        True if the string is valid base64, False otherwise
    """
    try:
        # Check if string is valid base64
        if not s or not isinstance(s, str):
            return False

        # Remove base64 data URL prefix if present
        if s.startswith("data:"):
            s = s.split(",", 1)[1]

        # Check if the string can be decoded as base64
        base64.b64decode(s)  # Just check if it can be decoded without errors
        return True
    except Exception:
        return False


def encode_image_to_base64(
    image_data: Union[bytes, str, Path],
    output_format: Optional[str] = None,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> str:
    """Encode image data to base64 string.

    Args:
        image_data: Image data as bytes, file path (string or Path), or base64 string
        output_format: Format to convert image to before encoding (png, jpeg, etc.)
        quality: JPEG quality level (1-100) if converting to JPEG

    Returns:
        Base64-encoded image data as string

    Raises:
        ImageProcessingError: If the image cannot be encoded
    """
    try:
        # If image_data is already a base64 string, return it as is
        if isinstance(image_data, str) and is_base64(image_data):
            # If no format conversion requested, return as is
            if not output_format:
                return image_data
            # Otherwise, need to decode first, then convert format
            image_bytes = base64.b64decode(image_data)
        # If image_data is a file path, read the file
        elif isinstance(image_data, (str, Path)):
            path = Path(image_data)
            if not path.exists():
                raise ImageProcessingError(f"Image file not found: {path}", str(path))
            with open(path, "rb") as f:
                image_bytes = f.read()
        # If image_data is bytes, use it directly
        elif isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            raise ImageProcessingError(
                f"Unsupported image data type: {type(image_data)}", str(type(image_data))
            )

        # Convert format if requested and PIL is available
        if output_format and HAS_PIL and output_format.lower() != IMAGE_FORMAT_SVG:
            try:
                img = PILImage.open(io.BytesIO(image_bytes))
                output_format = output_format.upper()
                buffer = io.BytesIO()

                # Set additional parameters for specific formats
                params = {}
                if output_format == "JPEG":
                    params["quality"] = quality
                    params["optimize"] = True
                elif output_format == "PNG":
                    params["optimize"] = True

                img.save(buffer, format=output_format, **params)
                image_bytes = buffer.getvalue()
            except Exception as e:
                raise ImageProcessingError(f"Failed to convert image format: {e}", output_format)

        # Encode to base64
        return base64.b64encode(image_bytes).decode("utf-8")

    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"Failed to encode image: {e}", str(image_data))


def decode_base64_to_image(
    base64_data: str,
    output_path: Optional[Union[str, Path]] = None,
) -> bytes:
    """Decode base64 string to image bytes.

    Args:
        base64_data: Base64-encoded image data
        output_path: Optional path to save the decoded image

    Returns:
        Decoded image bytes

    Raises:
        ImageProcessingError: If the image cannot be decoded
    """
    try:
        # Remove base64 data URL prefix if present
        if base64_data.startswith("data:"):
            base64_data = base64_data.split(",", 1)[1]

        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_data)

        # Save to file if output_path provided
        if output_path:
            path = Path(output_path)
            with open(path, "wb") as f:
                f.write(image_bytes)

        return image_bytes

    except Exception as e:
        raise ImageProcessingError(f"Failed to decode base64 image: {e}", base64_data[:20] + "...")


def detect_image_format(image_data: Union[bytes, str]) -> str:
    """Detect the format of an image.

    Args:
        image_data: Image data as bytes or base64 string

    Returns:
        Image format as string (png, jpeg, gif, webp, svg, or unknown)

    Raises:
        ImageProcessingError: If the image format cannot be detected
    """
    try:
        # Convert base64 string to bytes if needed
        if isinstance(image_data, str):
            # Check if it's a base64 data URL
            if image_data.startswith("data:"):
                # Extract MIME type from data URL
                mime_match = re.match(r"data:image/([a-z+]+);base64,", image_data)
                if mime_match:
                    mime_type = mime_match.group(1)
                    if mime_type == "jpeg" or mime_type == "jpg":
                        return IMAGE_FORMAT_JPEG
                    elif mime_type in ["png", "gif", "webp", "svg+xml"]:
                        return mime_type if mime_type != "svg+xml" else IMAGE_FORMAT_SVG

            # If it's a base64 string without a data URL or the MIME type couldn't be extracted,
            # decode it to bytes for header detection
            try:
                # Remove data URL prefix if present
                if image_data.startswith("data:"):
                    image_data = image_data.split(",", 1)[1]

                image_bytes = base64.b64decode(image_data)
            except Exception as e:
                raise ImageProcessingError(f"Invalid base64 data: {e}", image_data[:20] + "...")
        else:
            image_bytes = image_data

        # Check for SVG
        if SVG_TAG_PATTERN.search(image_bytes.decode("utf-8", errors="ignore")):
            return IMAGE_FORMAT_SVG

        # Check header bytes for common image formats
        if image_bytes.startswith(PNG_HEADER):
            return IMAGE_FORMAT_PNG
        elif image_bytes.startswith(JPEG_HEADER):
            return IMAGE_FORMAT_JPEG
        elif image_bytes.startswith(GIF_HEADER):
            return IMAGE_FORMAT_GIF
        elif re.match(WEBP_HEADER.replace(b".", b"."), image_bytes[:12]):
            return IMAGE_FORMAT_WEBP

        # Use PIL if available for more accurate detection
        if HAS_PIL:
            try:
                img = PILImage.open(io.BytesIO(image_bytes))
                fmt = img.format.lower() if img.format else "unknown"
                if fmt == "jpeg":
                    return IMAGE_FORMAT_JPEG
                elif fmt in ["png", "gif", "webp"]:
                    return fmt
            except Exception:
                pass  # Fall back to mime type detection

        # Use mimetypes as fallback
        mimetype, _ = mimetypes.guess_type("image.dat")
        if mimetype:
            if mimetype == "image/jpeg":
                return IMAGE_FORMAT_JPEG
            elif mimetype == "image/png":
                return IMAGE_FORMAT_PNG
            elif mimetype == "image/gif":
                return IMAGE_FORMAT_GIF
            elif mimetype == "image/webp":
                return IMAGE_FORMAT_WEBP
            elif mimetype == "image/svg+xml":
                return IMAGE_FORMAT_SVG

        # If all else fails, assume PNG (common default)
        logger.warning("Could not definitively detect image format, assuming PNG")
        return IMAGE_FORMAT_PNG

    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"Failed to detect image format: {e}", "")


def validate_image(
    image_data: Union[bytes, str],
    max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
    allowed_formats: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate an image for use in messages.

    Args:
        image_data: Image data as bytes or base64 string
        max_size_bytes: Maximum allowed image size in bytes
        allowed_formats: List of allowed image formats

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Convert base64 string to bytes if needed
    if isinstance(image_data, str):
        try:
            # Remove data URL prefix if present
            if image_data.startswith("data:"):
                image_data = image_data.split(",", 1)[1]

            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            return False, f"Invalid base64 data: {e}"
    else:
        image_bytes = image_data

    # Check size
    if len(image_bytes) > max_size_bytes:
        return False, f"Image too large: {len(image_bytes)} bytes (max {max_size_bytes} bytes)"

    # Check format
    try:
        image_format = detect_image_format(image_bytes)
        if allowed_formats and image_format not in allowed_formats:
            return (
                False,
                f"Unsupported image format: {image_format}. Allowed formats: {', '.join(allowed_formats)}",
            )
    except ImageProcessingError as e:
        return False, str(e)

    # Additional PIL-based validations if available
    if HAS_PIL:
        try:
            img = PILImage.open(io.BytesIO(image_bytes))
            # Check if image can be loaded
            img.load()
            # Additional checks could be added here (e.g., min/max dimensions)
        except Exception as e:
            return False, f"Invalid image data: {e}"

    return True, None


def resize_image(
    image_data: Union[bytes, str],
    width: Optional[int] = None,
    height: Optional[int] = None,
    mode: ImageResizeMode = ImageResizeMode.FIT,
    output_format: Optional[str] = None,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> str:
    """Resize an image and return it as base64.

    Args:
        image_data: Image data as bytes or base64 string
        width: Target width
        height: Target height
        mode: Resize mode
        output_format: Output format (png, jpeg, etc.)
        quality: JPEG quality level (1-100) if converting to JPEG

    Returns:
        Resized image as base64 string

    Raises:
        ImageProcessingError: If the image cannot be resized
        ConfigValueError: If PIL is not available
    """
    if not HAS_PIL:
        raise ConfigValueError(
            "resize_image", None, "PIL (Pillow) is required for image resizing but is not installed"
        )

    try:
        # Convert to bytes if necessary
        if isinstance(image_data, str):
            # Check if base64
            if is_base64(image_data):
                # Remove data URL prefix if present
                if image_data.startswith("data:"):
                    image_data = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(image_data)
            else:
                # Assume it's a file path
                path = Path(image_data)
                if not path.exists():
                    raise ImageProcessingError(f"Image file not found: {path}", str(path))
                with open(path, "rb") as f:
                    image_bytes = f.read()
        else:
            image_bytes = image_data

        # Open image with PIL
        img = PILImage.open(io.BytesIO(image_bytes))

        # Detect original format if not specified
        original_format = img.format or "PNG"
        output_format = output_format or original_format

        # Get original dimensions
        orig_width, orig_height = img.size

        # Skip resizing if both width and height are None or mode is NONE
        if (width is None and height is None) or mode == ImageResizeMode.NONE:
            buffer = io.BytesIO()

            # Set additional parameters for specific formats
            params = {}
            if output_format.upper() == "JPEG":
                params["quality"] = quality
                params["optimize"] = True
            elif output_format.upper() == "PNG":
                params["optimize"] = True

            img.save(buffer, format=output_format.upper(), **params)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Calculate new dimensions based on mode
        if mode == ImageResizeMode.FIT:
            # Calculate dimensions preserving aspect ratio (fit within target)
            if width is None and height is not None:
                width = int(orig_width * (height / orig_height))
            elif height is None and width is not None:
                height = int(orig_height * (width / orig_width))
            elif width is not None and height is not None:
                # Both dimensions provided, fit within
                ratio = min(width / orig_width, height / orig_height)
                width = int(orig_width * ratio)
                height = int(orig_height * ratio)
            else:
                # Both are None, use original dimensions
                width, height = orig_width, orig_height

        elif mode == ImageResizeMode.FILL:
            # Calculate dimensions preserving aspect ratio (fill target, may crop)
            if width is None and height is not None:
                width = int(orig_width * (height / orig_height))
            elif height is None and width is not None:
                height = int(orig_height * (width / orig_width))
            elif width is not None and height is not None:
                # Both dimensions provided, fill target
                ratio = max(width / orig_width, height / orig_height)
                width_new = int(orig_width * ratio)
                height_new = int(orig_height * ratio)

                # Resize image
                resized_img = img.resize((width_new, height_new), LANCZOS)

                # Calculate crop box
                left = (width_new - width) // 2
                top = (height_new - height) // 2
                right = left + width
                bottom = top + height

                # Crop image
                cropped_img = resized_img.crop((left, top, right, bottom))

                # Skip the rest of the resizing logic since we've already resized and cropped
                buffer = io.BytesIO()

                # Set additional parameters for specific formats
                params = {}
                if output_format.upper() == "JPEG":
                    params["quality"] = quality
                    params["optimize"] = True
                elif output_format.upper() == "PNG":
                    params["optimize"] = True

                cropped_img.save(buffer, format=output_format.upper(), **params)
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
            else:
                # Both are None, use original dimensions
                width, height = orig_width, orig_height

        elif mode == ImageResizeMode.STRETCH:
            # Use provided dimensions, stretching if necessary
            width = width or orig_width
            height = height or orig_height

        # Resize image (except for FILL mode which already resized and returned)
        resized_img = img.resize((width, height), LANCZOS)

        # Save to buffer
        buffer = io.BytesIO()

        # Set additional parameters for specific formats
        params = {}
        if output_format.upper() == "JPEG":
            params["quality"] = quality
            params["optimize"] = True
        elif output_format.upper() == "PNG":
            params["optimize"] = True

        resized_img.save(buffer, format=output_format.upper(), **params)

        # Encode to base64
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    except Exception as e:
        if isinstance(e, (ImageProcessingError, ConfigValueError)):
            raise
        raise ImageProcessingError(f"Failed to resize image: {e}", "")


def compress_image(
    image_data: Union[bytes, str],
    max_size_bytes: int = MAX_IMAGE_SIZE_BYTES,
    output_format: Optional[str] = None,
    initial_quality: int = DEFAULT_JPEG_QUALITY,
    max_width: Optional[int] = None,
) -> str:
    """Compress an image to fit within a maximum size.

    Args:
        image_data: Image data as bytes or base64 string
        max_size_bytes: Maximum size in bytes
        output_format: Output format (defaults to input format)
        initial_quality: Initial JPEG quality (for JPEG output)
        max_width: Maximum width to consider for resizing

    Returns:
        Compressed image as base64 string

    Raises:
        ImageProcessingError: If the image cannot be compressed
        ConfigValueError: If PIL is not available
    """
    if not HAS_PIL:
        raise ConfigValueError(
            "compress_image",
            None,
            "PIL (Pillow) is required for image compression but is not installed",
        )

    try:
        # Convert to bytes if necessary
        if isinstance(image_data, str):
            # Check if base64
            if is_base64(image_data):
                # Remove data URL prefix if present
                if image_data.startswith("data:"):
                    image_data = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(image_data)
            else:
                # Assume it's a file path
                path = Path(image_data)
                if not path.exists():
                    raise ImageProcessingError(f"Image file not found: {path}", str(path))
                with open(path, "rb") as f:
                    image_bytes = f.read()
        else:
            image_bytes = image_data

        # Check if already small enough
        if len(image_bytes) <= max_size_bytes:
            # If already small enough, just return encoded
            return base64.b64encode(image_bytes).decode("utf-8")

        # Open image with PIL
        img = PILImage.open(io.BytesIO(image_bytes))

        # Get original format and dimensions
        original_format = img.format or "PNG"
        original_width, original_height = img.size

        # Determine output format (use JPEG for compression unless SVG or specified)
        if not output_format:
            # Use original format if it's a format that can be compressed well
            if original_format.upper() in ["JPEG", "PNG", "WEBP"]:
                output_format = original_format
            else:
                # Default to JPEG for best compression
                output_format = "JPEG"

        # Strategy 1: Try compression with original dimensions
        if output_format.upper() == "JPEG":
            # Try progressively lower quality settings
            for quality in [initial_quality, 70, 50, 30]:
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality, optimize=True)
                if buffer.tell() <= max_size_bytes:
                    return base64.b64encode(buffer.getvalue()).decode("utf-8")
        else:
            # For PNG or other formats, just try optimized save
            buffer = io.BytesIO()
            img.save(buffer, format=output_format.upper(), optimize=True)
            if buffer.tell() <= max_size_bytes:
                return base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Strategy 2: Resize and compress
        # Calculate max width to maintain aspect ratio
        if not max_width:
            max_width = original_width

        # Try progressively smaller dimensions
        scale_factors = [0.8, 0.6, 0.5, 0.4, 0.3]

        for scale in scale_factors:
            new_width = int(min(original_width * scale, max_width))
            new_height = int(original_height * (new_width / original_width))

            resized_img = img.resize((new_width, new_height), LANCZOS)

            # Try different quality settings for JPEG
            if output_format.upper() == "JPEG":
                for quality in [initial_quality, 70, 50, 30]:
                    buffer = io.BytesIO()
                    resized_img.save(buffer, format="JPEG", quality=quality, optimize=True)
                    if buffer.tell() <= max_size_bytes:
                        return base64.b64encode(buffer.getvalue()).decode("utf-8")
            else:
                # For PNG or other formats
                buffer = io.BytesIO()
                resized_img.save(buffer, format=output_format.upper(), optimize=True)
                if buffer.tell() <= max_size_bytes:
                    return base64.b64encode(buffer.getvalue()).decode("utf-8")

        # If we get here, we couldn't compress enough - use the smallest version
        buffer = io.BytesIO()
        # Use smallest dimensions and lowest quality
        smallest_width = int(original_width * scale_factors[-1])
        smallest_height = int(original_height * (smallest_width / original_width))
        smallest_img = img.resize((smallest_width, smallest_height), LANCZOS)

        if output_format.upper() == "JPEG":
            smallest_img.save(buffer, format="JPEG", quality=30, optimize=True)
        else:
            smallest_img.save(buffer, format=output_format.upper(), optimize=True)

        logger.warning(
            f"Image could not be compressed below target size. Original: {len(image_bytes)} bytes, "
            f"Compressed: {buffer.tell()} bytes (target: {max_size_bytes} bytes)"
        )

        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    except Exception as e:
        if isinstance(e, (ImageProcessingError, ConfigValueError)):
            raise
        raise ImageProcessingError(f"Failed to compress image: {e}", "")


def create_image_content(
    image_data: Union[bytes, str, Path],
    format: Optional[str] = None,
    alt_text: Optional[str] = None,
    validate: bool = True,
    max_size_bytes: Optional[int] = None,
    compress_if_needed: bool = True,
) -> ContentProtocol:
    """Create an image content object for a message.

    Args:
        image_data: Image data as bytes, base64 string, or file path
        format: Image format (detected automatically if not provided)
        alt_text: Alternative text for the image
        validate: Whether to validate the image
        max_size_bytes: Maximum image size in bytes (defaults to MAX_IMAGE_SIZE_BYTES)
        compress_if_needed: Whether to compress if the image exceeds max_size_bytes

    Returns:
        An ImageContent object

    Raises:
        ImageProcessingError: If the image is invalid or cannot be processed
    """
    # Set default max size if not provided
    if max_size_bytes is None:
        max_size_bytes = MAX_IMAGE_SIZE_BYTES

    try:
        # Handle file paths
        if isinstance(image_data, (str, Path)) and not is_base64(str(image_data)):
            path = Path(image_data)
            if not path.exists():
                raise ImageProcessingError(f"Image file not found: {path}", str(path))
            with open(path, "rb") as f:
                image_bytes = f.read()
        # Handle base64 strings
        elif isinstance(image_data, str) and is_base64(image_data):
            # Extract raw base64 content if it's a data URL
            if image_data.startswith("data:"):
                # Extract format from MIME type if not provided
                if not format:
                    mime_match = re.match(r"data:image/([a-z+]+);base64,", image_data)
                    if mime_match:
                        mime_type = mime_match.group(1)
                        if mime_type == "jpeg" or mime_type == "jpg":
                            format = IMAGE_FORMAT_JPEG
                        elif mime_type in ["png", "gif", "webp", "svg+xml"]:
                            format = mime_type if mime_type != "svg+xml" else IMAGE_FORMAT_SVG

                # Extract raw base64
                image_data = image_data.split(",", 1)[1]

            image_bytes = base64.b64decode(image_data)
        # Handle bytes directly
        elif isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            raise ImageProcessingError(
                f"Unsupported image data type: {type(image_data)}", str(type(image_data))
            )

        # Detect format if not provided
        if not format:
            format = detect_image_format(image_bytes)

        # Validate the image if requested
        if validate:
            is_valid, error = validate_image(image_bytes, max_size_bytes)
            if not is_valid:
                # If compression is enabled and the image is too large, try compressing
                if compress_if_needed and error is not None and "too large" in error:
                    logger.info(f"Image is too large, attempting to compress: {error}")

                    # Determine output format for compression
                    output_format = format
                    if format not in [IMAGE_FORMAT_JPEG, IMAGE_FORMAT_PNG, IMAGE_FORMAT_WEBP]:
                        output_format = IMAGE_FORMAT_JPEG  # Use JPEG for best compression

                    # Compress the image
                    compressed_base64 = compress_image(
                        image_bytes, max_size_bytes=max_size_bytes, output_format=output_format
                    )

                    # Create image content with compressed data
                    return cast(
                        ContentProtocol,
                        ImageContentImpl(
                            data=compressed_base64,
                            format=cast(ImageFormatValue, output_format),
                            alt_text=alt_text,
                        ),
                    )
                else:
                    # If not compressing or other validation error, raise exception
                    raise ImageProcessingError(f"Invalid image: {error}", "")

        # For consistency, convert to base64 string
        base64_data = encode_image_to_base64(image_bytes)

        # Create and return image content
        return cast(
            ContentProtocol,
            ImageContentImpl(
                data=base64_data, format=cast(ImageFormatValue, format), alt_text=alt_text
            ),
        )

    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"Failed to create image content: {e}", "")


def prepare_image_for_provider(
    image_content: Union[ContentProtocol, ImageContent, str, bytes],
    provider: str,
    resize_if_needed: bool = True,
) -> Dict[str, Any]:
    """Prepare an image for a specific provider's requirements.

    Args:
        image_content: Image content object, base64 string, or raw bytes
        provider: Provider name ("openai", "anthropic", etc.)
        resize_if_needed: Whether to resize if the image exceeds provider limits

    Returns:
        Provider-specific image data as dictionary

    Raises:
        ImageProcessingError: If the image cannot be prepared
    """
    # Get provider-specific limits
    max_size = PROVIDER_IMAGE_LIMITS.get(provider.lower(), PROVIDER_IMAGE_LIMITS["default"])

    try:
        # Extract image data based on input type
        if isinstance(image_content, str):
            # Check if base64
            if is_base64(image_content):
                format = detect_image_format(base64.b64decode(image_content))
            else:
                # Assume it's a file path
                content_obj = create_image_content(
                    image_content,
                    validate=True,
                    max_size_bytes=max_size,
                    compress_if_needed=resize_if_needed,
                )
                if not isinstance(content_obj, ImageContent):
                    raise ImageProcessingError(
                        f"Expected ImageContent, got {type(content_obj)}", str(type(content_obj))
                    )
                image_content = content_obj
                # Continue to next branch to handle ImageContent

        if isinstance(image_content, bytes):
            # Create content object with validation
            content_obj = create_image_content(
                image_content,
                validate=True,
                max_size_bytes=max_size,
                compress_if_needed=resize_if_needed,
            )
            if not isinstance(content_obj, ImageContent):
                raise ImageProcessingError(
                    f"Expected ImageContent, got {type(content_obj)}", str(type(content_obj))
                )
            image_content = content_obj

        # At this point, should have ImageContent
        if (
            not hasattr(image_content, "content_type")
            or image_content.content_type != CONTENT_TYPE_IMAGE
        ):
            raise ImageProcessingError(
                f"Expected ImageContent, got {type(image_content)}", str(type(image_content))
            )

        # Cast to ImageContent
        img_content = cast(ImageContent, image_content)

        # Get base64 data and format
        if isinstance(img_content.data, bytes):
            base64_data = base64.b64encode(img_content.data).decode("utf-8")
        else:
            base64_data = img_content.data

        format = img_content.format

        # Prepare provider-specific output
        if provider.lower() == "openai":
            return {
                "type": "image_url",
                "image_url": {"url": f"data:image/{format};base64,{base64_data}", "detail": "auto"},
            }
        elif provider.lower() == "anthropic":
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": IMAGE_MIME_TYPES.get(format, f"image/{format}"),
                    "data": base64_data,
                },
            }
        else:
            # Default format (works for most providers)
            return {
                "data": base64_data,
                "format": format,
                "media_type": IMAGE_MIME_TYPES.get(format, f"image/{format}"),
            }

    except Exception as e:
        if isinstance(e, ImageProcessingError):
            raise
        raise ImageProcessingError(f"Failed to prepare image for provider {provider}: {e}", "")
