# Enterprise AI Documentation: Agent Module

## Module Overview

The Agent module is the core component of the Enterprise AI platform that enables the creation and orchestration of intelligent agents. These agents can reason, make decisions, use tools, and collaborate to accomplish complex tasks.

This module provides a flexible framework with different types of agents, reasoning patterns, memory implementations, and communication protocols. It's designed to be extensible and modular, allowing for specialized agents with different roles and capabilities.

Key features of the Agent module include:

- **Multiple Agent Types**: From simple base agents to advanced LLM-powered agents
- **Reasoning Frameworks**: Various reasoning patterns like ReAct, Chain of Thought, Software Engineering reasoning
- **Tool Integration**: Seamless discovery and use of tools via the Model Context Protocol (MCP)
- **Role Specialization**: Predefined roles like Developer, Manager, Researcher with customizable behaviors
- **State Management**: Persistent state tracking with conversation history
- **Memory Implementations**: Different memory patterns for storing and retrieving information
- **Inter-Agent Communication**: Structured messaging system for agent collaboration

## Key Components

### 1. Agent Protocol and Implementations

The foundation of the agent system is the `AgentProtocol` which defines the core capabilities all agents must implement.

#### `AgentProtocol`

The base protocol that defines what capabilities an agent must have:

- Processing messages
- Handling tasks
- Maintaining state
- Exposing identity information

```python
from enterprise_ai.agent import AgentProtocol

# All agent implementations follow this protocol
# Methods defined in the protocol:
# - id (property): Unique identifier
# - name (property): Human-readable name
# - state (property): Current agent state
# - process_message(message): Process incoming messages
# - assign_task(task): Take on a new task
# - process_task(): Execute the current task
# - get_status(): Get agent status summary
```

#### `BaseAgent`

A concrete implementation providing the foundational agent capabilities:

- Basic message handling
- Simple task processing
- State management

```python
from enterprise_ai.agent import BaseAgent

# Create a basic agent
agent = BaseAgent(
    agent_id="agent-123",
    name="Basic Agent",
    role_type="custom",
    role_kwargs={"name": "Assistant", "description": "General assistant role"},
    state_type="base"
)

# Process a message
response = agent.process_message(some_message)

# Assign and process a task
agent.assign_task(some_task)
status = agent.process_task()
```

#### `LLMAgent`

An advanced agent implementation powered by large language models:

- LLM-based message processing
- Tool usage capabilities
- Advanced reasoning frameworks
- Conversation history

```python
from enterprise_ai.agent import LLMAgent
from enterprise_ai.llm import get_default_provider

# Create an LLM-powered agent
agent = LLMAgent(
    agent_id="llm-agent-123",
    name="Assistant",
    role_type="researcher",
    llm_provider=get_default_provider(),
    reasoning_framework="react",
    use_tools=True,
    enable_mcp=True,
    tool_categories=["research", "file"]
)

# Process a message with LLM capabilities
response = agent.process_message(some_message)

# Change reasoning framework
agent.set_reasoning_framework("cot")

# Enable/disable tools
agent.enable_tools(tool_categories=["development"])
agent.disable_tools()
```

### 2. Reasoning Frameworks

The Agent module provides several reasoning frameworks that define how agents process information and make decisions.

#### `ReasoningFramework`

Base protocol for all reasoning frameworks:

- Processing inputs
- Handling tool execution
- Formatting system prompts
- Task processing

```python
from enterprise_ai.agent.reasoning import (
    ReActReasoning,
    ChainOfThoughtReasoning,
    ToolAugmentedCoT,
    SoftwareEngineeringReasoning,
    MCPReasoning
)

# Available reasoning frameworks
frameworks = {
    "react": "ReAct (Reasoning + Acting) for systematic thinking and tool use",
    "cot": "Chain of Thought for step-by-step reasoning",
    "tool_cot": "Tool-augmented Chain of Thought",
    "swe": "Software Engineering reasoning for development tasks",
    "mcp": "Model Context Protocol for standardized tool integration"
}
```

