#!/usr/bin/env python
"""
Enterprise AI Memory System Examples

This notebook demonstrates working with the conversation memory system for:
- Creating different types of memory implementations
- Managing conversation history with LLM models
- Using image support in multimodal conversations
- Testing sliding window memory with conversation pruning
"""

import os
import sys
from typing import Optional, List, Dict, Any, Union

# Import common utilities
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    print_user,
    print_assistant,
    print_system,
    separator,
    Timer,
    encode_image_to_base64,
    find_image_in_directory,
    create_test_image,
    detect_model_capabilities,
    get_image_path
)

# Set up project path
project_root = setup_project_path()

# Import enterprise_ai modules
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.schema.memory import (
    ConversationMemory,
    InMemoryConversation,
    SlidingWindowConversation,
    ConversationMemoryFactory
)
from enterprise_ai.schema.message import Message
from enterprise_ai.schema.image import add_image_to_message

# Configuration - modify these to match your environment
CONFIG = {
    "default_model": "smollm2",      # Default small model for basic tests
    "vision_model": "llava",         # Vision-capable model (if available)
    "base_url": "http://localhost:11434",
    "timeout": 500.0,                 # Default timeout in seconds
}

def initialize_provider(model_name: str = None, timeout: float = None):
    """Initialize and test an Ollama provider."""
    # Use default values from CONFIG if not specified
    model_name = model_name or CONFIG["default_model"]
    timeout = timeout or CONFIG["timeout"]

    print_info(f"Initializing Ollama provider with model: {model_name}")

    try:
        provider = OllamaProvider(
            model_name=model_name,
            base_url=CONFIG["base_url"],
            timeout=timeout
        )

        print_success("Provider initialized successfully!")
        return provider
    except Exception as e:
        print_error(f"Provider initialization failed: {e}")
        raise

def test_basic_memory():
    """Test basic in-memory conversation memory."""
    print_section("Basic Memory Test")

    # Initialize provider
    provider = initialize_provider()

    # Initialize memory with system prompt
    memory = InMemoryConversation(
        system_prompt="You are a helpful AI assistant. Keep your responses concise and informative."
    )

    # Show initial state
    messages = memory.get_messages()
    print_info(f"Initial memory state: {len(messages)} messages")
    for i, msg in enumerate(messages):
        if msg.role == "system":
            print_system(f"[{i}] {msg.content}")

    # Add a user message
    print_info("\nAdding user message...")
    user_query = "What are the three fundamental data structures in computer science?"
    memory.add_user_message(user_query)
    print_user(user_query)

    # Get messages for LLM
    messages = memory.get_messages()
    print_info(f"Messages for LLM: {len(messages)}")
    print_info(f"Estimated token count: {memory.get_token_count()}")

    # Generate response
    print_info("\nGenerating response...")
    with Timer("Response generation"):
        response = provider.complete(messages)

    # Add response to memory
    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Add a follow-up question
    print_info("\nAdding follow-up question...")
    follow_up = "Can you explain linked lists in more detail?"
    memory.add_user_message(follow_up)
    print_user(follow_up)

    # Get updated messages
    messages = memory.get_messages()
    print_info(f"Updated messages for LLM: {len(messages)}")
    print_info(f"Estimated token count: {memory.get_token_count()}")

    # Generate response to follow-up
    print_info("\nGenerating response to follow-up...")
    with Timer("Response generation"):
        response = provider.complete(messages)

    # Add response to memory
    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Add context-dependent question
    print_info("\nAdding context-dependent question...")
    context_question = "What are their advantages over arrays?"
    memory.add_user_message(context_question)
    print_user(context_question)

    # Get updated messages
    messages = memory.get_messages()
    print_info(f"Final messages for LLM: {len(messages)}")
    print_info(f"Estimated token count: {memory.get_token_count()}")

    # Generate response to context-dependent question
    print_info("\nGenerating response to context-dependent question...")
    with Timer("Response generation"):
        response = provider.complete(messages)

    # Add response to memory
    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Show final conversation state
    print_info("\nFinal conversation state:")
    for i, msg in enumerate(memory.get_messages()):
        if msg.role == "system":
            print_system(f"[{i}] {msg.content}")
        elif msg.role == "user":
            print_user(f"[{i}] {msg.content}")
        elif msg.role == "assistant":
            print_assistant(f"[{i}] {msg.content}")

    # Test memory clearing
    print_info("\nClearing memory...")
    memory.clear()
    print_info(f"Messages after clearing: {len(memory.get_messages())}")

    return provider

