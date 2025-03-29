"""
Tests for the image processing functionality in Enterprise AI.

This file tests the core image processing functions while avoiding metaclass conflicts
in the dependency chain by using strategic imports and mocking.
"""

import sys
import os
from pathlib import Path
import pytest
import base64
import io
from unittest.mock import MagicMock, patch

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# We'll patch these modules to avoid import errors
sys.modules["enterprise_ai.message.base"] = MagicMock()
sys.modules["enterprise_ai.logger"] = MagicMock()
sys.modules["enterprise_ai.logger.get_logger"] = MagicMock()

# Now we can import the constants
from enterprise_ai.message.constants import (  # noqa: E402
    IMAGE_FORMAT_PNG,
    IMAGE_FORMAT_JPEG,
    IMAGE_FORMAT_SVG,
    IMAGE_FORMAT_BASE64,
    CONTENT_TYPE_IMAGE,
)

# For the ImageResizeMode enum
from enterprise_ai.message.image import ImageResizeMode  # noqa: E402

# Check for PIL (Pillow) availability
try:
    from PIL import Image as PILImage

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("WARNING: PIL (Pillow) is not installed. Many tests will be skipped.")
    print("To install PIL, run: pip install Pillow")


# Create test fixtures
@pytest.fixture
def sample_png_bytes():
    """Create a small PNG image for testing."""
    if not HAS_PIL:
        pytest.skip("PIL (Pillow) is required for this test")

    img = PILImage.new("RGB", (10, 10), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_jpeg_bytes():
    """Create a small JPEG image for testing."""
    if not HAS_PIL:
        pytest.skip("PIL (Pillow) is required for this test")

    img = PILImage.new("RGB", (10, 10), color="green")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_svg_bytes():
    """Create a small SVG image for testing."""
    return b"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">
  <rect width="10" height="10" fill="blue" />
</svg>"""


@pytest.fixture
def sample_png_file(tmp_path, sample_png_bytes):
    """Create a temporary PNG file for testing."""
    file_path = tmp_path / "test_image.png"
    with open(file_path, "wb") as f:
        f.write(sample_png_bytes)
    return file_path


@pytest.fixture
def sample_base64_png(sample_png_bytes):
    """Create a base64-encoded PNG for testing."""
    return base64.b64encode(sample_png_bytes).decode("utf-8")


# Import individual functions for testing
# This avoids importing the entire module with dependencies
from enterprise_ai.message.image import (  # noqa: E402
    is_base64,
    encode_image_to_base64,
    decode_base64_to_image,
    detect_image_format,
    validate_image,
)

# --- Tests for is_base64 ---


def test_is_base64_with_valid_string(sample_base64_png):
    """Test is_base64 with a valid base64 string."""
    assert is_base64(sample_base64_png) is True


def test_is_base64_with_data_url():
    """Test is_base64 with a data URL."""
    data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    assert is_base64(data_url) is True


def test_is_base64_with_invalid_string():
    """Test is_base64 with an invalid string."""
    assert is_base64("not base64!") is False


def test_is_base64_with_empty_string():
    """Test is_base64 with an empty string."""
    assert is_base64("") is False


# --- Tests for encode_image_to_base64 ---


def test_encode_image_to_base64_from_bytes(sample_png_bytes):
    """Test encoding image bytes to base64."""
    base64_str = encode_image_to_base64(sample_png_bytes)
    assert is_base64(base64_str)


def test_encode_image_to_base64_from_file(sample_png_file):
    """Test encoding an image file to base64."""
    base64_str = encode_image_to_base64(sample_png_file)
    assert is_base64(base64_str)


def test_encode_image_to_base64_from_base64(sample_base64_png):
    """Test encoding an already base64-encoded image."""
    # This should just return the original string
    base64_str = encode_image_to_base64(sample_base64_png)
    assert base64_str == sample_base64_png


@pytest.mark.skipif(not HAS_PIL, reason="PIL (Pillow) is required for this test")
def test_encode_image_to_base64_with_format_conversion(sample_png_bytes):
    """Test encoding with format conversion."""
    base64_str = encode_image_to_base64(sample_png_bytes, output_format="jpeg")
    assert is_base64(base64_str)
    # Decode and verify it's a JPEG
    decoded = base64.b64decode(base64_str)
    img = PILImage.open(io.BytesIO(decoded))
    assert img.format == "JPEG"


# --- Tests for decode_base64_to_image ---


def test_decode_base64_to_image(sample_base64_png, sample_png_bytes):
    """Test decoding base64 to image bytes."""
    decoded = decode_base64_to_image(sample_base64_png)
    assert decoded == sample_png_bytes


def test_decode_base64_to_image_with_data_url(sample_png_bytes):
    """Test decoding a data URL to image bytes."""
    data_url = f"data:image/png;base64,{base64.b64encode(sample_png_bytes).decode('utf-8')}"
    decoded = decode_base64_to_image(data_url)
    assert decoded == sample_png_bytes


def test_decode_base64_to_image_with_output_path(sample_base64_png, tmp_path):
    """Test decoding base64 to a file."""
    output_path = tmp_path / "decoded_image.png"
    decode_base64_to_image(sample_base64_png, output_path)
    assert output_path.exists()
    with open(output_path, "rb") as f:
        file_content = f.read()
    assert file_content == base64.b64decode(sample_base64_png)


# --- Tests for detect_image_format ---


def test_detect_image_format_png(sample_png_bytes):
    """Test detecting PNG format."""
    format = detect_image_format(sample_png_bytes)
    assert format == IMAGE_FORMAT_PNG


def test_detect_image_format_jpeg(sample_jpeg_bytes):
    """Test detecting JPEG format."""
    format = detect_image_format(sample_jpeg_bytes)
    assert format == IMAGE_FORMAT_JPEG


def test_detect_image_format_svg(sample_svg_bytes):
    """Test detecting SVG format."""
    format = detect_image_format(sample_svg_bytes)
    assert format == IMAGE_FORMAT_SVG


def test_detect_image_format_from_base64(sample_base64_png):
    """Test detecting format from base64 string."""
    format = detect_image_format(sample_base64_png)
    assert format == IMAGE_FORMAT_PNG


def test_detect_image_format_from_data_url(sample_png_bytes):
    """Test detecting format from data URL."""
    data_url = f"data:image/png;base64,{base64.b64encode(sample_png_bytes).decode('utf-8')}"
    format = detect_image_format(data_url)
    assert format == IMAGE_FORMAT_PNG


# --- Tests for validate_image ---


def test_validate_image_valid(sample_png_bytes):
    """Test validating a valid image."""
    is_valid, error = validate_image(sample_png_bytes)
    assert is_valid is True
    assert error is None


def test_validate_image_too_large(sample_png_bytes):
    """Test validating an image that's too large."""
    is_valid, error = validate_image(sample_png_bytes, max_size_bytes=1)  # Impossibly small limit
    assert is_valid is False
    assert "too large" in error


def test_validate_image_invalid_format(sample_png_bytes):
    """Test validating an image with disallowed format."""
    is_valid, error = validate_image(sample_png_bytes, allowed_formats=["jpeg"])
    assert is_valid is False
    assert "Unsupported image format" in error


def test_validate_image_invalid_data():
    """Test validating invalid image data."""
    is_valid, error = validate_image(b"not an image")
    assert is_valid is False
    assert error is not None


# --- Advanced functions that require more mocking ---
# These functions are tested conditionally to avoid dependency issues


@pytest.mark.skipif(not HAS_PIL, reason="PIL (Pillow) is required for this test")
def test_resize_image():
    """Test image resizing functionality."""
    # Import directly inside the test to avoid top-level dependency issues
    from enterprise_ai.message.image import resize_image

    # Create a test image
    img = PILImage.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    image_data = img_bytes.getvalue()

    # Test resizing
    base64_str = resize_image(image_data, width=50, height=50, mode=ImageResizeMode.FIT)

    # Verify result
    assert is_base64(base64_str)
    img_bytes = base64.b64decode(base64_str)
    img = PILImage.open(io.BytesIO(img_bytes))
    assert img.width == 50
    assert img.height == 50
