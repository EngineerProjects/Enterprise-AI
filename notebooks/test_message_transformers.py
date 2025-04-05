#!/usr/bin/env python3
"""
Test script for message transformers in Enterprise AI.

This script tests the OpenAI, Anthropic, and Ollama message transformers to ensure
they correctly convert internal message formats to provider-specific formats.
It tests various message types including text, images, and tool calls.
"""

import os
import sys
from pathlib import Path
import json
import base64
import io
import uuid
from pprint import pprint

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Import the message components and transformers
from enterprise_ai.schema import Message, Role, Function, ToolCall
from enterprise_ai.message.constants import (
    MESSAGE_FORMAT_OPENAI,
    MESSAGE_FORMAT_ANTHROPIC,
    MESSAGE_FORMAT_OLLAMA,
)
from enterprise_ai.message.image import encode_image_to_base64
from enterprise_ai.message.base import EnhancedMessage
from enterprise_ai.message.transformers.base import TransformerRegistry

# For creating content objects directly if needed
try:
    from enterprise_ai.message.base import (
        ImageContentImpl,
        TextContentImpl,
        CodeContentImpl
    )
except ImportError:
    print("Note: Could not import content implementation classes")
    ImageContentImpl = TextContentImpl = CodeContentImpl = None

# Import all transformers to ensure they're registered
import enterprise_ai.message.transformers.openai
import enterprise_ai.message.transformers.anthropic
import enterprise_ai.message.transformers.ollama

# Create a test image programmatically
def get_test_image(size=(400, 300)):
    """Create a test image for transformer testing.

    Args:
        size: Image dimensions as (width, height) tuple

    Returns:
        Base64-encoded image string
    """
    try:
        # Create a test image using PIL
        from PIL import Image, ImageDraw

        # Create base image with gradient background
        img = Image.new("RGB", size, color="#f0f0f0")
        draw = ImageDraw.Draw(img)

        # Add some shapes for complexity
        width, height = size
        for i in range(0, width, 40):
            for j in range(0, height, 40):
                # Alternate between rectangles and circles
                if (i + j) % 80 == 0:
                    draw.rectangle([i, j, i+30, j+30], fill=(255, 0, 0))
                else:
                    draw.ellipse([i, j, i+30, j+30], fill=(0, 0, 255))

        # Add some text
        draw.text((width//4, height//2), "Test Image", fill=(0, 0, 0))

        # Convert to base64
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.getvalue()).decode("utf-8")

    except ImportError:
        print("PIL not installed, using placeholder base64 image")
        # Return a tiny 1x1 black PNG image
        return "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+P+/HgAFMQJ/9jXR5QAAAABJRU5ErkJggg=="

# Create test tool call
def create_test_tool_call(name="get_weather", args=None):
    """Create a test tool call for transformation testing."""
    if args is None:
        args = {"location": "San Francisco", "unit": "celsius"}

    # Convert args to string if they're a dict
    args_str = json.dumps(args) if isinstance(args, dict) else str(args)

    return ToolCall(
        id=str(uuid.uuid4()),
        type="function",
        function=Function(name=name, arguments=args_str)
    )

# Helper function to print formatted results
def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 80}")
    print(f" {title}")
    print(f"{'=' * 80}")

def print_result(title, data):
    """Print a result with title."""
    print(f"\n--- {title} ---")
    if isinstance(data, dict) or isinstance(data, list):
        print(json.dumps(data, indent=2))
    else:
        print(data)

