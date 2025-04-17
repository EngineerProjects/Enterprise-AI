# Enterprise AI Notebooks

This directory contains notebooks and example scripts for testing and demonstrating the capabilities of the Enterprise AI system.

## Setup

Before running these notebooks, make sure to set up your environment:

1. **Install required packages**:
   ```bash
   pip install pillow numpy requests httpx
   ```

2. **Prepare image directory**:
   ```bash
   mkdir -p notebooks/images
   ```

3. **Add your images**:
   Copy your image files to the `notebooks/images` directory. The system is configured to look for:
   - `animaux.jpg`
   - `indian_love.jpg`
   - `familly.jpg`
   - `paysage.jpg`
   - `logo2.png`

4. **Configure Ollama**:
   Make sure Ollama is running locally with appropriate models installed.
   Install Ollama models with:
   ```bash
   ollama pull smollm2  # Default small model
   ollama pull llava    # Vision model (optional)
   ollama pull llama3.2 # Function calling model (optional)
   ```

## Available Notebooks

### 1. Utilities Module (`utils.py`)

This module provides shared functionality for all notebooks:
- Terminal output formatting
- Image handling with proper resizing
- Model capability detection
- Timer utilities and more

### 2. Prompt System Examples (`prompt_example.py`)

Demonstrates working with the Enterprise AI prompt management system:
- Loading built-in prompt templates 
- Creating custom prompts
- Formatting templates with variables

```bash
python prompt_example.py
```

### 3. Agent System Examples (`agent_example.py`)

Explores the agent system capabilities:
- Creating different types of specialized agents
- Agent-to-agent communication
- Task assignment and processing

```bash
python agent_example.py
```

### 4. Team System Examples (`team_example.py`)

Shows how to work with the multi-agent team framework:
- Creating teams with different structures
- Building hierarchical organizations
- Managing team communication and task workflow

```bash
python team_example.py
```

### 5. Memory System Examples (`memory_example.py`)

Demonstrates the conversation memory system:
- Using different memory implementations
- Including images in conversation history
- Testing sliding window memory with pruning

```bash
python memory_example.py
```

### 6. LLM Provider Examples (`llm_provider_example.py`)

Tests the language model provider system:
- Basic completion APIs
- Streaming and async functionality
- Vision capabilities (if available)
- Function calling (if available)

```bash
python llm_provider_example.py
```

### 7. Sandbox Examples (`sandbox_example.py`)

Shows how to work with the secure execution environment:
- Creating Docker sandboxes
- Running code safely in containers
- File operations and network access control

```bash
python sandbox_example.py
```

### 8. Complete End-to-End Demo (`enterprise_ai_demo.py`)

A comprehensive demonstration of all components working together:
- Builds a team of specialized AI agents
- Creates a secure execution environment
- Processes a multi-step data analysis project
- Generates visualizations and a final report

```bash
python enterprise_ai_demo.py
```

## Configuration

You can modify the configuration in each notebook to match your environment:

- **Models**: Update the model names in `CONFIG` dictionaries to use different Ollama models
- **Timeouts**: Increase timeout values if you're using larger models or have a slower machine
- **Image Size**: The default is set to 400x268 pixels, optimized for older GPUs

## Troubleshooting

- If you encounter errors with images, make sure PIL/Pillow is installed
- For Docker sandbox errors, verify Docker is running and accessible
- If LLM tests fail, check that Ollama is running at http://localhost:11434