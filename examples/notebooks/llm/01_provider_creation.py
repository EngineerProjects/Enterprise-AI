#!/usr/bin/env python3
"""
Enterprise AI - Provider Creation Test Examples

This test demonstrates basic provider creation with different configurations
for both Ollama and OpenAI providers, optimized for GTX 1650 hardware.

Available Models:
- granite3.2-vision:latest (2.4 GB) - Vision capable
- deepseek-r1:latest (5.2 GB) - Large reasoning model
- smollm2:latest (1.8 GB) - Small efficient model
- llava:latest (4.7 GB) - Vision model
- llama3.2:latest (2.0 GB) - General purpose
"""

import sys
import os
import time
from pathlib import Path

# Add project to path and import utilities
sys.path.append(str(Path(__file__).parent.parent.parent))
from notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async
)

# Import Enterprise AI
setup_project_path()
from enterprise_ai.llm import create_provider, list_available_providers
from enterprise_ai.schema import CompletionOptions
from enterprise_ai.llm.ollama import OllamaProvider
from enterprise_ai.llm.openai import OpenAIProvider

def test_available_providers():
    """Test listing available providers."""
    print_header("Available LLM Providers", "box")
    
    try:
        providers = list_available_providers()
        for name, description in providers.items():
            print_test(f"{name}: {description}", "pass")
        return True
    except Exception as e:
        print_test(f"Failed to list providers: {e}", "fail")
        return False

def test_ollama_basic_creation():
    """Test basic Ollama provider creation."""
    print_header("Ollama Provider - Basic Creation", "single")
    
    # Test with smallest model first (good for GTX 1650)
    model = "smollm2:latest"
    
    try:
        print_test(f"Creating provider for {model}", "running")
        
        with Timer("Provider creation"):
            provider = create_provider("ollama", model)
        
        print_test(f"Provider type: {type(provider).__name__}", "pass")
        print_test(f"Model name: {provider.get_model_name()}", "pass")
        print_test(f"Base URL: {provider._base_url}", "pass")
        print_test(f"Timeout: {provider._timeout}s", "pass")
        
        return provider
    except Exception as e:
        print_test(f"Provider creation failed: {e}", "fail")
        return None

def test_ollama_advanced_configuration():
    """Test Ollama provider with advanced configuration."""
    print_header("Ollama Provider - Advanced Configuration", "single")
    
    # Configuration optimized for GTX 1650
    config = {
        "model_name": "llama3.2",
        "base_url": "http://localhost:11434",
        "timeout": 180.0,  # 3 minutes for GTX 1650
        "temperature": 0.7,
        "max_tokens": 1024,
        "top_p": 0.9
    }
    
    try:
        print_test("Creating provider with advanced config", "running")
        
        with Timer("Advanced provider creation"):
            provider = OllamaProvider(**config)
        
        # Test configuration values
        print_test(f"Model: {provider.model_name}", "pass")
        print_test(f"Timeout: {provider._timeout}s", "pass")
        
        # Test provider info
        provider_info = provider.get_provider_info()
        print_test(f"Provider name: {provider_info.name}", "pass")
        print_test(f"Features: {len(provider_info.features)}", "pass")
        
        return provider
    except Exception as e:
        print_test(f"Advanced configuration failed: {e}", "fail")
        return None

def test_ollama_vision_model():
    """Test Ollama provider with vision-capable model."""
    print_header("Ollama Provider - Vision Model", "single")
    
    # Test with vision model (be aware this is larger)
    model = "granite3.2-vision"
    
    config = {
        "model_name": model,
        "timeout": 240.0,  # 4 minutes for vision model on GTX 1650
        "temperature": 0.5,
        "max_tokens": 512,  # Smaller output for vision tasks
    }
    
    try:
        print_test(f"Creating vision provider for {model}", "running")
        
        with Timer("Vision provider creation"):
            provider = create_provider("ollama", **config)
        
        # Check if vision is detected
        model_info = provider.get_model_info()
        has_vision = "vision" in model_info.features
        
        print_test(f"Vision support detected: {has_vision}", "pass" if has_vision else "warn")
        print_test(f"Context window: {model_info.context_window}", "pass")
        print_test(f"Max tokens: {model_info.max_tokens}", "pass")
        
        return provider
    except Exception as e:
        print_test(f"Vision provider creation failed: {e}", "fail")
        return None
    
def test_deepseek_template_detection():
    """Test that deepseek-r1 template properly detects thinking."""
    print_header("DeepSeek-R1 Template Analysis", "single")
    
    try:
        provider = create_provider("ollama", "deepseek-r1:latest", timeout=60.0)
        
        # Get the raw template
        model_data = provider._fetch_model_data()
        template = model_data.get("template", "") if model_data else ""
        
        print_test(f"Template length: {len(template)} characters", "pass")
        
        # Check for thinking indicators in template
        thinking_indicators = ["IsThinkSet", "Think", "Thinking", "<think>"]
        found_indicators = [ind for ind in thinking_indicators if ind in template]
        
        print_test(f"Thinking indicators found: {len(found_indicators)}", "pass")
        for indicator in found_indicators:
            print_test(f"  ✓ {indicator}", "pass")
        
        # Test capability detection
        capabilities = provider._capabilities.detect_model_capabilities(
            "deepseek-r1:latest", 
            model_data
        )
        
        has_thinking = "thinking" in capabilities.to_feature_set()
        print_test(f"Thinking detected from template: {has_thinking}", "pass" if has_thinking else "fail")
        
        return has_thinking
    except Exception as e:
        print_test(f"Template analysis failed: {e}", "fail")
        return False

