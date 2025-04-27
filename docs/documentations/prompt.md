# Enterprise AI Prompt Module

## Module Overview

The Prompt module forms the core prompt management system of the Enterprise AI platform. It provides a structured way to define, store, retrieve, and compose the various prompts that drive agent behavior throughout the system. This module handles the "brain" of the AI agents by defining their roles, capabilities, reasoning frameworks, and tool usage patterns.

Key functions of the Prompt module include:

- Loading and organizing prompt templates from a directory structure
- Providing variable substitution in prompts for dynamic content
- Combining multiple prompt templates to create composite behaviors
- Supporting different agent roles and specializations
- Integrating reasoning frameworks like Chain of Thought, ReAct, and MCP
- Providing guidance for tool discovery and usage

The prompt system serves as the foundation for agent intelligence in the Enterprise AI platform, allowing for flexible and extensible agent behaviors while maintaining a consistent structure and organization.

## Key Components

### 1. PromptTemplate

The `PromptTemplate` class represents a single prompt template with variable substitution capabilities. It wraps the standard Python `string.Template` class with additional metadata and error handling.

```python
class PromptTemplate:
    def __init__(self, template: str, metadata: Optional[Dict[str, Any]] = None):
        # Initialize with template string and optional metadata

    def format(self, **kwargs: Any) -> str:
        # Format the template by substituting variables
```

Key features:

- String template with `$variable` placeholders
- Safe variable substitution with fallback to original template
- Associated metadata for categorization and source tracking

### 2. PromptLibrary

The `PromptLibrary` class manages a collection of prompt templates, providing methods for loading, retrieving, combining, and formatting prompts.

```python
class PromptLibrary:
    def __init__(self, prompt_dir: Optional[str] = None):
        # Initialize with directory containing prompt files

    def get_prompt(self, prompt_id: str) -> Optional[PromptTemplate]:
        # Get a prompt template by ID

    def format_prompt(self, prompt_id: str, **kwargs: Any) -> Optional[str]:
        # Format a prompt with variable substitution

    def combine_prompts(self, prompt_ids: List[str], **kwargs: Any) -> Optional[str]:
        # Combine multiple prompts into one

    def create_composite_prompt(self, role_id: str, system_id: str, **kwargs: Any) -> Optional[str]:
        # Create a composite prompt from role and system prompts
```

Key features:

- Automatic loading of prompts from a directory structure
- Hierarchical prompt organization (roles, systems, tools, etc.)
- Methods for prompt composition and combination
- Error handling for missing prompts

### 3. Global Utility Functions

The module provides several global utility functions for convenient access to the prompt library:

```python
def get_prompt_library() -> PromptLibrary:
    # Get the global prompt library instance

def get_prompt(prompt_id: str) -> Optional[PromptTemplate]:
    # Get a prompt template by ID

def format_prompt(prompt_id: str, **kwargs: Any) -> Optional[str]:
    # Format a prompt with variable substitution

def combine_prompts(prompt_ids: List[str], **kwargs: Any) -> Optional[str]:
    # Combine multiple prompts into one

def create_composite_prompt(role_id: str, system_id: str, **kwargs: Any) -> Optional[str]:
    # Create a composite prompt from role and system prompts
```

### 4. Prompt Template Categories

The prompt module organizes templates into four main categories:

1. **Composite Templates**: Pre-built combinations of role, system, and tool prompts for common agent types

   - Example: `all_capable_agent.prompt`, `browser_agent.prompt`, `developer_with_tools.prompt`

1. **Role Templates**: Define specialized agent roles and their primary responsibilities

   - Example: `browser_agent.prompt`, `developer.prompt`, `researcher.prompt`

1. **System Templates**: Define reasoning frameworks and general agent behaviors

   - Example: `analytical.prompt`, `cot.prompt`, `react.prompt`, `mcp.prompt`

1. **Tool Templates**: Provide guidance for using specific tool categories

   - Example: `browser.prompt`, `code_execution.prompt`, `file_operations.prompt`

## Architecture Design

The Prompt module follows several key design patterns and principles:

### 1. Singleton Pattern

The module uses a singleton pattern for the global prompt library instance, ensuring that prompts are loaded only once and shared across the application:

```python
_global_prompt_library: Optional[PromptLibrary] = None

def get_prompt_library() -> PromptLibrary:
    global _global_prompt_library
    if _global_prompt_library is None:
        _global_prompt_library = PromptLibrary()
    return _global_prompt_library
```

### 2. Template Method Pattern

The prompt composition methods follow a template method pattern, where the structure of the composition is defined but specific components can be customized:

```python
def create_composite_prompt(role_id: str, system_id: str, **kwargs: Any) -> Optional[str]:
    role_prompt = get_prompt(f"roles.{role_id}")
    system_prompt = get_prompt(f"system.{system_id}")

    # Combine in a specific structure
    combined_template = f"{system_prompt.template_str}\n\n{role_prompt.template_str}"
    combined_prompt = PromptTemplate(combined_template)

    return combined_prompt.format(**kwargs)
```

