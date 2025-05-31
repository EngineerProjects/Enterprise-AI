"""
Simple Metrics Test

This test file shows how to:
- Track provider metrics
- Monitor request counts and performance
- Test metrics updating

Everything about metrics tracking is here.
"""

import sys
import os
import time

# Add project path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(project_root)

# Import what we need
from enterprise_ai.llm import create_provider
from enterprise_ai.schema import Message
from examples.notebooks.utils import (
    print_title, print_section, print_info, print_success, print_error, print_warning,
    Timer
)

def test_metrics():
    """Test metrics tracking functionality."""
    print_title("Metrics Test")
    
    # Step 1: Create provider
    print_section("Creating Provider")
    try:
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434",
            timeout=300.0
        )
        print_success(f"✓ Provider created: {provider.get_model_name()}")
    except Exception as e:
        print_error(f"✗ Failed to create provider: {e}")
        return
    
    # Step 2: Check if metrics are supported
    print_section("Checking Metrics Support")
    if not hasattr(provider, 'get_metrics'):
        print_warning("! This provider doesn't support metrics tracking")
        return
    
    try:
        initial_metrics = provider.get_metrics()
        print_success("✓ Metrics are supported")
        print_info("Initial metrics:")
        for key, value in initial_metrics.items():
            if isinstance(value, float):
                print_info(f"  {key}: {value:.3f}")
            else:
                print_info(f"  {key}: {value}")
    except Exception as e:
        print_error(f"✗ Failed to get initial metrics: {e}")
        return
    
    # Step 3: Make some requests and track metrics
    print_section("Testing Metrics Updates")
    
    # Record start values
    start_request_count = initial_metrics.get("request_count", 0)
    start_success_count = initial_metrics.get("success_count", 0)
    
    try:
        # Make first request
        print_info("Making first request...")
        messages1 = [Message.user_message("Hello, how are you?")]
        
        start_time = time.time()
        response1 = provider.complete(messages1)
        end_time = time.time()
        request1_time = end_time - start_time
        
        print_info(f"Request 1 took: {request1_time:.3f} seconds")
        
        # Check metrics after first request
        metrics_after_1 = provider.get_metrics()
        print_info("Metrics after request 1:")
        for key, value in metrics_after_1.items():
            if isinstance(value, float):
                print_info(f"  {key}: {value:.3f}")
            else:
                print_info(f"  {key}: {value}")
        
        # Make second request
        print_info("Making second request...")
        messages2 = [Message.user_message("What is machine learning?")]
        response2 = provider.complete(messages2)
        
        # Check final metrics
        final_metrics = provider.get_metrics()
        print_info("Final metrics:")
        for key, value in final_metrics.items():
            if isinstance(value, float):
                print_info(f"  {key}: {value:.3f}")
            else:
                print_info(f"  {key}: {value}")
        
        print_success("✓ Metrics tracking test completed")
        
    except Exception as e:
        print_error(f"✗ Metrics tracking test failed: {e}")
        return
    
    # Step 4: Verify metrics increased
    print_section("Verifying Metrics")
    
    end_request_count = final_metrics.get("request_count", 0)
    end_success_count = final_metrics.get("success_count", 0)
    
    if end_request_count > start_request_count:
        increase = end_request_count - start_request_count
        print_success(f"✓ Request count increased by {increase}")
    else:
        print_warning(f"! Request count didn't increase: {start_request_count} → {end_request_count}")
    
    if end_success_count > start_success_count:
        increase = end_success_count - start_success_count
        print_success(f"✓ Success count increased by {increase}")
    else:
        print_warning(f"! Success count didn't increase: {start_success_count} → {end_success_count}")
    
    # Step 5: Test metrics reset (if supported)
    print_section("Testing Metrics Reset")
    if hasattr(provider, 'reset_metrics'):
        try:
            print_info("Resetting metrics...")
            provider.reset_metrics()
            
            reset_metrics = provider.get_metrics()
            print_info("Metrics after reset:")
            for key, value in reset_metrics.items():
                if isinstance(value, float):
                    print_info(f"  {key}: {value:.3f}")
                else:
                    print_info(f"  {key}: {value}")
            
            if reset_metrics.get("request_count", 0) == 0:
                print_success("✓ Metrics reset successful")
            else:
                print_warning("! Metrics may not have reset properly")
                
        except Exception as e:
            print_error(f"✗ Metrics reset failed: {e}")
    else:
        print_info("○ Metrics reset not supported by this provider")

if __name__ == "__main__":
    test_metrics()