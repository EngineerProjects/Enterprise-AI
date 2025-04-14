#!/usr/bin/env python
"""
Test script for memory management with LLM integration.

This script demonstrates how to use the conversation memory system
with the Ollama provider, including multimodal conversations with images.
"""

import os
import sys
import time
import base64
from pathlib import Path
from io import BytesIO
from typing import Optional, List, Dict, Any

# Try to import PIL for image handling, with a fallback message if not available
try:
    from PIL import Image
except ImportError:
    print("PIL/Pillow is not installed. Image processing will not be available.")
    print("Install with: pip install pillow")
    Image = None

# --- Setup project root ---
project_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

# --- Import enterprise_ai modules ---
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.schema.memory import SlidingWindowConversation
from enterprise_ai.schema.message import Message

# --- Terminal Colors ---
def print_title(title):
    print("\n" + "=" * 60)
    print(f"\033[1;34m{title}\033[0m")  # Blue title
    print("=" * 60 + "\n")

def print_user(msg, images=None):
    print(f"\033[1;32mUser:\033[0m {msg}")  # Green user
    if images and images > 0:
        print(f"\033[1;32m      [+{images} image{'s' if images > 1 else ''}]\033[0m")

def print_assistant(msg):
    print(f"\033[1;35mAssistant:\033[0m {msg}")  # Purple assistant

def print_system(msg):
    print(f"\033[1;33mSystem:\033[0m {msg}")  # Yellow system

def print_info(msg):
    print(f"\033[1;36m{msg}\033[0m")  # Cyan info

def separator():
    print("\n" + "-" * 60 + "\n")


def encode_image(image_path):
    """
    Encode an image to base64 from a file path.
    """
    if not Image:
        print("PIL/Pillow is not installed. Cannot process images.")
        return None
        
    try:
        # Open the image and get its format
        img = Image.open(image_path)
        img_format = img.format or "JPEG"  # Default to JPEG if format is None
        
        # Resize if the image is very large
        if max(img.size) > 1024:
            # Calculate new dimensions while preserving aspect ratio
            ratio = min(1024 / img.size[0], 1024 / img.size[1])
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            print(f"Resized image to {new_size[0]}x{new_size[1]}")
        
        # Create an in-memory file and save the image
        buffer = BytesIO()
        img.save(buffer, format=img_format)
        buffer.seek(0)
        
        # Encode to base64
        encoded = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return encoded
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None


def create_test_image(text="Test Image", size=(400, 300), color=(73, 109, 137), save_path=None):
    """
    Create a simple test image with text on it.
    Returns the path to the created image.
    """
    if not Image:
        print("PIL/Pillow is not installed. Cannot create test images.")
        return None
        
    try:
        # Create a new image with background color
        img = Image.new('RGB', size, color=color)
        
        # Add text if PIL has ImageDraw
        try:
            from PIL import ImageDraw, ImageFont
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
            
        except ImportError:
            print("PIL ImageDraw is not available. Creating image without text.")
        
        # Save the image if a path is provided
        if save_path:
            img.save(save_path)
            return save_path
        else:
            # Create a temporary path
            temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_image.png")
            img.save(temp_path)
            return temp_path
            
    except Exception as e:
        print(f"Error creating test image: {e}")
        return None


def find_image_in_directory():
    """
    Look for an image file in the current directory or the project's docs/images directory.
    Returns the path to the first image found, or None if no images are found.
    """
    # File extensions to look for
    extensions = ['.png', '.jpg', '.jpeg', '.gif']
    
    # Check current directory
    for ext in extensions:
        for file in os.listdir('.'):
            if file.lower().endswith(ext):
                return os.path.abspath(file)
    
    # Check docs/images directory
    docs_images_dir = os.path.join(project_root, 'docs', 'images')
    if os.path.exists(docs_images_dir):
        for ext in extensions:
            for file in os.listdir(docs_images_dir):
                if file.lower().endswith(ext):
                    return os.path.join(docs_images_dir, file)
    
    return None


