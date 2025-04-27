# Enterprise AI MCP Module

## Module Overview

The Model Context Protocol (MCP) module provides a standardized framework for AI agents to discover and utilize tools within the Enterprise AI platform. It serves as the interface layer between AI agents and the diverse tool ecosystem, enabling dynamic tool discovery, execution, and lifecycle management.

Key aspects of the MCP module include:

- **Dynamic Tool Discovery**: Enables agents to discover available tools at runtime based on their capabilities and requirements
- **Standardized Interface**: Provides a consistent interface for tool execution and error handling
- **Session Management**: Maintains isolated tool contexts for different agents and use cases
- **Tool Lifecycle Management**: Handles tool initialization, execution, and cleanup
- **Execution History**: Tracks tool usage and results for monitoring and debugging

The MCP module effectively decouples agent implementation from tool implementation, allowing each to evolve independently. It promotes a plugin architecture where new tools can be easily added to the system and discovered by agents without modifying the agent code.

## Key Components

### MCPServer

The `MCPServer` class is the central component of the MCP system, managing sessions and tool registration:

```python
class MCPServer:
    """Model Context Protocol server that manages tool access."""

    def create_session(
        self,
        session_id: str,
        tool_categories: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
    ) -> MCPSession:
        """Create a new MCP session with specific tools."""

    def get_session(self, session_id: str) -> Optional[MCPSession]:
        """Get an existing MCP session."""

    async def close_session(self, session_id: str) -> bool:
        """Close and cleanup an MCP session."""

    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs."""
```

The server is implemented as a singleton, accessible through the `get_mcp_server()` function:

```python
# Get the global MCP server instance
server = get_mcp_server()
```

Key features:

- Singleton implementation ensuring a single global MCP server
- Session creation with dynamic tool loading
- Tool category and name-based tool selection
- Session cleanup and lifecycle management

### MCPSession

The `MCPSession` class represents a tool execution context for a specific agent or use case:

```python
class MCPSession:
    """A session for interacting with tools via the MCP protocol."""

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool with this session."""

    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool from this session."""

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools with their descriptions."""

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters."""

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the history of tool executions in this session."""

    async def cleanup(self) -> None:
        """Clean up resources used by this session."""
```

Key features:

- Tool registration and unregistration
- Tool execution with parameter passing
- Execution history tracking
- Resource cleanup on session termination

### MCPClient

The `MCPClient` class provides a client interface for connecting to the MCP server:

```python
class MCPClient:
    """Client for interacting with the MCP server."""

    def __init__(self, session_id: str, create_if_not_exists: bool = True):
        """Initialize an MCP client."""

    def discover_tools(self) -> List[Dict[str, Any]]:
        """Discover available tools in this session."""

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool with the given parameters."""

    async def close(self) -> None:
        """Close the MCP client and session."""
```

Key features:

- Connection to existing or new MCP sessions
- Tool discovery through the session
- Tool execution with parameter passing
- Session cleanup on client close

### AgentMCPClient

The `AgentMCPClient` class extends the base client with agent-specific functionality:

```python
class AgentMCPClient(MCPClient):
    """An MCP client specifically for agent use."""

    def __init__(
        self,
        agent_id: str,
        tool_categories: Optional[List[str]] = None,
        tool_names: Optional[List[str]] = None,
    ):
        """Initialize an agent MCP client."""

    async def update_tools(
        self,
        add_categories: Optional[List[str]] = None,
        add_tools: Optional[List[str]] = None,
        remove_tools: Optional[List[str]] = None,
    ) -> None:
        """Update the tools available to this agent."""
```

Key features:

- Agent-specific session creation with agent ID
- Tool category and name-based tool selection
- Dynamic tool updates during agent operation
- Tool removal capability

### Utility Functions

The MCP module provides several utility functions for common operations:

```python
# Format tool descriptions for inclusion in prompts
formatted_descriptions = format_tool_descriptions(tools)

# Format a tool result for display
formatted_result = format_tool_result(result)

# Get information about all active MCP sessions
sessions_info = get_all_sessions_info()

# Execute a tool by name in a specific session or create a temporary session
result = await execute_tool_by_name("tool_name", **params)

# Get the JSON schema for a tool
tool_schema = get_tool_schema("tool_name")
```

## Architecture Design

The MCP module implements several key architectural patterns:

### 1. Singleton Server Pattern

The MCP server uses the singleton pattern to ensure a single global server instance:

```python
class MCPServer:
    _instance = None

    def __new__(cls) -> "MCPServer":
        """Create a singleton instance of the MCP server."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
```

This pattern ensures:

- A single point of access for tool management
- Consistent session handling across the application
- Shared state for tool registration and discovery

