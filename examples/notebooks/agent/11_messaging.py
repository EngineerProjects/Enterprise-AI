#!/usr/bin/env python
"""
Advanced Agent Messaging

This script demonstrates advanced messaging capabilities between agents,
including different message types and structured communication.
"""

import asyncio
import os
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
from enterprise_ai.agent.messaging.message import (
    create_message,
    QueryMessage,
    ResponseMessage,
    NotificationMessage,
    ErrorMessage
)
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_messaging_test")

# Set a high timeout for our slow devices
TIMEOUT = 1200  # 20 minutes for very slow GPU/CPU

async def test_advanced_messaging():
    """Test advanced messaging capabilities between agents."""
    print_title("TESTING ADVANCED AGENT MESSAGING")
    
    # Set environment variable for Ollama timeout
    os.environ["ENTERPRISE_AI_OLLAMA_TIMEOUT"] = str(TIMEOUT)

    # 1. Create agents for messaging
    print_section("1. Creating agents for messaging")
    
    agent1 = create_agent(
        agent_type="llm",
        name="Agent 1",
        role_type="developer",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": TIMEOUT}
    )
    
    agent2 = create_agent(
        agent_type="llm",
        name="Agent 2",
        role_type="researcher",
        llm_provider_name="ollama",
        llm_provider_kwargs={"model_name": "smollm2", "timeout": TIMEOUT}
    )
    
    print_success(f"Created Agent 1: {agent1.name} (ID: {agent1.id})")
    print_success(f"Created Agent 2: {agent2.name} (ID: {agent2.id})")
    
    # 2. Basic message passing
    print_section("2. Basic message passing")
    
    # Create a query message
    query = create_message(
        "QUERY",
        sender_id=agent1.id,
        receiver_id=agent2.id,
        content="What are the best machine learning libraries for Python?",
        metadata={"priority": "high", "topic": "machine_learning"}
    )
    
    print_info(f"Query from Agent 1 to Agent 2: '{query.content}'")
    print_info(f"Message metadata: {query.metadata}")
    
    # Process the message
    with Timer("Query Processing"):
        response = await agent2.aprocess_message(query)
    
    print_info(f"Response from Agent 2: '{response.content}' (truncated)")
    if hasattr(response, "metadata") and response.metadata:
        print_info(f"Response metadata: {response.metadata}")
    
    # 3. Different message types
    print_section("3. Different message types")
    
    # Notification message
    notification = NotificationMessage(
        sender_id=agent1.id,
        receiver_id=agent2.id,
        content="The project deadline has been extended to next week.",
        metadata={"notification_type": "deadline_update", "urgency": "medium"}
    )
    
    print_info(f"Notification from Agent 1 to Agent 2: '{notification.content}'")
    print_info(f"Notification type: {notification.metadata.get('notification_type')}")
    
    with Timer("Notification Processing"):
        notif_response = await agent2.aprocess_message(notification)
    
    print_info(f"Response to notification: '{notif_response.content}' (truncated)")
    
    # Error message
    error_msg = ErrorMessage(
        sender_id=agent1.id,
        receiver_id=agent2.id,
        error_message="Failed to process data due to missing values.",  # Changed from content to error_message
        error_code="DATA_VALIDATION_ERROR",
        metadata={"affected_component": "data_processor"}
    )
    
    print_info(f"Error message from Agent 1 to Agent 2: '{error_msg.content}'")
    print_info(f"Error code: {error_msg.metadata.get('error_code')}")
    
    with Timer("Error Message Processing"):
        error_response = await agent2.aprocess_message(error_msg)
    
    print_info(f"Response to error: '{error_response.content}' (truncated)")
    
    # 4. Message with structured data
    print_section("4. Message with structured data")
    
    structured_data = {
        "project_name": "AI Research Platform",
        "components": [
            {"name": "Data Collection", "status": "completed", "owner": "Team A"},
            {"name": "Model Training", "status": "in_progress", "owner": "Team B"},
            {"name": "Evaluation", "status": "pending", "owner": "Team C"}
        ],
        "deadline": "2025-08-15"
    }
    
    # Create a custom "DATA" message type for structured data
    try:
        structured_msg = create_message(
            "DATA",
            sender_id=agent1.id,
            receiver_id=agent2.id,
            content="Project status update",
            metadata={"data_type": "project_status", "structured_data": structured_data}
        )
        
        print_info(f"Structured message from Agent 1 to Agent 2: '{structured_msg.content}'")
        print_info(f"Structured data: {structured_msg.metadata.get('structured_data')}")
        
        with Timer("Structured Message Processing"):
            struct_response = await agent2.aprocess_message(structured_msg)
        
        print_info(f"Response to structured message: '{struct_response.content}' (truncated)")
    except ValueError as e:
        print_error(f"Error creating structured message: {e}")
        # Fallback to using a regular notification message
        fallback_msg = NotificationMessage(
            sender_id=agent1.id,
            receiver_id=agent2.id,
            content=f"Project status update: {structured_data['project_name']} due {structured_data['deadline']}",
            metadata={"data_type": "project_status", "structured_data": structured_data}
        )
        with Timer("Fallback Structured Message Processing"):
            struct_response = await agent2.aprocess_message(fallback_msg)
        
        print_info(f"Response to fallback message: '{struct_response.content}' (truncated)")
    
    # Properly clean up resources
    try:
        # Terminate agents to clean up resources
        if hasattr(agent1, "terminate"):
            await agent1.terminate()
            print_info(f"Terminated Agent 1: {agent1.id}")
        
        if hasattr(agent2, "terminate"):
            await agent2.terminate()
            print_info(f"Terminated Agent 2: {agent2.id}")
            
        # Ensure MCP sessions are properly closed
        from enterprise_ai.mcp.server import get_mcp_server
        mcp_server = get_mcp_server()
        
        # Close individual agent sessions if they exist
        for agent in [agent1, agent2]:
            if hasattr(agent, "_tools") and agent._tools and hasattr(agent._tools, "_mcp_client"):
                # Mark as explicitly closed
                if agent._tools._mcp_client:
                    agent._tools._mcp_client._explicitly_closed = True
                
                # Close the session
                agent_session_id = f"agent-{agent.id}"
                try:
                    await mcp_server.close_session(agent_session_id)
                    print_info(f"Closed MCP session: {agent_session_id}")
                except Exception as e:
                    print_error(f"Error closing session {agent_session_id}: {e}")
    except Exception as e:
        print_error(f"Error during cleanup: {e}")
    
    print_success("All advanced messaging tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_advanced_messaging())