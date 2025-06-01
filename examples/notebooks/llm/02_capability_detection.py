#!/usr/bin/env python3
"""
Enterprise AI - Model Capability Detection Tests

This test demonstrates the universal capability detection system that works
with any Ollama model by analyzing actual model metadata. Optimized for GTX 1650.

Tests include:
- Universal capability detection
- Model specifications extraction  
- Feature set analysis
- Task suitability assessment
- Performance characteristics
"""

import sys
import os
import json
from pathlib import Path
from typing import Set, Dict, Any

# Add project to path and import utilities
sys.path.append(str(Path(__file__).parent.parent.parent))
from notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer
)

# Import Enterprise AI
setup_project_path()
from enterprise_ai.llm import create_provider, inspect_model_capabilities
from enterprise_ai.llm.ollama import OllamaProvider

# Available models on the system
AVAILABLE_MODELS = [
    "granite3.2-vision:latest",  # 2.4 GB - Vision
    "deepseek-r1:latest",        # 5.2 GB - Large reasoning  
    "smollm2:latest",            # 1.8 GB - Small efficient
    "llava:latest",              # 4.7 GB - Vision
    "llama3.2:latest",           # 2.0 GB - General purpose
]

def test_model_info_basic():
    """Test basic model info retrieval."""
    print_header("Basic Model Information", "single")
    
    model = "smollm2:latest"  # Start with smallest model
    
    try:
        print_test(f"Getting model info for {model}", "running")
        
        with Timer("Model info retrieval"):
            provider = create_provider("ollama", model, timeout=60.0)
            model_info = provider.get_model_info()
        
        print_test(f"Model ID: {model_info.id}", "pass")
        print_test(f"Provider: {model_info.provider}", "pass")
        print_test(f"Max tokens: {model_info.max_tokens}", "pass")
        print_test(f"Context window: {model_info.context_window}", "pass")
        print_test(f"Features count: {len(model_info.features)}", "pass")
        print_test(f"Description: {model_info.description}", "pass")
        
        return model_info
    except Exception as e:
        print_test(f"Model info retrieval failed: {e}", "fail")
        return None

def test_capability_detection_api():
    """Test the high-level capability detection API."""
    print_header("High-Level Capability Detection API", "single")
    
    model = "llama3.2:latest"
    
    try:
        print_test(f"Detecting capabilities for {model}", "running")
        
        with Timer("Capability detection"):
            capabilities = inspect_model_capabilities(model, "ollama", timeout=90.0)
        
        print_test(f"Model name: {capabilities['model_name']}", "pass")
        print_test(f"Provider: {capabilities['provider']}", "pass")
        print_test(f"Context window: {capabilities['context_window']}", "pass")
        print_test(f"Max tokens: {capabilities['max_tokens']}", "pass")  # CORRECTED: use max_tokens
        
        features = capabilities['detected_features']
        print_test(f"Detected features: {len(features)}", "pass")
        
        # Show detected features
        for feature in sorted(features):
            print_test(f"  ✓ {feature}", "pass")
        
        return capabilities
    except Exception as e:
        print_test(f"Capability detection failed: {e}", "fail")
        return None

def test_detailed_capability_analysis():
    """Test detailed capability analysis with OllamaProvider."""
    print_header("Detailed Capability Analysis", "single")
    
    model = "granite3.2-vision:latest"  # Test vision model
    
    try:
        print_test(f"Detailed analysis for {model}", "running")
        
        with Timer("Detailed capability analysis"):
            provider = OllamaProvider(
                model_name=model,
                timeout=120.0  # Longer timeout for vision model
            )
            
            # Get detailed capability information
            details = provider.get_capability_details()
        
        print_test(f"Model: {details['model_name']}", "pass")
        
        # Show detected features
        features = details['detected_features']
        print_test(f"Features detected: {len(features)}", "pass")
        for feature in sorted(features):
            print_test(f"  ✓ {feature}", "pass")
        
        # Show capabilities
        print_test(f"Supports streaming: {details['supports_streaming']}", "pass")
        print_test(f"Supports tools: {details['supports_tools']}", "pass")
        print_test(f"Supports vision: {details['supports_vision']}", "pass")
        print_test(f"Supports async: {details['supports_async']}", "pass")
        
        # Context and token info - CORRECTED: use consistent key names
        print_test(f"Context window: {details['context_window']}", "pass")
        print_test(f"Max output tokens: {details['max_tokens']}", "pass")  # CORRECTED: use max_tokens
        
        # Model specializations
        if details.get('specializations'):
            print_test(f"Specializations: {len(details['specializations'])}", "pass")
            for spec in details['specializations']:
                print_test(f"  • {spec}", "pass")
        
        return details
    except Exception as e:
        print_test(f"Detailed analysis failed: {e}", "fail")
        return None

