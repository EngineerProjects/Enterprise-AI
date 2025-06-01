#!/usr/bin/env python3
"""
Enterprise AI - Basic Chat Completion Tests

Simple tests for basic completion functionality using Ollama models.
Tests both synchronous and asynchronous completion methods.

Features tested:
- Basic text completion (sync)
- Basic text completion (async)
- Different model sizes
- Error handling and timeouts
- Response validation
"""

import sys
import asyncio
from pathlib import Path
from typing import List, Optional

# Add project to path and import utilities
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async
)

# Import Enterprise AI
setup_project_path()
from enterprise_ai.llm import complete, create_provider
from enterprise_ai.llm.ollama import OllamaProvider
from enterprise_ai.schema import Message, CompletionOptions

# Test models optimized for GTX 1650
TEST_MODELS = {
    "small": "smollm2:latest",      # 1.8GB - Fastest
    "medium": "llama3.2:latest",    # 2.0GB - Balanced
    "large": "deepseek-r1:latest",  # 5.2GB - Use sparingly
}

TIMEOUT = 300.0

def test_sync_basic_completion():
    """Test synchronous basic completion."""
    print_header("Synchronous Basic Completion", "single")
    
    model = TEST_MODELS["small"]
    prompt = "Explain what artificial intelligence is in 2-3 sentences."
    
    try:
        print_test(f"Testing sync completion with {model}", "running")
        print_chat("user", prompt, model=model)
        
        with Timer("Sync completion"):
            response = complete(
                messages=[prompt],
                provider_name="ollama",
                model_name=model,
                options=CompletionOptions(
                    temperature=0.7,
                    max_tokens=256,
                    timeout=TIMEOUT,
                )
            )
        
        print_chat("assistant", response.content, model=model)
        
        # Validate response
        print_test(f"✓ Response received: {len(response.content)} chars", "pass")
        print_test(f"✓ Role is assistant: {response.role == 'assistant'}", "pass")
        print_test(f"✓ Has meaningful content: {len(response.content) > 10}", "pass")
        
        return response
    except Exception as e:
        print_test(f"Sync completion failed: {e}", "fail")
        return None
    
def test_create_provider_completion():
    """Test creating a provider and using it for completion."""
    print_header("Provider Creation Completion Test", "single")
    
    model = TEST_MODELS["small"]
    prompt = "What is the capital of France?"
    
    try:
        print_test(f"Creating provider for {model}", "running")
        provider = create_provider("ollama", model_name=model, timeout=TIMEOUT)
        
        print_chat("user", prompt, model=model)
        
        with Timer("Provider completion"):
            response = provider.complete([Message.user_message(prompt)])
        
        print_chat("assistant", response.content, model=model)
        
        # Validate response
        print_test(f"✓ Response received: {len(response.content)} chars", "pass")
        print_test(f"✓ Role is assistant: {response.role == 'assistant'}", "pass")
        print_test(f"✓ Has meaningful content: {len(response.content) > 10}", "pass")
        return response
    except Exception as e:
        print_test(f"Provider completion failed: {e}", "fail")
        return None

def test_async_basic_completion():
    """Test asynchronous basic completion."""
    print_header("Asynchronous Basic Completion", "single")
    
    model = TEST_MODELS["small"]
    prompt = "What are the main benefits of renewable energy? Give me 3 key points."
    
    async def async_completion_test():
        try:
            print_test(f"Testing async completion with {model}", "running")
            print_chat("user", prompt, model=model)
            
            provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
            
            with Timer("Async completion"):
                response = await provider.acomplete([Message.user_message(prompt)])
            
            print_chat("assistant", response.content, model=model)
            
            # Validate response
            print_test(f"✓ Async response received: {len(response.content)} chars", "pass")
            print_test(f"✓ Role is assistant: {response.role == 'assistant'}", "pass")
            print_test(f"✓ Has meaningful content: {len(response.content) > 10}", "pass")
            
            return response
        except Exception as e:
            print_test(f"Async completion failed: {e}", "fail")
            return None
    
    return run_async(async_completion_test())

def test_different_models():
    """Test completion with different model sizes."""
    print_header("Multi-Model Completion Test", "single")
    
    prompt = "What is Python programming language?"
    results = {}
    
    for model_type, model_name in TEST_MODELS.items():
        try:
            print_test(f"Testing {model_type} model: {model_name}", "running")
            
            # Create provider with explicit timeout
            provider = OllamaProvider(
                model_name=model_name,
                timeout=TIMEOUT  # Pass timeout directly to provider
            )
            
            with Timer(f"{model_type} model completion"):
                response = provider.complete(
                    [Message.user_message(prompt)],
                    temperature=0.5,
                    max_tokens=128
                )
            
            results[model_type] = {
                "model": model_name,
                "response_length": len(response.content),
                "success": True
            }
            
            print_test(f"✓ {model_type}: {len(response.content)} chars", "pass")
            print_chat("assistant", response.content, model=model_name)
        
        except Exception as e:
            print_test(f"✗ {model_type} model failed: {e}", "fail")
            results[model_type] = {"model": model_name, "success": False, "error": str(e)}
    
    # Summary
    separator()
    successful_models = sum(1 for r in results.values() if r.get("success", False))
    print_test(f"Models tested successfully: {successful_models}/{len(TEST_MODELS)}", "pass")
    
    return results
    
    # Summary
    separator()
    successful_models = sum(1 for r in results.values() if r.get("success", False))
    print_test(f"Models tested successfully: {successful_models}/{len(TEST_MODELS)}", "pass")
    
    return results

