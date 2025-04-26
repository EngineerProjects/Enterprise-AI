"""
Enterprise AI LLM Provider Examples

This notebook demonstrates working with the LLM provider system for:
- Initializing and configuring LLM providers (Ollama)
- Testing basic completion capabilities
- Testing streaming and async APIs
- Testing vision capabilities (if available)
- Testing tool calling capabilities (if available)
"""

import os
import sys
import time
import asyncio
import json
from typing import Dict, List, Optional, Any, Union

# Import common utilities
from utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    Timer,
    AsyncTimer,
    encode_image_to_base64,
    find_image_in_directory,
    create_test_image,
    detect_model_capabilities,
    run_async,
    get_image_path
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.schema import Message

# Configuration - modify these to match your environment
CONFIG = {
    "default_model": "smollm2",      # Default small model for basic tests
    "vision_model": "llava",         # Vision-capable model (if available)
    "function_model": "llama3.2",    # Function/tool-capable model (if available)
    "base_url": "http://localhost:11434",
    "timeout": 500.0,                 # Default timeout in seconds
    "max_tokens": 1024,              # Maximum tokens to generate
}

def test_initialization():
    """Test initializing the Ollama provider."""
    print_section("Provider Initialization")

    try:
        provider = OllamaProvider(
            model_name=CONFIG["default_model"],
            base_url=CONFIG["base_url"],
            timeout=CONFIG["timeout"],
            max_tokens=CONFIG["max_tokens"]
        )

        print_success("Provider initialized successfully!")
        print_info(f"Model name: {provider.get_model_name()}")
        print_info(f"Base URL: {provider.config['base_url']}")
        print_info(f"Timeout: {provider._timeout} seconds")

        return provider
    except Exception as e:
        print_error(f"Initialization failed: {e}")
        raise

def test_basic_completion(provider):
    """Test basic completion functionality."""
    print_section("Basic Completion Test")

    messages = [Message.user_message("Tell me a short programming joke.")]

    print_info("Sending request to model...")

    with Timer("Response generation"):
        response = provider.complete(messages)

    print_info("Response received:")
    print("-" * 40)
    print(response.content)
    print("-" * 40)

    return response

def test_streaming_completion(provider):
    """Test streaming completion functionality."""
    print_section("Streaming Completion Test")

    messages = [Message.user_message("Explain recursion in three sentences.")]

    print_info("Streaming response:")
    print("-" * 40)

    # Track previous content length to only print new content
    previous_length = 0
    chunk_count = 0

    with Timer("Streaming response") as timer:
        for chunk in provider.complete_stream(messages):
            chunk_count += 1

            # Get current chunk content
            current_content = chunk.content

            # Only print the new content
            new_content = current_content[previous_length:]
            if new_content:
                print(new_content, end='', flush=True)

            # Update previous length
            previous_length = len(current_content)

    print()
    print("-" * 40)
    print_info(f"Received {chunk_count} chunks in {timer.duration:.2f} seconds")

async def test_async_completion(provider):
    """Test async completion functionality."""
    print_section("Async Completion Test")

    messages = [Message.user_message("Explain why async programming is useful.")]

    print_info("Sending async request...")

    async with AsyncTimer("Async response generation") as timer:
        response = await provider.acomplete(messages)

    print_info("Async response received:")
    print("-" * 40)
    print(response.content)
    print("-" * 40)

    return response

async def test_async_streaming(provider):
    """Test async streaming functionality."""
    print_section("Async Streaming Completion Test")

    messages = [Message.user_message("Write a haiku about programming.")]

    print_info("Streaming async response:")
    print("-" * 40)

    # Track previous content length to only print new content
    previous_length = 0
    chunk_count = 0

    async with AsyncTimer("Async streaming") as timer:
        async for chunk in provider.acomplete_stream(messages):
            chunk_count += 1

            # Get current chunk content
            current_content = chunk.content

            # Only print the new content
            new_content = current_content[previous_length:]
            if new_content:
                print(new_content, end='', flush=True)

            # Update previous length
            previous_length = len(current_content)

    print()
    print("-" * 40)
    print_info(f"Received {chunk_count} chunks in {timer.duration:.2f} seconds")

