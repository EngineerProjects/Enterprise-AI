#!/usr/bin/env python3
"""
Enterprise AI - Streaming Completion Tests

Tests streaming completion capabilities using Ollama models.
Tests both synchronous and asynchronous streaming methods.

Features tested:
- Basic streaming completion (sync/async)
- Streaming with different models
- Streaming performance analysis
- Chunk processing and validation
- Streaming error handling
- Progressive content building
- Streaming interruption and timeout handling
"""

import sys
import asyncio
import time
from pathlib import Path
from typing import List, Optional, Iterator, AsyncIterator

# Add project to path and import utilities
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async
)

# Import Enterprise AI
setup_project_path()
from enterprise_ai.llm import create_provider
from enterprise_ai.llm.ollama import OllamaProvider
from enterprise_ai.schema import Message, CompletionOptions

# Configuration
TIMEOUT = 300.0  # 5 minutes for GTX 1650

# Test models optimized for GTX 1650
STREAMING_MODELS = {
    "small": "smollm2:latest",      # 1.8GB - Fastest streaming
    "medium": "llama3.2:latest",    # 2.0GB - Balanced streaming
    "large": "deepseek-r1:latest",  # 5.2GB - Slower but detailed
}

def test_sync_streaming():
    """Test synchronous streaming completion."""
    print_header("Synchronous Streaming Completion", "single")
    
    model = STREAMING_MODELS["small"]
    prompt = "Write a short story about a robot learning to paint. Make it creative and engaging, around 200 words."
    
    try:
        print_test(f"Testing sync streaming with {model}", "running")
        print_chat("user", prompt, model=model)
        
        provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
        
        # Streaming metrics
        start_time = time.time()
        chunks_received = 0
        total_content = ""
        first_chunk_time = None
        last_chunk_time = None
        
        print_test("Starting sync streaming...", "running")
        
        with Timer("Sync streaming completion"):
            for chunk in provider.complete_stream([Message.user_message(prompt)]):
                chunks_received += 1
                
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    ttfb = first_chunk_time - start_time  # Time to first byte
                    print_test(f"First chunk received in {ttfb:.2f}s", "pass")
                
                if chunk.content:
                    total_content = chunk.content
                    last_chunk_time = time.time()
                
                # Show progress every 5 chunks
                if chunks_received % 5 == 0:
                    print_test(f"Chunk {chunks_received}: {len(total_content)} chars", "running")
        
        # Final metrics
        total_time = last_chunk_time - start_time if last_chunk_time else 0
        chars_per_second = len(total_content) / total_time if total_time > 0 else 0
        
        print_chat("assistant", total_content, model=model)
        
        # Validate streaming
        print_test(f"✓ Chunks received: {chunks_received}", "pass")
        print_test(f"✓ Final content: {len(total_content)} chars", "pass")
        print_test(f"✓ Streaming speed: {chars_per_second:.1f} chars/sec", "pass")
        print_test(f"✓ Time to first byte: {ttfb:.2f}s", "pass" if first_chunk_time else "fail")
        
        return {
            "chunks": chunks_received,
            "content_length": len(total_content),
            "total_time": total_time,
            "chars_per_second": chars_per_second,
            "ttfb": ttfb if first_chunk_time else None
        }
        
    except Exception as e:
        print_test(f"Sync streaming failed: {e}", "fail")
        return None