#### `ReActReasoning` (Reasoning + Acting)

A framework that alternates between:

1. **Thought**: Reasoning about what to do
1. **Action**: Using tools to gather information or perform actions
1. **Observation**: Interpreting the results
1. Repeating until task completion

```python
# ReAct is ideal for tasks requiring:
# - External tool usage
# - Multi-step problem solving
# - Information gathering
# - Sequential decision making
```

#### `ChainOfThoughtReasoning` (CoT)

A framework that encourages breaking down complex problems into steps:

- Explicit step-by-step thinking
- Showing work for complex reasoning
- Detailed explanation of logical connections

```python
# Chain of Thought is ideal for tasks requiring:
# - Complex logical reasoning
# - Mathematical problem solving
# - Detailed explanations
# - Transparent thinking processes
```

#### `SoftwareEngineeringReasoning` (SWE)

Specialized framework for software development tasks:

- Requirements analysis
- Design and implementation
- Testing and debugging
- Code optimization

```python
# SWE reasoning is ideal for tasks involving:
# - Code generation
# - Debugging
# - Software design
# - Technical architecture
```

#### `MCPReasoning`

Framework specifically designed to work with the Model Context Protocol:

- Standardized tool discovery
- Consistent tool execution patterns
- Dynamic tool selection

```python
# MCP reasoning is ideal for:
# - Dynamic tool discovery
# - Standardized tool execution
# - Tool-heavy workflows
```

### 3. Agent Roles

The Agent module includes several role implementations that define an agent's capabilities, instructions, and specialty.

#### `AgentRole`

Base protocol for all roles defining:

- Name and description
- Capabilities list
- Role-specific instructions

```python
from enterprise_ai.agent.role import (
    BaseAgentRole,
    SimpleRole,
    TemplatedRole,
    DeveloperRole,
    ManagerRole,
    ResearcherRole
)

# Create a custom role
custom_role = SimpleRole(
    _name="Analyst",
    _description="Data analysis specialist",
    _capabilities=["data_processing", "visualization", "statistical_analysis"],
    _instructions="You are an expert in data analysis and visualization."
)
```

#### Specialized Roles

The module includes several pre-defined specialized roles:

```python
# Developer role
dev_role = DeveloperRole(
    additional_context="Specialized in Python backend development"
)

# Manager role
manager_role = ManagerRole(
    additional_context="Focused on Agile project management"
)

# Researcher role
researcher_role = ResearcherRole(
    additional_context="Specialized in market research and competitive analysis"
)
```

### 4. Agent State and Memory

The Agent module provides various state and memory implementations to maintain agent information.

#### `AgentState`

Protocol for managing agent state including:

- Current task tracking
- Role assignment
- Memory access
- State persistence

```python
from enterprise_ai.agent.state import (
    BaseAgentState,
    ConversationState,
    create_agent_state
)

# Conversation state for tracking history
state = create_agent_state(
    "agent-123",
    state_type="conversation",
    memory_type="dict",
    state_dir="/path/to/state",
    max_history=50
)
```

#### Memory Implementations

Different memory patterns for storing and retrieving information:

```python
from enterprise_ai.agent.memory import (
    DictMemory,
    NamespacedMemory,
    ScopedMemory,
    create_memory
)

# Dictionary-based memory
dict_memory = create_memory("dict")

# Namespaced memory for organization
namespaced = create_memory("namespaced")
namespaced.add("key", "value", namespace="category")

# Scoped memory with automatic cleanup
scoped = create_memory("scoped")
scoped.push_scope()  # Create new scope
scoped.add("temp_key", "temp_value")
scoped.pop_scope()   # Clean up scope and all its values
```

### 5. Messaging System

The Agent module includes a messaging system for inter-agent communication.

#### `AgentMessage`

Protocol for agent-to-agent messages with various implementations:

```python
from enterprise_ai.agent.message import (
    BaseAgentMessage,
    TaskAssignmentMessage,
    TaskUpdateMessage,
    QueryMessage,
    ResponseMessage,
    BroadcastMessage,
    NotificationMessage,
    ErrorMessage,
    create_message
)

# Create a query message
query = create_message(
    "QUERY",
    sender_id="agent-1",
    receiver_id="agent-2",
    content="What is the status of task XYZ?"
)

# Create a broadcast message
broadcast = create_message(
    "BROADCAST",
    sender_id="manager-agent",
    content="Team meeting in 5 minutes."
)

# Create a task assignment
task_msg = create_message(
    "TASK_ASSIGNMENT",
    sender_id="manager",
    receiver_id="worker",
    task_id="task-123",
    task_description="Analyze the latest sales data."
)
```

### 6. Tool Integration

The Agent module provides mechanisms for agents to discover and use tools.

#### `AgentToolManager`

Manages tool access and execution for an agent:

- Tool discovery via MCP
- Tool execution
- Tool usage history tracking

```python
from enterprise_ai.agent.tooling import AgentToolManager
from enterprise_ai.tool.core.base import BaseTool

# Create a tool manager
tool_manager = AgentToolManager("agent-123")

# Add a tool directly
tool_manager.add_tool(some_tool)

# Enable MCP for dynamic tool discovery
await tool_manager.enable_mcp(
    tool_categories=["research", "development"],
    tool_names=["WebSearch", "CodeExecution"]
)

# Execute a tool
result = await tool_manager.execute_tool(
    "WebSearch",
    query="Enterprise AI patterns"
)

# Get formatted tool descriptions for prompts
tool_descriptions = tool_manager.get_formatted_tool_descriptions()
```

## Architecture Design

The Agent module follows a highly modular, protocol-based architecture with several key design patterns:

### 1. Protocol-Driven Design

The system is built around clearly defined protocols (interfaces) that define contracts between components:

- `AgentProtocol`: Defines what an agent can do
- `AgentRole`: Defines specialization behavior
- `AgentState`: Defines state management
- `AgentMemory`: Defines memory capabilities
- `ReasoningFramework`: Defines reasoning patterns

This protocol-based design enables:

- Multiple implementations of core interfaces
- Easy extension with new implementations
- Clear separation of concerns
- Testable components

### 2. Factory and Builder Patterns

The module uses factory functions and builder patterns for flexible object creation:

```python
# Factory pattern for agent creation
from enterprise_ai.agent import create_agent

agent = create_agent(
    agent_type="llm",
    name="Research Assistant",
    role_type="researcher"
)

# Builder pattern for more complex construction
from enterprise_ai.agent import AgentBuilder

agent = (AgentBuilder()
    .with_type("llm")
    .with_name("Developer Assistant")
    .with_role("developer")
    .with_reasoning("swe")
    .with_tools(True)
    .with_tool_categories(["development", "execution"])
    .build())
```

### 3. Layered Architecture

The module is organized in a layered architecture:

1. **Core Layer**: Basic protocols and implementations (BaseAgent)
1. **Capability Layer**: Enhanced capabilities (LLMAgent, reasoning frameworks)
1. **Specialization Layer**: Role implementations and tool integration
1. **Communication Layer**: Messaging system for agent interaction

### 4. Extension Points

The architecture includes several extension points:

- **Reasoning Frameworks**: Register new reasoning approaches
- **Roles**: Create custom role implementations
- **Memory**: Implement new memory patterns
- **Tools**: Integrate custom tools via MCP

## Usage Examples

### Creating and Using Agents

#### Basic Agent Creation

