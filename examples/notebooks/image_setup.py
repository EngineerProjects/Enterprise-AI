#!/usr/bin/env python
"""
Image Setup Script for Enterprise AI Notebooks

This script creates the necessary directory structure for the notebooks
and provides guidance on placing your image files.
"""

import os
import sys
from pathlib import Path

def print_color(text, color_code):
    """Print colored text."""
    print(f"\033[{color_code}m{text}\033[0m")

def print_info(text):
    """Print info message in cyan."""
    print_color(text, "1;36")

def print_success(text):
    """Print success message in green."""
    print_color(text, "1;32")

def print_warning(text):
    """Print warning message in yellow."""
    print_color(text, "1;33")

def print_error(text):
    """Print error message in red."""
    print_color(text, "1;31")

def setup_image_directory():
    """Create necessary directories for notebook images."""
    # Get notebook directory
    notebook_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    images_dir = os.path.join(notebook_dir, 'images')

    # Create directories
    os.makedirs(images_dir, exist_ok=True)

    # Check for existing images
    image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]

    # Display setup information
    print_info("\n=== Enterprise AI Image Setup ===\n")
    print_info(f"Image directory: {images_dir}")

    if image_files:
        print_success(f"Found {len(image_files)} existing images:")
        for img in image_files:
            print(f"  - {img}")
    else:
        print_warning("No images found in the directory.")

    # Check for our specific expected images
    expected_images = [
        'animaux.jpg',
        'indian_love.jpg',
        'familly.jpg',
        'paysage.jpg',
        'logo2.png'
    ]

    missing_images = [img for img in expected_images if img not in image_files]

    if missing_images:
        print_warning("\nThe following expected images are missing:")
        for img in missing_images:
            print(f"  - {img}")

        print_info("\nTo use these notebooks with your own images:")
        print("1. Add your image files to the 'notebooks/images' directory")
        print("2. Rename your images to match the expected filenames, or")
        print("3. Update the code to look for your specific image filenames")
        print("\nRecommended image dimensions: around 400x268 pixels for optimal performance.")
    else:
        print_success("\nAll expected images are present!")

    return images_dir

def main():
    """Main function."""
    try:
        images_dir = setup_image_directory()

        print_info("\n=== Next Steps ===")
        print("1. Run the notebooks to test Enterprise AI functionality")
        print("2. To update image configuration, edit utils.py")
        print_success("\nSetup completed successfully!")

    except Exception as e:
        print_error(f"Error during setup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
