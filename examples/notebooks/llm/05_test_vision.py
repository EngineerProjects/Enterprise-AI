"""
Simple Vision Test

This test file shows how to:
- Create a vision-capable provider
- Encode and send images
- Test vision understanding
- Test multi-modal conversations

Everything about vision capabilities is here.
"""

import sys
import os

# Add project path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Import what we need
from enterprise_ai.llm import create_provider
from enterprise_ai.schema import Message
from examples.notebooks.utils import (
    print_title, print_section, print_info, print_success, print_error, print_warning,
    print_user, print_assistant, Timer,
    detect_model_capabilities, encode_image_to_base64, find_image_in_directory
)

def test_vision():
    """Test vision capabilities."""
    print_title("Vision Test")
    
    # Step 1: Create vision provider
    print_section("Creating Vision Provider")
    try:
        provider = create_provider(
            "ollama",
            model_name="llava",  # Vision model
            base_url="http://localhost:11434",
            timeout=600.0  # Longer timeout for vision
        )
        print_success(f"✓ Vision provider created: {provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Failed to create vision provider: {e}")
        return
    
    # Step 2: Check vision capabilities
    print_section("Checking Vision Support")
    try:
        capabilities = detect_model_capabilities(provider)
        supports_vision = capabilities.get("vision", False)
        
        if supports_vision:
            print_success("✓ Vision is supported")
        else:
            print_warning("! Vision not supported by this model")
            return
            
    except Exception as e:
        print_error(f"✗ Failed to check vision capabilities: {e}")
        return
    
    # Step 3: Find and prepare test image
    print_section("Preparing Test Image")
    try:
        # Look for test images
        image_path = find_image_in_directory(
            specific_images=['animaux.jpg', 'indian_love.jpg', 'familly.jpg', 'paysage.jpg', 'logo2.png'],
            target_size=(400, 268)
        )
        
        if not image_path:
            print_error("✗ No test images found")
            return
        
        print_success(f"✓ Found test image: {image_path}")
        
        # Encode the image
        encoded_image = encode_image_to_base64(image_path, max_size=(400, 268))
        if not encoded_image:
            print_error("✗ Failed to encode image")
            return
        
        print_success("✓ Image encoded successfully")
        
    except Exception as e:
        print_error(f"✗ Image preparation failed: {e}")
        return
    
    # Step 4: Test basic vision understanding
    print_section("Basic Vision Test")
    try:
        # Create vision message
        vision_message = Message.user_message("Describe what you see in this image in detail.")
        vision_message.metadata = {"images": [encoded_image]}
        
        messages = [
            Message.system_message("You are a vision AI assistant. Describe images accurately."),
            vision_message
        ]
        
        # Make vision request
        with Timer("Vision processing time"):
            response = provider.complete(messages)
        
        print_user("Describe what you see in this image in detail.", images=1)
        print_assistant(response.content)
        print_success("✓ Basic vision test successful")
        
    except Exception as e:
        print_error(f"✗ Basic vision test failed: {e}")
    
    # Step 5: Test follow-up question (context retention)
    print_section("Vision Context Test")
    try:
        # Add follow-up question to existing conversation
        followup_messages = messages + [
            Message.assistant_message(response.content or ""),
            Message.user_message("What colors are most prominent in the image?")
        ]
        
        followup_response = provider.complete(followup_messages)
        
        print_user("What colors are most prominent in the image?")
        print_assistant(followup_response.content)
        print_success("✓ Vision context retention successful")
        
    except Exception as e:
        print_error(f"✗ Vision context test failed: {e}")
    
    # Step 6: Test multiple images (if supported)
    print_section("Multiple Images Test")
    try:
        # Use the same image twice for testing (in real use, you'd have different images)
        multi_vision_message = Message.user_message("Compare these images. What similarities do you notice?")
        multi_vision_message.metadata = {"images": [encoded_image, encoded_image]}
        
        multi_messages = [
            Message.system_message("You are a vision AI assistant. Compare images carefully."),
            multi_vision_message
        ]
        
        multi_response = provider.complete(multi_messages)
        
        print_user("Compare these images. What similarities do you notice?", images=2)
        print_assistant(multi_response.content)
        print_success("✓ Multiple images test successful")
        
    except Exception as e:
        print_error(f"✗ Multiple images test failed: {e}")

if __name__ == "__main__":
    test_vision()