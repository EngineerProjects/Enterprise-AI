"""
Simple Vision Streaming Test

This test file shows how to:
- Create a vision provider that supports streaming
- Stream vision analysis in real-time
- Combine vision and streaming capabilities

Everything about vision + streaming is here.
"""

import sys
import os
import asyncio

# Add project path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Import what we need
from enterprise_ai.llm import create_provider
from enterprise_ai.schema import Message
from examples.notebooks.utils import (
    print_title, print_section, print_info, print_success, print_error, print_warning,
    print_user, print_assistant, Timer, AsyncTimer,
    detect_model_capabilities, encode_image_to_base64, find_image_in_directory
)

def test_vision_streaming():
    """Test vision streaming capabilities."""
    print_title("Vision Streaming Test")
    
    # Step 1: Create vision provider
    print_section("Creating Vision Provider")
    try:
        provider = create_provider(
            "ollama",
            model_name="llava",
            base_url="http://localhost:11434",
            timeout=600.0
        )
        print_success(f"✓ Provider created: {provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Step 2: Check capabilities
    print_section("Checking Capabilities")
    try:
        capabilities = detect_model_capabilities(provider)
        has_vision = capabilities.get("vision", False)
        has_streaming = capabilities.get("streaming", False)
        
        print_info(f"Vision support: {'✓ YES' if has_vision else '✗ NO'}")
        print_info(f"Streaming support: {'✓ YES' if has_streaming else '✗ NO'}")
        
        if not (has_vision and has_streaming):
            print_warning("! Both vision and streaming are required for this test")
            return
            
        print_success("✓ Both vision and streaming are supported")
        
    except Exception as e:
        print_error(f"✗ Failed to check capabilities: {e}")
        return
    
    # Step 3: Prepare test image
    print_section("Preparing Test Image")
    try:
        image_path = find_image_in_directory(
            specific_images=['animaux.jpg', 'indian_love.jpg', 'familly.jpg', 'paysage.jpg', 'logo2.png'],
            target_size=(400, 268)
        )
        
        if not image_path:
            print_error("✗ No test images found")
            return
        
        encoded_image = encode_image_to_base64(image_path, max_size=(400, 268))
        if not encoded_image:
            print_error("✗ Failed to encode image")
            return
        
        print_success(f"✓ Image ready: {image_path}")
        
    except Exception as e:
        print_error(f"✗ Image preparation failed: {e}")
        return
    
    # Step 4: Test vision streaming
    print_section("Vision Streaming Test")
    try:
        # Create detailed prompt for streaming
        vision_message = Message.user_message(
            "Analyze this image in great detail. Start with the overall composition, "
            "then describe specific elements, colors, mood, and any interesting details. "
            "Take your time and be comprehensive."
        )
        vision_message.metadata = {"images": [encoded_image]}
        
        messages = [
            Message.system_message("You are a detailed vision AI assistant."),
            vision_message
        ]
        
        print_user("Analyze this image in great detail...", images=1)
        print_assistant("", end="")
        
        chunk_count = 0
        with Timer("Vision streaming time"):
            for chunk in provider.complete_stream(messages):
                chunk_count += 1
                if hasattr(chunk, 'content') and chunk.content:
                    print(chunk.content, end='', flush=True)
        
        print()  # New line
        print_success(f"✓ Vision streaming successful ({chunk_count} chunks)")
        
    except Exception as e:
        print_error(f"✗ Vision streaming failed: {e}")

async def test_vision_async_streaming():
    """Test async vision streaming."""
    print_section("Async Vision Streaming Test")
    
    # Create provider
    try:
        provider = create_provider(
            "ollama",
            model_name="llava",
            base_url="http://localhost:11434",
            timeout=600.0
        )
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Check capabilities
    try:
        capabilities = detect_model_capabilities(provider)
        if not (capabilities.get("vision", False) and capabilities.get("streaming", False)):
            print_warning("! Vision and streaming required - skipping async test")
            return
    except Exception as e:
        print_error(f"✗ Failed to check capabilities: {e}")
        return
    
    # Prepare image
    try:
        image_path = find_image_in_directory(
            specific_images=['animaux.jpg', 'indian_love.jpg', 'familly.jpg', 'paysage.jpg', 'logo2.png'],
            target_size=(400, 268)
        )
        if not image_path:
            print_error("✗ No test images found")
            return
        
        encoded_image = encode_image_to_base64(image_path, max_size=(400, 268))
        if not encoded_image:
            print_error("✗ Failed to encode image")
            return
    except Exception as e:
        print_error(f"✗ Image preparation failed: {e}")
        return
    
    # Test async vision streaming
    try:
        vision_message = Message.user_message(
            "Provide a step-by-step analysis of this image, explaining your thought process as you examine different parts."
        )
        vision_message.metadata = {"images": [encoded_image]}
        
        messages = [
            Message.system_message("You are an analytical vision AI."),
            vision_message
        ]
        
        print_user("Provide a step-by-step analysis of this image...", images=1)
        print_assistant("", end="")
        
        chunk_count = 0
        async with AsyncTimer("Async vision streaming time"):
            async for chunk in provider.acomplete_stream(messages):
                chunk_count += 1
                if hasattr(chunk, 'content') and chunk.content:
                    print(chunk.content, end='', flush=True)
        
        print()  # New line
        print_success(f"✓ Async vision streaming successful ({chunk_count} chunks)")
        
    except Exception as e:
        print_error(f"✗ Async vision streaming failed: {e}")

def run_all_tests():
    """Run all vision streaming tests."""
    # Sync tests
    test_vision_streaming()
    
    # Async tests
    asyncio.run(test_vision_async_streaming())

if __name__ == "__main__":
    run_all_tests()