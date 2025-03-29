import os
import sys
from pathlib import Path

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

# Path to your test image
image_path = "/home/amiche/Pictures/llm_test.jpg"

def test_basic_image_functions():
    """Test basic image processing functions directly."""
    print("=== Testing basic image processing functions ===\n")
    
    # 1. Read the image file
    print("1. Reading image file")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
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