def add_image_to_message(memory, user_message, image_path):
    """
    Add a user message with an image to the conversation memory.
    
    Args:
        memory: The ConversationMemory instance
        user_message: The text of the user message
        image_path: Path to the image file
        
    Returns:
        The created Message object
    """
    # Create base message
    message = Message.user_message(user_message)
    
    # Encode the image
    encoded_image = encode_image(image_path)
    if encoded_image:
        # Initialize metadata if not present
        if not message.metadata:
            message.metadata = {}
        
        # Initialize images list if not present
        if "images" not in message.metadata:
            message.metadata["images"] = []
        
        # Add the encoded image
        message.metadata["images"].append(encoded_image)
        
        # Debug info
        print_info(f"Added image to message. Base64 length: {len(encoded_image)}")
    else:
        print_info("Failed to encode image")
    
    # Add to memory
    memory.add_message(message)
    return message


def test_basic_memory_with_llm():
    """Test basic conversation memory with LLM integration."""
    print_title("1. Basic Memory with LLM Test")
    
    # Initialize provider
    provider = OllamaProvider(
        model_name="smollm2",  # Use a small model for faster testing
        timeout=300.0,  # Shorter timeout for testing
    )
    
    # Initialize conversation memory with a system prompt
    memory = SlidingWindowConversation(
        system_prompt="You are a helpful AI assistant. Keep your responses concise and informative.",
        max_messages=10  # Keep only the latest 10 messages (5 turns)
    )
    
    try:
        # First turn
        user_question = "What are the three fundamental data structures in computer science?"
        print_user(user_question)
        memory.add_user_message(user_question)
        
        # Get all messages for context
        messages = memory.get_messages()
        print_info(f"Number of messages in context: {len(messages)}")
        print_info(f"Approximate token count: {memory.get_token_count()}")
        
        # Generate a response
        start_time = time.time()
        response = provider.complete(messages)
        duration = time.time() - start_time
        
        # Add the response to memory
        memory.add_assistant_message(response.content or "")
        
        # Print the response
        print_assistant(response.content)
        print_info(f"Response time: {duration:.2f} seconds")
        separator()
        
        # Second turn
        user_question = "Can you explain linked lists in more detail?"
        print_user(user_question)
        memory.add_user_message(user_question)
        
        # Get updated messages for context
        messages = memory.get_messages()
        print_info(f"Number of messages in context: {len(messages)}")
        print_info(f"Approximate token count: {memory.get_token_count()}")
        
        # Generate a response
        start_time = time.time()
        response = provider.complete(messages)
        duration = time.time() - start_time
        
        # Add the response to memory
        memory.add_assistant_message(response.content or "")
        
        # Print the response
        print_assistant(response.content)
        print_info(f"Response time: {duration:.2f} seconds")
        separator()
        
        # Third turn - testing context awareness
        user_question = "What are their advantages over arrays?"
        print_user(user_question)
        memory.add_user_message(user_question)
        
        # Get updated messages for context
        messages = memory.get_messages()
        print_info(f"Number of messages in context: {len(messages)}")
        print_info(f"Approximate token count: {memory.get_token_count()}")
        
        # Generate a response
        start_time = time.time()
        response = provider.complete(messages)
        duration = time.time() - start_time
        
        # Add the response to memory
        memory.add_assistant_message(response.content or "")
        
        # Print the response
        print_assistant(response.content)
        print_info(f"Response time: {duration:.2f} seconds")
        
        # Show conversation state
        print_info("\nFinal conversation state:")
        for i, msg in enumerate(memory.messages):
            if msg.role == "system":
                print_system(f"[{i}] {msg.content}")
            elif msg.role == "user":
                print_user(f"[{i}] {msg.content}")
            elif msg.role == "assistant":
                print_assistant(f"[{i}] {msg.content}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        provider.close()


def test_memory_with_image():
    """Test conversation memory with image support."""
    print_title("2. Memory with Image Support Test")
    
    # Find or create a test image
    image_path = find_image_in_directory()
    if not image_path:
        print_info("No image found in directories, creating a test image...")
        image_path = create_test_image("Test for Memory with Images", size=(640, 480))
    
    if not image_path:
        print("Cannot find or create an image for testing. Skipping test.")
        return
        
    print_info(f"Using image: {image_path}")
    
    # Check if we have a vision model available
    try:
        # First try with a vision model if available
        model_name = "llava"  # Common vision model name
        
        # Initialize provider with vision model
        provider = OllamaProvider(
            model_name=model_name,
            timeout=1000.0,  # Longer timeout for vision models
            capabilities={
                "vision",  # Explicitly set vision capability
                "streaming"
            }
        )
        
        if "vision" not in provider.get_model_features():
            print_info(f"Model {model_name} doesn't support vision. Trying another model...")
            provider.close()
            raise ValueError("Vision not supported")
            
    except Exception as e:
        print(f"Could not use vision model: {e}")
        print_info("Falling back to standard model. Note that it won't be able to process the image content.")
        
        # Fall back to a regular model
        provider = OllamaProvider(
            model_name="smollm2",
            timeout=60.0,
        )
    
    # Initialize conversation memory with a system prompt
    memory = SlidingWindowConversation(
        system_prompt="You are a helpful AI assistant. If you receive an image, describe it in detail.",
        max_messages=10
    )
    
    try:
        # Add a regular message first
        user_message = "Hello, I'm going to share an image with you in my next message."
        print_user(user_message)
        memory.add_user_message(user_message)
        
        # Generate response
        messages = memory.get_messages()
        response = provider.complete(messages)
        memory.add_assistant_message(response.content or "")
        print_assistant(response.content)
        separator()
        
        # Now add a message with an image
        user_message = "What do you see in this image?"
        print_user(user_message, images=1)
        
        # Create message with image
        message = add_image_to_message(memory, user_message, image_path)
        
        # Verify image was added to message
        has_image = message.metadata and "images" in message.metadata and message.metadata["images"]
        if has_image:
            print_info(f"Image successfully added to message (Base64 length: {len(message.metadata['images'][0])}, preview: {message.metadata['images'][0][:30]}...)")
        else:
            print_info("Failed to add image to message metadata")
        
        # Generate response
        messages = memory.get_messages()
        print_info(f"Number of messages in context: {len(messages)}")
        print_info(f"Last message has image: {has_image}")
        
        # Process response
        start_time = time.time()
        response = provider.complete(messages)
        duration = time.time() - start_time
        
        # Add the response to memory
        memory.add_assistant_message(response.content or "")
        
        # Print the response
        print_assistant(response.content)
        print_info(f"Response time: {duration:.2f} seconds")
        separator()
        
        # Test if memory keeps the image through conversation turns
        user_message = "Can you tell me more about what you see in the image?"
        print_user(user_message)
        memory.add_user_message(user_message)
        
        # Get messages from memory
        messages = memory.get_messages()
        
        # Check if image is still in context
        has_image_in_context = False
        for msg in messages:
            if (msg.metadata and "images" in msg.metadata and 
                msg.metadata["images"]):
                has_image_in_context = True
                break
        
        print_info(f"Image still in conversation context: {has_image_in_context}")
        
        # Generate response
        start_time = time.time()
        response = provider.complete(messages)
        duration = time.time() - start_time
        
        # Add the response to memory
        memory.add_assistant_message(response.content or "")
        
        # Print the response
        print_assistant(response.content)
        print_info(f"Response time: {duration:.2f} seconds")
        
        # Show final memory state
        print_info("\nFinal memory state:")
        for i, msg in enumerate(memory.messages):
            # Check if the message has an image
            has_img = (msg.metadata and "images" in msg.metadata and 
                      msg.metadata["images"] and len(msg.metadata["images"]) > 0)
            
            if msg.role == "system":
                print_system(f"[{i}] {msg.content}")
            elif msg.role == "user":
                print_user(f"[{i}] {msg.content}", images=1 if has_img else 0)
            elif msg.role == "assistant":
                print_assistant(f"[{i}] {msg.content}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        provider.close()


def test_sliding_window_with_images():
    """Test sliding window memory with images."""
    print_title("3. Sliding Window with Images Test")
    
    # Find or create a test image
    image_path = find_image_in_directory()
    if not image_path:
        print_info("No image found in directories, creating a test image...")
        image_path = create_test_image("Test for Sliding Window", size=(640, 480))
    
    if not image_path:
        print("Cannot find or create an image for testing. Skipping test.")
        return
    
    # Initialize provider
    provider = OllamaProvider(
        model_name="smollm2",  # Use a small model for faster testing
        timeout=1000.0,
    )
    
    # Initialize sliding window memory with very small window (2 messages)
    # to test if images get pruned properly
    memory = SlidingWindowConversation(
        system_prompt="You are a helpful AI assistant.",
        max_messages=2  # Very small window for testing
    )
    
    try:
        # First turn - with image
        user_message = "Hello, here's an image!"
        print_user(user_message, images=1)
        add_image_to_message(memory, user_message, image_path)
        
        # Get response
        messages = memory.get_messages()
        response = provider.complete(messages)
        memory.add_assistant_message(response.content or "")
        print_assistant(response.content)
        separator()
        
        # Count messages with images before sliding window
        images_before = sum(
            1 for msg in memory.messages 
            if msg.metadata and "images" in msg.metadata and msg.metadata["images"]
        )
        print_info(f"Messages with images before window slides: {images_before}")
        
        # Add more messages to force window sliding
        for i in range(3):
            # User message
            user_message = f"This is message {i+1} to push out the image."
            print_user(user_message)
            memory.add_user_message(user_message)
            
            # Get response
            messages = memory.get_messages()
            response = provider.complete(messages)
            memory.add_assistant_message(response.content or "")
            print_assistant(response.content)
        
        # Count messages with images after sliding window
        images_after = sum(
            1 for msg in memory.messages 
            if msg.metadata and "images" in msg.metadata and msg.metadata["images"]
        )
        print_info(f"Messages with images after window slides: {images_after}")
        
        # Check if sliding window properly pruned the image
        if images_before > 0 and images_after == 0:
            print_info("✓ Sliding window correctly pruned the message with image")
        elif images_after > 0:
            print_info("✗ Sliding window did not prune the message with image")
        else:
            print_info("? Image was not properly added to begin with")
            
        # Show final memory state
        print_info("\nFinal memory state:")
        for i, msg in enumerate(memory.messages):
            # Check if the message has an image
            has_img = (msg.metadata and "images" in msg.metadata and 
                      msg.metadata["images"] and len(msg.metadata["images"]) > 0)
            
            if msg.role == "system":
                print_system(f"[{i}] {msg.content}")
            elif msg.role == "user":
                print_user(f"[{i}] {msg.content}", images=1 if has_img else 0)
            elif msg.role == "assistant":
                print_assistant(f"[{i}] {msg.content}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        provider.close()


if __name__ == "__main__":
    print("\033[1;36mMemory with LLM Integration Tests\033[0m")
    print("This script tests conversation memory with LLM integration,")
    print("including support for images in conversations.")
    
    # Change working directory to the script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run tests
    try:
        # Basic memory with LLM
        test_basic_memory_with_llm()
        
        # Memory with image support
        test_memory_with_image()
        
        # Sliding window with images
        test_sliding_window_with_images()
        
        print("\n\033[1;32mAll tests completed!\033[0m")
    except Exception as e:
        print(f"\n\033[1;31mError: {e}\033[0m")
        import traceback
        traceback.print_exc()