### 3. File-Based Organization

The module organizes prompts in a hierarchical file structure that reflects their purpose and relationships:

```
templates/
  ├── composite/      # Pre-built compositions
  ├── roles/          # Agent role definitions
  ├── system/         # Reasoning frameworks and behaviors
  └── tools/          # Tool usage guidance
```

This organization allows for:

- Logical grouping of related prompts
- Easy discovery of available prompts
- Separation of concerns between different prompt types
- Simple extension by adding new prompt files

### 4. Configuration Integration

The prompt module integrates with the platform's configuration system to determine the default prompt directory:

```python
self.prompt_dir = prompt_dir or get_config(
    "prompt.directory", os.path.join(os.path.dirname(__file__), "templates")
)
```

### 5. Composition Over Inheritance

The module uses composition to build complex prompts by combining simpler components, rather than using inheritance hierarchies:

```python
def combine_prompts(prompt_ids: List[str], **kwargs: Any) -> Optional[str]:
    # Combine multiple prompts into a single composite prompt
```

## Usage Examples

### 1. Basic Prompt Formatting

```python
from enterprise_ai.prompt import format_prompt

# Format a system prompt with variables
system_prompt = format_prompt(
    "system.base",
    additional_instructions="Be concise and focus on technical accuracy."
)

# Use the formatted prompt
print(system_prompt)
```

### 2. Creating a Specialized Agent

```python
from enterprise_ai.prompt import create_composite_prompt

# Create a developer agent with chain-of-thought reasoning
developer_prompt = create_composite_prompt(
    role_id="developer",
    system_id="cot",
    additional_instructions="Focus on Python best practices.",
    additional_cot_instructions="Break down programming problems step by step."
)

# Use the composite prompt for an agent
print(developer_prompt)
```

### 3. Adding Tool Capabilities

```python
from enterprise_ai.prompt import combine_prompts

# Create a prompt with tool capabilities
tools_prompt = combine_prompts(
    ["system.with_tools", "tools.code_execution", "tools.file_operations"],
    tools_description="Code execution and file management tools",
    additional_tool_instructions="Prioritize using the file operations tool for viewing code."
)

# Use the prompt with tools
print(tools_prompt)
```

### 4. Creating a Custom Prompt

```python
from enterprise_ai.prompt import get_prompt_library

# Get the prompt library
library = get_prompt_library()

# Add a custom prompt
library.add_prompt(
    prompt_id="custom.specialized_agent",
    template="""You are a specialized agent for $domain tasks.
    Your primary responsibilities include:
    $responsibilities

    Follow these guidelines:
    $guidelines
    """,
    metadata={"category": "custom", "author": "AI Team"}
)

# Format the custom prompt
specialized_prompt = library.format_prompt(
    "custom.specialized_agent",
    domain="medical data analysis",
    responsibilities="- Analyzing patient data\n- Identifying patterns\n- Generating reports",
    guidelines="- Maintain patient privacy\n- Follow medical standards\n- Cite relevant research"
)

print(specialized_prompt)
```

### 5. Using Pre-built Composite Prompts

```python
from enterprise_ai.prompt import format_prompt

# Use a pre-built all-capable agent template
agent_prompt = format_prompt(
    "composite.all_capable_agent",
    tools_description="Browser, code execution, and file operation tools",
    additional_context="Focus on security considerations when writing code."
)

# Use the formatted prompt
print(agent_prompt)
```

## Integration Points

The Prompt module integrates with several other components of the Enterprise AI platform:

### 1. Agent Module

The Agent module uses prompts to define agent behavior, reasoning frameworks, and capabilities:

```python
from enterprise_ai.prompt import create_composite_prompt
from enterprise_ai.agent import Agent

# Create a developer agent with chain-of-thought reasoning
prompt = create_composite_prompt(
    role_id="developer",
    system_id="cot",
    additional_context="This agent specializes in Python development."
)

# Create an agent with the prompt
agent = Agent(system_prompt=prompt)
```

### 2. Tool Integration

The prompt module facilitates tool discovery and usage through specialized tool prompts:

```python
from enterprise_ai.prompt import format_prompt
from enterprise_ai.tool import register_tools

# Format a tool prompt with available tools
tools_prompt = format_prompt(
    "system.with_tools",
    tools_description=register_tools(["browser", "file_operations"]),
    additional_tool_instructions="Use the browser tool for external information."
)
```

### 3. Reasoning Frameworks

The system prompts define different reasoning frameworks that agents can use:

```python
from enterprise_ai.prompt import format_prompt
from enterprise_ai.agent.reasoning import COTReasoning

# Format a chain-of-thought prompt
cot_prompt = format_prompt(
    "system.cot",
    additional_cot_instructions="Include mathematical formulas when relevant."
)

# Create a reasoning module with the prompt
reasoning = COTReasoning(system_prompt=cot_prompt)
```