def test_memory_with_image(base_provider):
    """Test conversation memory with image support."""
    print_section("Memory with Image Support Test")

    # Check if we can use a vision model
    vision_capabilities = None
    vision_provider = None

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
            return

    print_info(f"Using image: {image_path}")

    try:
        # Try to use a vision model
        vision_provider = initialize_provider(CONFIG["vision_model"], CONFIG["timeout"] * 2)
        vision_capabilities = detect_model_capabilities(vision_provider)

        if not vision_capabilities.get("vision", False):
            print_warning(f"Model {CONFIG['vision_model']} doesn't support vision.")
            vision_provider = None
    except Exception as e:
        print_warning(f"Could not initialize vision model: {e}")
        vision_provider = None

    # Fall back to the base provider if vision provider not available
    provider = vision_provider or base_provider
    can_process_images = vision_capabilities.get("vision", False) if vision_provider else False

    if not can_process_images:
        print_warning("Using a model without vision capabilities. It won't process the image content.")

    # Initialize memory with system prompt
    memory = SlidingWindowConversation(
        system_prompt="You are a helpful AI assistant. If you receive an image, describe it in detail.",
        max_messages=10
    )

    # Add initial message
    print_info("\nStarting conversation...")
    user_message = "Hello, I'm going to share an image with you in my next message."
    memory.add_user_message(user_message)
    print_user(user_message)

    # Generate response
    with Timer("Response generation"):
        response = provider.complete(memory.get_messages())

    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Create message with image
    print_info("\nAdding message with image...")
    user_question = "What do you see in this image?"

    # Create a new message
    msg = Message.user_message(user_question)

    # Encode the image and add to message
    encoded_image = encode_image_to_base64(image_path, (400, 268))
    if encoded_image:
        # Initialize metadata if not present
        if not msg.metadata:
            msg.metadata = {}

        # Add the encoded image
        if "images" not in msg.metadata:
            msg.metadata["images"] = []

        msg.metadata["images"].append(encoded_image)
        print_success("Image added to message metadata")
    else:
        print_error("Failed to encode image")

    # Add message to memory
    memory.add_message(msg)
    print_user(user_question, images=1)

    # Generate response
    print_info("\nGenerating response to image message...")
    with Timer("Response generation"):
        response = provider.complete(memory.get_messages())

    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Add follow-up about the image
    print_info("\nAdding follow-up question about the image...")
    follow_up = "Can you tell me more about what you see in the image?"
    memory.add_user_message(follow_up)
    print_user(follow_up)

    # Check if image is still in context
    image_in_context = False
    for msg in memory.get_messages():
        if msg.metadata and "images" in msg.metadata and msg.metadata["images"]:
            image_in_context = True
            break

    print_info(f"Image still in conversation context: {image_in_context}")

    # Generate response to follow-up
    print_info("\nGenerating response to follow-up...")
    with Timer("Response generation"):
        response = provider.complete(memory.get_messages())

    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Show final memory state
    print_info("\nFinal memory state:")
    for i, msg in enumerate(memory.get_messages()):
        # Check if message has an image
        has_image = msg.metadata and "images" in msg.metadata and msg.metadata["images"]

        if msg.role == "system":
            print_system(f"[{i}] {msg.content}")
        elif msg.role == "user":
            print_user(f"[{i}] {msg.content}", images=1 if has_image else 0)
        elif msg.role == "assistant":
            print_assistant(f"[{i}] {msg.content}")

    # Clean up vision provider if created
    if vision_provider and vision_provider != base_provider:
        vision_provider.close()

