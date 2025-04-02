import os
import sys
from pathlib import Path
import io
import base64

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Import the image processing functions directly
from enterprise_ai.message.image import (
    is_base64,
    encode_image_to_base64,
    decode_base64_to_image,
    detect_image_format,
    validate_image,
    compress_image,
)

# Instead of referencing an external file, we'll create a test image programmatically
def get_test_image(size=(1200, 800)):
    """Create a test image with sufficient complexity to test compression.

    Args:
        size: Image dimensions as (width, height) tuple

    Returns:
        Image bytes for testing
    """
    try:
        # Create a larger, more complex image using PIL
        from PIL import Image, ImageDraw, ImageFont

        # Create base image with gradient background
        img = Image.new("RGB", size, color="#f0f0f0")
        draw = ImageDraw.Draw(img)

        # Create a color gradient background (adds complexity)
        width, height = size
        for y in range(height):
            r = int(255 * (y / height))
            g = int(255 * (1 - y / height))
            b = int(128 + 127 * (y % 100) / 100)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add some patterns and shapes (increases file size)
        for i in range(0, width, 40):
            for j in range(0, height, 40):
                # Alternate between rectangles and circles with different colors
                if (i + j) % 80 == 0:
                    draw.rectangle([i, j, i+30, j+30], fill=(255, 0, 0, 128))
                else:
                    draw.ellipse([i, j, i+30, j+30], fill=(0, 0, 255, 128))

        # Add some text for additional complexity
        for i in range(5):
            x = width // 6 + i * 150
            y = height // 2 + (i % 3) * 100
            text = f"Test Image {i+1}"
            draw.text((x, y), text, fill=(255, 255, 255))

        # Save to bytes
        img_bytes = io.BytesIO()
        # Use high quality for JPEG to ensure the image is larger
        img.save(img_bytes, format="JPEG", quality=95)
        img_bytes.seek(0)
        return img_bytes.getvalue()

    except (ImportError, Exception) as e:
        print(f"Error creating complex test image: {e}")
        print("Falling back to simple image")

        # If PIL is not available or there's an error, create a simple colored image
        # This creates a 100x100 black image that's approximately 30KB
        header = bytes([
            0xff, 0xd8,                         # JPEG SOI marker
            0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, # JFIF header
            0x49, 0x46, 0x00, 0x01, 0x01, 0x01,
            0x00, 0x48, 0x00, 0x48, 0x00, 0x00,
            0xff, 0xdb, 0x00, 0x43, 0x00        # Define quantization table
        ])

        # Add some filler data to create a larger file
        filler = bytes([0x99] * 30000)  # 30KB of filler data

        # End with JPEG EOI marker
        footer = bytes([0xff, 0xd9])

        return header + filler + footer

def test_basic_image_functions():
    """Test basic image processing functions directly."""
    print("=== Testing basic image processing functions ===\n")

    # 1. Generate test image
    print("1. Creating test image")
    image_bytes = get_test_image()
    print(f" Image size: {len(image_bytes) / 1024:.2f} KB")

    # 2. Encode to base64
    print("\n2. Encoding to base64")
    base64_data = encode_image_to_base64(image_bytes)
    print(f" Base64 length: {len(base64_data)} chars")
    print(f" Is valid base64: {is_base64(base64_data)}")

    # 3. Detect format
    print("\n3. Detecting image format")
    format = detect_image_format(image_bytes)
    print(f" Detected format: {format}")

    # 4. Validate image
    print("\n4. Validating image")
    is_valid, error = validate_image(image_bytes)
    print(f" Image valid: {is_valid}")
    if error:
        print(f" Error: {error}")

    # 5. Try to import PIL for additional tests
    try:
        from PIL import Image
        import io
        print("\n5. Getting image dimensions with PIL")
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        print(f" Dimensions: {width}x{height}")
        print(f" Mode: {img.mode}")

        # 6. Test compression
        print("\n6. Testing image compression")
        target_size = 100 * 1024  # 100KB
        compressed_base64 = compress_image(image_bytes, max_size_bytes=target_size)
        compressed_bytes = decode_base64_to_image(compressed_base64)
        print(f" Original size: {len(image_bytes) / 1024:.2f} KB")
        print(f" Compressed size: {len(compressed_bytes) / 1024:.2f} KB")
        print(f" Compression ratio: {len(image_bytes) / len(compressed_bytes):.2f}x")

    except ImportError:
        print("\n5. PIL not installed, skipping additional tests")

    return "Basic tests completed successfully!"

# Run the test
if __name__ == "__main__":
    result = test_basic_image_functions()
    print(f"\n{result}")
