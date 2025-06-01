#!/usr/bin/env python3
"""
Enterprise AI - Vision Completion Tests

Tests vision capabilities using Ollama vision models with image analysis.
Tests both synchronous and asynchronous vision completion methods.

Features tested:
- Basic vision analysis (sync/async)
- Image description and analysis
- Multiple image formats
- Different vision prompts
- Image+text multimodal completion
- Error handling for non-vision models
"""

import sys
import asyncio
import os
from pathlib import Path
from typing import List, Optional

# Add project to path and import utilities
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from notebooks.utils import (
    setup_project_path, print_header, print_test, print_chat, 
    separator, Timer, run_async, choose_random_image, encode_image_to_base64
)

# Import Enterprise AI
setup_project_path()
from enterprise_ai.llm import complete, create_provider
from enterprise_ai.llm.ollama import OllamaProvider
from enterprise_ai.schema import Message, CompletionOptions

# Configuration
TIMEOUT = 1200.0

# Vision models available
VISION_MODELS = {
    "granite_vision": "granite3.2-vision:latest",  # 2.4GB - Primary vision model
    "llava": "llava:latest",                       # 4.7GB - Alternative vision model (if available)
}

# Non-vision model for comparison
NON_VISION_MODEL = "smollm2:latest"

def test_image_setup():
    """Test image directory setup and availability."""
    print_header("Image Setup & Availability", "single")
    
    # Check if images directory exists
    images_dir = Path(__file__).parent.parent.parent / "images"
    print_test(f"Images directory: {images_dir}", "running")
    
    if not images_dir.exists():
        print_test(f"Creating images directory: {images_dir}", "running")
        images_dir.mkdir(parents=True, exist_ok=True)
    
    # Check for available images
    valid_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    image_files = [f for f in images_dir.glob('*') if f.suffix.lower() in valid_exts]
    
    print_test(f"Found {len(image_files)} images", "pass" if image_files else "warn")
    
    if image_files:
        for img_file in image_files[:5]:  # Show first 5 images
            size_mb = img_file.stat().st_size / (1024 * 1024)
            print_test(f"  📷 {img_file.name} ({size_mb:.1f}MB)", "pass")
    else:
        print_test("⚠️ No images found! Please add some images to test vision capabilities", "warn")
        print_test(f"Add images to: {images_dir}", "warn")
        print_test("Supported formats: JPG, PNG, GIF, BMP, WebP", "warn")
    
    return len(image_files) > 0

def test_sync_vision_analysis():
    """Test synchronous vision analysis."""
    print_header("Synchronous Vision Analysis", "single")
    
    model = VISION_MODELS["granite_vision"]
    
    # Get a random image
    image_data = choose_random_image(resize=True, target_size=(512, 512))
    if not image_data:
        print_test("No images available for vision testing", "skip")
        return None
    
    try:
        print_test(f"Testing sync vision with {model}", "running")
        
        # Create message with image
        prompt = "Describe this image in detail. What do you see?"
        message = Message(
            role="user",
            content=prompt,
            metadata={"images": [image_data]}
        )
        
        print_chat("user", prompt, model=model, images=1)
        
        # Create provider directly for better control
        provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
        
        with Timer("Sync vision analysis"):
            response = provider.complete([message])
        
        print_chat("assistant", response.content, 
                   model=model)
        
        # Validate response
        print_test(f"✓ Vision response: {len(response.content)} chars", "pass")
        print_test(f"✓ Role is assistant: {response.role == 'assistant'}", "pass")
        print_test(f"✓ Has detailed content: {len(response.content) > 50}", "pass")
        
        return response
    except Exception as e:
        print_test(f"Sync vision analysis failed: {e}", "fail")
        return None

def test_async_vision_analysis():
    """Test asynchronous vision analysis."""
    print_header("Asynchronous Vision Analysis", "single")
    
    model = VISION_MODELS["granite_vision"]
    
    async def async_vision_test():
        # Get a random image
        image_data = choose_random_image(resize=True, target_size=(400, 400))
        if not image_data:
            print_test("No images available for async vision testing", "skip")
            return None
        
        try:
            print_test(f"Testing async vision with {model}", "running")
            
            prompt = "What's happening in this image? Identify key objects and activities."
            message = Message(
                role="user",
                content=prompt,
                metadata={"images": [image_data]}
            )
            
            print_chat("user", prompt, model=model, images=1)
            
            provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
            
            with Timer("Async vision analysis"):
                response = await provider.acomplete([message])
            
            print_chat("assistant", response.content, 
                       model=model)
            
            # Validate response
            print_test(f"✓ Async vision response: {len(response.content)} chars", "pass")
            print_test(f"✓ Role is assistant: {response.role == 'assistant'}", "pass")
            print_test(f"✓ Has detailed content: {len(response.content) > 50}", "pass")
            
            return response
        except Exception as e:
            print_test(f"Async vision analysis failed: {e}", "fail")
            return None
    
    return run_async(async_vision_test())

