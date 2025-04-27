# Enterprise AI LLM Module

## Module Overview

The LLM (Language Learning Model) module serves as the core intelligence layer of the Enterprise AI platform. It provides a unified interface for interacting with various language models through different providers (such as Ollama, OpenAI, Anthropic, etc.). The module abstracts away provider-specific implementation details, offering a consistent API across the platform.

Key capabilities of the LLM module include:

- Provider-agnostic interface for language model interactions
- Extensible registry system for adding new LLM providers
- Factory pattern for creating correctly configured provider instances
- Model capability detection and feature checking
- Performance metrics tracking
- Support for both synchronous and asynchronous completions

The LLM module forms the foundation of AI capabilities throughout the Enterprise AI platform, enabling agents, teams, and tools to leverage language models without being tightly coupled to specific providers or implementations.

## Key Components

### 1. LLMProvider (Abstract Base Class)

The `LLMProvider` class defines the interface that all LLM providers must implement. It serves as the base class for provider-specific implementations.

```python
class LLMProvider(abc.ABC):
    def __init__(self, model_name: str, **kwargs: Any):
        # Initialize with model name and provider-specific parameters

    @abc.abstractmethod
    def complete(self, messages: List[MessageProtocol], **kwargs: Any) -> MessageProtocol:
        # Generate completion from messages

    @abc.abstractmethod
    def get_model_info(self) -> ModelInfo:
        # Get model capabilities and information

    def supports_feature(self, feature: str) -> bool:
        # Check if model supports a specific feature

    def track_request(self, success: bool) -> None:
        # Track metrics for requests

    def get_metrics(self) -> Dict[str, Any]:
        # Get usage metrics for this provider
```

Key features:

- Abstract methods that providers must implement (`complete`, `get_model_info`)
- Utility methods for feature checking and metrics tracking
- Provider-specific configuration through kwargs

### 2. Provider Registry System

The registry system manages available LLM providers and provides a way to register and retrieve them.

```python
class ProviderRegistry:
    def register(self, name: str, provider_cls: Type[LLMProvider]) -> None:
        # Register a provider class

    def get_provider_class(self, name: str) -> Optional[Type[LLMProvider]]:
        # Get a provider class by name

    def list_providers(self) -> Dict[str, Type[LLMProvider]]:
        # Get all registered providers
```

The registry is implemented as a singleton, ensuring a single global registry throughout the application. Providers can be registered using a decorator:

```python
@register_provider("provider_name")
class MyProvider(LLMProvider):
    # Provider implementation
```

### 3. Factory Functions

Factory functions simplify the creation of correctly configured provider instances:

```python
def create_provider(provider_name: str, model_name: Optional[str] = None, **kwargs: Any) -> LLMProvider:
    # Create a provider instance with appropriate configuration

def get_default_provider(**kwargs: Any) -> LLMProvider:
    # Get the default provider instance as configured in settings
```

These functions handle provider instantiation, configuration loading, and error handling.

### 4. Simple LLM Interface

The `LLM` class provides a simplified interface for tools and components that need to interact with language models:

```python
class LLM:
    def __init__(self, provider_name: Optional[str] = None, model_name: Optional[str] = None,
                 provider: Optional[LLMProvider] = None, **kwargs: Any):
        # Initialize with optional provider and model specifications

    def complete(self, messages: List[Any], **kwargs: Any) -> Any:
        # Generate completion synchronously

    async def acomplete(self, messages: List[Any], **kwargs: Any) -> Any:
        # Generate completion asynchronously
```

Key features:

- Lazy provider initialization
- Attribute forwarding to the underlying provider
- Support for both synchronous and asynchronous operations

### 5. High-Level API

The module exposes a high-level API for simple interactions:

```python
def complete(messages: List[Union[Message, str]], options: Optional[CompletionOptions] = None,
             provider: Optional[LLMProvider] = None) -> MessageProtocol:
    # Generate a completion for messages using the specified options and provider
```

This function handles message preprocessing, provider selection, and option mapping.

## Architecture Design

The LLM module implements several design patterns and architectural principles:

### 1. Provider Pattern

The module uses a provider pattern to abstract away specific implementations of language model interactions. This enables:

- Substituting different LLM providers without changing consumer code
- Supporting multiple providers simultaneously
- Adding new providers without modifying existing code
- Testing with mock providers

Implementation:

- Abstract base class (`LLMProvider`) defines the interface
- Concrete provider classes implement provider-specific logic
- Consumers depend on the abstract interface, not concrete implementations

### 2. Registry Pattern

The registry pattern manages provider registration and retrieval:

```python
# Provider registration
@register_provider("ollama")
class OllamaProvider(LLMProvider):
    # Implementation

# Provider retrieval
provider_cls = get_registry().get_provider_class("ollama")
provider = provider_cls(model_name="llama2")
```

This pattern enables:

- Dynamic discovery of available providers
- Runtime registration of new providers
- Decoupling provider implementation from provider selection

### 3. Factory Pattern

The factory pattern encapsulates provider creation logic:

```python
# Creation through factory
provider = create_provider("ollama", model_name="llama2")

# Creation with default provider
default_provider = get_default_provider()
```

This pattern enables:

- Centralized provider configuration
- Integration with the configuration system
- Error handling during provider creation
- Default provider selection

### 4. Singleton Pattern

The provider registry uses a singleton pattern to ensure a single global registry:

```python
class ProviderRegistry:
    _instance = None

    def __new__(cls) -> "ProviderRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
        return cls._instance
```

This ensures:

- Consistent registration state throughout the application
- Thread-safe provider registration and retrieval
- Single point of access for provider information

### 5. Lazy Initialization

The `LLM` class uses lazy initialization for the provider:

```python
@property
def provider(self) -> LLMProvider:
    if self._provider is None:
        # Initialize provider
    return self._provider
```

This pattern enables:

- Resource efficiency (provider only created when needed)
- Flexibility in provider selection
- Reduced initialization overhead

### 6. Feature Detection

The model feature detection system allows checking for specific capabilities:

```python
if provider.supports_feature(ModelFeature.FUNCTION_CALLING):
    # Use function calling feature
else:
    # Use alternative approach
```

This enables:

- Adaptable agent behavior based on model capabilities
- Graceful degradation when features aren't available
- Forward compatibility with new model features

## Usage Examples

### 1. Basic Completion

```python
from enterprise_ai.llm import complete
from enterprise_ai.schema import Message

# Simple string messages (automatically converted to user messages)
response = complete(["Hello, how can you help me with Enterprise AI?"])

# Using explicit Message objects
messages = [
    Message.system_message("You are a helpful AI assistant."),
    Message.user_message("What is Enterprise AI?")
]
response = complete(messages)

print(response.content)
```

### 2. Using Completion Options

```python
from enterprise_ai.llm import complete
from enterprise_ai.schema import CompletionOptions

# Configure completion parameters
options = CompletionOptions(
    temperature=0.7,
    max_tokens=500,
    top_p=0.9,
    stop=["\n###\n"],
    extra_params={"frequency_penalty": 0.5}
)

# Generate completion with options
response = complete(
    ["Write a short description of Enterprise AI."],
    options=options
)

print(response.content)
```

### 3. Using Specific Providers

```python
from enterprise_ai.llm import create_provider, complete

# Create a specific provider
ollama_provider = create_provider(
    "ollama",
    model_name="llama2",
    server_url="http://localhost:11434"
)

# Use the provider for completion
response = complete(
    ["Explain the concept of agent-based AI systems."],
    provider=ollama_provider
)

print(response.content)
```

### 4. Using the Simple LLM Interface

```python
from enterprise_ai.llm import LLM
from enterprise_ai.schema import Message

# Create an LLM instance with specific configuration
llm = LLM(
    provider_name="ollama",
    model_name="codellama",
    server_url="http://localhost:11434"
)

# Prepare messages
messages = [
    Message.system_message("You are a coding assistant."),
    Message.user_message("Write a Python function to sort a dictionary by values.")
]

# Generate completion
response = llm.complete(messages, temperature=0.2)

print(response.content)
```

### 5. Asynchronous Completion

```python
import asyncio
from enterprise_ai.llm import LLM
from enterprise_ai.schema import Message

async def generate_async():
    llm = LLM(model_name="llama2")

    messages = [
        Message.system_message("You are a helpful AI assistant."),
        Message.user_message("Explain asynchronous programming in Python.")
    ]

    # Asynchronous completion
    response = await llm.acomplete(messages)
    return response.content

# Run the async function
result = asyncio.run(generate_async())
print(result)
```