### 2. Session-Based Isolation

The MCP system uses sessions to isolate tool contexts:

```python
def create_session(
    self,
    session_id: str,
    tool_categories: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
) -> MCPSession:
    """Create a new MCP session with specific tools."""
    session = MCPSession(session_id)
    # ... load tools based on categories and names ...
    self._sessions[session_id] = session
    return session
```

This design provides:

- Isolation between different agents' tool sets
- Tool lifecycle management per agent
- Independent history tracking
- Clean resource cleanup

### 3. Dynamic Tool Discovery

Tools are dynamically discovered and loaded based on categories or names:

```python
# Load tools from categories
if tool_categories:
    for category in tool_categories:
        tool_classes = self._registry.get_tools_by_category(category)
        for tool_cls in tool_classes:
            # ... instantiate and register tool ...

# Load specific tools
if tool_names:
    for name in tool_names:
        maybe_tool_cls = self._registry.get_tool_class(name)
        if maybe_tool_cls is not None:
            # ... instantiate and register tool ...
```

This approach enables:

- Agent-specific tool sets
- Tool addition without modifying agent code
- Category-based tool organization
- Runtime tool selection

### 4. Tool Execution and Tracking

The MCP system provides standardized tool execution with history tracking:

```python
async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
    """Execute a tool with the given parameters."""
    start_time = datetime.now()

    # Record the execution request
    request_record = {
        "type": "request",
        "tool": tool_name,
        "parameters": kwargs,
        "timestamp": start_time.isoformat(),
    }
    self._history.append(request_record)

    # Execute the tool
    result = await self._tool_collection.execute(name=tool_name, tool_input=kwargs)

    # ... record result and return ...
```

This design provides:

- Consistent execution interface
- Parameter validation
- History tracking for auditing and debugging
- Timing information

## Usage Examples

### 1. Setting Up and Using the MCP Server

```python
from enterprise_ai.mcp import get_mcp_server, MCPSession

# Get the global MCP server instance
server = get_mcp_server()

# Create a session with tools from specific categories
session_id = "research_session"
session = server.create_session(
    session_id,
    tool_categories=["research", "browser"]
)

# Execute a tool in the session
result = await session.execute_tool(
    "web_search",
    query="Enterprise AI frameworks",
    num_results=5
)

# View tool execution history
history = session.get_history()
for entry in history:
    print(f"{entry['type']} - {entry['tool']} - {entry['timestamp']}")

# Clean up the session when done
await server.close_session(session_id)
```

### 2. Using the MCP Client

```python
from enterprise_ai.mcp import MCPClient

# Connect to an existing session or create a new one
client = MCPClient("research_session", create_if_not_exists=True)

# Discover available tools
tools = client.discover_tools()
for tool in tools:
    print(f"Found tool: {tool['name']} - {tool['description']}")

# Execute a tool
result = await client.execute_tool(
    "web_search",
    query="Latest AI research",
    num_results=3
)

# Process the result
if result.error:
    print(f"Error: {result.error}")
else:
    print(f"Success: {result.output}")

# Close the client when done
await client.close()
```

### 3. Agent-Specific MCP Client

```python
from enterprise_ai.mcp import AgentMCPClient

# Create an agent-specific client with selected tool categories
agent_client = AgentMCPClient(
    agent_id="research_agent",
    tool_categories=["research", "utility"]
)

# Discover the agent's tools
tools = agent_client.discover_tools()
tool_descriptions = [f"{tool['name']}: {tool['description']}" for tool in tools]
print(f"Available tools: {', '.join(tool_descriptions)}")

# Update the agent's tools during operation
await agent_client.update_tools(
    add_categories=["browser"],
    add_tools=["python_execute"],
    remove_tools=["terminate"]
)

# Execute multiple tools in sequence
search_result = await agent_client.execute_tool(
    "web_search",
    query="Python data analysis libraries"
)

browser_result = await agent_client.execute_tool(
    "browser_use",
    action="go_to_url",
    url=search_result.results[0].url if search_result.results else "https://python.org"
)

# Close the client when done
await agent_client.close()
```

### 4. Utility Functions for MCP

```python
from enterprise_ai.mcp import (
    format_tool_descriptions,
    format_tool_result,
    get_all_sessions_info,
    execute_tool_by_name,
    get_tool_schema
)

# Get information about all active sessions
sessions = get_all_sessions_info()
for session_id, info in sessions.items():
    print(f"Session: {session_id}")
    print(f"  Tools: {info['tool_count']}")
    print(f"  History entries: {info['history_count']}")
    print(f"  Agent session: {info['is_agent_session']}")

# Format tool descriptions for prompt inclusion
tools = [get_tool_schema("web_search"), get_tool_schema("python_execute")]
formatted = format_tool_descriptions(tools)
print(formatted)

# Execute a tool directly without managing the client
result = await execute_tool_by_name(
    "web_search",
    query="Enterprise AI frameworks"
)

# Format the result for display
formatted_result = format_tool_result(result)
print(formatted_result)
```

