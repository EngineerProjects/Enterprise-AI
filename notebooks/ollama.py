import io
import os
import sys
import asyncio
import base64
import time
from time import sleep
from PIL import Image

# --- Setup project root ---
project_root = os.path.abspath(os.path.join(os.getcwd()))
if project_root not in sys.path:
    sys.path.append(project_root)

# --- Import your library ---
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.schema import Message

# --- Terminal Colors ---
def print_title(title):
    print("\n" + "=" * 60)
    print(f"\033[1;34m{title}\033[0m")  # Blue title
    print("=" * 60 + "\n")

def print_success(msg):
    print(f"\033[1;32m{msg}\033[0m")  # Green success

def print_error(msg):
    print(f"\033[1;31m{msg}\033[0m")  # Red error

def separator():
    print("\n" + "-" * 60 + "\n")

# --- Helper Functions ---
def encode_image_to_base64(path):
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# --- Tests ---
def test_initialization(model_name, base_url, timeout):
    print_title("1. Provider Initialization Test")
    try:
        provider = OllamaProvider(
            model_name=model_name,
            base_url=base_url,
            timeout=timeout
        )
        print(f"Model name: {provider.get_model_name()}")
        print(f"Base URL: {provider.config['base_url']}")
        print(f"Timeout: {provider._timeout} seconds")
        print_success("Provider initialized successfully!")
        return provider
    except Exception as e:
        print_error(f"Initialization failed: {e}")
        raise

def test_model_info(provider):
    print_title("2. Model Info Detection Test")
    try:
        model_info = provider.get_model_info()
        print(f"Model ID: {model_info.id}")
        print(f"Context Window: {model_info.context_window}")
        print(f"Features: {model_info.features}")
        print(f"Description: {model_info.description}")
        print_success("Model info detection passed!")
    except Exception as e:
        print_error(f"Model info detection failed: {e}")
        raise

def test_basic_completion(provider):
    print_title("3. Basic Completion Test")
    try:
        messages = [Message.user_message("Tell me a short programming joke.")]
        
        print("Sending request to model...")
        start_time = time.time()  # Using time.time() instead of asyncio.get_event_loop().time()
        
        response = provider.complete(messages)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Response received in {duration:.2f} seconds:")
        print("-" * 40)
        print(response.content)
        print("-" * 40)
        print_success("Basic completion test passed!")
    except Exception as e:
        print_error(f"Basic completion test failed: {e}")
        raise

def test_streaming_completion(provider):
    print_title("4. Streaming Completion Test")
    try:
        messages = [Message.user_message("Explain recursion in a simple way.")]
        
        print("Streaming response:")
        print("-" * 40)
        
        # Track previous content length to only print new content
        previous_length = 0
        start_time = time.time()
        chunk_count = 0
        
        for chunk in provider.complete_stream(messages):
            chunk_count += 1
            # Get current chunk content
            current_content = chunk.content
            
            # Only print the new content
            new_content = current_content[previous_length:]
            if new_content:
                print(new_content, end='', flush=True)
                
            # Update previous length
            previous_length = len(current_content)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print()
        print("-" * 40)
        print(f"Received {chunk_count} chunks in {duration:.2f} seconds")
        print_success("Streaming completion test passed!")
    except Exception as e:
        print_error(f"Streaming completion test failed: {e}")
        raise

def test_async_completion(provider):
    print_title("5. Async Completion Test")
    async def async_test():
        try:
            messages = [Message.user_message("Why is async programming useful?")]
            
            print("Sending async request...")
            start_time = time.time()
            
            response = await provider.acomplete(messages)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"Async response received in {duration:.2f} seconds:")
            print("-" * 40)
            print(response.content)
            print("-" * 40)
            print_success("Async completion test passed!")
        except Exception as e:
            print_error(f"Async completion test failed: {e}")
            raise

    asyncio.run(async_test())

