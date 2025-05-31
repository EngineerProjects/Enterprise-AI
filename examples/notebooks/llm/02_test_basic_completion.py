"""
Simple Basic Completion Test

This test file shows how to:
- Create a provider
- Make basic completion requests
- Test sync and async completion
- Use different completion options
- Proper resource management

Everything you need to know about basic completion is here.
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
    print_title, print_section, print_info, print_success, print_error,
    print_user, print_assistant, Timer, AsyncTimer
)

def test_basic_completion():
    """Test basic completion functionality."""
    print_title("Basic Completion Test")
    
    provider = None
    try:
        # Step 1: Create provider
        print_section("Creating Provider")
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
        print_success(f"✓ Provider created: {provider.get_model_name()}")
        
        # Step 2: Simple completion test
        print_section("Simple Completion")
        try:
            # Create messages
            messages = [
                Message.system_message("You are a helpful AI assistant."),
                Message.user_message("What is artificial intelligence?")
            ]
            
            # Make completion request
            with Timer("Completion time"):
                response = provider.complete(messages)
            
            # Show the conversation
            print_user("What is artificial intelligence?")
            print_assistant(response.content)
            print_success("✓ Basic completion successful")
            
        except Exception as e:
            print_error(f"✗ Basic completion failed: {e}")
        
        # Step 3: Test with options
        print_section("Completion with Options")
        try:
            messages = [Message.user_message("Write a very short poem about cats.")]
            
            # Test with specific parameters
            response = provider.complete(
                messages,
                temperature=0.7,
                max_tokens=100
            )
            
            print_user("Write a very short poem about cats.")
            print_assistant(response.content)
            print_success("✓ Completion with options successful")
            
        except Exception as e:
            print_error(f"✗ Completion with options failed: {e}")
        
        # Step 4: Test with different temperature
        print_section("Completion with Different Temperature")
        try:
            messages = [Message.user_message("Say hello in a creative way.")]
            
            response = provider.complete(
                messages,
                temperature=0.9,
                max_tokens=50
            )
            
            print_user("Say hello in a creative way.")
            print_assistant(response.content)
            print_success("✓ Creative completion successful")
            
        except Exception as e:
            print_error(f"✗ Creative completion failed: {e}")
    
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
    
    finally:
        # Cleanup
        if provider:
            try:
                provider.close()
                print_info("Provider resources cleaned up")
            except Exception as e:
                print_error(f"Error cleaning up provider: {e}")

async def test_async_completion():
    """Test async completion functionality."""
    print_section("Async Completion")
    
    provider = None
    try:
        # Create provider
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
        
        # Test async completion
        messages = [Message.user_message("Explain quantum computing in one sentence.")]
        
        async with AsyncTimer("Async completion time"):
            response = await provider.acomplete(messages)
        
        print_user("Explain quantum computing in one sentence.")
        print_assistant(response.content)
        print_success("✓ Async completion successful")
        
        # Test async completion with options
        print_section("Async Completion with Options")
        messages = [Message.user_message("What is the meaning of life?")]
        
        response = await provider.acomplete(
            messages,
            temperature=0.5,
            max_tokens=75
        )
        
        print_user("What is the meaning of life?")
        print_assistant(response.content)
        print_success("✓ Async completion with options successful")
        
    except Exception as e:
        print_error(f"✗ Async completion failed: {e}")
    
    finally:
        # Cleanup async resources
        if provider:
            try:
                await provider.aclose()
                print_info("Async provider resources cleaned up")
            except Exception as e:
                print_error(f"Error cleaning up async provider: {e}")

def test_resource_management():
    """Test proper resource management."""
    print_section("Resource Management Test")
    
    try:
        # Create multiple providers to test resource handling
        providers = []
        
        for i in range(3):
            provider = create_provider(
                "ollama",
                model_name="smollm2",
                base_url="http://localhost:11434",
                timeout=300.0
            )
            providers.append(provider)
            
            # Quick test
            messages = [Message.user_message(f"Test message {i+1}")]
            response = provider.complete(messages, max_tokens=10)
            print_info(f"Provider {i+1} response: {response.content}")
        
        # Clean up all providers
        for i, provider in enumerate(providers):
            provider.close()
            print_info(f"Provider {i+1} closed")
        
        print_success("✓ Resource management test successful")
        
    except Exception as e:
        print_error(f"✗ Resource management test failed: {e}")

def run_all_tests():
    """Run all basic completion tests."""
    # Sync tests
    test_basic_completion()
    
    # Resource management test
    test_resource_management()
    
    # Async tests (in separate event loop)
    try:
        asyncio.run(test_async_completion())
    except Exception as e:
        print_error(f"✗ Async tests failed: {e}")

if __name__ == "__main__":
    run_all_tests()