def test_openai_mock_creation():
    """Test OpenAI provider creation (mock/demo mode)."""
    print_header("OpenAI Provider - Mock Creation", "single")
    
    # Note: This will fail without API key, but shows configuration
    config = {
        "model_name": "gpt-4o-mini",
        "api_type": "openai",
        "timeout": 60.0,
        "temperature": 0.7,
        "max_tokens": 1000,
    }
    
    try:
        print_test("Creating OpenAI provider (demo)", "running")
        
        # Check for API key first
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print_test("No OPENAI_API_KEY found (expected)", "warn")
            print_test("OpenAI provider requires API key", "pass")
            return "no_api_key"  # Return special value instead of None
        
        # This will work if API key is present
        provider = OpenAIProvider(**config)
        
        print_test(f"Provider type: {type(provider).__name__}", "pass")
        print_test(f"Model: {provider.model_name}", "pass")
        print_test(f"API type: {provider.api_type}", "pass")
        print_test(f"Timeout: {provider._timeout}s", "pass")
        
        return provider
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower():
            print_test("OpenAI provider needs API key (expected)", "warn")
            print_test("Set OPENAI_API_KEY to test OpenAI functionality", "pass")
            return "no_api_key"
        else:
            print_test(f"OpenAI provider creation failed: {e}", "fail")
            return None

def test_completion_options():
    """Test CompletionOptions schema."""
    print_header("Completion Options Configuration", "single")
    
    try:
        # Create options optimized for GTX 1650
        options = CompletionOptions(
            temperature=0.8,
            max_tokens=512,  # Conservative for performance
            top_p=0.9,
            stream=False,  # Start with non-streaming
            timeout=120.0,  # 2 minutes
            extra_params={
                "repeat_penalty": 1.1,
                "top_k": 40,
            }
        )
        
        print_test("CompletionOptions created", "pass")
        print_test(f"Temperature: {options.temperature}", "pass")
        print_test(f"Max tokens: {options.max_tokens}", "pass")
        print_test(f"Extra params: {len(options.extra_params)}", "pass")
        
        # Test conversion to dict
        options_dict = options.to_dict()
        print_test(f"Dict conversion: {len(options_dict)} keys", "pass")
        
        # Test creation from dict
        recreated = CompletionOptions.from_dict(options_dict)
        print_test("Recreated from dict", "pass")
        
        return options
    except Exception as e:
        print_test(f"CompletionOptions test failed: {e}", "fail")
        return None

async def test_async_provider_creation():
    """Test async provider operations."""
    print_header("Async Provider Operations", "single")
    
    try:
        print_test("Creating async-capable provider", "running")
        
        # Use smallest model for async test
        provider = create_provider("ollama", "smollm2:latest", timeout=120.0)
        
        # Test that async client can be created
        if hasattr(provider, '_get_async_client'):
            async_client = await provider._get_async_client()
            print_test("Async client created", "pass")
        else:
            print_test("Async client not available", "warn")
        
        # Test model info (this is sync)
        model_info = provider.get_model_info()
        print_test(f"Model info retrieved: {model_info.id}", "pass")
        
        return provider
    except Exception as e:
        print_test(f"Async provider test failed: {e}", "fail")
        return None

def main():
    """Run all provider creation tests."""
    print_header("🚀 Enterprise AI - Provider Creation Tests", "double")
    print_test("Starting provider creation test suite...", "running")
    
    
    
    # Test results tracking
    results = {}
    
    # Test 1: Available providers
    results['providers'] = test_available_providers()
    
    
    # Test 2: Basic Ollama creation
    results['basic_ollama'] = test_ollama_basic_creation() is not None
    
    
    # Test 3: Advanced Ollama configuration
    results['advanced_ollama'] = test_ollama_advanced_configuration() is not None
    
    
    # Test 4: Vision model (might be slow on GTX 1650)
    results['vision_model'] = test_ollama_vision_model() is not None
    

    # Test 5: DeepSeek template detection
    results['deepseek_template'] = test_deepseek_template_detection()
    
    
    # Test 5: OpenAI mock (expected to warn without API key)
    results['openai_mock'] = test_openai_mock_creation() is not None
    
    
    # Test 6: Completion options
    results['completion_options'] = test_completion_options() is not None
    
    
    # Test 7: Async operations
    results['async_provider'] = run_async(test_async_provider_creation()) is not None
    
    
    # Final summary
    print_header("📊 Test Results Summary", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All provider creation tests completed successfully!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    return results

if __name__ == "__main__":
    main()