def test_model_specifications():
    """Test model specifications extraction."""
    print_header("Model Specifications Extraction", "single")
    
    model = "deepseek-r1:latest"  # Test large reasoning model
    
    try:
        print_test(f"Extracting specifications for {model}", "running")
        
        with Timer("Specifications extraction"):
            provider = OllamaProvider(
                model_name=model,
                timeout=150.0  # Extra time for large model
            )
            specs = provider.get_model_specifications()
        
        print_test(f"Architecture: {specs.get('architecture', 'unknown')}", "pass")
        print_test(f"Parameter size: {specs.get('parameter_size', 'unknown')}", "pass")
        print_test(f"Format: {specs.get('format', 'unknown')}", "pass")
        print_test(f"Quantization: {specs.get('quantization', 'unknown')}", "pass")
        print_test(f"Context window: {specs.get('context_window', 'unknown')}", "pass")
        
        # Model families
        families = specs.get('families', [])
        if families:
            print_test(f"Model families: {len(families)}", "pass")
            for family in families:
                print_test(f"  • {family}", "pass")
        
        # Native capabilities
        native_caps = specs.get('capabilities', [])
        if native_caps:
            print_test(f"Native capabilities: {len(native_caps)}", "pass")
            for cap in native_caps:
                print_test(f"  • {cap}", "pass")
        
        return specs
    except Exception as e:
        print_test(f"Specifications extraction failed: {e}", "fail")
        return None

def test_task_suitability():
    """Test task suitability assessment."""
    print_header("Task Suitability Assessment", "single")
    
    # Define different task requirements - CORRECTED for better matching
    tasks = {
        "text_generation": {"streaming"},      # Basic capability all models should have
        "vision_analysis": {"vision"},         # Only vision models
        "tool_usage": {"tools"},              # Only tool-capable models
        "reasoning": {"reasoning"},           # Models with reasoning capability
        "coding": {"tools"},                  # Models that support tools (for code execution)
    }
    
    models_to_test = ["smollm2:latest", "granite3.2-vision:latest", "llama3.2:latest"]
    
    try:
        results = {}
        
        for model in models_to_test:
            print_test(f"Testing suitability for {model}", "running")
            
            provider = OllamaProvider(model_name=model, timeout=90.0)
            
            model_results = {}
            for task_name, requirements in tasks.items():
                try:
                    is_suitable = provider.is_suitable_for_task(requirements)
                    model_results[task_name] = is_suitable
                    
                    status = "pass" if is_suitable else "warn"
                    print_test(f"  {task_name}: {is_suitable}", status)
                except Exception as e:
                    model_results[task_name] = False
                    print_test(f"  {task_name}: Error - {e}", "fail")
            
            results[model] = model_results
        
        # Summary
        separator()
        print_test("Task Suitability Summary:", "pass")
        
        for task_name in tasks.keys():
            suitable_models = [m for m, r in results.items() if r.get(task_name, False)]
            print_test(f"{task_name}: {len(suitable_models)} models suitable", "pass")
            for model in suitable_models:
                print_test(f"  ✓ {model}", "pass")
        
        return results
    except Exception as e:
        print_test(f"Task suitability test failed: {e}", "fail")
        return None