### 6. Checking Model Features

```python
from enterprise_ai.llm import create_provider
from enterprise_ai.constants import ModelFeature

# Create provider
provider = create_provider("ollama", model_name="llama2")

# Check for specific features
if provider.supports_feature(ModelFeature.FUNCTION_CALLING):
    print("Function calling is supported")
else:
    print("Function calling is not supported")

# Get all supported features
features = provider.get_model_features()
print(f"Supported features: {', '.join(features)}")
```

### 7. Getting Provider Metrics

```python
from enterprise_ai.llm import get_default_provider

# Get the default provider
provider = get_default_provider()

# Make some requests
provider.complete(["Hello"])
provider.complete(["How are you?"])

# Get usage metrics
metrics = provider.get_metrics()
print(f"Provider: {metrics['provider']}")
print(f"Model: {metrics['model']}")
print(f"Requests: {metrics['request_count']}")
print(f"Success rate: {metrics['success_rate'] * 100:.1f}%")
```

## Integration Points

The LLM module integrates with several other components of the Enterprise AI platform:

### 1. Agent Module

Agents use the LLM module as their core reasoning engine:

```python
from enterprise_ai.agent import Agent
from enterprise_ai.llm import create_provider

# Create a specific provider for the agent
provider = create_provider("ollama", model_name="llama2")

# Create an agent with the provider
agent = Agent(llm_provider=provider, system_prompt="You are a developer agent.")

# The agent uses the provider for reasoning
response = agent.respond("How would you implement a cache in Python?")
```

### 2. Schema Module

The LLM module uses the Schema module for message representation and completion options:

```python
from enterprise_ai.schema import Message, CompletionOptions
from enterprise_ai.llm import complete

# Create messages using the Schema module
messages = [
    Message.system_message("You are a helpful assistant."),
    Message.user_message("Help me with Enterprise AI.")
]

# Configure options using the Schema module
options = CompletionOptions(temperature=0.7, max_tokens=500)

# Generate completion
response = complete(messages, options=options)
```

### 3. Configuration System

The LLM module integrates with the configuration system for provider settings:

```python
# Configuration in config.yaml
llm:
  default_provider: ollama
  providers:
    ollama:
      server_url: http://localhost:11434
      model_name: llama2
```

```python
from enterprise_ai.llm import get_default_provider

# The provider is configured from the config system
provider = get_default_provider()
# provider is now an Ollama provider with the configured settings
```

### 4. Tool Module

Tools can use the simplified LLM interface for their own AI capabilities:

```python
from enterprise_ai.llm import LLM
from enterprise_ai.tool.core import Tool

class SummarizationTool(Tool):
    def __init__(self):
        super().__init__()
        # Create an LLM instance specifically for this tool
        self.llm = LLM(model_name="llama2")

    def execute(self, text: str) -> str:
        # Use the LLM to summarize text
        messages = [
            {"role": "system", "content": "Summarize the following text."},
            {"role": "user", "content": text}
        ]
        response = self.llm.complete(messages)
        return response.content
```

### 5. Logging System

The LLM module integrates with the logging system for diagnostics:

```python
from enterprise_ai.logger import get_logger
logger = get_logger("llm.base")

# Usage in provider implementations
logger.debug(f"Created provider: {provider_name}")
logger.error(f"Failed to create provider {provider_name}: {e}")
```

## Best Practices

### Provider Selection

1. **Use the default provider for most cases**:

   ```python
   from enterprise_ai.llm import complete

   # Uses the configured default provider
   response = complete(["Hello, world!"])
   ```

1. **Specify providers explicitly for special requirements**:

   ```python
   provider = create_provider("ollama", model_name="codellama")
   response = complete(["Write a Python function."], provider=provider)
   ```

1. **Consider model capabilities when selecting providers**:

   ```python
   provider = create_provider("openai", model_name="gpt-4")
   if provider.supports_feature(ModelFeature.FUNCTION_CALLING):
       # Use function calling
   ```

### Configuration Management