```python
from enterprise_ai.agent import create_agent, BaseAgent

# Create a simple agent
agent = create_agent(
    agent_type="base",
    agent_id="simple-agent",
    name="Simple Agent",
    role_type="custom",
    role_kwargs={
        "name": "Assistant",
        "description": "General purpose assistant",
        "instructions": "You assist users with various tasks."
    }
)

# Process a message
from enterprise_ai.agent.message import create_message

msg = create_message("QUERY", "user-123", "simple-agent", "What can you do?")
response = agent.process_message(msg)
print(response.content)
```

#### LLM Agent with Reasoning

```python
from enterprise_ai.agent import create_agent
from enterprise_ai.llm import get_default_provider

# Create an LLM agent with Chain of Thought reasoning
agent = create_agent(
    agent_type="llm",
    agent_id="thinking-agent",
    name="Thinking Agent",
    role_type="researcher",
    llm_provider_name="anthropic",  # Will use Anthropic's Claude
    reasoning_framework="cot",      # Chain of Thought reasoning
    use_tools=False                 # No tools needed for pure reasoning
)

# Process a complex question
from enterprise_ai.agent.message import create_message

msg = create_message(
    "QUERY",
    "user-123",
    "thinking-agent",
    "Explain the key differences between supervised and unsupervised learning."
)
response = agent.process_message(msg)
print(response.content)  # Will show step-by-step reasoning
```

#### Tool-using Agent with ReAct

```python
from enterprise_ai.agent import create_agent

# Create a developer agent with tools and ReAct reasoning
agent = create_agent(
    agent_type="llm",
    agent_id="dev-agent",
    name="Developer Assistant",
    role_type="developer",
    reasoning_framework="react",
    use_tools=True,
    enable_mcp=True,
    tool_categories=["development", "execution", "file"]
)

# Ask it to perform a development task
from enterprise_ai.agent.message import create_message

msg = create_message(
    "QUERY",
    "user-123",
    "dev-agent",
    "Create a Python function that calculates the Fibonacci sequence recursively."
)
response = agent.process_message(msg)
print(response.content)  # Will show thought process and code
```

### Specialized Agent Creation

```python
from enterprise_ai.agent import (
    create_developer_agent,
    create_manager_agent,
    create_researcher_agent
)

# Create specialized agents
dev_agent = create_developer_agent(
    name="Code Wizard",
    additional_context="Specialized in Python and JavaScript development"
)

manager_agent = create_manager_agent(
    name="Project Lead",
    additional_context="Experienced in Agile project management"
)

researcher_agent = create_researcher_agent(
    name="Research Specialist",
    additional_context="Focuses on data gathering and synthesis"
)
```

### Task Assignment and Processing

```python
from enterprise_ai.agent import create_agent
from enterprise_ai.agent.types import Task, TaskStatus

# Create an agent
agent = create_agent(
    agent_type="llm",
    name="Task Processor",
    reasoning_framework="cot"
)

# Create and assign a task
task = Task(
    id="task-123",
    description="Summarize the key points from the latest quarterly report.",
    dependencies=[]
)

# Assign the task
if agent.assign_task(task):
    # Process the task
    status = agent.process_task()

    # Check the result
    if status == TaskStatus.COMPLETED:
        task_result = agent.state.current_task.metadata.get("response")
        print(f"Task completed. Result: {task_result}")
    else:
        print(f"Task processing failed with status: {status.name}")
```

### Agent Communication

```python
from enterprise_ai.agent import create_agent
from enterprise_ai.agent.message import create_message

# Create two agents
manager = create_agent(
    agent_type="llm",
    agent_id="manager-1",
    name="Project Manager",
    role_type="manager"
)

worker = create_agent(
    agent_type="llm",
    agent_id="worker-1",
    name="Worker",
    role_type="developer"
)

# Manager assigns a task to worker
task_msg = create_message(
    "TASK_ASSIGNMENT",
    sender_id=manager.id,
    receiver_id=worker.id,
    task_id="task-123",
    task_description="Implement the user authentication module."
)

# Worker processes the message
response = worker.process_message(task_msg)
print(f"Worker response: {response.content}")

# Worker updates task status
update_msg = create_message(
    "TASK_UPDATE",
    sender_id=worker.id,
    receiver_id=manager.id,
    task_id="task-123",
    status="IN_PROGRESS",
    status_message="Started working on the authentication module."
)

# Manager processes the update
manager.process_message(update_msg)
```