async def test_async_streaming():
    print_title("5b. Async Streaming Completion Test")
    try:
        # Initialize provider inside the async function
        provider = OllamaProvider(
            model_name=MODEL_NAME,
            base_url=BASE_URL,
            timeout=TIMEOUT
        )
        
        messages = [Message.user_message("Write a haiku about programming.")]
        
        print("Streaming async response:")
        print("-" * 40)
        
        # Track previous content length to only print new content
        previous_length = 0
        start_time = time.time()
        chunk_count = 0
        
        # Fixed: removed incorrect 'await' before the async generator
        async for chunk in provider.acomplete_stream(messages):
            chunk_count += 1
            # Get current chunk content
            current_content = chunk.content
            
            # Only print the new content
            new_content = current_content[previous_length:]
            if new_content:
                print(new_content, end='', flush=True)
                
            # Update previous length
            previous_length = len(current_content)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print()
        print("-" * 40)
        print(f"Received {chunk_count} chunks in {duration:.2f} seconds")
        print_success("Async streaming completion test passed!")
        
        # Explicitly close the async client
        if provider._async_client:
            await provider._async_client.aclose()
            
    except Exception as e:
        print_error(f"Async streaming completion test failed: {e}")
        import traceback
        traceback.print_exc()

def encode_image_to_base64(path, max_size=None, format=None):
    """
    Load an image with Pillow, optionally resize it, and convert to base64.
    
    Args:
        path (str): Path to the image file
        max_size (tuple, optional): Max width, height to resize to while preserving aspect ratio
        format (str, optional): Output format (jpg, png, etc.). If None, uses original format
        
    Returns:
        str: Base64-encoded image data
    """
    try:
        # Open and validate the image
        img = Image.open(path)
        
        # Optional resize (preserving aspect ratio)
        if max_size is not None:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
        # Determine output format
        output_format = format or img.format or "JPEG"
        
        # Create an in-memory byte buffer
        buffer = io.BytesIO()
        
        # Save the image to the buffer
        img.save(buffer, format=output_format)
        buffer.seek(0)
        
        # Encode to base64
        encoded_image = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        print(f"Image processed: {img.width}x{img.height}, format: {output_format}")
        return encoded_image
        
    except Exception as e:
        print(f"Error processing image: {e}")
        raise