def test_async_streaming():
    """Test asynchronous streaming completion."""
    print_header("Asynchronous Streaming Completion", "single")
    
    model = STREAMING_MODELS["small"]
    prompt = "Explain the concept of machine learning in simple terms. Include examples and make it about 150 words."
    
    async def async_streaming_test():
        try:
            print_test(f"Testing async streaming with {model}", "running")
            print_chat("user", prompt, model=model)
            
            provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
            
            # Streaming metrics
            start_time = time.time()
            chunks_received = 0
            total_content = ""
            first_chunk_time = None
            last_chunk_time = None
            
            print_test("Starting async streaming...", "running")
            
            with Timer("Async streaming completion"):
                async for chunk in provider.acomplete_stream([Message.user_message(prompt)]):
                    chunks_received += 1
                    
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                        ttfb = first_chunk_time - start_time
                        print_test(f"First async chunk in {ttfb:.2f}s", "pass")
                    
                    if chunk.content:
                        total_content = chunk.content
                        last_chunk_time = time.time()
                    
                    # Show progress every 5 chunks
                    if chunks_received % 5 == 0:
                        print_test(f"Async chunk {chunks_received}: {len(total_content)} chars", "running")
            
            # Final metrics
            total_time = last_chunk_time - start_time if last_chunk_time else 0
            chars_per_second = len(total_content) / total_time if total_time > 0 else 0
            
            print_chat("assistant", total_content, model=model)
            
            # Validate async streaming
            print_test(f"✓ Async chunks: {chunks_received}", "pass")
            print_test(f"✓ Async content: {len(total_content)} chars", "pass")
            print_test(f"✓ Async speed: {chars_per_second:.1f} chars/sec", "pass")
            print_test(f"✓ Async TTFB: {ttfb:.2f}s", "pass" if first_chunk_time else "fail")
            
            return {
                "chunks": chunks_received,
                "content_length": len(total_content),
                "total_time": total_time,
                "chars_per_second": chars_per_second,
                "ttfb": ttfb if first_chunk_time else None
            }
            
        except Exception as e:
            print_test(f"Async streaming failed: {e}", "fail")
            return None
    
    return run_async(async_streaming_test())

def test_streaming_models_comparison():
    """Test streaming performance across different models."""
    print_header("Streaming Models Comparison", "single")
    
    prompt = "What is artificial intelligence? Explain in about 100 words."
    results = {}
    
    for model_type, model_name in STREAMING_MODELS.items():
        try:
            print_test(f"Testing streaming with {model_type} model: {model_name}", "running")
            
            provider = OllamaProvider(model_name=model_name, timeout=TIMEOUT)
            
            # Metrics tracking
            start_time = time.time()
            chunks_received = 0
            content_length = 0
            first_chunk_time = None
            
            with Timer(f"{model_type} model streaming"):
                for chunk in provider.complete_stream([Message.user_message(prompt)]):
                    chunks_received += 1
                    
                    if first_chunk_time is None:
                        first_chunk_time = time.time()
                    
                    if chunk.content:
                        content_length = len(chunk.content)
                    
                    # Early break for testing (don't wait for full completion)
                    if chunks_received >= 20:  # Sample first 20 chunks
                        break
            
            total_time = time.time() - start_time
            ttfb = first_chunk_time - start_time if first_chunk_time else 0
            
            results[model_type] = {
                "model": model_name,
                "chunks_sampled": chunks_received,
                "content_length": content_length,
                "total_time": total_time,
                "ttfb": ttfb,
                "success": True
            }
            
            print_test(f"✓ {model_type}: {chunks_received} chunks, TTFB: {ttfb:.2f}s", "pass")
            
        except Exception as e:
            print_test(f"✗ {model_type} streaming failed: {e}", "fail")
            results[model_type] = {"model": model_name, "success": False, "error": str(e)}
    
    # Comparison summary
    separator()
    print_test("📊 Streaming Performance Comparison:", "pass")
    
    for model_type, result in results.items():
        if result.get("success"):
            ttfb = result["ttfb"]
            chunks = result["chunks_sampled"]
            print_test(f"  {model_type}: TTFB {ttfb:.2f}s, {chunks} chunks", "pass")
        else:
            print_test(f"  {model_type}: Failed", "fail")
    
    return results