def test_vision_capabilities(provider, capabilities):
    """Test vision capabilities if supported."""
    print_section("Vision Capabilities Test")

    # Skip if vision is not supported
    if not capabilities.get("vision", False):
        print_warning("Vision capabilities not supported by this model.")
        print_info("To test vision, configure a vision-capable model in CONFIG.")
        return False

    # Find an image from the specified collection
    image_path = find_image_in_directory(
        specific_images=['animaux.jpg', 'indian_love.jpg', 'familly.jpg', 'paysage.jpg', 'logo2.png'],
        target_size=(400, 268)
    )

    if not image_path:
        print_warning("None of the specified images found. Searching for any image...")
        image_path = find_image_in_directory()

        if not image_path:
            print_error("Cannot find any images for testing.")
            return False

    print_info(f"Using image: {image_path}")

    # Process image - resize to smaller dimensions for lightweight vision models
    # Using 400x268 as requested for lightweight models running on older GPUs
    encoded_image = encode_image_to_base64(image_path, max_size=(400, 268))
    if not encoded_image:
        print_error("Failed to encode image.")
        return False

    print_info(f"Image encoded successfully (length: {len(encoded_image)})")

    # Create message with image
    msg = Message.user_message("Describe this image in detail.")
    msg.metadata = {"images": [encoded_image]}

    print_info("Sending vision request...")

    with Timer("Vision response generation"):
        response = provider.complete([msg])

    print_info("Vision response received:")
    print("-" * 40)
    print(response.content)
    print("-" * 40)

    return True

def test_function_calling(provider, capabilities):
    """Test function calling capabilities if supported."""
    print_section("Function Calling Test")

    # Skip if function calling is not supported
    if not capabilities.get("function_calling", False):
        print_warning("Function calling not supported by this model.")
        print_info("To test function calling, configure a function-capable model in CONFIG.")
        return False

    # Define calculator tool
    calculator_tool = {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "A simple calculator that can add, subtract, multiply, and divide",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "The operation to perform"
                    },
                    "a": {
                        "type": "number",
                        "description": "The first number"
                    },
                    "b": {
                        "type": "number",
                        "description": "The second number"
                    }
                },
                "required": ["operation", "a", "b"]
            }
        }
    }

    tools = [calculator_tool]

    # Create messages with a calculation request
    messages = [
        Message.system_message("You have access to a calculator tool. Use it when appropriate."),
        Message.user_message("Calculate 142 divided by 17.75")
    ]

    print_info("Sending function calling request...")

    with Timer("Function calling response"):
        response = provider.complete(messages, tools=tools)

    print_info("Response received:")
    print("-" * 40)
    print(response.content)
    print("-" * 40)

    # Check for tool calls in metadata
    if hasattr(response, "metadata") and response.metadata and "tool_calls" in response.metadata:
        print_success("Tool calls detected in response!")
        print_info("Tool calls:")
        for i, tool_call in enumerate(response.metadata["tool_calls"]):
            print(f"Tool call {i+1}:")
            print(f"  Name: {tool_call['function']['name']}")
            print(f"  Arguments: {tool_call['function']['arguments']}")
        return True
    else:
        print_warning("No tool calls detected in metadata.")
        print_info("The model may support function calling but didn't use it for this prompt.")
        return False