# Test functions for each transformer
def test_openai_transformer():
    """Test the OpenAI transformer with various message types."""
    print_section("TESTING OPENAI TRANSFORMER")

    # 1. Basic user message
    user_msg = Message.user_message("Hello, can you help me with something?")
    openai_user = TransformerRegistry.transform(user_msg, MESSAGE_FORMAT_OPENAI)
    print_result("1. Basic User Message", openai_user)

    # 2. System message
    system_msg = Message.system_message("You are a helpful assistant.")
    openai_system = TransformerRegistry.transform(system_msg, MESSAGE_FORMAT_OPENAI)
    print_result("2. System Message", openai_system)

    # 3. Assistant message with tool calls
    tool_call = create_test_tool_call()
    assistant_msg = Message.assistant_message(
        content="I'll check the weather for you.",
        tool_calls=[tool_call]
    )
    openai_assistant = TransformerRegistry.transform(assistant_msg, MESSAGE_FORMAT_OPENAI)
    print_result("3. Assistant Message with Tool Calls", openai_assistant)

    # 4. Tool message (becomes function in OpenAI)
    tool_msg = Message.tool_message(
        content='{"temperature": 22, "condition": "sunny"}',
        name="get_weather",
        tool_call_id=tool_call.id
    )
    openai_tool = TransformerRegistry.transform(tool_msg, MESSAGE_FORMAT_OPENAI)
    print_result("4. Tool Message", openai_tool)

    # 5. Message with image
    base64_img = get_test_image()
    img_msg = Message.user_message(
        content="What's in this image?",
        base64_image=base64_img
    )
    openai_img = TransformerRegistry.transform(img_msg, MESSAGE_FORMAT_OPENAI)
    # Truncate the image data for display
    if isinstance(openai_img["content"], list):
        for item in openai_img["content"]:
            if "image_url" in item:
                item["image_url"]["url"] = item["image_url"]["url"][:50] + "..."
    print_result("5. Message with Image", openai_img)

    # 6. Enhanced message with multiple content types
    try:
        enhanced_msg = EnhancedMessage(
            role=Role.ASSISTANT,
            content="Here's information about the weather:",
            id=str(uuid.uuid4())  # Explicitly provide ID
        )

        try:
            # Try to add image, catch any specific errors
            enhanced_msg.add_image(base64_img, "Weather map")
        except Exception as img_error:
            print(f"Note: Could not add image to enhanced message: {img_error}")

        openai_enhanced = TransformerRegistry.transform(enhanced_msg, MESSAGE_FORMAT_OPENAI)
        # Truncate image data for display
        if isinstance(openai_enhanced["content"], list):
            for item in openai_enhanced["content"]:
                if "image_url" in item:
                    item["image_url"]["url"] = item["image_url"]["url"][:50] + "..."
        print_result("6. Enhanced Message with Multiple Content", openai_enhanced)
    except Exception as e:
        print_result("6. Enhanced Message Test", f"Error: {e}")
        print("Skipping OpenAI enhanced message test due to error")

    return "OpenAI transformer tests completed!"

