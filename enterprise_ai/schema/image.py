"""
Image handling utilities for messages.

This module provides functionality for working with images in messages.
"""

import base64
import os
from pathlib import Path
from typing import Optional, Union

from enterprise_ai.logger import get_logger
from enterprise_ai.schema import Message

logger = get_logger("schema.image")


def is_base64(s: str) -> bool:
    """
    Check if a string is valid base64.

    Args:
        s: String to check

    Returns:
        True if the string is valid base64, False otherwise
    """
    try:
        if not s or not isinstance(s, str):
            return False

        # Remove base64 data URL prefix if present
        if s.startswith("data:"):
            s = s.split(",", 1)[1]

        # Check if the string can be decoded as base64
        base64.b64decode(s)
        return True
    except Exception:
        return False


def encode_image_to_base64(image_path: Union[str, Path]) -> str:
    """
    Encode an image file to base64.

    Args:
        image_path: Path to the image file

    Returns:
        Base64-encoded image string

    Raises:
        FileNotFoundError: If the image file doesn't exist
        IOError: If the image file can't be read
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"Failed to encode image {path}: {e}")
        raise


def add_image_to_message(message: "Message", image_path: Union[str, Path]) -> "Message":
    """
    Add an image to a message by adding base64 data to metadata.

    This is a simple approach; a more sophisticated solution would be implemented
    as the project evolves.

    Args:
        message: Message to add the image to
        image_path: Path to the image file

    Returns:
        Message with image data in metadata
    """
    # Import here to avoid circular imports
    from enterprise_ai.schema.message import Message

    if not isinstance(message, Message):
        raise TypeError("message must be an instance of Message")

    base64_image = encode_image_to_base64(image_path)

    # Add image data to metadata
    if "images" not in message.metadata:
        message.metadata["images"] = []

    message.metadata["images"].append(base64_image)

    return message
