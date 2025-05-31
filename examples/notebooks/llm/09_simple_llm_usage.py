"""
Simple LLM Usage Examples

This demonstrates the easiest ways to get started with the Enterprise AI LLM module.
Perfect for beginners and quick prototyping.
"""

from examples.notebooks.utils import (
    print_title, print_section, print_info, print_success, print_error,
    print_user, print_assistant, setup_project_path
)

setup_project_path()

from enterprise_ai.llm import complete, create_provider, get_default_provider
from enterprise_ai.llm.simple import LLM
from enterprise_ai.schema import Message, CompletionOptions


def example_1_simplest_usage():
    """The absolute simplest way to use the LLM."""
    print_section("Example 1: Simplest Usage")
    
    try:
        # One-liner completion using default provider
        response = complete(["What is machine learning?"])
        
        print_user("What is machine learning?")
        print_assistant(response.content)
        print_success("✓ Simplest usage successful")
        
    except Exception as e:
        print_error(f"✗ Simple usage failed: {e}")

def example_2_with_options():
    """Using completion with options."""
    print_section("Example 2: With Completion Options")
    
    try:
        # Using completion options for better control
        options = CompletionOptions(
            temperature=0.7,
            max_tokens=100
        )
        
        messages = [
            "You are a helpful AI assistant.",
            "Explain artificial intelligence in simple terms."
        ]
        
        response = complete(messages, options=options)
        
        print_user("Explain artificial intelligence in simple terms.")
        print_assistant(response.content)
        print_success("✓ Options usage successful")
        
    except Exception as e:
        print_error(f"✗ Options usage failed: {e}")

def example_3_message_objects():
    """Using proper Message objects."""
    print_section("Example 3: Using Message Objects")
    
    try:
        # Create structured messages
        messages = [
            Message.system_message("You are a creative writing assistant."),
            Message.user_message("Write a haiku about coding.")
        ]
        
        response = complete(messages)
        
        print_user("Write a haiku about coding.")
        print_assistant(response.content)
        print_success("✓ Message objects usage successful")
        
    except Exception as e:
        print_error(f"✗ Message objects usage failed: {e}")

def example_4_specific_provider():
    """Using a specific provider."""
    print_section("Example 4: Specific Provider")
    
    try:
        # Create a specific provider
        provider = create_provider(
            "ollama",
            model_name="smollm2",
            base_url="http://localhost:11434"
        )
        
        messages = [Message.user_message("What is the capital of France?")]
        
        # Use the specific provider
        response = complete(messages, provider=provider)
        
        print_user("What is the capital of France?")
        print_assistant(response.content)
        print_success("✓ Specific provider usage successful")
        
        # Clean up
        provider.close()
        
    except Exception as e:
        print_error(f"✗ Specific provider usage failed: {e}")

def example_5_llm_wrapper():
    """Using the LLM wrapper class."""
    print_section("Example 5: LLM Wrapper Class")
    
    try:
        # Use LLM wrapper for easier management
        with LLM(provider_name="ollama", model_name="smollm2") as llm:
            
            # Simple completion
            messages = [Message.user_message("Tell me a fun fact about space.")]
            response = llm.complete(messages)
            
            print_user("Tell me a fun fact about space.")
            print_assistant(response.content)
            
            # Check metrics
            metrics = llm.get_metrics()
            print_info(f"Requests made: {metrics['request_count']}")
            
        print_success("✓ LLM wrapper usage successful")
        
    except Exception as e:
        print_error(f"✗ LLM wrapper usage failed: {e}")

def example_6_conversation():
    """Building a simple conversation."""
    print_section("Example 6: Simple Conversation")
    
    try:
        # Start with system message
        conversation = [
            Message.system_message("You are a helpful math tutor.")
        ]
        
        # First exchange
        conversation.append(Message.user_message("What is 15 * 24?"))
        response = complete(conversation)
        conversation.append(Message.assistant_message(response.content))
        
        print_user("What is 15 * 24?")
        print_assistant(response.content)
        
        # Second exchange
        conversation.append(Message.user_message("Can you show me how to solve it step by step?"))
        response = complete(conversation)
        
        print_user("Can you show me how to solve it step by step?")
        print_assistant(response.content)
        
        print_success("✓ Conversation example successful")
        
    except Exception as e:
        print_error(f"✗ Conversation example failed: {e}")

def example_7_error_handling():
    """Proper error handling patterns."""
    print_section("Example 7: Error Handling")
    
    try:
        # Try to use a non-existent model
        try:
            provider = create_provider("ollama", model_name="nonexistent-model")
            messages = [Message.user_message("Test")]
            response = provider.complete(messages)
            print_assistant(response.content)
            
        except Exception as model_error:
            print_error(f"Model error (expected): {model_error}")
            
            # Fallback to default
            print_info("Falling back to default provider...")
            provider = get_default_provider()
            messages = [Message.user_message("This is a fallback test.")]
            response = provider.complete(messages)
            
            print_user("This is a fallback test.")
            print_assistant(response.content)
            print_success("✓ Fallback successful")
            
            provider.close()
        
    except Exception as e:
        print_error(f"✗ Error handling failed: {e}")

def example_8_with_parameters():
    """Using various completion parameters."""
    print_section("Example 8: Completion Parameters")
    
    try:
        with LLM(provider_name="ollama", model_name="smollm2") as llm:
            
            # Conservative settings
            print_info("Conservative settings (low temperature):")
            messages = [Message.user_message("Generate a creative story opening.")]
            response = llm.complete(messages, temperature=0.1, max_tokens=50)
            print_assistant(response.content)
            
            # Creative settings
            print_info("\nCreative settings (high temperature):")
            response = llm.complete(messages, temperature=0.9, max_tokens=50)
            print_assistant(response.content)
            
        print_success("✓ Parameter examples successful")
        
    except Exception as e:
        print_error(f"✗ Parameter examples failed: {e}")

def example_9_quick_qa():
    """Quick question-answering helper."""
    print_section("Example 9: Quick Q&A Helper")
    
    def ask_question(question: str) -> str:
        """Helper function for quick questions."""
        try:
            response = complete([Message.user_message(question)])
            return response.content
        except Exception as e:
            return f"Error: {e}"
    
    # Use the helper
    questions = [
        "What is Python?",
        "How do neural networks work?",
        "What is the meaning of life?"
    ]
    
    for question in questions:
        answer = ask_question(question)
        print_user(question)
        print_assistant(answer)
        print()
    
    print_success("✓ Quick Q&A helper successful")

def run_all_examples():
    """Run all simple usage examples."""
    print_title("Simple LLM Usage Examples")
    
    example_1_simplest_usage()
    example_2_with_options()
    example_3_message_objects()
    example_4_specific_provider()
    example_5_llm_wrapper()
    example_6_conversation()
    example_7_error_handling()
    example_8_with_parameters()
    example_9_quick_qa()
    
    print_success("All simple usage examples completed!")

if __name__ == "__main__":
    run_all_examples()