def test_anthropic_transformer():
    """Test the Anthropic transformer with various message types."""
    print_section("TESTING ANTHROPIC TRANSFORMER")

    # 1. Basic user message
    user_msg = Message.user_message("Hello, can you help me with something?")
    anthropic_user = TransformerRegistry.transform(user_msg, MESSAGE_FORMAT_ANTHROPIC)
    print_result("1. Basic User Message", anthropic_user)

    # 2. System message (becomes assistant in Anthropic)
    system_msg = Message.system_message("You are a helpful assistant.")
    anthropic_system = TransformerRegistry.transform(system_msg, MESSAGE_FORMAT_ANTHROPIC)
    print_result("2. System Message (as Assistant)", anthropic_system)

    # 3. Assistant message with tool calls (tool_use in Anthropic)
    tool_call = create_test_tool_call()
    assistant_msg = Message.assistant_message(
        content="I'll check the weather for you.",
        tool_calls=[tool_call]
    )
    anthropic_assistant = TransformerRegistry.transform(assistant_msg, MESSAGE_FORMAT_ANTHROPIC)
    print_result("3. Assistant Message with Tool Calls (tool_use)", anthropic_assistant)

    # 4. Tool message (tool_result in Anthropic)
    tool_msg = Message.tool_message(
        content='{"temperature": 22, "condition": "sunny"}',
        name="get_weather",
        tool_call_id=tool_call.id
    )
    anthropic_tool = TransformerRegistry.transform(tool_msg, MESSAGE_FORMAT_ANTHROPIC)
    print_result("4. Tool Message (tool_result)", anthropic_tool)

    # 5. Message with image
    base64_img = get_test_image()
    img_msg = Message.user_message(
        content="What's in this image?",
        base64_image=base64_img
    )
    anthropic_img = TransformerRegistry.transform(img_msg, MESSAGE_FORMAT_ANTHROPIC)
    # Truncate the image data for display
    for item in anthropic_img["content"]:
        if item.get("type") == "image" and "source" in item:
            item["source"]["data"] = item["source"]["data"][:50] + "..."
    print_result("5. Message with Image", anthropic_img)

    # 6. Enhanced message with multiple content types
    try:
        enhanced_msg = EnhancedMessage(
            role=Role.ASSISTANT,
            content="Here's information about the weather:",
            id=str(uuid.uuid4())  # Explicitly provide ID
        )

        try:
            # Try to add image, catch any specific errors
            enhanced_msg.add_image(base64_img, "Weather map")
        except Exception as img_error:
            print(f"Note: Could not add image to enhanced message: {img_error}")

        anthropic_enhanced = TransformerRegistry.transform(enhanced_msg, MESSAGE_FORMAT_ANTHROPIC)
        # Truncate image data for display
        for item in anthropic_enhanced["content"]:
            if item.get("type") == "image" and "source" in item:
                item["source"]["data"] = item["source"]["data"][:50] + "..."
        print_result("6. Enhanced Message with Multiple Content", anthropic_enhanced)
    except Exception as e:
        print_result("6. Enhanced Message Test", f"Error: {e}")
        print("Skipping Anthropic enhanced message test due to error")

    return "Anthropic transformer tests completed!"

def test_ollama_transformer():
    """Test the Ollama transformer with various message types."""
    print_section("TESTING OLLAMA TRANSFORMER")

    # 1. Basic user message
    user_msg = Message.user_message("Hello, can you help me with something?")
    ollama_user = TransformerRegistry.transform(user_msg, MESSAGE_FORMAT_OLLAMA)
    print_result("1. Basic User Message", ollama_user)

    # 2. System message
    system_msg = Message.system_message("You are a helpful assistant.")
    ollama_system = TransformerRegistry.transform(system_msg, MESSAGE_FORMAT_OLLAMA)
    print_result("2. System Message", ollama_system)

    # 3. Assistant message with tool calls
    tool_call = create_test_tool_call()
    assistant_msg = Message.assistant_message(
        content="I'll check the weather for you.",
        tool_calls=[tool_call]
    )
    ollama_assistant = TransformerRegistry.transform(assistant_msg, MESSAGE_FORMAT_OLLAMA)
    print_result("3. Assistant Message with Tool Calls", ollama_assistant)

    # 4. Tool message
    tool_msg = Message.tool_message(
        content='{"temperature": 22, "condition": "sunny"}',
        name="get_weather",
        tool_call_id=tool_call.id
    )
    ollama_tool = TransformerRegistry.transform(tool_msg, MESSAGE_FORMAT_OLLAMA)
    print_result("4. Tool Message", ollama_tool)

    # 5. Message with image
    base64_img = get_test_image()
    img_msg = Message.user_message(
        content="What's in this image?",
        base64_image=base64_img
    )
    ollama_img = TransformerRegistry.transform(img_msg, MESSAGE_FORMAT_OLLAMA)
    # Truncate the image data for display
    if "images" in ollama_img and ollama_img["images"]:
        ollama_img["images"][0] = ollama_img["images"][0][:50] + "..."
    print_result("5. Message with Image", ollama_img)

    # 6. Enhanced message with multiple content types
    try:
        enhanced_msg = EnhancedMessage(
            role=Role.ASSISTANT,
            content="Here's information about the weather:",
            id=str(uuid.uuid4())  # Explicitly provide ID
        )

        try:
            # Try to add image, catch any specific errors
            enhanced_msg.add_image(base64_img, "Weather map")
        except Exception as img_error:
            print(f"Note: Could not add image to enhanced message: {img_error}")

        ollama_enhanced = TransformerRegistry.transform(enhanced_msg, MESSAGE_FORMAT_OLLAMA)
        # Truncate image data for display
        if "images" in ollama_enhanced and ollama_enhanced["images"]:
            ollama_enhanced["images"][0] = ollama_enhanced["images"][0][:50] + "..."
        print_result("6. Enhanced Message with Multiple Content", ollama_enhanced)
    except Exception as e:
        print_result("6. Enhanced Message Test", f"Error: {e}")
        print("Skipping Ollama enhanced message test due to error")

    return "Ollama transformer tests completed!"