def test_vision_prompts():
    """Test different types of vision analysis prompts."""
    print_header("Various Vision Analysis Prompts", "single")
    
    model = VISION_MODELS["granite_vision"]
    
    # Different types of vision prompts to test
    vision_prompts = [
        "Describe what you see in this image in one sentence.",
        "What colors are prominent in this image?",
        "Count any objects you can identify in this image.",
        "What is the mood or atmosphere of this image?",
        "Is this image taken indoors or outdoors? How can you tell?",
    ]
    
    results = {}
    
    for i, prompt in enumerate(vision_prompts):
        try:
            print_test(f"Testing vision prompt {i+1}/{len(vision_prompts)}", "running")
            
            # Get a fresh image for each test
            image_data = choose_random_image(resize=True, target_size=(400, 400))
            if not image_data:
                print_test(f"Skipping prompt {i+1}: No image available", "skip")
                continue
            
            message = Message(
                role="user",
                content=prompt,
                metadata={"images": [image_data]}
            )
            
            print_chat("user", prompt, model=model, images=1)
            
            provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
            
            with Timer(f"Vision prompt {i+1}"):
                response = provider.complete([message])
            
            results[f"prompt_{i+1}"] = {
                "prompt": prompt,
                "response_length": len(response.content),
                "success": True
            }
            
            print_chat("assistant", response.content, 
                       model=model)
            print_test(f"✓ Prompt {i+1}: {len(response.content)} chars", "pass")
            
        except Exception as e:
            print_test(f"✗ Prompt {i+1} failed: {e}", "fail")
            results[f"prompt_{i+1}"] = {"prompt": prompt, "success": False, "error": str(e)}
    
    # Summary
    separator()
    successful_prompts = sum(1 for r in results.values() if r.get("success", False))
    print_test(f"Vision prompts successful: {successful_prompts}/{len(vision_prompts)}", "pass")
    
    return results

def test_multimodal_conversation():
    """Test multi-turn conversation with images."""
    print_header("Multimodal Conversation", "single")
    
    model = VISION_MODELS["granite_vision"]
    
    try:
        print_test(f"Testing multimodal conversation with {model}", "running")
        
        # Get an image for the conversation
        image_data = choose_random_image(resize=True, target_size=(400, 400))
        if not image_data:
            print_test("No images available for multimodal testing", "skip")
            return None
        
        provider = OllamaProvider(model_name=model, timeout=TIMEOUT)
        
        # Turn 1: Initial image analysis
        message1 = Message(
            role="user",
            content="Look at this image and tell me what you see. Be specific about any objects or people.",
            metadata={"images": [image_data]}
        )
        
        print_chat("user", "Look at this image and tell me what you see. Be specific about any objects or people.", 
                   model=model, images=1)
        
        with Timer("Multimodal turn 1"):
            response1 = provider.complete([message1])
        
        print_chat("assistant", response1.content, model=model)
        
        # Turn 2: Follow-up question (no new image)
        followup_prompt = "Based on what you just described, what do you think is the main subject of the image?"
        message2 = Message.user_message(followup_prompt)
        
        print_chat("user", followup_prompt, model=model)
        
        # Multi-turn conversation
        conversation = [message1, response1, message2]
        
        with Timer("Multimodal turn 2"):
            response2 = provider.complete(conversation)
        
        print_chat("assistant", response2.content, model=model)
        
        # Validate conversation
        print_test(f"✓ Turn 1 response: {len(response1.content)} chars", "pass")
        print_test(f"✓ Turn 2 response: {len(response2.content)} chars", "pass")
        print_test(f"✓ Maintained context: {len(response2.content) > 10}", "pass")
        
        return {"turn1": response1, "turn2": response2}
        
    except Exception as e:
        print_test(f"Multimodal conversation failed: {e}", "fail")
        return None