def test_capability_comparison():
    """Compare capabilities across multiple models."""
    print_header("Multi-Model Capability Comparison", "single")
    
    # Test with a subset of models (avoid overwhelming GTX 1650)
    models_to_compare = [
        "smollm2:latest",           # Small efficient
        "llama3.2:latest",          # General purpose  
        "granite3.2-vision:latest", # Vision capable
    ]
    
    try:
        comparison_data = {}
        
        for model in models_to_compare:
            print_test(f"Analyzing {model}", "running")
            
            try:
                with Timer(f"Analysis of {model}"):
                    provider = OllamaProvider(model_name=model, timeout=90.0)
                    details = provider.get_capability_details()
                    
                    # CORRECTED: Use consistent key names from the API
                    comparison_data[model] = {
                        "features": details['detected_features'],
                        "context_window": details['context_window'],
                        "max_tokens": details['max_tokens'],  # CORRECTED: use max_tokens
                        "supports_vision": details['supports_vision'],
                        "supports_tools": details['supports_tools'],
                        "specializations": details.get('specializations', []),
                    }
                    
                print_test(f"✓ {model} analyzed", "pass")
            except Exception as e:
                print_test(f"✗ {model} failed: {e}", "fail")
                continue
        
        # Generate comparison report
        separator()
        print_test("📊 Capability Comparison Report", "pass")
        
        # Feature comparison
        all_features = set()
        for data in comparison_data.values():
            all_features.update(data['features'])
        
        print_test(f"Total unique features found: {len(all_features)}", "pass")
        
        # Model comparison table
        for feature in sorted(all_features):
            models_with_feature = [
                model for model, data in comparison_data.items() 
                if feature in data['features']
            ]
            print_test(f"{feature}: {len(models_with_feature)}/{len(comparison_data)} models", "pass")
        
        # Performance characteristics
        separator()
        print_test("Performance Characteristics:", "pass")
        for model, data in comparison_data.items():
            print_test(f"{model}:", "pass")
            print_test(f"  Context: {data['context_window']:,} tokens", "pass")
            print_test(f"  Max output: {data['max_tokens']:,} tokens", "pass")  # CORRECTED
            print_test(f"  Vision: {data['supports_vision']}", "pass")
            print_test(f"  Tools: {data['supports_tools']}", "pass")
        
        return comparison_data
    except Exception as e:
        print_test(f"Capability comparison failed: {e}", "fail")
        return None

def main():
    """Run all capability detection tests."""
    print_header("🔍 Enterprise AI - Model Capability Detection", "double")
    print_test("Starting capability detection test suite...", "running")
    
    separator()
    
    # Test results tracking
    results = {}
    
    # Test 1: Basic model info
    results['basic_info'] = test_model_info_basic() is not None
    separator()
    
    # Test 2: High-level API
    results['api_detection'] = test_capability_detection_api() is not None
    separator()
    
    # Test 3: Detailed analysis
    results['detailed_analysis'] = test_detailed_capability_analysis() is not None
    separator()
    
    # Test 4: Model specifications
    results['specifications'] = test_model_specifications() is not None
    separator()
    
    # Test 5: Task suitability
    results['task_suitability'] = test_task_suitability() is not None
    separator()
    
    # Test 6: Multi-model comparison
    results['comparison'] = test_capability_comparison() is not None
    separator()
    
    # Final summary
    print_header("📊 Capability Detection Results", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    separator()
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All capability detection tests completed!", "pass")
        print_test("Your universal detection system is working perfectly!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    # Hardware recommendations
    separator()
    print_header("💡 GTX 1650 Optimization Tips", "box")
    print_test("For best performance on your hardware:", "pass")
    print_test("• Start with smollm2:latest (1.8GB) for testing", "pass")
    print_test("• Use timeouts of 120-180s for larger models", "pass")
    print_test("• Limit max_tokens to 512-1024 for faster responses", "pass")
    print_test("• Vision models (granite3.2, llava) need 3-4 min timeouts", "pass")
    print_test("• deepseek-r1 may require 5+ min on your hardware", "pass")
    
    return results

if __name__ == "__main__":
    main()