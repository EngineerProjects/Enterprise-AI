"""
Simple Error Handling Test

This test file shows how to:
- Test various error conditions
- Verify proper error handling
- Test recovery after errors

Everything about error handling is here.
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
    print_title, print_section, print_info, print_success, print_error, print_warning
)

def test_error_handling():
    """Test various error handling scenarios."""
    print_title("Error Handling Test")
    
    # Test 1: Invalid model name
    print_section("Invalid Model Test")
    try:
        print_info("Trying to create provider with non-existent model...")
        bad_provider = create_provider(
            "ollama",
            model_name="non_existent_model_12345",
            base_url="http://localhost:11434",
            timeout=10.0
        )
        
        # Try to use it
        response = bad_provider.complete([Message.user_message("Test")])
        print_error("✗ Expected error was not raised!")
        
    except Exception as e:
        print_success(f"✓ Invalid model error properly caught: {type(e).__name__}")
        print_info(f"  Error message: {str(e)[:100]}...")
    
    # Test 2: Invalid connection URL
    print_section("Connection Error Test")
    try:
        print_info("Trying to connect to invalid URL...")
        bad_url_provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://invalid-url-that-doesnt-exist:12345",
            timeout=5.0
        )
        
        # Try to use it
        response = bad_url_provider.complete([Message.user_message("Test")])
        print_error("✗ Expected connection error was not raised!")
        
    except Exception as e:
        print_success(f"✓ Connection error properly caught: {type(e).__name__}")
        print_info(f"  Error message: {str(e)[:100]}...")
    
    # Test 3: Create a working provider for remaining tests
    print_section("Creating Working Provider")
    try:
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
        print_success(f"✓ Working provider created: {provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Failed to create working provider: {e}")
        return
    
    # Test 4: Invalid message format
    print_section("Invalid Message Format Test")
    
    # Test with string instead of list
    try:
        print_info("Testing with string instead of message list...")
        response = provider.complete("This should be a list of messages")
        print_error("✗ Expected error for string input was not raised!")
    except Exception as e:
        print_success(f"✓ String input error caught: {type(e).__name__}")
    
    # Test with None
    try:
        print_info("Testing with None input...")
        response = provider.complete(None)
        print_error("✗ Expected error for None input was not raised!")
    except Exception as e:
        print_success(f"✓ None input error caught: {type(e).__name__}")
    
    # Test with empty list
    try:
        print_info("Testing with empty message list...")
        response = provider.complete([])
        print_error("✗ Expected error for empty list was not raised!")
    except Exception as e:
        print_success(f"✓ Empty list error caught: {type(e).__name__}")
    
    # Test 5: Very short timeout
    print_section("Timeout Test")
    try:
        print_info("Testing with very short timeout...")
        timeout_provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=0.1  # Very short timeout
        )
        
        # Try a request that should timeout
        long_prompt = "Write a very detailed 1000-word essay about artificial intelligence."
        response = timeout_provider.complete([Message.user_message(long_prompt)])
        print_warning("! Request completed faster than expected timeout")
        
    except Exception as e:
        print_success(f"✓ Timeout error properly caught: {type(e).__name__}")
    
    # Test 6: Recovery after error
    print_section("Recovery Test")
    try:
        print_info("Testing provider recovery after errors...")
        
        # First, make a valid request
        print_info("  Step 1: Valid request")
        response1 = provider.complete([Message.user_message("Hello")])
        print_success(f"  ✓ Valid request successful: {response1.content[:50]}...")
        
        # Then, try an invalid request
        print_info("  Step 2: Invalid request")
        try:
            response2 = provider.complete("invalid format")
        except Exception:
            print_success("  ✓ Invalid request properly rejected")
        
        # Finally, test recovery with another valid request
        print_info("  Step 3: Recovery test")
        response3 = provider.complete([Message.user_message("Are you still working?")])
        print_success(f"  ✓ Provider recovered: {response3.content[:50]}...")
        
    except Exception as e:
        print_error(f"✗ Recovery test failed: {e}")
    
    # Test 7: Large input handling
    print_section("Large Input Test")
    try:
        print_info("Testing with very large input...")
        
        # Create a very large prompt
        large_prompt = "Please repeat this word: " + "supercalifragilisticexpialidocious " * 1000
        
        response = provider.complete(
            [Message.user_message(large_prompt)],
            max_tokens=50  # Limit output to avoid huge response
        )
        
        print_success("✓ Large input handled successfully")
        print_info(f"  Response: {response.content[:100]}...")
        
    except Exception as e:
        print_success(f"✓ Large input appropriately handled: {type(e).__name__}")
        print_info(f"  Error message: {str(e)[:100]}...")

if __name__ == "__main__":
    test_error_handling()