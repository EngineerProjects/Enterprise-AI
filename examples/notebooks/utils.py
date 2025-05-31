"""
Common utilities for Enterprise AI notebooks.

This module provides shared functions for:
- Terminal output formatting
- Image handling
- Model detection
- Notebook helpers
"""

import os
import sys
import io
import time
import base64
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Tuple

# Try to import PIL for image handling
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("PIL/Pillow is not installed. Image processing will not be available.")
    print("Install with: pip install pillow")

# Add project root to path
def setup_project_path():
    """Setup project path and ensure necessary directories exist."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.append(project_root)

    # Ensure notebooks directory exists
    notebooks_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(notebooks_dir, exist_ok=True)

    # Ensure notebooks/images directory exists
    images_dir = os.path.join(notebooks_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    return project_root

# Terminal color formatting
class Colors:
    BLUE = "\033[1;34m"
    GREEN = "\033[1;32m"
    RED = "\033[1;31m"
    YELLOW = "\033[1;33m"
    PURPLE = "\033[1;35m"
    CYAN = "\033[1;36m"
    RESET = "\033[0m"

# Print functions
def print_title(title, style="single"):
    """Print a formatted title with optional styling.
    
    Args:
        title: The title text to print
        style: Style to use ('single', 'double', 'hash')
    """
    print("\n")
    
    if style == "double":
        print("=" * 60)
        print("=" * 60)
        print(f"{Colors.BLUE}{title}{Colors.RESET}")
        print("=" * 60)
        print("=" * 60)
    elif style == "hash":
        print("# " + "#" * 58)
        print(f"{Colors.BLUE}# {title}{Colors.RESET}")
        print("# " + "#" * 58)
    else:  # Default "single" style
        print("=" * 60)
        print(f"{Colors.BLUE}{title}{Colors.RESET}")
        print("=" * 60)
    
    print("\n")

def print_section(title):
    """Print a section title."""
    print(f"\n{Colors.CYAN}## {title} {Colors.RESET}")
    print("-" * 60)

def print_user(msg, images=None):
    """Print user message."""
    print(f"{Colors.GREEN}User:{Colors.RESET} {msg}")
    if images and images > 0:
        print(f"{Colors.GREEN}      [+{images} image{'s' if images > 1 else ''}]{Colors.RESET}")

def print_assistant(msg, **kwargs):
    """Print assistant message with optional keyword arguments."""
    print(f"{Colors.PURPLE}Assistant:{Colors.RESET} {msg}", **kwargs)

def print_system(msg):
    """Print system message."""
    print(f"{Colors.YELLOW}System:{Colors.RESET} {msg}")

def print_info(msg):
    """Print info message."""
    print(f"{Colors.CYAN}{msg}{Colors.RESET}")

def print_success(msg):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")

def print_error(msg):
    """Print error message."""
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")

def print_warning(msg):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")

def separator():
    """Print a separator line."""
    print("\n" + "-" * 60 + "\n")

# Image utilities
def resize_image(path: Union[str, Path], target_size: Tuple[int, int] = (400, 268)) -> Optional[Image.Image]:
    """
    Resize an image to target dimensions while preserving aspect ratio.

    Args:
        path: Path to the image file
        target_size: Target (width, height) for resizing

    Returns:
        PIL Image object or None if failed
    """
    if not HAS_PIL:
        print_warning("PIL/Pillow is not installed. Cannot process images.")
        return None

    try:
        # Open the image
        img = Image.open(path)

        # Get original dimensions
        orig_width, orig_height = img.width, img.height

        # Don't resize if already smaller than target size
        if orig_width <= target_size[0] and orig_height <= target_size[1]:
            print_info(f"Image already smaller than target size: {orig_width}x{orig_height}")
            return img

        # Calculate new dimensions while preserving aspect ratio
        ratio = min(target_size[0] / orig_width, target_size[1] / orig_height)
        new_size = (int(orig_width * ratio), int(orig_height * ratio))

        # Resize using high quality resizing
        resized_img = img.resize(new_size, Image.LANCZOS)
        print_info(f"Resized image from {orig_width}x{orig_height} to {new_size[0]}x{new_size[1]}")

        return resized_img
    except Exception as e:
        print_error(f"Error resizing image: {e}")
        return None

def encode_image_to_base64(path: Union[str, Path], max_size: Optional[Tuple[int, int]] = (400, 268)) -> Optional[str]:
    """
    Encode an image file to base64, with optional resizing.

    Args:
        path: Path to the image file
        max_size: Target (width, height) to resize to (default: 400x268)

    Returns:
        Base64-encoded image string or None if failed
    """
    if not HAS_PIL:
        print_warning("PIL/Pillow is not installed. Cannot process images.")
        return None

    try:
        # Get the resized image
        img = resize_image(path, max_size) if max_size else Image.open(path)
        if not img:
            return None

        # Determine format (use original format or default to JPEG)
        img_format = getattr(img, "format", None) or "JPEG"

        # Create an in-memory file and save the image
        buffer = io.BytesIO()

        # Save with appropriate quality to reduce size for vision models
        # For JPEGs, use quality=85 for good balance of size and quality
        if img_format.upper() == "JPEG":
            img.save(buffer, format=img_format, quality=85)
        else:
            img.save(buffer, format=img_format)

        buffer.seek(0)

        # Get file size in KB
        file_size_kb = len(buffer.getvalue()) / 1024
        print_info(f"Image size: {file_size_kb:.1f}KB, format: {img_format}")

        # Encode to base64
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return encoded
    except Exception as e:
        print_error(f"Error encoding image: {e}")
        return None

def find_image_in_directory(extensions=['.png', '.jpg', '.jpeg', '.gif'],
                      specific_images=None, target_size=(400, 268)):
    """
    Look for image files in the notebooks/images directory or create a path to a specific image.

    Args:
        extensions: List of file extensions to look for
        specific_images: List of specific image filenames to look for
        target_size: Size to resize images to (width, height)

    Returns:
        Path to the first image found, or None if no images are found
    """
    # Use specified images if provided
    notebook_dir = os.path.dirname(os.path.abspath(__file__))
    notebooks_images_dir = os.path.join(notebook_dir, 'images')

    print_info(f"Looking for images in: {notebooks_images_dir}")

    # List of default images to try
    default_images = [
        'animaux.jpg',
        'indian_love.jpg',
        'familly.jpg',
        'paysage.jpg',
        'logo2.png'
    ]

    # Use specific images if provided, otherwise use defaults
    images_to_check = specific_images if specific_images else default_images

    # Check if any of the specific images exist
    for img_name in images_to_check:
        img_path = os.path.join(notebooks_images_dir, img_name)
        if os.path.exists(img_path):
            print_info(f"Found image: {img_path}")
            return img_path

    # If specific images not found, check notebooks/images directory for any images
    if os.path.exists(notebooks_images_dir):
        for ext in extensions:
            for file in os.listdir(notebooks_images_dir):
                if file.lower().endswith(ext):
                    return os.path.join(notebooks_images_dir, file)

    # Check current directory
    for ext in extensions:
        for file in os.listdir('.'):
            if file.lower().endswith(ext):
                return os.path.abspath(file)

    # Check docs/images directory as a last resort
    project_root = setup_project_path()
    docs_images_dir = os.path.join(project_root, 'docs', 'images')
    if os.path.exists(docs_images_dir):
        for ext in extensions:
            for file in os.listdir(docs_images_dir):
                if file.lower().endswith(ext):
                    return os.path.join(docs_images_dir, file)

    return None

def create_test_image(text="Test Image", size=(400, 300), color=(73, 109, 137), save_path=None):
    """
    Create a simple test image with text on it.

    Args:
        text: Text to display on the image
        size: Image dimensions (width, height)
        color: Background color (R, G, B)
        save_path: Optional path to save the image

    Returns:
        Path to the created image or None if failed
    """
    if not HAS_PIL:
        print_warning("PIL/Pillow is not installed. Cannot create test images.")
        return None

    try:
        # Create a new image with background color
        img = Image.new('RGB', size, color=color)

        # Add text
        try:
            draw = ImageDraw.Draw(img)

            # Try to get a font, fall back to default if not available
            try:
                # Try to use a TrueType font if available
                font = ImageFont.truetype("arial.ttf", 24)
            except IOError:
                # Fall back to default font
                font = ImageFont.load_default()

            # Add text in the center
            text_size = draw.textbbox((0, 0), text, font=font)
            text_width = text_size[2] - text_size[0]
            text_height = text_size[3] - text_size[1]
            text_x = (size[0] - text_width) // 2
            text_y = (size[1] - text_height) // 2

            # Draw the text
            draw.text((text_x, text_y), text, fill=(255, 255, 0), font=font)

        except Exception as e:
            print_warning(f"Could not add text to image: {e}")

        # Save the image if a path is provided
        if save_path:
            img.save(save_path)
            return save_path
        else:
            # Create a temporary path
            notebooks_dir = os.path.dirname(os.path.abspath(__file__))
            images_dir = os.path.join(notebooks_dir, 'images')
            os.makedirs(images_dir, exist_ok=True)
            temp_path = os.path.join(images_dir, "test_image.png")
            img.save(temp_path)
            return temp_path

    except Exception as e:
        print_error(f"Error creating test image: {e}")
        return None

def get_image_path():
    """Get a path to an image for testing, preferring the specified images."""
    return find_image_in_directory(
        specific_images=['animaux.jpg', 'indian_love.jpg', 'familly.jpg', 'paysage.jpg', 'logo2.png'],
        target_size=(400, 268)
    )

# Model utilities
def detect_model_capabilities(provider):
    """
    Detect and print model capabilities.

    Args:
        provider: LLM provider instance

    Returns:
        Dictionary of capabilities
    """
    print_section("Model Capabilities")

    model_info = provider.get_model_info()

    print(f"Model: {model_info.id}")
    print(f"Provider: {model_info.provider}")

    capabilities = {}

    # Check for vision capability
    has_vision = "vision" in model_info.features
    capabilities["vision"] = has_vision
    print(f"Vision support: {Colors.GREEN if has_vision else Colors.RED}{has_vision}{Colors.RESET}")

    # Check for function calling capability
    has_functions = "function_calling" in model_info.features
    capabilities["function_calling"] = has_functions
    print(f"Function calling support: {Colors.GREEN if has_functions else Colors.RED}{has_functions}{Colors.RESET}")

    # Check for streaming capability
    has_streaming = "streaming" in model_info.features
    capabilities["streaming"] = has_streaming
    print(f"Streaming support: {Colors.GREEN if has_streaming else Colors.RED}{has_streaming}{Colors.RESET}")

    # Check for code capability
    has_code = "code" in model_info.features
    capabilities["code"] = has_code
    print(f"Code support: {Colors.GREEN if has_code else Colors.RED}{has_code}{Colors.RESET}")

    return capabilities

# Timer utility
class Timer:
    """Simple timer for measuring operations."""

    def __init__(self, description="Operation"):
        self.description = description
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"{self.description} completed in {duration:.2f} seconds")

    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        return self

    def stop(self):
        """Stop the timer and print duration."""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"{self.description} completed in {duration:.2f} seconds")

    @property
    def duration(self):
        if self.start_time is None:
            return 0
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time

# Async timer utility
class AsyncTimer:
    """Async timer for measuring async operations."""

    def __init__(self, description="Async operation"):
        self.description = description
        self.start_time = None
        self.end_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, *args):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"{self.description} completed in {duration:.2f} seconds")

    def start(self):
        """Start the timer."""
        self.start_time = time.time()
        return self

    def stop(self):
        """Stop the timer and print duration."""
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        print(f"{self.description} completed in {duration:.2f} seconds")

    @property
    def duration(self):
        if self.start_time is None:
            return 0
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time

# Run async function in sync context
def run_async(coro):
    """Run an async function in a synchronous context."""
    return asyncio.run(coro)