## Integration Points

### 1. Integration with Agent Module

Agents use the MCP module to discover and execute tools:

```python
# In an agent implementation
from enterprise_ai.mcp import AgentMCPClient

class Agent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.mcp_client = AgentMCPClient(
            agent_id=agent_id,
            tool_categories=["research", "browser", "utility"]
        )

    async def initialize(self):
        # Discover available tools
        self.tools = self.mcp_client.discover_tools()
        self.tool_descriptions = format_tool_descriptions(self.tools)

    async def execute_tool(self, tool_name: str, **params):
        # Execute a tool via MCP
        return await self.mcp_client.execute_tool(tool_name, **params)

    async def cleanup(self):
        # Clean up MCP resources
        await self.mcp_client.close()
```

Key integration points:

- Tool discovery for agent capabilities
- Standardized tool execution
- Resource lifecycle management
- Tool updates based on agent needs

### 2. Integration with Tool Module

The MCP module leverages the Tool registry for tool discovery:

```python
def create_session(
    self,
    session_id: str,
    tool_categories: Optional[List[str]] = None,
    tool_names: Optional[List[str]] = None,
) -> MCPSession:
    # ...
    # Load tools from categories if specified
    if tool_categories:
        for category in tool_categories:
            tool_classes = self._registry.get_tools_by_category(category)
            # ...
    # ...
```

Key integration points:

- Tool registry for class discovery
- Tool instantiation with proper parameters
- Tool categorization and organization
- Tool execution via the ToolCollection

### 3. Integration with LLM Module

LLMs can use tool schemas to determine which tools to call:

```python
# Example in an agent implementation
from enterprise_ai.mcp import AgentMCPClient, format_tool_descriptions
from enterprise_ai.llm import LLM

class LLMAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.mcp_client = AgentMCPClient(agent_id=agent_id)
        self.llm = LLM()

    async def process_query(self, query: str):
        # Get tool definitions for the LLM
        tools = self.mcp_client.discover_tools()

        # Create messages with tool descriptions
        messages = [
            {"role": "system", "content": f"You have access to these tools:\n{format_tool_descriptions(tools)}"},
            {"role": "user", "content": query}
        ]

        # Get LLM response with function calling
        response = await self.llm.complete(
            messages=messages,
            functions=tools,
            function_call="auto"
        )

        # Extract function call if any
        if hasattr(response, "function_call"):
            tool_name = response.function_call.get("name")
            tool_args = json.loads(response.function_call.get("arguments", "{}"))

            # Execute the tool via MCP
            tool_result = await self.mcp_client.execute_tool(tool_name, **tool_args)

            # Process the result
            return tool_result

        return response
```

Key integration points:

- Tool descriptions for LLM function calling
- Tool schema formatting for LLM understanding
- Tool parameter validation
- Tool result formatting for LLM consumption

## Best Practices

### Session Management

1. **Use session IDs consistently**:

   ```python
   # Use structured session IDs to identify purpose
   agent_session_id = f"agent-{agent_id}"
   task_session_id = f"task-{task_id}"
   ```

1. **Clean up sessions when done**:

   ```python
   try:
       # Use the session...
   finally:
       # Always ensure cleanup
       await server.close_session(session_id)
   ```

1. **Consider session lifetime**:

   - Short-lived sessions for temporary operations
   - Long-lived sessions for ongoing agent activities
   - Periodic cleanup for abandoned sessions

1. **Monitor session usage**:

   ```python
   # Regularly check session status
   sessions_info = get_all_sessions_info()
   for session_id, info in sessions_info.items():
       if info["history_count"] > 1000:  # Large history
           logger.warning(f"Session {session_id} has large history")
   ```

### Tool Discovery and Selection

1. **Select appropriate tool categories**:

   ```python
   # Match tool categories to agent capabilities
   researcher_categories = ["research", "browser", "utility"]
   developer_categories = ["execution", "file", "utility"]
   ```

1. **Consider tool dependencies**:

   ```python
   # Ensure dependent tools are available
   if "browser" in needed_categories and "research" not in needed_categories:
       needed_categories.append("research")  # Browser tools may depend on research
   ```

1. **Update tools dynamically**:

   ```python
   # Add tools based on new task requirements
   if task_requires_code_execution:
       await agent_client.update_tools(add_categories=["execution"])
   ```

1. **Limit tool scope**:

   - Provide only the tools an agent needs
   - Remove dangerous tools from untrusted contexts
   - Consider security implications of tool combinations

