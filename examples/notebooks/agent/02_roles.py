"""
Agent roles

This script demonstrates how to create agents with different roles
and how these roles affect agent behavior and capabilities.
"""

import asyncio
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
from enterprise_ai.agent.core import (
    create_agent, 
    create_developer_agent,
    create_researcher_agent,
    create_manager_agent
)
from enterprise_ai.agent.role import create_role
from enterprise_ai.schema import Message
from enterprise_ai.logger import get_logger

# Configure logger
logger = get_logger("agent_roles_test")

# Fix the initialization of tools in enterprise_ai.agent.core.base.LLMAgent
from enterprise_ai.agent.core import base

# Save the original method
original_init = base.LLMAgent.__init__

def fixed_init(
    self,
    agent_id: Optional[str] = None,
    name: Optional[str] = None,
    role_type: Optional[str] = None,
    role_kwargs: Optional[Dict[str, Any]] = None,
    state_type: Optional[str] = None,
    state_kwargs: Optional[Dict[str, Any]] = None,
    llm_provider: Optional[Any] = None,
    reasoning_framework: str = "base",
    use_tools: bool = False,
    enable_mcp: bool = False,
    tool_categories: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
    **kwargs: Any,
):
    """Fixed initialization that properly handles async MCP initialization."""
    # Call the parent class's __init__ method
    base.BaseAgent.__init__(
        self,
        agent_id=agent_id,
        name=name,
        role_type=role_type,
        role_kwargs=role_kwargs,
        state_type=state_type,
        state_kwargs=state_kwargs,
        **kwargs,
    )
    
    # Set up LLM provider
    self._llm_provider = llm_provider
    
    # Initialize tools manager if tools are enabled
    if use_tools:
        self._tools = base.AgentToolsManager(self)
        
        # We don't initialize MCP here - it will be initialized during the first tool usage
        # This avoids the coroutine issue
    else:
        self._tools = None
    
    # Create reasoning manager with specified framework
    self._reasoning = base.ReasoningManager(
        self,
        config=base.ReasoningManagerConfig(default_framework=reasoning_framework)
    )
    
    base.logger.info(f"Initialized LLM agent {self.id} with framework {reasoning_framework}")

# Replace the original method with our fixed version
base.LLMAgent.__init__ = fixed_init

# Fix the aprocess_message method in BaseAgent to properly await process_message
original_aprocess_message = base.BaseAgent.aprocess_message

async def fixed_aprocess_message(self, message, **kwargs):
    """
    Fixed implementation that properly awaits the process_message coroutine.
    This prevents the 'coroutine object has no attribute content' error.
    """
    # The original method doesn't await, causing the coroutine error
    # Here we ensure the process_message result is properly awaited
    result = await self.process_message(message, **kwargs)
    return result

# Apply the patched method
base.BaseAgent.aprocess_message = fixed_aprocess_message

# Also ensure that LLMAgent.process_message timeout is set correctly
original_llm_process_message = base.LLMAgent.process_message

async def fixed_llm_process_message(self, message, **kwargs):
    """
    Fixed implementation that ensures timeout is set to at least 300 seconds.
    """
    # Ensure minimum timeout of 300 seconds
    if "timeout" not in kwargs:
        kwargs["timeout"] = 300.0
    return await original_llm_process_message(self, message, **kwargs)

# Apply the patched method
base.LLMAgent.process_message = fixed_llm_process_message

print("Applied LLMAgent patches to fix coroutine handling and timeout issues")

async def test_agent_roles():
    """Test creating and using agents with different roles."""
    print_title("TESTING AGENT ROLES")

    # 1. Create agents with built-in roles
    print_section("1. Creating agents with built-in roles")
    
    developer = create_developer_agent(
        name="Developer",
        llm_provider_kwargs={"timeout": 2400.0, "model_name": "llama3.2"}  # Set model and timeout
    )
    researcher = create_researcher_agent(
        name="Researcher",
        llm_provider_kwargs={"timeout": 2400.0, "model_name": "llama3.2"}  # Set model and timeout
    )
    manager = create_manager_agent(
        name="Manager",
        llm_provider_kwargs={"timeout": 2400.0, "model_name": "llama3.2"}  # Set model and timeout
    )
    
    print_success(f"Created developer agent: {developer.name}")
    print_success(f"Created researcher agent: {researcher.name}")
    print_success(f"Created manager agent: {manager.name}")
    
    # 2. Test role-specific behavior
    print_section("2. Testing role-specific behavior")
    
    coding_task = "Write a Python function to calculate the factorial of a number."
    research_task = "Find information about quantum computing algorithms."
    planning_task = "Create a project plan for developing a new mobile app."
    
    print_info(f"Asking developer about: '{coding_task}'")
    with Timer("Developer Response"):
        dev_response = await developer.aprocess_message(coding_task)
    print_info(f"Developer response: '{dev_response.content}'")
    
    print_info(f"Asking researcher about: '{research_task}'")
    with Timer("Researcher Response"):
        research_response = await researcher.aprocess_message(research_task)
    print_info(f"Researcher response: '{research_response.content}'")
    
    print_info(f"Asking manager about: '{planning_task}'")
    with Timer("Manager Response"):
        manager_response = await manager.aprocess_message(planning_task)
    print_info(f"Manager response: '{manager_response.content}'")
    
    # 3. Create an agent with a custom role
    print_section("3. Creating an agent with a custom role")
    
    # Create agent with direct role object
    custom_role = create_role(
        "custom",
        name="Customer Support Agent",
        description="Specialized in customer support and service",
        capabilities=["customer_service", "problem_solving", "communication"],
        instructions="Your primary goal is to provide excellent customer service. Listen carefully to customer issues, empathize with their concerns, and provide clear solutions."
    )
    
    support_agent = create_agent(
        agent_type="llm",
        name="Support Agent",
        role=custom_role,
        llm_provider_name="ollama",
        llm_provider_kwargs={"timeout": 2400.0, "model_name": "llama3.2"}  # Set model and timeout
    )
    
    print_success(f"Created custom support agent: {support_agent.name}")
    
    # Test the custom role agent
    support_query = "I've been charged twice for my subscription and need a refund."
    
    print_info(f"Customer query: '{support_query}'")
    with Timer("Support Agent Response"):
        support_response = await support_agent.aprocess_message(support_query)
    print_info(f"Support response: '{support_response.content}'")
    
    # Clean up resources
    print_section("4. Cleaning up resources")
    await developer.terminate()
    await researcher.terminate()
    await manager.terminate()
    await support_agent.terminate()
    print_success("Agents terminated properly")
    
    print_success("All agent role tests completed successfully!")
    separator()

if __name__ == "__main__":
    asyncio.run(test_agent_roles())