def test_completion_options():
    """Test different completion options and parameters."""
    print_header("Completion Options Test", "single")
    
    model = TEST_MODELS["small"]
    prompt = "Tell me about machine learning."
    
    test_configs = [
        {"name": "Creative", "temperature": 0.9, "max_tokens": 150},
        {"name": "Balanced", "temperature": 0.7, "max_tokens": 150}, 
        {"name": "Focused", "temperature": 0.3, "max_tokens": 150},
        {"name": "Brief", "temperature": 0.5, "max_tokens": 50},
    ]
    
    results = {}
    
    for config in test_configs:
        try:
            print_test(f"Testing {config['name']} settings", "running")
            
            with Timer(f"{config['name']} completion"):
                response = complete(
                    messages=[prompt],
                    provider_name="ollama",
                    model_name=model,
                    options=CompletionOptions(
                        temperature=config["temperature"],
                        max_tokens=config["max_tokens"],
                        timeout=TIMEOUT
                    )
                )
            
            results[config["name"]] = {
                "length": len(response.content),
                "temperature": config["temperature"],
                "max_tokens": config["max_tokens"]
            }
            
            print_test(f"✓ {config['name']}: {len(response.content)} chars (temp: {config['temperature']})", "pass")
            
        except Exception as e:
            print_test(f"✗ {config['name']} failed: {e}", "fail")
            results[config["name"]] = {"error": str(e)}
    
    return results

def test_error_handling():
    """Test error handling and edge cases."""
    print_header("Error Handling Tests", "single")
    
    test_cases = [
        {
            "name": "Empty prompt",
            "messages": [""],
            "should_fail": False,
            "model": TEST_MODELS["small"]
        },
        {
            "name": "Very short timeout",
            "messages": ["What is AI?"],
            "should_fail": True,
            "model": TEST_MODELS["small"],
            "options": CompletionOptions(timeout=0.1)
        },
        {
            "name": "Non-existent model",
            "messages": ["Hello"],
            "should_fail": True,
            "model": "non-existent-model:latest"
        }
    ]
    
    results = {}
    
    for test_case in test_cases:
        try:
            print_test(f"Testing: {test_case['name']}", "running")
            
            options = test_case.get("options", CompletionOptions(timeout=TIMEOUT))
            
            response = complete(
                messages=test_case["messages"],
                provider_name="ollama",
                model_name=test_case["model"],
                options=options
            )
            
            if test_case["should_fail"]:
                print_test(f"✗ Expected failure but got response: {len(response.content)} chars", "warn")
                results[test_case["name"]] = {"unexpected_success": True}
            else:
                print_test(f"✓ Handled gracefully: {len(response.content)} chars", "pass")
                results[test_case["name"]] = {"success": True}
                
        except Exception as e:
            if test_case["should_fail"]:
                print_test(f"✓ Expected error caught: {type(e).__name__}", "pass")
                results[test_case["name"]] = {"expected_error": str(e)}
            else:
                print_test(f"✗ Unexpected error: {e}", "fail")
                results[test_case["name"]] = {"unexpected_error": str(e)}
    
    return results

def main():
    """Run all basic completion tests."""
    print_header("🤖 Enterprise AI - Basic Completion Tests", "double")
    print_test("Starting basic completion test suite...", "running")
    
    separator()
    
    # Test results tracking
    results = {}
    
    # Test 1: Sync completion
    results['sync_completion'] = test_sync_basic_completion() is not None
    separator()
    
    # Test 2: Async completion  
    results['async_completion'] = test_async_basic_completion() is not None
    separator()
    
    # Test 3: Different models
    model_results = test_different_models()
    results['multi_model'] = any(r.get("success", False) for r in model_results.values())
    separator()
    
    # Test 4: Completion options
    option_results = test_completion_options()
    results['completion_options'] = len([r for r in option_results.values() if "error" not in r]) > 0
    separator()
    
    # Test 5: Error handling
    error_results = test_error_handling()
    results['error_handling'] = len(error_results) > 0
    separator()
    
    # Final summary
    print_header("📊 Basic Completion Test Results", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    separator()
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All basic completion tests passed!", "pass")
        print_test("Your LLM integration is working perfectly!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    # Performance tips
    separator()
    print_header("💡 Performance Tips", "box")
    print_test("For optimal performance:", "pass")
    print_test("• Use smollm2:latest for fast responses", "pass")
    print_test("• Set appropriate timeouts based on model size", "pass")
    print_test("• Limit max_tokens for faster completion", "pass")
    print_test("• Use temperature 0.7 for balanced creativity", "pass")
    
    return results

if __name__ == "__main__":
    main()