def switch_to_vision_model(current_provider):
    """Switch to a vision-capable model if configured."""
    print_section("Switching to Vision Model")

    if CONFIG["vision_model"] == CONFIG["default_model"]:
        print_info("Current model is already configured for vision tests.")
        return current_provider, current_provider.get_model_info().features

    try:
        vision_provider = OllamaProvider(
            model_name=CONFIG["vision_model"],
            base_url=CONFIG["base_url"],
            timeout=CONFIG["timeout"] * 2,  # Double timeout for vision
            max_tokens=CONFIG["max_tokens"],
            capabilities={"vision", "streaming"}  # Explicitly set capabilities
        )

        print_success(f"Switched to vision model: {vision_provider.get_model_name()}")
        capabilities = detect_model_capabilities(vision_provider)

        return vision_provider, capabilities
    except Exception as e:
        print_error(f"Failed to switch to vision model: {e}")
        print_warning("Continuing with current model, but vision tests may fail.")
        return current_provider, current_provider.get_model_info().features

def switch_to_function_model(current_provider):
    """Switch to a function-calling capable model if configured."""
    print_section("Switching to Function-Calling Model")

    if CONFIG["function_model"] == CONFIG["default_model"]:
        print_info("Current model is already configured for function calling tests.")
        return current_provider, current_provider.get_model_info().features

    try:
        function_provider = OllamaProvider(
            model_name=CONFIG["function_model"],
            base_url=CONFIG["base_url"],
            timeout=CONFIG["timeout"],
            max_tokens=CONFIG["max_tokens"],
            capabilities={"function_calling", "streaming"}  # Explicitly set capabilities
        )

        print_success(f"Switched to function model: {function_provider.get_model_name()}")
        capabilities = detect_model_capabilities(function_provider)

        return function_provider, capabilities
    except Exception as e:
        print_error(f"Failed to switch to function model: {e}")
        print_warning("Continuing with current model, but function calling tests may fail.")
        return current_provider, current_provider.get_model_info().features

def test_error_handling():
    """Test error handling with invalid inputs."""
    print_section("Error Handling Test")

    # Test with non-existent model
    print_info("Testing with non-existent model...")
    try:
        bad_provider = OllamaProvider(
            model_name="non_existent_model_12345",
            base_url=CONFIG["base_url"],
            timeout=10.0
        )
        bad_provider.complete([Message.user_message("This should fail!")])
        print_error("Error handling test failed: No error was raised!")
    except Exception as e:
        print_success(f"Successfully caught error: {type(e).__name__} - {e}")

    # Test with invalid base URL
    print_info("\nTesting with invalid URL...")
    try:
        bad_url_provider = OllamaProvider(
            model_name=CONFIG["default_model"],
            base_url="http://invalid-url-that-doesnt-exist:12345",
            timeout=5.0
        )
        bad_url_provider.complete([Message.user_message("This should fail!")])
        print_error("Error handling test failed: No error was raised for invalid URL!")
    except Exception as e:
        print_success(f"Successfully caught error: {type(e).__name__} - {e}")

async def run_async_tests(provider, capabilities):
    """Run all async tests."""
    # Test async completion
    await test_async_completion(provider)
    separator()

    # Test async streaming
    await test_async_streaming(provider)
    separator()

def main():
    """Run all LLM provider tests."""
    print_title("Enterprise AI LLM Provider Examples")

    try:
        # Initialize provider
        provider = test_initialization()
        separator()

        # Detect model capabilities
        capabilities = detect_model_capabilities(provider)
        separator()

        # Test basic completion
        test_basic_completion(provider)
        separator()

        # Test streaming
        test_streaming_completion(provider)
        separator()

        # Run async tests
        run_async(run_async_tests(provider, capabilities))

        # Test vision capabilities with appropriate model
        vision_provider, vision_capabilities = switch_to_vision_model(provider)
        test_vision_capabilities(vision_provider, vision_capabilities)
        separator()

        # Test function calling with appropriate model
        function_provider, function_capabilities = switch_to_function_model(provider)
        test_function_calling(function_provider, function_capabilities)
        separator()

        # Test error handling
        test_error_handling()
        separator()

        print_success("All LLM provider tests completed!")

    except Exception as e:
        print_error(f"Tests failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