### 4. Team Coordination

Team prompts can define coordination patterns between different specialized agents:

```python
from enterprise_ai.prompt import format_prompt
from enterprise_ai.team import Team

# Format a manager prompt
manager_prompt = format_prompt(
    "roles.manager",
    additional_context="Coordinate between research and development agents."
)

# Create a team with the manager
team = Team(manager_prompt=manager_prompt)
```

### 5. Workflow Management

The Flow module can use prompts to define the behavior of workflow nodes:

```python
from enterprise_ai.prompt import format_prompt
from enterprise_ai.flow import WorkflowNode

# Format a prompt for a workflow node
node_prompt = format_prompt(
    "system.planning",
    additional_planning_instructions="Break tasks into steps of similar complexity."
)

# Create a workflow node with the prompt
planning_node = WorkflowNode(system_prompt=node_prompt)
```

## Best Practices

### Prompt Design

1. **Keep prompts modular and focused**:

   - Each prompt should have a clear, single responsibility
   - Avoid creating complex monolithic prompts
   - Use prompt composition to build complex behaviors

   ```python
   # Good: Modular prompts with clear responsibilities
   role_prompt = format_prompt("roles.developer")
   system_prompt = format_prompt("system.cot")
   tool_prompt = format_prompt("tools.file_operations")

   # Composition instead of monoliths
   composite = combine_prompts(["system.cot", "roles.developer", "tools.file_operations"])
   ```

1. **Use consistent formatting for variables**:

   - Follow a consistent naming convention for variables
   - Document required variables for each prompt
   - Provide defaults for optional variables when possible

   ```python
   # Consistent variable naming
   format_prompt(
       "system.base",
       additional_instructions="...",  # Consistent suffix for extensibility points
       model_capabilities="..."        # Descriptive and specific names
   )
   ```

1. **Balance specificity and flexibility**:

   - Make prompts specific enough to guide behavior
   - Keep them flexible enough for different contexts
   - Use variables for customization points

   ```python
   # Template with specific guidance but flexible customization
   """
   You are a $role_type specialist with expertise in $domain.

   Your responsibilities include:
   $responsibilities

   Follow these guidelines for $domain tasks:
   $guidelines
   """
   ```

### Prompt Organization

1. **Follow the established directory structure**:

   - Place new prompts in the appropriate category directory
   - Use consistent file naming conventions
   - Update documentation when adding new prompt categories

1. **Use metadata for additional organization**:

   - Add relevant metadata to prompts for filtering and discovery
   - Include information about prompt purpose and usage
   - Document required variables in metadata

   ```python
   library.add_prompt(
       prompt_id="custom.my_prompt",
       template="...",
       metadata={
           "category": "custom",
           "purpose": "Specialized data analysis",
           "required_vars": ["domain", "data_type", "analysis_goals"],
           "author": "AI Team"
       }
   )
   ```

1. **Maintain a prompt registry**:

   - Document available prompts and their purposes
   - Group related prompts together
   - Provide usage examples for each prompt category

### Tool Integration

1. **Keep tool descriptions updated**:

   - Ensure tool prompts match actual tool capabilities
   - Update tool documentation when adding or changing tools
   - Include examples of proper tool usage

1. **Follow the standard tool format**:

   - Use consistent JSON structure for tool requests
   - Document required parameters for each tool
   - Provide error handling guidance

   ```python
   # Standard tool request format
   """
   <tool_request>
     "tool": "$tool_name",
     "parameters": {
       "param1": "value1",
       "param2": "value2"
     }
   </tool_request>
   """
   ```

1. **Balance guidance and flexibility**:

   - Provide specific guidance for common tool usage patterns
   - Allow flexibility for creative tool applications
   - Include troubleshooting steps for common errors

### Potential Pitfalls

1. **Prompt Conflicts**:

   - Be cautious when combining multiple prompts
   - Watch for contradictory instructions across prompts
   - Test composite prompts thoroughly

   ```python
   # Potential conflict between analytical and creative approaches
   combine_prompts(["system.analytical", "system.creative"])  # May create conflicting guidance
   ```

1. **Variable Substitution Errors**:

   - Ensure all required variables are provided
   - Handle missing variables gracefully
   - Watch for typos in variable names

   ```python
   # Missing variable will leave placeholder in output
   format_prompt("system.base", additonal_instructions="...")  # Typo in "additional"
   ```

1. **Prompt Library Management**:

   - Avoid modifying the prompt library after initialization
   - Be cautious with thread safety in multi-threaded environments
   - Manage prompt template versioning carefully

1. **Excessive Prompt Complexity**:

   - Very long or complex prompts may be ineffective
   - Overly verbose prompts can impact model performance
   - Balance detail with conciseness

1. **Tool Format Consistency**:

   - Ensure consistent formatting across tool-related prompts
   - Maintain the standard tool request/response format
   - Test tool integration with different prompt combinations