### Tool Discovery and Execution

```python
from enterprise_ai.agent import create_agent

# Create an agent with MCP tool discovery
agent = create_agent(
    agent_type="llm",
    agent_id="tool-user",
    name="Tool User",
    reasoning_framework="mcp",
    use_tools=True,
    enable_mcp=True,
    tool_categories=["research", "file", "content"]
)

# Get available tools
available_tools = agent._tool_manager.list_tools()
print(f"Available tools: {available_tools}")

# Execute a tool directly
import asyncio

async def execute_tool():
    result = await agent._tool_manager.execute_tool(
        "WebSearch",
        query="Enterprise AI agents"
    )
    print(f"Tool result: {result.output}")

# Run the async function
asyncio.run(execute_tool())

# Process a message that will use tools
from enterprise_ai.agent.message import create_message

msg = create_message(
    "QUERY",
    "user-123",
    "tool-user",
    "Search for information about Multi-Agent Systems and summarize the key concepts."
)

# The agent will use tools as needed to respond
response = agent.process_message(msg)
print(response.content)
```

### Switching Reasoning Frameworks

```python
from enterprise_ai.agent import create_agent

# Create an LLM agent
agent = create_agent(
    agent_type="llm",
    agent_id="adaptive-agent",
    name="Adaptive Agent",
    reasoning_framework="cot"  # Start with Chain of Thought
)

# Process a reasoning task
from enterprise_ai.agent.message import create_message

reasoning_msg = create_message(
    "QUERY",
    "user-123",
    "adaptive-agent",
    "Explain why the sky appears blue during the day."
)
response1 = agent.process_message(reasoning_msg)
print("CoT Response:", response1.content)

# Switch to ReAct for a task requiring tools
agent.set_reasoning_framework("react")
agent.enable_tools(enable_mcp=True, tool_categories=["research"])

tool_msg = create_message(
    "QUERY",
    "user-123",
    "adaptive-agent",
    "Find the current exchange rate between USD and EUR."
)
response2 = agent.process_message(tool_msg)
print("ReAct Response:", response2.content)

# Switch to SWE for a development task
agent.set_reasoning_framework("swe")

dev_msg = create_message(
    "QUERY",
    "user-123",
    "adaptive-agent",
    "Write a Python function to check if a string is a palindrome."
)
response3 = agent.process_message(dev_msg)
print("SWE Response:", response3.content)
```

## Integration Points

The Agent module integrates with several other components of the Enterprise AI platform:

### 1. Model Context Protocol (MCP)

Agents integrate with MCP for standardized tool discovery and execution:

```python
# Enable MCP for an agent
agent.enable_tools(
    enable_mcp=True,
    tool_categories=["research", "development"]
)

# The agent can now discover and use tools via MCP
# This connects to the global MCP server that manages tool sessions
```

### 2. LLM Providers

Agents use LLM providers for generating responses:

```python
from enterprise_ai.llm import create_provider

# Create a specific LLM provider
llm_provider = create_provider(
    provider_name="anthropic",
    model_name="claude-3-opus"
)

# Create an agent with this provider
from enterprise_ai.agent import create_agent

agent = create_agent(
    agent_type="llm",
    llm_provider_name="anthropic"  # Will use the default Anthropic provider
)

# Or directly pass the provider
agent = create_agent(
    agent_type="llm",
    llm_provider=llm_provider
)
```

### 3. Team Module

Agents can be organized into teams for collaboration:

```python
from enterprise_ai.team import create_team
from enterprise_ai.agent import create_developer_agent, create_manager_agent

# Create agents
manager = create_manager_agent(name="Team Lead")
dev1 = create_developer_agent(name="Backend Developer")
dev2 = create_developer_agent(name="Frontend Developer")

# Create a team with these agents
team = create_team(
    team_type="hierarchical",
    manager_agent=manager,
    member_agents=[dev1, dev2]
)

# The team can now coordinate tasks among agents
# The manager can delegate tasks to members
# Members can share information via the team
```

### 4. Flow Module

Agents can be integrated into workflows:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create agents for different workflow steps
researcher = create_agent(
    agent_type="llm",
    role_type="researcher",
    reasoning_framework="react"
)

developer = create_agent(
    agent_type="llm",
    role_type="developer",
    reasoning_framework="swe"
)

# Create a workflow using agents
workflow = (WorkflowBuilder()
    .add_agent_node("research", researcher, "Research market trends")
    .add_agent_node("development", developer, "Develop prototype")
    .add_edge("research", "development")
    .build())

# Execute the workflow
workflow.execute()
```

### 5. Tool Registry

Agents can discover and use tools from the global registry:

```python
from enterprise_ai.tool.core.registry import get_registry
from enterprise_ai.agent import create_agent

# Get the global tool registry
registry = get_registry()

# Create an agent with specific tools from the registry
agent = create_agent(
    agent_type="llm",
    use_tools=True,
    enable_mcp=True,
    tool_names=registry.list_tools()[:5]  # Use first 5 registered tools
)
```

## Best Practices

### 1. Choosing the Right Reasoning Framework

Different reasoning frameworks are suited for different types of tasks:

- **Chain of Thought (CoT)**: Best for complex reasoning, problem solving, and explanation tasks.
- **ReAct**: Ideal for tasks requiring tool use, information gathering, and multi-step processes.
- **Software Engineering (SWE)**: Specialized for development tasks, code generation, and debugging.
- **MCP Reasoning**: Best when standardized tool discovery and usage is critical.

Guidelines:

- Use CoT for tasks that benefit from explicit reasoning steps
- Use ReAct when tools are needed to gather information or perform actions
- Use SWE for software development and coding tasks
- Consider using ToolAugmentedCoT for reasoning tasks that might benefit from occasional tool use

```python
# Choose the right framework for the task
agent = create_agent(
    agent_type="llm",
    reasoning_framework="cot",     # For math problems or logical reasoning
    # OR
    reasoning_framework="react",   # For research or information gathering
    # OR
    reasoning_framework="swe",     # For coding tasks
    # OR
    reasoning_framework="mcp",     # For tool-heavy workflows
)
```

### 2. Memory Management

Efficiently manage agent memory to avoid performance issues and state bloat:

- Use the appropriate memory implementation for your needs
- Clean up temporary data when no longer needed
- Be mindful of memory size constraints
- Save state periodically for persistence

```python
# Using scoped memory for temporary data
from enterprise_ai.agent.memory import create_memory

memory = create_memory("scoped")

# Create a scope for a specific operation
memory.push_scope()
memory.add("temp_calculation", large_result)
# ... use the temporary data ...
memory.pop_scope()  # Automatically cleans up all data in this scope

# Using namespaced memory for organization
namespaced = create_memory("namespaced")
namespaced.add("user_preference", "dark_mode", namespace="ui")
namespaced.add("query_history", ["term1", "term2"], namespace="search")
```

### 3. Tool Integration

Best practices for integrating tools with agents:

- Provide specific tool categories rather than all tools
- Be mindful of tool execution costs and rate limits
- Handle tool errors gracefully
- Use MCP for standardized tool access

```python
# Provide specific tool categories
agent.enable_tools(
    enable_mcp=True,
    tool_categories=["research", "file"]  # Only what's needed
)

# Update tools dynamically based on task
await agent._tool_manager.update_mcp_tools(
    add_categories=["development"],  # Add new categories
    remove_tools=["ExpensiveTool"]   # Remove unused or costly tools
)