1. **Use the configuration system for provider settings**:

   ```yaml
   # config.yaml
   llm:
     default_provider: ollama
     providers:
       ollama:
         server_url: http://localhost:11434
         model_name: llama2
   ```

1. **Override configurations for specific cases**:

   ```python
   # Override only what's needed
   provider = create_provider("ollama", model_name="codellama")
   ```

1. **Share provider instances where appropriate**:

   ```python
   # Create once, use multiple times
   provider = create_provider("ollama")
   response1 = complete(["First question"], provider=provider)
   response2 = complete(["Second question"], provider=provider)
   ```

### Message Formatting

1. **Use system messages to set context**:

   ```python
   messages = [
       Message.system_message("You are a Python expert."),
       Message.user_message("How do I use decorators?")
   ]
   ```

1. **Prefer Message objects over raw strings**:

   ```python
   # Preferred
   messages = [Message.user_message("Hello")]

   # Less explicit
   messages = ["Hello"]  # Converted to user message internally
   ```

1. **Use appropriate message roles**:

   ```python
   # For context and instructions
   system_msg = Message.system_message("You are a helpful assistant.")

   # For user inputs
   user_msg = Message.user_message("Hello, AI!")

   # For AI responses
   assistant_msg = Message.assistant_message("I'm here to help.")

   # For tool outputs
   tool_msg = Message.tool_message("Result", "calculator", "call_123")
   ```

### Error Handling

1. **Handle provider unavailability**:

   ```python
   try:
       provider = create_provider("ollama")
       response = provider.complete(messages)
   except ProviderNotSupportedError:
       # Fallback to another provider
       provider = create_provider("openai")
       response = provider.complete(messages)
   ```

1. **Implement retries for transient errors**:

   ```python
   max_retries = 3
   for attempt in range(max_retries):
       try:
           response = provider.complete(messages)
           break
       except Exception as e:
           if attempt == max_retries - 1:
               raise
           # Exponential backoff
           time.sleep(2 ** attempt)
   ```

1. **Monitor provider metrics**:

   ```python
   metrics = provider.get_metrics()
   if metrics["error_count"] > threshold:
       # Log warning or switch providers
   ```

### Potential Pitfalls

1. **Model Name Inconsistency**:
   Different providers have different model naming conventions. Use provider-specific constants or configuration.

1. **Feature Detection Limitations**:
   Feature detection is only as accurate as the provider implementation. Test critical features before relying on them.

1. **Performance Overhead**:
   LLM calls can be slow and expensive. Cache results when appropriate and minimize unnecessary calls.

1. **Token Limits**:
   Be aware of model token limits for both input and output. Truncate or chunk inputs when necessary.

1. **Provider-Specific Parameters**:
   Some parameters in `CompletionOptions` may not be supported by all providers. Check provider documentation.

## Provider-Specific Implementations

Each provider implementation should be documented separately, covering:

1. Provider-specific configuration
1. Supported models and features
1. Performance characteristics
1. Usage examples
1. Integration notes

Below is a template for provider-specific documentation:

### Ollama Provider

The Ollama provider enables integration with the Ollama local model server.

#### Configuration Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| server_url | str | No | http://localhost:11434 | URL of the Ollama server |
| model_name | str | Yes | - | Name of the Ollama model to use |
| timeout | int | No | 60 | Request timeout in seconds |

#### Supported Models

Depends on your local Ollama installation. Common models include:

- llama2
- codellama
- mistral
- vicuna

#### Feature Support

| Feature | Support | Notes |
|---------|---------|-------|
| Function Calling | Limited | Depends on model capabilities |
| Image Understanding | No | Not currently supported |
| Tool Use | Limited | Depends on model capabilities |

#### Usage Example

```python
from enterprise_ai.llm import create_provider

# Create Ollama provider
provider = create_provider(
    "ollama",
    model_name="llama2",
    server_url="http://localhost:11434"
)

# Use the provider
response = provider.complete([
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Tell me about Enterprise AI."}
])

print(response.content)
```

#### Performance Notes

- Ollama provides local LLM execution, avoiding API latency
- Performance depends on hardware resources and model size
- Models can be quantized to balance performance and quality

______________________________________________________________________

Additional provider documentation (OpenAI, Anthropic, etc.) will follow the same template structure as they are implemented.