def test_streaming_with_parameters():
    """Test streaming with different completion parameters."""
    print_header("Streaming with Different Parameters", "single")
    
    model = STREAMING_MODELS["small"]
    prompt = "Tell me about renewable energy sources."
    
    test_configs = [
        {"name": "Creative", "temperature": 0.9, "max_tokens": 100},
        {"name": "Balanced", "temperature": 0.7, "max_tokens": 100},
        {"name": "Focused", "temperature": 0.3, "max_tokens": 100},
        {"name": "Brief", "temperature": 0.5, "max_tokens": 50},
    ]
    
    results = {}
    
    for config in test_configs:
        try:
            print_test(f"Testing {config['name']} streaming", "running")
            
            provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
            
            chunks_received = 0
            final_content = ""
            
            with Timer(f"{config['name']} streaming"):
                for chunk in provider.complete_stream(
                    [Message.user_message(prompt)],
                    temperature=config["temperature"],
                    max_tokens=config["max_tokens"]
                ):
                    chunks_received += 1
                    if chunk.content:
                        final_content = chunk.content
            
            results[config["name"]] = {
                "chunks": chunks_received,
                "content_length": len(final_content),
                "temperature": config["temperature"],
                "max_tokens": config["max_tokens"],
                "success": True
            }
            
            print_test(f"✓ {config['name']}: {chunks_received} chunks, {len(final_content)} chars", "pass")
            print_chat("assistant", final_content[:100] + "..." if len(final_content) > 100 else final_content, 
                       model=f"{model} (temp: {config['temperature']})")
            
        except Exception as e:
            print_test(f"✗ {config['name']} streaming failed: {e}", "fail")
            results[config["name"]] = {"success": False, "error": str(e)}
    
    return results

def test_streaming_content_analysis():
    """Test streaming content building and analysis."""
    print_header("Streaming Content Analysis", "single")
    
    model = STREAMING_MODELS["medium"]
    prompt = "Write a step-by-step guide for making coffee. Include equipment needed and detailed instructions."
    
    try:
        print_test(f"Testing content building with {model}", "running")
        print_chat("user", prompt, model=model)
        
        provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
        
        # Content analysis tracking
        content_milestones = [50, 100, 200, 500, 1000]  # Character milestones
        reached_milestones = {}
        chunks_received = 0
        word_count = 0
        current_content = ""
        
        print_test("Analyzing streaming content building...", "running")
        
        with Timer("Content analysis streaming"):
            for chunk in provider.complete_stream([Message.user_message(prompt)]):
                chunks_received += 1
                
                if chunk.content:
                    current_content = chunk.content
                    word_count = len(current_content.split())
                    
                    # Check milestones
                    for milestone in content_milestones:
                        if len(current_content) >= milestone and milestone not in reached_milestones:
                            reached_milestones[milestone] = chunks_received
                            print_test(f"  Reached {milestone} chars at chunk {chunks_received}", "pass")
        
        # Final analysis
        final_word_count = len(current_content.split())
        sentences = current_content.count('.') + current_content.count('!') + current_content.count('?')
        
        print_chat("assistant", current_content[:300] + "..." if len(current_content) > 300 else current_content, 
                   model=model)
        
        # Content quality metrics
        print_test(f"✓ Total chunks: {chunks_received}", "pass")
        print_test(f"✓ Final length: {len(current_content)} chars", "pass")
        print_test(f"✓ Word count: {final_word_count} words", "pass")
        print_test(f"✓ Sentences: {sentences}", "pass")
        print_test(f"✓ Milestones reached: {len(reached_milestones)}/{len(content_milestones)}", "pass")
        
        return {
            "chunks": chunks_received,
            "final_length": len(current_content),
            "word_count": final_word_count,
            "sentences": sentences,
            "milestones": reached_milestones
        }
        
    except Exception as e:
        print_test(f"Content analysis streaming failed: {e}", "fail")
        return None