# Handle tool results carefully
try:
    result = await agent.execute_tool("WebSearch", query="Enterprise AI")
    if result.error:
        # Fallback strategy
        print(f"Tool error: {result.error}")
    else:
        # Process successful result
        print(f"Tool output: {result.output}")
except Exception as e:
    # Handle unexpected errors
    print(f"Execution error: {e}")
```

### 4. State Persistence

Maintain agent state across sessions or system restarts:

- Configure state directories for persistence
- Save state at appropriate intervals
- Handle state loading gracefully

```python
# Configure state persistence
agent = create_agent(
    agent_type="llm",
    state_type="conversation",
    state_kwargs={
        "state_dir": "/path/to/persistent/storage",
        "max_history": 50  # Limit history size
    }
)

# Manually save state at important points
try:
    agent.state.save()
except Exception as e:
    print(f"Failed to save state: {e}")

# Load state for an existing agent
try:
    agent.state.load()
except FileNotFoundError:
    print("No saved state found, using fresh state")
except Exception as e:
    print(f"Error loading state: {e}")
```

### 5. Role and Capability Management

Use roles effectively to specialize agent behavior:

- Choose appropriate predefined roles when possible
- Customize roles with additional context
- Define clear capabilities for custom roles
- Provide detailed instructions

```python
# Use predefined roles with customization
agent = create_agent(
    agent_type="llm",
    role_type="developer",
    role_kwargs={
        "additional_context": "Specialized in Python backend development and API design."
    }
)

# Create custom roles for specialized needs
from enterprise_ai.agent.role import SimpleRole

custom_role = SimpleRole(
    _name="Data Scientist",
    _description="Specialized in data analysis and ML",
    _capabilities=["data_processing", "statistical_analysis", "machine_learning"],
    _instructions="""You are a data scientist with expertise in analyzing complex datasets.
    Your approach should involve:
    1. Understanding the data sources
    2. Cleaning and preprocessing data
    3. Applying appropriate statistical methods
    4. Building machine learning models when appropriate
    5. Interpreting and communicating results clearly"""
)

# Assign the custom role
agent.role = custom_role
```

### 6. Performance and Resource Considerations

Optimize agent performance and resource usage:

- Use the simplest reasoning framework that meets your needs
- Enable tools selectively only when needed
- Monitor tool execution time and costs
- Set appropriate limits for iterations and history

```python
# Limit conversation history
agent = create_agent(
    agent_type="llm",
    state_type="conversation",
    state_kwargs={"max_history": 20}  # Only keep last 20 messages
)

# Set iteration limits for task processing
from enterprise_ai.agent.types import Task

task = Task(
    id="task-123",
    description="Research quantum computing advancements",
    metadata={"max_iterations": 5}  # Limit to 5 iterations
)

# Monitor tool usage
tool_history = agent._tool_manager.get_usage_history()
total_time = sum(entry["duration"] for entry in tool_history)
failed_calls = sum(1 for entry in tool_history if not entry["success"])
print(f"Tool statistics: {len(tool_history)} calls, {total_time:.2f}s total time, {failed_calls} failures")
```

### 7. Error Handling and Fallbacks

Implement robust error handling and fallback strategies:

- Handle tool execution errors gracefully
- Provide fallback strategies for failed reasoning
- Monitor agent status and reset if needed

```python
# Handle tool errors with fallbacks
try:
    result = await agent.execute_tool("PrimaryTool", **params)
    if result.error:
        # Try fallback tool
        result = await agent.execute_tool("FallbackTool", **params)
except Exception:
    # Last resort fallback
    print("All tool attempts failed, using manual processing")

# Reset agent if it gets stuck
max_messages = 20
if len(agent.state.get_conversation_history()) > max_messages:
    if "completed" not in agent.state.current_task.status.name:
        print("Agent may be stuck, resetting conversation")
        agent.state.clear_conversation()
```
