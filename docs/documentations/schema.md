# Enterprise AI Schema Module

## Module Overview

The Schema module forms the foundational data layer of the Enterprise AI platform. It defines the core data models and structures that are used throughout the framework for representing, storing, and manipulating conversation data, messages, model configurations, and related metadata.

This module provides essential abstractions for:

- Representing different types of messages in conversations
- Managing conversation history with various memory implementations
- Defining LLM model capabilities and completion parameters
- Handling multimedia content within messages (specifically images)

The Schema module serves as a communication standard between different components of the Enterprise AI platform, ensuring consistent data representation across agents, teams, workflows, and tools.

## Key Components

### Message

The `Message` class is the atomic unit of communication in the Enterprise AI system. It implements the `MessageProtocol` and represents a single message in a conversation with the following characteristics:

- **Role-based messaging**: Supports different roles (user, assistant, system, tool)
- **Metadata support**: Allows arbitrary metadata to be attached to messages
- **Timestamp tracking**: Automatically records message creation time
- **Tool integration**: Special support for tool-based messages with tool_call_id

```python
from enterprise_ai.schema import Message

# Create different types of messages
user_msg = Message.user_message("How can I create a new agent?")
system_msg = Message.system_message("You are a helpful AI assistant.")
assistant_msg = Message.assistant_message("I can help you create a new agent.")
tool_msg = Message.tool_message(
    content="The weather is sunny and 72°F",
    name="weather_tool",
    tool_call_id="call_123456"
)
```

### Conversation Memory

The memory submodule provides an abstraction for storing and retrieving conversation history with different implementations to suit various use cases:

- **ConversationMemory (Abstract Base Class)**: Defines the interface for all memory implementations
- **InMemoryConversation**: Simple in-memory storage suitable for short-lived conversations
- **SlidingWindowConversation**: Memory implementation that maintains a limited history window
- **ConversationMemoryFactory**: Factory pattern for creating and registering memory implementations

```python
from enterprise_ai.schema.memory import ConversationMemoryFactory

# Create a basic in-memory conversation
memory = ConversationMemoryFactory.create(
    memory_type="memory",
    system_prompt="You are a helpful AI assistant."
)

# Create a sliding window conversation with limits
sliding_memory = ConversationMemoryFactory.create(
    memory_type="sliding_window",
    system_prompt="You are a helpful AI assistant.",
    max_messages=10,
    max_tokens=4000
)
```

### LLM Configuration

LLM-related schemas define model capabilities and completion parameters:

- **ModelInfo**: Represents an LLM model's capabilities, constraints, and metadata
- **CompletionOptions**: Configuration options for generating completions from LLMs

```python
from enterprise_ai.schema import ModelInfo, CompletionOptions

# Define model information
model = ModelInfo(
    id="gpt-4",
    provider="openai",
    max_tokens=8192,
    features={"function_calling", "image_understanding"},
    context_window=8192,
    description="Advanced reasoning model with broad capabilities"
)

# Configure completion parameters
options = CompletionOptions(
    temperature=0.7,
    max_tokens=1024,
    top_p=0.95,
    stop=["\n###\n"]
)
```

### Image Utilities

The image module provides utilities for adding images to messages:

- **encode_image_to_base64**: Converts image files to base64 encoding
- **add_image_to_message**: Adds an encoded image to a message's metadata
- **is_base64**: Validates if a string is valid base64 encoding

```python
from enterprise_ai.schema.image import add_image_to_message
from enterprise_ai.schema import Message

# Create a message and add an image to it
message = Message.user_message("What's in this image?")
message_with_image = add_image_to_message(message, "path/to/image.jpg")
```

## Architecture Design

The Schema module follows several key design principles:

### 1. Protocol-Based Design

The module uses abstract protocols (like `MessageProtocol`) to define interfaces that different implementations can adhere to. This allows for flexibility and extensibility while maintaining a consistent API.

### 2. Factory Pattern

The `ConversationMemoryFactory` implements the Factory pattern to create different types of memory objects. This pattern:

- Encapsulates object creation logic
- Provides a registry for different implementations
- Allows for runtime selection of implementation types

```python
# Registration of a new memory implementation
class CustomMemory(ConversationMemory):
    # Implementation...
    pass

ConversationMemoryFactory.register("custom", CustomMemory)

# Later usage
memory = ConversationMemoryFactory.create("custom", **kwargs)
```

### 3. Composition Over Inheritance

The module uses composition to build complex behaviors. For example, `SlidingWindowConversation` extends `InMemoryConversation` but adds token and message limiting behavior.

### 4. Immutable Message Creation

Messages are created through factory methods that enforce role-specific constraints:

```python
# Factory methods for different message types
user_msg = Message.user_message("Hello")
system_msg = Message.system_message("Instructions")
assistant_msg = Message.assistant_message("Response")
tool_msg = Message.tool_message("Result", "tool_name", "call_id")
```

## Usage Examples

### Basic Conversation Flow

```python
from enterprise_ai.schema import Message
from enterprise_ai.schema.memory import InMemoryConversation

# Initialize conversation memory
memory = InMemoryConversation(system_prompt="You are a helpful assistant.")

# Add messages to the conversation
memory.add_user_message("How can I create a new agent in Enterprise AI?")
memory.add_assistant_message("To create a new agent, you'll need to use the agent factory. Here's how...")

# Retrieve conversation history
messages = memory.get_messages()
for msg in messages:
    print(f"{msg.role}: {msg.content}")

# Get token count estimate
token_count = memory.get_token_count()
print(f"Approximate token count: {token_count}")
```

### Managing Long Conversations

