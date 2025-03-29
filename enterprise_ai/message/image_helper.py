"""
High-level image processing utilities for Enterprise AI messages.

This module provides simplified interfaces for working with images in messages,
with automatic detection, optimization, and formatting capabilities.
"""

import os
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from enterprise_ai.logger import get_logger
from enterprise_ai.exceptions import ConfigValueError, ImageProcessingError
from enterprise_ai.message.constants import (
    CONTENT_TYPE_IMAGE,
    IMAGE_FORMAT_PNG,
    IMAGE_FORMAT_JPEG,
    IMAGE_FORMAT_SVG,
    MAX_IMAGE_SIZE_BYTES,
    PROVIDER_IMAGE_LIMITS,
)
from enterprise_ai.message.types import ContentProtocol, ImageContent
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

# Initialize logger
logger = get_logger("message.image_helper")


class ImageHelper:
    """Helper class for simplified image handling in messages.

    This class provides high-level methods to process images for use in messages,
    automatically handling format detection, encoding, validation, and optimization.
    """

    @staticmethod
    def process_image(
        image: Union[str, bytes, Path],
        alt_text: Optional[str] = None,
        max_size: Optional[int] = None,
        provider: Optional[str] = None,
        optimize: bool = True,
    ) -> Union[ContentProtocol, Dict[str, Any]]:
        """Process any image input into a format suitable for messages.

        This method automatically:
        1. Detects the image format
        2. Validates and optimizes the image
        3. Creates an appropriate image content object
        4. Optionally formats it for a specific provider

        Args:
            image: Image data as file path, bytes, or base64 string
            alt_text: Alternative text for the image
            max_size: Maximum size in bytes (auto-compressed if larger)
            provider: Optional provider name for provider-specific formatting
            optimize: Whether to automatically compress/optimize images

        Returns:
            If provider is specified, returns provider-specific dict.
            Otherwise, returns an ImageContent object.

        Raises:
            ImageProcessingError: If image processing fails
        """
        try:
            # Set default max size if not specified
            if max_size is None:
                if provider:
                    # Use provider-specific limit if available
                    max_size = PROVIDER_IMAGE_LIMITS.get(
                        provider.lower(), PROVIDER_IMAGE_LIMITS["default"]
                    )
                else:
                    max_size = MAX_IMAGE_SIZE_BYTES

            # Create image content object
            image_content = create_image_content(
                image_data=image,
                alt_text=alt_text,
                validate=True,
                max_size_bytes=max_size,
                compress_if_needed=optimize,
            )

            # Return provider-specific format if requested
            if provider:
                return prepare_image_for_provider(
                    image_content=image_content,
                    provider=provider,
                    resize_if_needed=optimize,
                )

            # Otherwise return the content object
            return image_content

        except Exception as e:
            # Rethrow as a MessageImageError in the future when we have message-specific exceptions
            if isinstance(e, ImageProcessingError):
                logger.warning(f"Image processing error: {e}")
                raise
            logger.error(f"Unexpected error during image processing: {e}")
            raise ImageProcessingError(f"Failed to process image: {e}", "")

    @staticmethod
    def optimize_image(
        image: Union[str, bytes, Path],
        target_size: int,
        preserve_quality: bool = True,
    ) -> Union[bytes, str]:
        """Optimize an image to meet size constraints while preserving quality.

        Args:
            image: Image data as file path, bytes, or base64 string
            target_size: Target maximum size in bytes
            preserve_quality: Whether to prioritize quality over size

        Returns:
            Optimized image as bytes or base64 string (matching input type)

        Raises:
            ImageProcessingError: If optimization fails
        """
        # Track whether input was bytes or string for consistent return type
        return_bytes = isinstance(image, bytes)

        try:
            # Convert Path to string if needed
            image_data: Union[str, bytes] = str(image) if isinstance(image, Path) else image

            # Compress the image
            base64_str = compress_image(
                image_data=image_data,
                max_size_bytes=target_size,
                initial_quality=90 if preserve_quality else 70,
            )

            # Return in the same format as input
            if return_bytes:
                return base64.b64decode(base64_str)
            return base64_str

        except Exception as e:
            if isinstance(e, ImageProcessingError):
                raise
            raise ImageProcessingError(f"Failed to optimize image: {e}", "")

    @staticmethod
    def get_image_info(image: Union[str, bytes, Path]) -> Dict[str, Any]:
        """Extract information about an image.

        Args:
            image: Image data as file path, bytes, or base64 string

        Returns:
            Dictionary with image information:
            - format: Detected image format
            - size: Size in bytes
            - dimensions: (width, height) if PIL is available
            - is_valid: Whether the image is valid

        Raises:
            ImageProcessingError: If image cannot be processed
        """
        result: Dict[str, Any] = {
            "format": None,
            "size": 0,
            "dimensions": None,
            "is_valid": False,
        }

        try:
            # Convert to bytes if needed
            if isinstance(image, (str, Path)):
                if os.path.exists(str(image)):
                    # It's a file path
                    with open(image, "rb") as f:
                        image_bytes = f.read()
                elif isinstance(image, str) and is_base64(image):
                    # It's base64
                    image_bytes = decode_base64_to_image(image)
                else:
                    raise ImageProcessingError("Invalid image path or base64 string", str(image))
            else:
                image_bytes = image

            # Get basic info
            result["size"] = len(image_bytes)
            result["format"] = detect_image_format(image_bytes)

            # Validate image
            is_valid, error = validate_image(image_bytes)
            result["is_valid"] = is_valid
            if not is_valid:
                result["error"] = error

            # Get dimensions if PIL is available
            try:
                from PIL import Image as PILImage
                import io

                img = PILImage.open(io.BytesIO(image_bytes))
                result["dimensions"] = img.size  # This is a tuple (width, height)
            except ImportError:
                pass  # PIL not available

            return result

        except Exception as e:
            if isinstance(e, ImageProcessingError):
                raise
            raise ImageProcessingError(f"Failed to get image info: {e}", "")


# Convenience functions
def process_image_for_message(
    image: Union[str, bytes, Path],
    alt_text: Optional[str] = None,
    provider: Optional[str] = None,
) -> Union[ContentProtocol, Dict[str, Any]]:
    """Process an image for use in a message.

    Convenience function that delegates to ImageHelper.process_image.
    """
    return ImageHelper.process_image(image, alt_text, provider=provider)


def optimize_image_for_message(
    image: Union[str, bytes, Path],
    target_size: Optional[int] = None,
    provider: Optional[str] = None,
) -> Union[bytes, str]:
    """Optimize an image for use in a message.

    Convenience function that delegates to ImageHelper.optimize_image.
    """
    # Determine target size
    if target_size is None:
        if provider:
            target_size = PROVIDER_IMAGE_LIMITS.get(
                provider.lower(), PROVIDER_IMAGE_LIMITS["default"]
            )
        else:
            target_size = MAX_IMAGE_SIZE_BYTES

    return ImageHelper.optimize_image(image, target_size)
