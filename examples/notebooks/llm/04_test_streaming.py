"""
Simple Streaming Test

This test file shows how to:
- Create a provider that supports streaming
- Test sync streaming
- Test async streaming
- Handle streaming chunks

Everything about streaming is demonstrated here.
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
    print_user, print_assistant, Timer, AsyncTimer, detect_model_capabilities
)

def test_streaming():
    """Test streaming completion functionality."""
    print_title("Streaming Test")
    
    # Step 1: Create provider
    print_section("Creating Provider")
    try:
        provider = create_provider(
            "ollama",
            model_name="smollm2",  # Change to a model you know supports streaming
            base_url="http://localhost:11434",
            timeout=300.0
        )
        print_success(f"✓ Provider created: {provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Step 2: Check if streaming is supported
    print_section("Checking Streaming Support")
    try:
        capabilities = detect_model_capabilities(provider)
        supports_streaming = capabilities.get("streaming", False)
        
        if supports_streaming:
            print_success("✓ Streaming is supported")
        else:
            print_warning("! Streaming not supported by this model")
            return
            
    except Exception as e:
        print_error(f"✗ Failed to check capabilities: {e}")
        return
    
    # Step 3: Test sync streaming
    print_section("Sync Streaming Test")
    try:
        messages = [Message.user_message("Write a short story about a robot learning to paint.")]
        
        print_user("Write a short story about a robot learning to paint.")
        print_assistant("", end="")  # Start assistant output
        
        chunk_count = 0
        with Timer("Streaming time"):
            for chunk in provider.complete_stream(messages):
                chunk_count += 1
                if hasattr(chunk, 'content') and chunk.content:
                    print(chunk.content, end='', flush=True)
        
        print()  # New line
        print_success(f"✓ Sync streaming successful ({chunk_count} chunks)")
        
    except Exception as e:
        print_error(f"✗ Sync streaming failed: {e}")

async def test_async_streaming():
    """Test async streaming functionality."""
    print_section("Async Streaming Test")
    
    # Create provider
    try:
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Check streaming support
    try:
        capabilities = detect_model_capabilities(provider)
        if not capabilities.get("streaming", False):
            print_warning("! Streaming not supported - skipping async test")
            return
    except Exception as e:
        print_error(f"✗ Failed to check capabilities: {e}")
        return
    
    # Test async streaming
    try:
        messages = [Message.user_message("Explain how neural networks work, step by step.")]
        
        print_user("Explain how neural networks work, step by step.")
        print_assistant("", end="")
        
        chunk_count = 0
        async with AsyncTimer("Async streaming time"):
            async for chunk in provider.acomplete_stream(messages):
                chunk_count += 1
                if hasattr(chunk, 'content') and chunk.content:
                    print(chunk.content, end='', flush=True)
        
        print()  # New line
        print_success(f"✓ Async streaming successful ({chunk_count} chunks)")
        
    except Exception as e:
        print_error(f"✗ Async streaming failed: {e}")

def test_streaming_interruption():
    """Test interrupting a stream early."""
    print_section("Streaming Interruption Test")
    
    # Create provider
    try:
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Test interruption
    try:
        messages = [Message.user_message("Write a very long essay about the history of computers.")]
        
        print_info("Starting stream and will interrupt after 5 chunks...")
        chunk_count = 0
        max_chunks = 5
        
        for chunk in provider.complete_stream(messages):
            chunk_count += 1
            if hasattr(chunk, 'content') and chunk.content:
                print(f"Chunk {chunk_count}: {chunk.content[:50]}...")
            
            if chunk_count >= max_chunks:
                print_info(f"Interrupting stream after {chunk_count} chunks")
                break
        
        print_success("✓ Stream interruption successful")
        
    except Exception as e:
        print_error(f"✗ Stream interruption failed: {e}")

def run_all_tests():
    """Run all streaming tests."""
    # Sync tests
    test_streaming()
    test_streaming_interruption()
    
    # Async tests
    asyncio.run(test_async_streaming())

if __name__ == "__main__":
    run_all_tests()