```python
from enterprise_ai.schema.memory import SlidingWindowConversation

# Create memory with limits
memory = SlidingWindowConversation(
    system_prompt="You are a helpful assistant.",
    max_messages=10,  # Keep only 10 most recent non-system messages
    max_tokens=4000   # Approximate token limit
)

# Add many messages (only the most recent will be kept)
for i in range(20):
    memory.add_user_message(f"Question {i}")
    memory.add_assistant_message(f"Answer {i}")

# Retrieve limited history (will only have ~10 messages plus system)
messages = memory.get_messages()
print(f"Total messages retained: {len(messages)}")
```

### Using Images in Messages

```python
from enterprise_ai.schema import Message
from enterprise_ai.schema.image import add_image_to_message

# Create a message with an image
user_msg = Message.user_message("What can you tell me about this image?")
user_msg_with_image = add_image_to_message(user_msg, "path/to/image.jpg")

# The image is now available in the message metadata
image_data = user_msg_with_image.metadata.get("images", [])[0]
print(f"Image data is {len(image_data)} characters long")
```

### Working with Model Information

```python
from enterprise_ai.schema import ModelInfo

# Define model capabilities
model = ModelInfo(
    id="local-model",
    provider="ollama",
    max_tokens=2048,
    features={"text_completion", "code_generation"},
    context_window=8192
)

# Check for specific capabilities
if model.supports_feature("function_calling"):
    print("Model supports function calling")
else:
    print("Function calling not supported")

# Get serializable representation
model_dict = model.to_dict()
```

## Integration Points

The Schema module integrates with several other components of the Enterprise AI platform:

### 1. Agent Module

Agents use the Schema module to:

- Create and manage messages through the Message class
- Store conversation history using ConversationMemory implementations
- Configure LLM interactions with CompletionOptions

```python
# Example of how an Agent might use the Schema module
from enterprise_ai.schema import Message, CompletionOptions
from enterprise_ai.schema.memory import InMemoryConversation

class SimpleAgent:
    def __init__(self, system_prompt):
        self.memory = InMemoryConversation(system_prompt=system_prompt)
        self.options = CompletionOptions(temperature=0.7, max_tokens=1024)

    def respond_to_user(self, user_input):
        # Add user message to memory
        self.memory.add_user_message(user_input)

        # Get conversation history
        messages = self.memory.get_messages()

        # Generate response using LLM (simplified)
        # response = llm.complete(messages, self.options)

        # Add assistant response to memory
        # self.memory.add_assistant_message(response)
        # return response
```

### 2. LLM Module

The LLM module uses:

- ModelInfo to represent model capabilities
- CompletionOptions to configure generation parameters
- Message objects to format prompts for the models

### 3. Tool Module

Tools interact with the Schema module by:

- Creating tool messages with tool-specific content
- Handling image data in messages for vision-based tools
- Parsing user messages to extract tool commands

### 4. Flow Module

The workflow system uses:

- Message objects to pass data between workflow nodes
- Memory implementations to store conversation state during workflow execution

## Best Practices

### Memory Management

1. **Choose the right memory implementation** for your use case:

   - Use `InMemoryConversation` for simple, short-lived conversations
   - Use `SlidingWindowConversation` for long-running conversations with token limits

1. **Set appropriate limits** for `SlidingWindowConversation` based on your model's context window:

   ```python
   # Example for an 8K context window model (reserving some tokens for the prompt)
   memory = SlidingWindowConversation(
       max_tokens=7000,  # Leave ~1000 tokens for the response
       system_prompt="You are a helpful assistant."
   )
   ```

1. **Always include a system prompt** to provide consistent behavior:

   ```python
   memory = InMemoryConversation(system_prompt="You are an Enterprise AI assistant...")
   ```

### Message Creation

1. **Use factory methods** for creating message types:

   ```python
   # Preferred
   message = Message.user_message("Hello")

   # Avoid
   message = Message(role="user", content="Hello")
   ```

1. **Add metadata judiciously** to avoid bloating message objects:

   ```python
   # Good practice
   message = Message.user_message(
       "How many records are in the database?",
       metadata={"query_context": "database_stats"}
   )
   ```

1. **Handle image data efficiently** by referencing files rather than embedding large base64 strings:

   ```python
   # For large datasets, store reference to image path
   message.metadata["image_path"] = "/path/to/image.jpg"

   # Only encode to base64 when sending to models that require it
   ```

### LLM Configuration

1. **Start with conservative completion parameters** and adjust based on needs:

   ```python
   options = CompletionOptions(
       temperature=0.3,  # Lower for more deterministic outputs
       max_tokens=512,   # Start small and increase if needed
       top_p=0.9
   )
   ```

1. **Match model features to requirements** when selecting models:

   ```python
   # Check for required capabilities
   if not model.supports_feature("function_calling"):
       # Fall back to alternative approach without function calling
       pass
   ```

### Potential Pitfalls

1. **Token count estimation** is approximate; use a proper tokenizer for accurate counts when critical:

   ```python
   # The built-in method is an approximation
   approx_tokens = memory.get_token_count()

   # For accurate counts, use a model-specific tokenizer
   # accurate_tokens = tokenizer.count_tokens(memory.get_messages())
   ```

1. **Memory leaks** with long-running conversations:

   - Always use `SlidingWindowConversation` or implement custom cleanup for long-running agents
   - Consider adding a timeout mechanism to clear stale conversations

1. **Large message content** can impact performance:

   - Consider implementing chunking for very large text inputs
   - Use references to external resources rather than embedding large content directly

1. **System messages** are special and should be used carefully:

   - They're always preserved in `SlidingWindowConversation`
   - They might be treated differently by different LLM providers
