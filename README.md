<p align="center">
  <img src="docs/images/logo2.png" alt="Enterprise AI Logo" width="200">
</p>

<h1 align="center">Enterprise AI: The Future of Automated Workforces</h1>

<p align="center">
  <b>Building multi-agent AI organizations that collaborate like humans</b><br>
  <i>Empowering enterprises to delegate complex tasks to autonomous AI teams</i>
</p>

## Project Vision

Enterprise AI is building the future of intelligent work automation by creating multi-agent AI systems that collaborate like human organizations. Rather than single agents working in isolation, Enterprise AI orchestrates specialized AI workers into cohesive teams with defined roles, responsibilities, and workflows.

This framework enables enterprises and individuals to delegate complex tasks to AI teams that can:

- Solve problems requiring multiple skill sets
- Maintain long-term context and organizational memory
- Execute complex, multi-step workflows with minimal supervision
- Self-organize and adapt to changing requirements
- Securely handle sensitive information and code execution

The long-term vision is to create AI teams that operate with sufficient autonomy to become trusted extensions of human workforces, handling entire classes of knowledge work with minimal oversight.

## Core Architecture

Enterprise AI is built on a modular architecture with clear separation of concerns:

1. **Core Framework** - Foundation classes, protocols, and utilities
1. **Message System** - Enhanced message handling with validation, formatting, and memory
1. **Storage System** - Persistent storage for messages, conversations, and agent state
1. **LLM Framework** - Unified API for working with different language model providers
1. **Agent System** - Base agent capabilities and specialized role implementations
1. **Team Management** - Coordination and communication between agents
1. **Tool Framework** - Extensible capabilities agents can use to interact with external systems
1. **Workflow Engine** - Task orchestration and process management
1. **Sandbox** - Secure execution environment for code and tools

## Project Status

Enterprise AI is currently in active development, with core messaging functionality implemented and storage capabilities under construction. The framework is being built incrementally with a focus on establishing solid foundations before building higher-level components.

## Development Checklist

### Core Infrastructure

- [x] Project structure and packaging
- [x] Configuration system
- [x] Logging system
- [x] Exception hierarchy
- [x] Type definitions and protocols
- [x] Basic testing framework

### Message System

- [x] Message schema and protocols
- [x] Enhanced message with mixed content support
- [x] Content validation system
- [x] Formatting for different outputs (markdown, HTML, etc.)
- [x] Image processing and handling
- [x] Memory management for conversations
- [x] Message transformers for different providers
  - [x] Base transformer functionality
  - [x] OpenAI format support
  - [x] Anthropic format support
  - [x] Ollama format support

### Storage System

- [ ] Storage interfaces and protocols
- [ ] File-based storage implementation
- [ ] SQLite storage implementation
- [ ] Message repository pattern
- [ ] Conversation persistence
- [ ] Advanced query capabilities
- [ ] Cloud storage providers (future)
  - [ ] S3/Minio support
  - [ ] PostgreSQL support
  - [ ] MongoDB support
  - [ ] Redis support

### LLM Integration

- [x] Provider interface
- [ ] API integration for major providers
  - [ ] OpenAI integration
  - [ ] Anthropic integration
  - [ ] Ollama integration
- [ ] Token counting and management
- [ ] Response caching
- [ ] Fallback mechanisms
- [ ] Request throttling and rate limiting
- [ ] Streaming support
- [ ] Cost tracking
- [ ] Service layer abstractions

### Agent System

- [ ] Base agent implementation
- [ ] Agent state management
- [ ] Agent memory integration
- [ ] Planning capabilities
- [ ] Specialized agent roles
- [ ] Agent factories and configuration

### Team Management

- [ ] Team configuration
- [ ] Role and responsibility management
- [ ] Inter-agent communication
- [ ] Hierarchical team structures
- [ ] Task delegation and coordination
- [ ] Team performance monitoring

### Tool Framework

- [ ] Tool definition and registration
- [ ] Input/output validation
- [ ] Tool access controls
- [ ] Standard tool library
  - [ ] File operations
  - [ ] Web search
  - [ ] Code execution
  - [ ] Data analysis
  - [ ] API client tools

### Workflow Engine

- [ ] Task definition and management
- [ ] Workflow execution
- [ ] State tracking
- [ ] Error handling and recovery
- [ ] Progress reporting
- [ ] Workflow templates

### Sandbox

- [ ] Secure code execution
- [ ] Resource limitations
- [ ] Input/output filtering
- [ ] Environment isolation
- [ ] Session management

### Documentation

- [ ] API Documentation
- [ ] Usage examples
- [ ] Architecture diagrams
- [ ] Best practices guide
- [ ] Deployment guide

### Quality Assurance

- [x] Unit testing framework
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Security audits
- [ ] Continuous integration

## Getting Started

Enterprise AI is still in development and not yet ready for production use. However, you can explore the existing functionality:

```python
from enterprise_ai.message import Message, EnhancedMessage, MessageFactory
from enterprise_ai.message.memory import ConversationMemory

# Create a conversation memory with system prompt
memory = ConversationMemory(system_prompt="You are a helpful AI assistant.")

# Add messages to the conversation
memory.add_user_message("Hello, can you help me with a Python problem?")
memory.add_assistant_message("Of course! What's the problem you're facing?")

# Create a message with code
code_message = MessageFactory.with_code(
    role="user",
    text_content="I'm trying to understand list comprehensions. Can you explain this code?",
    code="[x*2 for x in range(10) if x % 2 == 0]",
    language="python"
)

# Add to conversation
memory.add_message(code_message)

# Get formatted conversation history
from enterprise_ai.message.formatter import format_messages
formatted = format_messages(memory.messages, format_name="markdown")
print(formatted)
```

Stay tuned for more features as development progresses!

## Contributing

Enterprise AI is currently in early development. If you're interested in contributing, reach out to the project maintainers.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
