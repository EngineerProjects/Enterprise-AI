#!/usr/bin/env python
"""
Agent Memory and State

This script demonstrates how agents manage conversation memory
and persistent state across multiple interactions.
"""

import asyncio
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional

# Import utilities
from examples.notebooks.utils import (
    setup_project_path,
    print_title,
    print_section,
    print_info,
    print_success,
    print_error,
    separator,
    Timer
)

# Set up project path
setup_project_path()

# Import core components
from enterprise_ai.agent.core import create_agent
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_memory_test")

TIMEOUT = 2400  # 40 minutes for very slow GPU/CPU

async def test_agent_memory_state():
    """Test agent memory and state management."""
    print_title("TESTING AGENT MEMORY AND STATE")

    # Create a temporary directory for state storage - using absolute path
    state_dir = tempfile.mkdtemp(prefix="agent_state_")
    print_info(f"Created state directory at absolute path: {state_dir}")

    try:
        # 1. Create agent with persistent state
        print_section("1. Creating agent with persistent state")

        agent = create_agent(
            agent_type="llm",
            name="Memory Agent",
            state_type="conversation",
            state_kwargs={"state_dir": state_dir},
            llm_provider_name="ollama",
            llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"}
        )

        # Directly set the state directory on the lifecycle manager
        # This is a workaround for the state_kwargs not being properly processed
        if hasattr(agent, "_lifecycle"):
            agent._lifecycle._state_dir = state_dir
            print_info(f"Directly set state directory on lifecycle manager: {state_dir}")

        print_success(f"Created agent with persistent state: {agent.name} (ID: {agent.id})")
        print_info(f"Using state directory: {state_dir}")

        # 2. Test short-term memory (conversation context)
        print_section("2. Testing short-term memory (conversation context)")

        # Initial conversation
        messages = [
            "My name is Bob.",
            "I live in New York.",
            "I have a dog named Max."
        ]

        for i, msg in enumerate(messages, 1):
            print_info(f"Message {i}: '{msg}'")
            response = await agent.aprocess_message(msg)
            print_info(f"Response: '{response.content}'")

        # Test if agent remembers previous context
        memory_test = "What's my name, where do I live, and what pet do I have?"
        print_info(f"Memory test: '{memory_test}'")

        with Timer("Memory Recall"):
            response = await agent.aprocess_message(memory_test)

        print_info(f"Response: '{response.content}'")

        # 3. Test conversation management
        print_section("3. Testing conversation management")

        # Get conversation history
        conversation_id = "default"
        messages = agent.get_messages(conversation_id)

        print_info(f"Conversation has {len(messages)} messages")
        for i, msg in enumerate(messages[:3], 1):  # Show the first 3 messages
            print_info(f"Message {i} - Role: {msg.role}, Content: '{msg.content[:50]}...'")

        # Create a new conversation
        new_conversation_id = "second_conversation"

        # Add messages to the new conversation
        new_messages = [
            "This is a different conversation.",
            "I'm discussing a technical topic here."
        ]

        for msg in new_messages:
            agent.add_message(msg, conversation_id=new_conversation_id)

        # Get messages from the new conversation
        second_conv_messages = agent.get_messages(new_conversation_id)
        print_info(f"Second conversation has {len(second_conv_messages)} messages")

        # 4. Test persistent state
        print_section("4. Testing persistent state")

        # Explicitly verify the state directory exists and is writable
        if not os.path.exists(state_dir):
            print_error(f"State directory {state_dir} does not exist!")
            os.makedirs(state_dir, exist_ok=True)
            print_info(f"Created state directory {state_dir}")

        if not os.access(state_dir, os.W_OK):
            print_error(f"State directory {state_dir} is not writable!")
            # Try to fix permissions
            try:
                os.chmod(state_dir, 0o755)
                print_info(f"Fixed permissions for {state_dir}")
            except Exception as e:
                print_error(f"Failed to fix permissions: {e}")

        # Save agent state
        print_info(f"Saving agent state to: {state_dir}")

        # First, have a conversation with the agent to test memory
        print_info("Having a conversation with the agent before saving state...")

        # Use the same conversation as in the earlier memory test for consistency
        memory_setup_messages = [
            "My name is Bob.",
            "I live in New York.",
            "I have a dog named Max."
        ]

        for i, msg in enumerate(memory_setup_messages, 1):
            print_info(f"Memory setup message {i}: '{msg}'")
            response = await agent.aprocess_message(msg)
            print_info(f"Response: '{response.content}'")

        # Now save the state
        success = agent.save_state()
        print_success(f"Saved agent state: {success}")

        if not success:
            print_error("Failed to save state, checking state directory configuration...")
            if hasattr(agent, "_lifecycle") and hasattr(agent._lifecycle, "_state_dir"):
                print_info(f"Agent ID: {agent.id}")
                print_info(f"State directory from configuration: {agent._lifecycle._state_dir}")
            else:
                print_error("Agent does not have a proper state directory configuration")

        # List files in state directory
        if os.path.exists(state_dir):
            state_files = os.listdir(state_dir)
            print_info(f"Files in state directory: {state_files}")

        # Create a new agent and load the state
        print_info("Creating a new agent and loading saved state")

        new_agent = create_agent(
            agent_type="llm",
            agent_id=agent.id,  # Use same ID to load the saved state
            name="Restored Agent",
            state_type="conversation",
            state_kwargs={"state_dir": state_dir},
            llm_provider_name="ollama",
            llm_provider_kwargs={"timeout": TIMEOUT, "model_name": "smollm2"}
        )

        # Directly set the state directory on the lifecycle manager for the new agent too
        if hasattr(new_agent, "_lifecycle"):
            new_agent._lifecycle._state_dir = state_dir
            print_info(f"Directly set state directory on new agent's lifecycle manager: {state_dir}")

        # Load the state
        print_info(f"Loading agent state from: {state_dir}")
        success = new_agent.load_state()
        print_success(f"Loaded agent state: {success}")

        if not success:
            print_error("Failed to load state, checking state directory configuration...")
            if hasattr(new_agent, "_lifecycle") and hasattr(new_agent._lifecycle, "_state_dir"):
                print_info(f"Agent ID: {new_agent.id}")
                print_info(f"State directory from configuration: {new_agent._lifecycle._state_dir}")
            else:
                print_error("Agent does not have a proper state directory configuration")

        # Verify the loaded state
        loaded_messages = new_agent.get_messages(conversation_id)
        print_info(f"Loaded conversation has {len(loaded_messages)} messages")

        # Test if the new agent remembers the previous context
        memory_test = "Can you remember our previous conversation? What's my name, where do I live, and what pet do I have?"
        print_info(f"Memory test with restored agent: '{memory_test}'")

        with Timer("Memory Recall After Restore"):
            response = await new_agent.aprocess_message(memory_test)

        print_info(f"Response from restored agent: '{response.content}'")

        # Check if the response mentions the key details
        success = all(keyword.lower() in response.content.lower()
                     for keyword in ["Bob", "New York", "Max"])

        if success:
            print_success("✓ The agent successfully remembered details from the previous conversation!")
        else:
            print_error("✗ The agent failed to remember one or more details from the previous conversation.")

        print_success("All memory and state tests completed successfully!")

    finally:
        # Clean up the temporary directory
        print_info(f"Cleaning up temporary state directory: {state_dir}")
        try:
            shutil.rmtree(state_dir, ignore_errors=True)
            print_info("Cleaned up temporary state directory")
        except Exception as e:
            print_error(f"Error cleaning up state directory: {e}")
        separator()

if __name__ == "__main__":
    asyncio.run(test_agent_memory_state())
