#!/usr/bin/env python
"""
Basic Agent Creation and Interaction - Final Fixed Version

This script demonstrates how to create different types of agents
and interact with them using basic message passing.
"""

import asyncio
import time
import sys
import os
from typing import Any, Dict, List, Optional

# Import utilities for better formatting
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    print_warning,
    separator,
    Timer
)

# Set up project path
setup_project_path()

# Import core components
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger
from enterprise_ai.llm.providers.ollama import OllamaProvider
from enterprise_ai.exceptions import APIError, ModelNotFoundError
from enterprise_ai.llm import create_provider

# Configure logger
logger = get_logger("agent_test")

async def test_basic_agents():
    """Test creating and interacting with basic agents."""
    print_title("TESTING BASIC AGENT CREATION AND INTERACTION")

    # First, test direct Ollama connectivity
    print_section("0. Testing direct Ollama connectivity")
    ollama_works = False
    try:
        # Initialize Ollama provider directly
        ollama_provider = OllamaProvider(model_name="smollm2", timeout=2400.0)
        print_info(f"Direct Ollama provider initialized with model: {ollama_provider.model_name}")

        # Test basic completion
        test_message = Message.user_message("Hello!")
        print_info("Sending direct test message to Ollama...")

        timer = Timer("Direct Ollama Response")
        timer.start()

        try:
            response = ollama_provider.complete([test_message])
            timer.stop()
            print_info(f"Direct Ollama response: '{response.content}'")
            print_success("Direct Ollama test successful!")
            ollama_works = True
        except APIError as e:
            timer.stop()
            print_error(f"Ollama API error: {e}")
            if "timeout" in str(e).lower():
                print_warning("Ollama request timed out. The server might be overloaded or the model is still loading.")
            else:
                print_warning("API error communicating with Ollama.")
        except ModelNotFoundError as e:
            timer.stop()
            print_error(f"Model not found: {e}")
            print_warning("The specified model 'smollm2' does not exist. Please download it with 'ollama pull smollm2'")
        except Exception as e:
            timer.stop()
            print_error(f"Unexpected error: {e}")
    except Exception as e:
        print_error(f"Direct Ollama test failed: {e}")
        print_warning("This suggests Ollama is not running or not configured properly.")
        print_warning("Please make sure Ollama is installed and running with the 'smollm2' model.")

    if not ollama_works:
        print_warning("Skipping agent tests since Ollama test failed.")
        print_info("Please fix your Ollama setup and try again.")
        return

    # Create LLM agents using the factory pattern with model_params correctly
    print_section("1. Creating LLM agents with proper model parameters")

    # Create agent with smollm2
    llm_agent = create_agent(
        agent_type="llm",
        name="LLMAgent",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": 2400.0}
    )
    print_success(f"Created LLM agent: {llm_agent.name} (ID: {llm_agent.id})")
    print_info(f"Using model: {llm_agent._llm_provider.model_name}")

    # Create second agent with smollm2
    llm_agent2 = create_agent(
        agent_type="llm",
        name="SecondLLMAgent",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": 2400.0}
    )
    print_success(f"Created second LLM agent: {llm_agent2.name} (ID: {llm_agent2.id})")
    print_info(f"Using model: {llm_agent2._llm_provider.model_name}")

    # Verify that the LLM provider is correctly set up
    if hasattr(llm_agent, "_llm_provider"):
        print_info(f"LLM provider class: {type(llm_agent._llm_provider).__name__}")
        print_info(f"LLM provider model: {llm_agent._llm_provider.model_name}")
    else:
        print_warning("LLM agent does not have an LLM provider attached!")
        return

    # 3. Basic interaction with the LLM agent
    print_section("2. Basic interaction with LLM agent")
    message = "Hello, Agent!"

    timer = Timer("LLM Agent Basic Response")
    timer.start()
    response = await llm_agent.aprocess_message(message)
    timer.stop()

    print_info(f"Message: '{message}'")
    print_info(f"Response: '{response.content}'")

    # 4. Question-answering with the LLM agent
    print_section("3. Question-answering with LLM agent")
    message = "What's the capital of France?"

    timer = Timer("LLM Agent Question Response")
    timer.start()
    response = await llm_agent.aprocess_message(message)
    timer.stop()

    print_info(f"Message: '{message}'")
    print_info(f"Response: '{response.content}'")

    # 5. Test conversation context with LLM agent using llama3.2
    print_section("4. Testing conversation context with llama3.2 model")

    # Create agent with llama3.2
    context_agent = create_agent(
        agent_type="llm",
        name="ContextAgent",
        llm_provider_name="ollama",
        # Properly pass llm_provider_kwargs to factory
        llm_provider_kwargs={"model_name": "llama3.2", "timeout": 2400.0}
    )
    print_success(f"Created context agent: {context_agent.name} (ID: {context_agent.id})")
    print_info(f"Using model: {context_agent._llm_provider.model_name}")

    # First message in conversation
    message1 = "My name is Alice."
    print_info(f"First message: '{message1}'")

    # Create a conversation ID to ensure continuity
    conversation_id = "alice_conversation"

    timer = Timer("First Response (llama3.2)")
    timer.start()
    # Use process_message with explicit conversation_id
    response1 = await context_agent.aprocess_message(message1, conversation_id=conversation_id)
    timer.stop()

    print_info(f"Response: '{response1.content}'")

    # Second message that relies on context
    message2 = "What's my name?"
    print_info(f"Second message: '{message2}'")

    timer = Timer("Second Response (with context, llama3.2)")
    timer.start()
    # Use process_message with the SAME conversation_id to maintain context
    response2 = await context_agent.aprocess_message(message2, conversation_id=conversation_id)
    timer.stop()

    print_info(f"Response: '{response2.content}'")

    # Test with system prompt
    print_section("5. Testing with enhanced system prompt (llama3.2)")

    # Create enhanced agent with llama3.2
    enhanced_agent = create_agent(
        agent_type="llm",
        name="EnhancedContextAgent",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "llama3.2", "timeout": 2400.0}
    )
    print_success(f"Created enhanced agent: {enhanced_agent.name} (ID: {enhanced_agent.id})")
    print_info(f"Using model: {enhanced_agent._llm_provider.model_name}")

    # Add a system message first to emphasize the importance of context
    system_message = Message.system_message(
        "You are an assistant that has perfect memory of conversations. "
        "When referring to information shared earlier in the conversation, "
        "always use that information to provide accurate responses."
    )

    # Send system message first
    enhanced_conv_id = "enhanced_context"
    enhanced_agent._conversation.add_message(system_message, conversation_id=enhanced_conv_id)

    # First user message
    await enhanced_agent.aprocess_message(message1, conversation_id=enhanced_conv_id)

    # Second user message
    print_info("Enhanced context test:")
    timer = Timer("Enhanced Context Response (llama3.2)")
    timer.start()
    enhanced_response = await enhanced_agent.aprocess_message(message2, conversation_id=enhanced_conv_id)
    timer.stop()

    print_info(f"Enhanced response: '{enhanced_response.content}'")

    # Test additional conversation abilities
    print_section("6. Testing complex conversation")
    conversation_agent = create_agent(
        agent_type="llm",
        name="ConversationAgent",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": 2400.0}
    )
    print_success(f"Created conversation agent: {conversation_agent.name} (ID: {conversation_agent.id})")
    print_info(f"Using model: {conversation_agent._llm_provider.model_name}")

    # Start a conversation about a specific topic
    topic_message = "Let's talk about machine learning. What's the difference between supervised and unsupervised learning?"
    print_info(f"Topic message: '{topic_message}'")

    timer = Timer("Topic Response")
    timer.start()
    topic_response = await conversation_agent.aprocess_message(topic_message)
    timer.stop()

    print_info(f"Response: '{topic_response.content}'")

    # Follow-up message
    followup_message = "Can you give me an example of each?"
    print_info(f"Follow-up message: '{followup_message}'")

    timer = Timer("Follow-up Response")
    timer.start()
    followup_response = await conversation_agent.aprocess_message(followup_message)
    timer.stop()

    print_info(f"Response: '{followup_response.content}'")

    # Clean up resources properly before exiting
    print_section("7. Cleaning up resources")
    await llm_agent.terminate()
    await llm_agent2.terminate()
    await context_agent.terminate()
    await enhanced_agent.terminate()
    await conversation_agent.terminate()
    print_success("Agents terminated properly")

    separator()
    print_success("All LLM agent tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_basic_agents())