def test_conversation_flow():
    """Test a complete conversation flow through all transformers."""
    print_section("TESTING COMPLETE CONVERSATION FLOW")

    # Create a simple conversation
    conversation = [
        Message.system_message("You are a helpful weather assistant."),
        Message.user_message("What's the weather like in San Francisco?"),
        Message.assistant_message(
            content="I'll check that for you.",
            tool_calls=[create_test_tool_call()]
        ),
        Message.tool_message(
            content='{"temperature": 22, "condition": "sunny"}',
            name="get_weather",
            tool_call_id="123",
        ),
        Message.assistant_message("It's currently 22°C and sunny in San Francisco."),
    ]

    # Transform the whole conversation with each transformer
    for msg_format in [MESSAGE_FORMAT_OPENAI, MESSAGE_FORMAT_ANTHROPIC, MESSAGE_FORMAT_OLLAMA]:
        format_name = msg_format.upper()
        print_result(f"Conversation in {format_name} Format",
                    [TransformerRegistry.transform(msg, msg_format) for msg in conversation])

    return "Conversation flow test completed!"

def test_validation():
    """Test validation functionality in transformers."""
    print_section("TESTING VALIDATION")

    validation_results = []

    # Test 1: Invalid tool message
    try:
        # Create an invalid tool message (missing required fields)
        invalid_tool = Message.tool_message(
            content="Result",
            name="",  # Missing name
            tool_call_id="",  # Missing tool_call_id
        )
        # Try to transform it - should raise ValueError
        TransformerRegistry.transform(invalid_tool, MESSAGE_FORMAT_OLLAMA)
        validation_results.append("❌ FAILED: Expected ValueError for invalid tool message")
    except Exception as e:
        validation_results.append(f"✅ PASSED: Correctly caught validation error: {e}")

    # Test 2: Message with no role
    try:
        # Try to create message with invalid role - should fail validation
        invalid_msg = Message(
            role="",  # Empty role
            content="Test message"
        )
        # Try to transform it
        TransformerRegistry.transform(invalid_msg, MESSAGE_FORMAT_ANTHROPIC)
        validation_results.append("❌ FAILED: Expected error for message with no role")
    except Exception as e:
        validation_results.append(f"✅ PASSED: Correctly caught validation error: {e}")

    # Print all validation results
    for result in validation_results:
        print(result)

    return "Validation tests completed!"

# Run the tests
if __name__ == "__main__":
    print("\nEnterpriseAI Message Transformer Test\n")

    # Run each test and collect results
    results = []

    # Create simplified test function to catch and log all errors
    def run_test(test_fn, test_name):
        try:
            result = test_fn()
            results.append(result)
            return True
        except Exception as e:
            error_msg = f"{test_name} failed: {str(e)}"
            print(f"\n❌ ERROR: {error_msg}")
            import traceback
            print(traceback.format_exc())
            results.append(error_msg)
            return False

    # Run all tests with better error handling
    run_test(test_openai_transformer, "OpenAI transformer tests")
    run_test(test_anthropic_transformer, "Anthropic transformer tests")
    run_test(test_ollama_transformer, "Ollama transformer tests")
    run_test(test_conversation_flow, "Conversation flow tests")
    run_test(test_validation, "Validation tests")

    # Print summary
    print_section("TEST SUMMARY")
    for result in results:
        print(result)

    print("\nTests completed!")