### Error Handling

1. **Handle tool execution errors**:

   ```python
   try:
       result = await client.execute_tool("tool_name", **params)
       if result.error:
           # Handle tool error
           logger.error(f"Tool error: {result.error}")
           # Implement fallback strategy
       else:
           # Process successful result
   except Exception as e:
       # Handle unexpected errors
       logger.exception(f"Unexpected error executing tool: {e}")
   ```

1. **Implement retries for transient errors**:

   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
   async def execute_with_retry(client, tool_name, **params):
       result = await client.execute_tool(tool_name, **params)
       if result.error and "rate limit" in result.error.lower():
           # Retry on rate limiting
           raise ValueError("Rate limited, retrying")
       return result
   ```

1. **Validate tool parameters**:

   ```python
   # Validate required parameters before execution
   if not query:
       return ToolResult(error="Query parameter is required")

   # Validate parameter types
   if not isinstance(num_results, int) or num_results < 1:
       return ToolResult(error="num_results must be a positive integer")
   ```

1. **Log tool activity for debugging**:

   ```python
   # Log before and after tool execution
   logger.debug(f"Executing tool {tool_name} with parameters: {params}")
   result = await client.execute_tool(tool_name, **params)
   logger.debug(f"Tool execution result: {result.error or 'success'}")
   ```

### Resource Management

1. **Clean up tool resources**:

   ```python
   # Implement cleanup for tools that need it
   async def cleanup(self):
       if hasattr(self, "browser") and self.browser:
           await self.browser.close()
   ```

1. **Monitor tool execution time**:

   ```python
   start_time = time.time()
   result = await client.execute_tool(tool_name, **params)
   execution_time = time.time() - start_time

   if execution_time > 5.0:  # Threshold
       logger.warning(f"Tool {tool_name} took {execution_time:.2f}s to execute")
   ```

1. **Limit parallel tool executions**:

   ```python
   # Use semaphore to limit concurrency
   semaphore = asyncio.Semaphore(5)  # Max 5 concurrent executions

   async def execute_with_limit(client, tool_name, **params):
       async with semaphore:
           return await client.execute_tool(tool_name, **params)
   ```

1. **Use context managers where appropriate**:

   ```python
   async with AsyncExitStack() as stack:
       client = stack.enter_async_context(MCPClient(session_id))
       # Use client with automatic cleanup
   ```

## Potential Pitfalls

1. **Tool Initialization Overhead**:
   Some tools have significant initialization overhead. Create them once per session rather than for each execution.

1. **Failing to Close Sessions**:
   Unclosed sessions can lead to resource leaks. Use try/finally blocks or context managers to ensure cleanup.

1. **Tool Execution Timeouts**:
   Tools like browser automation may take a long time to execute. Consider implementing custom timeouts:

   ```python
   async def execute_with_timeout(client, tool_name, timeout=30, **params):
       try:
           async with asyncio.timeout(timeout):
               return await client.execute_tool(tool_name, **params)
       except asyncio.TimeoutError:
           return ToolResult(error=f"Tool execution timed out after {timeout} seconds")
   ```

1. **Circular Tool Dependencies**:
   Be cautious about tools that may call other tools, as this can lead to circular dependencies:

   ```python
   # Avoid this pattern:
   async def execute(self, **kwargs):
       # Tool calling another tool that might call this tool again
       result = await execute_tool_by_name("another_tool", **kwargs)
   ```

1. **Session Explosion**:
   Creating too many sessions without cleanup can exhaust resources. Implement periodic session cleanup:

   ```python
   async def cleanup_old_sessions():
       server = get_mcp_server()
       sessions_info = get_all_sessions_info()

       now = datetime.now()
       for session_id, info in sessions_info.items():
           # Example logic to determine old sessions
           if now - info.get("last_activity", now) > timedelta(hours=1):
               await server.close_session(session_id)
   ```

1. **Tool Registration Errors**:
   Tools may fail to register due to import errors or missing dependencies. Implement robust error handling during session creation:

   ```python
   def create_session_safe(server, session_id, tool_categories=None, tool_names=None):
       try:
           return server.create_session(session_id, tool_categories, tool_names)
       except Exception as e:
           logger.error(f"Failed to create session {session_id}: {e}")
           # Create a session with safer tool set
           return server.create_session(session_id, tool_categories=["utility"])
   ```

1. **MCP Client Garbage Collection Issues**:
   The `__del__` method in MCPClient attempts to close sessions, but this can be unreliable. Prefer explicit cleanup:

   ```python
   client = MCPClient(session_id)
   try:
       # Use client
   finally:
       # Explicit cleanup
       asyncio.create_task(client.close())
   ```