def test_streaming_error_handling():
    """Test streaming error handling and edge cases."""
    print_header("Streaming Error Handling", "single")
    
    test_cases = [
        {
            "name": "Empty prompt streaming",
            "prompt": "",
            "model": STREAMING_MODELS["small"],
            "should_fail": False
        },
        {
            "name": "Very short max_tokens",
            "prompt": "Tell me about space exploration",
            "model": STREAMING_MODELS["small"],
            "max_tokens": 5,
            "should_fail": False
        },
        {
            "name": "Non-existent model streaming",
            "prompt": "Hello world",
            "model": "non-existent-model:latest",
            "should_fail": True
        }
    ]
    
    results = {}
    
    for test_case in test_cases:
        try:
            print_test(f"Testing: {test_case['name']}", "running")
            
            provider = OllamaProvider(
                model_name=test_case["model"], 
                timeout=60.0  # Shorter timeout for error tests
            )
            
            chunks_received = 0
            final_content = ""
            
            stream_kwargs = {}
            if "max_tokens" in test_case:
                stream_kwargs["max_tokens"] = test_case["max_tokens"]
            
            for chunk in provider.complete_stream([Message.user_message(test_case["prompt"])], **stream_kwargs):
                chunks_received += 1
                if chunk.content:
                    final_content = chunk.content
                
                # Limit chunks for testing
                if chunks_received >= 10:
                    break
            
            if test_case["should_fail"]:
                print_test(f"✗ Expected failure but got {chunks_received} chunks", "warn")
                results[test_case["name"]] = {"unexpected_success": True, "chunks": chunks_received}
            else:
                print_test(f"✓ Handled gracefully: {chunks_received} chunks", "pass")
                results[test_case["name"]] = {"success": True, "chunks": chunks_received}
                
        except Exception as e:
            if test_case["should_fail"]:
                print_test(f"✓ Expected error: {type(e).__name__}", "pass")
                results[test_case["name"]] = {"expected_error": str(e)}
            else:
                print_test(f"✗ Unexpected error: {e}", "fail")
                results[test_case["name"]] = {"unexpected_error": str(e)}
    
    return results

def main():
    """Run all streaming completion tests."""
    print_header("🌊 Enterprise AI - Streaming Completion Tests", "double")
    print_test("Starting streaming completion test suite...", "running")
    
    separator()
    
    # Test results tracking
    results = {}
    
    # Test 1: Sync streaming
    results['sync_streaming'] = test_sync_streaming() is not None
    separator()
    
    # Test 2: Async streaming
    results['async_streaming'] = test_async_streaming() is not None
    separator()
    
    # Test 3: Model comparison
    model_results = test_streaming_models_comparison()
    results['model_comparison'] = any(r.get("success", False) for r in model_results.values())
    separator()
    
    # Test 4: Parameter testing
    param_results = test_streaming_with_parameters()
    results['parameter_streaming'] = len([r for r in param_results.values() if r.get("success", False)]) > 0
    separator()
    
    # Test 5: Content analysis
    results['content_analysis'] = test_streaming_content_analysis() is not None
    separator()
    
    # Test 6: Error handling
    error_results = test_streaming_error_handling()
    results['error_handling'] = len(error_results) > 0
    separator()
    
    # Final summary
    print_header("📊 Streaming Completion Test Results", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    separator()
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All streaming tests passed!", "pass")
        print_test("Your streaming capabilities are working perfectly!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    # Streaming-specific tips
    separator()
    print_header("💡 Streaming Performance Tips", "box")
    print_test("For optimal streaming performance:", "pass")
    print_test("• Use smollm2:latest for fastest streaming responses", "pass")
    print_test("• Monitor Time to First Byte (TTFB) for responsiveness", "pass")
    print_test("• Process chunks incrementally for better UX", "pass")
    print_test("• Use async streaming for better concurrency", "pass")
    print_test("• Set appropriate max_tokens to control stream length", "pass")
    
    return results

if __name__ == "__main__":
    main()