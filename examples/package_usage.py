"""
Enterprise AI Package Usage Examples

This shows how to use Enterprise AI as a package with no config files required.
"""

from enterprise_ai.agent import create_agent, AgentRole
from enterprise_ai.llm.factory import create_provider


def basic_usage_example():
    """Basic usage with all defaults - no config files needed."""
    
    # Create an agent with all defaults
    agent = create_agent(
        name="assistant",
        role="helpful assistant"  # Simple string role
    )
    
    print(f"Created agent: {agent.get_summary()}")
    return agent


def advanced_usage_example():
    """Advanced usage with explicit configuration."""
    
    # Create custom LLM provider
    llm = create_provider(
        "ollama",
        "llama3.2",
        timeout=120.0,
        base_url="http://localhost:11434"
    )
    
    # Create custom role
    role = AgentRole(
        name="Code Assistant",
        description="A specialized programming assistant",
        capabilities=["code_generation", "debugging", "explanation"]
    )
    
    # Create agent with explicit configuration
    agent = create_agent(
        name="programmer",
        role=role,
        llm=llm,
        reasoning_pattern="swe",  # Software engineering pattern
        verbose=True
    )
    
    print(f"Created specialized agent: {agent.get_summary()}")
    return agent


def environment_override_example():
    """Example using environment variables for configuration."""
    
    import os
    
    # Set environment variables to override defaults
    os.environ["ENTERPRISE_AI_TIMEOUT"] = "180.0"
    os.environ["ENTERPRISE_AI_OLLAMA_MODEL"] = "llama3.2:13b"
    os.environ["ENTERPRISE_AI_VERBOSE"] = "true"
    
    # Create agent - will use environment overrides
    agent = create_agent(
        name="researcher",
        role="research assistant"
    )
    
    print(f"Created agent with env overrides: {agent.get_summary()}")
    return agent


async def usage_example():
    """Example of using the agent for a task."""
    
    # Create agent
    agent = basic_usage_example()
    
    # Use the agent
    response = await agent.process("What is machine learning?")
    print(f"Agent response: {response}")


if __name__ == "__main__":
    print("=== Enterprise AI Package Examples ===\n")
    
    print("1. Basic Usage (all defaults):")
    basic_usage_example()
    print()
    
    print("2. Advanced Usage (explicit config):")
    advanced_usage_example()
    print()
    
    print("3. Environment Override:")
    environment_override_example()
    print()
    
    print("No config files required! The package works out of the box.")
    print("For advanced configuration, see examples/sample_config.yml")
