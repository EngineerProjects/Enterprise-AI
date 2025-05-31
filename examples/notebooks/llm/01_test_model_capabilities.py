"""
Simple Model Capabilities Test

This test file shows how to:
- Create different LLM providers
- Detect what capabilities each model has
- Test basic model information retrieval

Everything is explicit and easy to understand.
"""

import sys
import os

# Add project path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Import what we need
from enterprise_ai.llm import create_provider, get_default_provider
from enterprise_ai.schema import Message
from examples.notebooks.utils import (
    print_title, print_section, print_info, print_success, print_error,
    detect_model_capabilities
)

def test_model_capabilities():
    """Test model capabilities detection."""
    print_title("Model Capabilities Test")
    
    # Test 1: Create a basic provider
    print_section("Creating Basic Provider")
    try:
        provider = create_provider(
            "ollama",
            model_name="llama3.2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
        print_success(f"✓ Created provider with model: {provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Test 2: Detect capabilities
    print_section("Detecting Capabilities")
    try:
        capabilities = detect_model_capabilities(provider)
        print_info("Detected capabilities:")
        for feature, supported in capabilities.items():
            status = "✓ YES" if supported else "✗ NO"
            print_info(f"  {feature}: {status}")
    except Exception as e:
        print_error(f"✗ Failed to detect capabilities: {e}")
    
    # Test 3: Get model information
    print_section("Getting Model Information")
    try:
        model_info = provider.get_model_info()
        print_info(f"Context window: {model_info.context_window:,} tokens")
        print_info(f"Max tokens: {model_info.max_tokens:,}")
        print_info(f"Features: {', '.join(model_info.features)}")
        print_success("✓ Model information retrieved successfully")
    except Exception as e:
        print_error(f"✗ Failed to get model info: {e}")
    
    # Test 4: Try vision model
    print_section("Testing Vision Model")
    try:
        vision_provider = create_provider(
            "ollama",
            model_name="llava",
            base_url="http://localhost:11434",
            timeout=600.0
        )
        print_success(f"✓ Created vision provider: {vision_provider.get_model_name()}")
        
        # Check vision capabilities
        vision_caps = detect_model_capabilities(vision_provider)
        if vision_caps.get("vision", False):
            print_success("✓ Vision capabilities confirmed")
        else:
            print_info("○ No vision capabilities detected")
            
    except Exception as e:
        print_error(f"✗ Vision model not available: {e}")
    
    # Test 5: Get default provider
    print_section("Testing Default Provider")
    try:
        default_provider = get_default_provider()
        print_success(f"✓ Default provider: {default_provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Default provider failed: {e}")

if __name__ == "__main__":
    test_model_capabilities()