def test_vision_input(provider, image_path):
    print_title("6. Vision Input (Image) Test")
    if not provider.supports_feature("vision"):
        print_error("Vision feature not supported by this model.")
        return

    try:
        if not os.path.exists(image_path):
            print_error(f"Image not found at path: {image_path}")
            print("Checking for alternative test images...")
            
            # Try to find an image file in the current directory
            image_files = [f for f in os.listdir('.') if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if image_files:
                image_path = image_files[0]
                print(f"Found alternative image: {image_path}")
            else:
                print_error("No image files found. Creating a simple test image...")
                try:
                    from PIL import Image, ImageDraw
                    
                    # Create a simple test image
                    test_image_path = "test_image.png"
                    img = Image.new('RGB', (300, 200), color=(73, 109, 137))
                    d = ImageDraw.Draw(img)
                    d.text((10,10), "Test image for Ollama", fill=(255,255,0))
                    img.save(test_image_path)
                    
                    image_path = test_image_path
                    print(f"Created test image at {test_image_path}")
                except ImportError:
                    print_error("PIL not installed. Cannot create test image.")
                    return
        
        print(f"Using image at path: {image_path}")
        
        # Process image with Pillow - resize to reasonable dimensions if needed
        # Many vision models work best with images less than 1024x1024
        encoded_image = encode_image_to_base64(image_path, max_size=(1024, 1024), format="JPEG")
        print(f"Image encoded successfully (length: {len(encoded_image)})")

        msg = Message.user_message("Describe this image in detail.")
        msg.metadata["images"] = [encoded_image]

        print("Sending vision request...")
        start_time = time.time()
        
        response = provider.complete([msg])
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Vision response received in {duration:.2f} seconds:")
        print("-" * 40)
        print(response.content)
        print("-" * 40)
        print_success("Vision input test passed!")
    except FileNotFoundError:
        print_error(f"Image file not found at {image_path}! Please check your image path.")
    except Exception as e:
        print_error(f"Vision input test failed: {e}")
        import traceback
        traceback.print_exc()

def test_error_handling(model_name, base_url, timeout):
    print_title("7. Error Handling Test")
    try:
        # Test with non-existent model
        print("Testing with non-existent model...")
        bad_provider = OllamaProvider(model_name="non_existent_model_12345", timeout=10.0)
        bad_provider.complete([Message.user_message("This should fail!")])
        print_error("Error handling test failed: No error was raised!")
    except Exception as e:
        print_success(f"Successfully caught error: {type(e).__name__} - {e}")
    
    try:
        # Test with invalid URL
        print("\nTesting with invalid URL...")
        bad_url_provider = OllamaProvider(
            model_name=model_name, 
            base_url=base_url,
            timeout=timeout,
        )
        bad_url_provider.complete([Message.user_message("This should fail!")])
        print_error("Error handling test failed: No error was raised for invalid URL!")
    except Exception as e:
        print_success(f"Successfully caught error: {type(e).__name__} - {e}")

def test_tool_call_detection(provider):
    print_title("8. Tool Call Capability Detection (Optional)")
    try:
        if not provider.supports_feature("function_calling"):
            print(f"Model {provider.get_model_name()} doesn't appear to support function calling.")
            print("Skipping tool call test.")
            return
        
        print(f"Model {provider.get_model_name()} supports function calling!")
        
        # Define tools to test (simple calculator)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "A simple calculator that can add, subtract, multiply, and divide",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "operation": {
                                "type": "string",
                                "enum": ["add", "subtract", "multiply", "divide"],
                                "description": "The operation to perform"
                            },
                            "a": {
                                "type": "number",
                                "description": "The first number"
                            },
                            "b": {
                                "type": "number",
                                "description": "The second number"
                            }
                        },
                        "required": ["operation", "a", "b"]
                    }
                }
            }
        ]
        
        messages = [
            Message.system_message("You have access to a calculator tool. Use it when appropriate."),
            Message.user_message("Calculate 25 multiplied by 13")
        ]

        print("Sending tool call request...")
        response = provider.complete(messages, tools=tools)
        
        print("Response:")
        print("-" * 40)
        print(response.content)
        print("-" * 40)
        
        # Check for tool calls in metadata
        if hasattr(response, "metadata") and response.metadata and "tool_calls" in response.metadata:
            print("\nTool calls detected in response:")
            for i, tool_call in enumerate(response.metadata["tool_calls"]):
                print(f"Tool call {i+1}:")
                print(f"  Name: {tool_call['function']['name']}")
                print(f"  Arguments: {tool_call['function']['arguments']}")
            print_success("Tool call test passed!")
        else:
            print("No tool calls detected in metadata. The model may support function calling but didn't use it for this prompt.")
            
    except Exception as e:
        print_error(f"Tool call test failed: {e}")
        import traceback
        traceback.print_exc()

# --- Main ---
if __name__ == "__main__":
    # --- Central Config (Change only here!) ---
    MODEL_NAME = "smollm2"  
    BASE_URL = "http://localhost:11434"  
    TIMEOUT = 500.0  # seconds
    IMAGE_PATH = os.path.join(project_root, "docs", "images", "logo1.png")
    
    # --- Run Tests ---
    
    # Keep track of overall test status
    all_tests_passed = True
    
    try:
        provider = test_initialization(MODEL_NAME, BASE_URL, TIMEOUT)
        separator()
        sleep(1)

        test_model_info(provider)
        separator()
        sleep(1)

        test_basic_completion(provider)
        separator()
        sleep(1)

        test_streaming_completion(provider)
        separator()
        sleep(1)

        test_async_completion(provider)
        separator()
        sleep(1)
        
        asyncio.run(test_async_streaming())
        separator()
        sleep(1)

        test_vision_input(provider, IMAGE_PATH)
        separator()
        sleep(1)

        test_error_handling(MODEL_NAME, BASE_URL, TIMEOUT)
        separator()
        sleep(1)

        test_tool_call_detection(provider)
        separator()

        print("\n\033[1;35m🎉 ALL TESTS COMPLETED!\033[0m\n")

    except Exception as final_error:
        print_error(f"🚨 A critical error occurred during testing: {final_error}")
        import traceback
        traceback.print_exc()
        all_tests_passed = False
        
    # Report final status
    if all_tests_passed:
        print_success("All tests completed successfully!")
    else:
        print_error("Some tests failed. Please review the output for details.")