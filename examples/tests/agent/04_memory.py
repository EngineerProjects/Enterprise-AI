#!/usr/bin/env python
"""
Agent Memory and State

This script demonstrates how agents manage conversation memory
and persistent state across multiple interactions.
"""

import asyncio
import os
import json
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

async def test_agent_memory_state():
    """Test agent memory and state management."""
    print_title("TESTING AGENT MEMORY AND STATE")

    # Create a temporary directory for state storage
    state_dir = "temp_agent_state"
    os.makedirs(state_dir, exist_ok=True)
    
    try:
        # 1. Create agent with persistent state
        print_section("1. Creating agent with persistent state")
        
        agent = create_agent(
            agent_type="llm",
            name="Memory Agent",
            state_type="conversation",
            state_kwargs={"state_dir": state_dir}
        )
        
        print_success(f"Created agent with persistent state: {agent.name} (ID: {agent.id})")
        
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
        
        # Save agent state
        success = agent.save_state()
        print_success(f"Saved agent state: {success}")
        
        # Create a new agent and load the state
        print_info("Creating a new agent and loading saved state")
        
        new_agent = create_agent(
            agent_type="llm",
            agent_id=agent.id,  # Use same ID to load the saved state
            name="Restored Agent",
            state_type="conversation",
            state_kwargs={"state_dir": state_dir}
        )
        
        # Load the state
        success = new_agent.load_state()
        print_success(f"Loaded agent state: {success}")
        
        # Verify the loaded state
        loaded_messages = new_agent.get_messages(conversation_id)
        print_info(f"Loaded conversation has {len(loaded_messages)} messages")
        
        # Test if the new agent remembers the previous context
        memory_test = "Can you remember our previous conversation?"
        print_info(f"Memory test with restored agent: '{memory_test}'")
        
        with Timer("Memory Recall After Restore"):
            response = await new_agent.aprocess_message(memory_test)
        
        print_info(f"Response from restored agent: '{response.content}'")
        
        print_success("All memory and state tests completed successfully!")
        
    finally:
        # Clean up the temporary directory
        import shutil
        shutil.rmtree(state_dir, ignore_errors=True)
        print_info("Cleaned up temporary state directory")
        separator()

if __name__ == "__main__":
    asyncio.run(test_agent_memory_state())