def test_sliding_window_memory():
    """Test sliding window conversation memory."""
    print_section("Sliding Window Memory Test")

    # Initialize provider
    provider = initialize_provider()

    # Initialize memory with very small window to demonstrate pruning
    memory = SlidingWindowConversation(
        system_prompt="You are a helpful AI assistant.",
        max_messages=2  # Very small window for testing
    )

    # Find an image from the specified collection (use a different one than before if possible)
    image_path = find_image_in_directory(
        specific_images=['logo2.png', 'paysage.jpg', 'familly.jpg', 'indian_love.jpg', 'animaux.jpg'],
        target_size=(400, 268)
    )

    # Start with an image message
    if image_path:
        print_info("Starting conversation with an image message...")
        user_message = "Hello, here's an image!"

        # Create and add message with image
        msg = Message.user_message(user_message)
        encoded_image = encode_image_to_base64(image_path, (400, 268))

        if encoded_image:
            if not msg.metadata:
                msg.metadata = {}
            if "images" not in msg.metadata:
                msg.metadata["images"] = []
            msg.metadata["images"].append(encoded_image)

            memory.add_message(msg)
            print_user(user_message, images=1)
        else:
            memory.add_user_message(user_message)
            print_user(user_message)
    else:
        print_warning("No image available for testing.")
        user_message = "Hello, I'm starting a conversation that will test sliding window behavior."
        memory.add_user_message(user_message)
        print_user(user_message)

    # Get response
    response = provider.complete(memory.get_messages())
    memory.add_assistant_message(response.content or "")
    print_assistant(response.content)

    # Count messages with images before sliding window
    images_before = sum(
        1 for msg in memory.get_messages()
        if msg.metadata and "images" in msg.metadata and msg.metadata["images"]
    )
    print_info(f"\nMessages with images before window slides: {images_before}")

    # Add more messages to force window sliding
    print_info("\nAdding messages to trigger sliding window behavior...")

    for i in range(3):
        # Add user message
        user_message = f"This is message {i+1} to push out older messages."
        memory.add_user_message(user_message)
        print_user(user_message)

        # Get response
        response = provider.complete(memory.get_messages())
        memory.add_assistant_message(response.content or "")
        print_assistant(response.content)

    # Count messages with images after sliding window
    images_after = sum(
        1 for msg in memory.get_messages()
        if msg.metadata and "images" in msg.metadata and msg.metadata["images"]
    )
    print_info(f"\nMessages with images after window slides: {images_after}")

    # Check if sliding window properly pruned the image
    if images_before > 0 and images_after == 0:
        print_success("Sliding window correctly pruned the message with image")
    elif images_after > 0:
        print_warning("Sliding window did not prune the message with image")
    else:
        print_warning("Image was not properly added to begin with")

    # Show final memory state
    print_info("\nFinal memory state (should only have recent messages):")
    for i, msg in enumerate(memory.get_messages()):
        # Check if message has an image
        has_image = msg.metadata and "images" in msg.metadata and msg.metadata["images"]

        if msg.role == "system":
            print_system(f"[{i}] {msg.content}")
        elif msg.role == "user":
            print_user(f"[{i}] {msg.content}", images=1 if has_image else 0)
        elif msg.role == "assistant":
            print_assistant(f"[{i}] {msg.content}")

    provider.close()

def test_memory_factory():
    """Test the ConversationMemoryFactory for creating different memory types."""
    print_section("Conversation Memory Factory Test")

    # Create different types of memory
    print_info("Creating different memory implementations...")

    # Basic in-memory conversation
    basic_memory = ConversationMemoryFactory.create(
        memory_type="memory",
        system_prompt="You are a helpful assistant."
    )

    # Sliding window memory
    sliding_memory = ConversationMemoryFactory.create(
        memory_type="sliding_window",
        system_prompt="You are a helpful assistant.",
        max_messages=15,
        max_tokens=4000
    )

    print_success("Created multiple memory implementations")

    # Test basic properties
    print_info("\nTesting basic memory properties:")
    basic_memory.add_user_message("Hello, how are you?")
    basic_memory.add_assistant_message("I'm doing well, thank you for asking!")
    basic_memory.add_user_message("Tell me about conversation memory.")

    print_info(f"Basic memory message count: {len(basic_memory.get_messages())}")
    print_info(f"Basic memory token count: {basic_memory.get_token_count()}")

    print_info("\nTesting sliding window memory properties:")
    sliding_memory.add_user_message("Hello, how are you?")
    sliding_memory.add_assistant_message("I'm doing well, thank you for asking!")
    sliding_memory.add_user_message("Tell me about conversation memory.")

    print_info(f"Sliding window memory message count: {len(sliding_memory.get_messages())}")
    print_info(f"Sliding window memory token count: {sliding_memory.get_token_count()}")
    print_info(f"Sliding window memory max messages: {sliding_memory.max_messages}")

    # Register a custom memory implementation
    print_info("\nDemonstrating how to register a custom memory implementation...")
    try:
        # This is just an example - we'd normally define a new class
        ConversationMemoryFactory.register("custom", InMemoryConversation)

        # Create an instance of our custom type
        custom_memory = ConversationMemoryFactory.create(
            memory_type="custom",
            system_prompt="I am a custom memory implementation."
        )

        print_success("Successfully registered and created custom memory type")
        print_info(f"Custom memory type: {type(custom_memory).__name__}")
        print_info(f"Custom memory system prompt: {custom_memory.get_messages()[0].content}")
    except Exception as e:
        print_error(f"Failed to register custom memory: {e}")

def main():
    """Run all memory examples."""
    print_title("Enterprise AI Memory System Examples")

    try:
        # Test basic memory
        provider = test_basic_memory()
        separator()

        # Test memory with image support
        test_memory_with_image(provider)
        separator()

        # Test sliding window memory
        test_sliding_window_memory()
        separator()

        # Test memory factory
        test_memory_factory()
        separator()

        print_success("All memory examples completed!")

    except Exception as e:
        print_error(f"Error during memory examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