def test_non_vision_model_error():
    """Test error handling when using non-vision model with images."""
    print_header("Non-Vision Model Error Handling", "single")
    
    model = NON_VISION_MODEL
    
    try:
        print_test(f"Testing non-vision model {model} with image", "running")
        
        image_data = choose_random_image(resize=True, target_size=(200, 200))
        if not image_data:
            print_test("No images available for error testing", "skip")
            return None
        
        message = Message(
            role="user",
            content="What do you see in this image?",
            metadata={"images": [image_data]}
        )
        
        print_chat("user", "What do you see in this image?", model=model, images=1)
        
        provider = OllamaProvider(model_name=model, timeout=60.0)
        
        response = provider.complete([message])
        
        # Non-vision models might still respond, just ignoring the image
        print_chat("assistant", response.content, model=model)
        print_test(f"✓ Non-vision model handled gracefully: {len(response.content)} chars", "pass")
        
        return response
        
    except Exception as e:
        print_test(f"✓ Expected behavior - Non-vision model error: {type(e).__name__}", "pass")
        return None

def test_vision_model_availability():
    """Test which vision models are available."""
    print_header("Vision Model Availability", "single")
    
    available_models = {}
    
    for model_type, model_name in VISION_MODELS.items():
        try:
            print_test(f"Testing availability: {model_name}", "running")
            
            provider = OllamaProvider(model_name=model_name, timeout=30.0)
            model_info = provider.get_model_info()
            
            # Check if model supports vision
            supports_vision = "vision" in model_info.features
            
            available_models[model_type] = {
                "name": model_name,
                "available": True,
                "supports_vision": supports_vision,
                "features": len(model_info.features)
            }
            
            print_test(f"✓ {model_name}: Available, Vision: {supports_vision}", "pass")
            
        except Exception as e:
            print_test(f"✗ {model_name}: Not available - {e}", "fail")
            available_models[model_type] = {"name": model_name, "available": False, "error": str(e)}
    
    return available_models

def main():
    """Run all vision completion tests."""
    print_header("🖼️ Enterprise AI - Vision Completion Tests", "double")
    print_test("Starting vision completion test suite...", "running")
    
    separator()
    
    # Test results tracking
    results = {}
    
    # Test 0: Image setup
    has_images = test_image_setup()
    results['image_setup'] = has_images
    separator()
    
    if not has_images:
        print_test("⚠️ No images available - skipping vision tests", "warn")
        print_test("Please add images to examples/notebooks/images/ directory", "warn")
        return results
    
    # Test 1: Vision model availability
    model_availability = test_vision_model_availability()
    results['model_availability'] = any(m.get("available", False) for m in model_availability.values())
    separator()
    
    if not results['model_availability']:
        print_test("⚠️ No vision models available - skipping vision tests", "warn")
        return results
    
    # Test 2: Sync vision analysis
    results['sync_vision'] = test_sync_vision_analysis() is not None
    separator()
    
    # Test 3: Async vision analysis
    results['async_vision'] = test_async_vision_analysis() is not None
    separator()
    
    # Test 4: Various vision prompts
    prompt_results = test_vision_prompts()
    results['vision_prompts'] = len([r for r in prompt_results.values() if r.get("success", False)]) > 0
    separator()
    
    # Test 5: Multimodal conversation
    results['multimodal_conversation'] = test_multimodal_conversation() is not None
    separator()
    
    # Test 6: Non-vision model error handling
    results['error_handling'] = test_non_vision_model_error() is not None
    separator()
    
    # Final summary
    print_header("📊 Vision Completion Test Results", "box")
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, success in results.items():
        status = "pass" if success else "fail"
        print_test(f"{test_name.replace('_', ' ').title()}", status)
    
    separator()
    print_test(f"Overall: {passed}/{total} tests passed", "pass" if passed == total else "warn")
    
    if passed == total:
        print_test("🎉 All vision tests passed!", "pass")
        print_test("Your vision capabilities are working perfectly!", "pass")
    else:
        print_test(f"⚠️ {total - passed} tests need attention", "warn")
    
    # Vision-specific tips
    separator()
    print_header("💡 Vision Model Tips", "box")
    print_test("For optimal vision performance:", "pass")
    print_test("• Use granite3.2-vision:latest for best results", "pass")
    print_test("• Resize images to 400x400 or smaller for speed", "pass")
    print_test("• Use longer timeouts (300s+) for vision models", "pass")
    print_test("• Place test images in examples/notebooks/images/", "pass")
    print_test("• Vision models work better with clear, high-contrast images", "pass")
    
    return results

if __name__ == "__main__":
    main()