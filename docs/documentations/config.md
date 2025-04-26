# Enterprise AI Configuration System

## Overview

The Enterprise AI configuration system provides a centralized way to manage settings across the platform. It uses a YAML-based approach with environment variable overrides, allowing for flexible configuration management in different deployment scenarios.

Key features:

- Hierarchical configuration via YAML files
- Environment variable overrides
- Dot notation for accessing nested settings
- Configuration caching for performance
- Default values to handle missing settings gracefully

## Basic Usage

### Getting Configuration Values

```python
from enterprise_ai.config import get_config

# Get a simple configuration value
api_key = get_config("llm.openai.api_key")

# Provide a default value if the setting might not exist
max_tokens = get_config("llm.max_tokens", 1024)

# Use a specific configuration file
custom_setting = get_config("custom.setting", 
                           default="default_value",
                           config_path="/path/to/custom_config.yml")
```

### Loading a Configuration File

```python
from enterprise_ai.config import load_config

# Load the default configuration
config = load_config()

# Load a specific configuration file
custom_config = load_config("/path/to/custom_config.yml")
```

## Configuration File Structure

The configuration file uses YAML format with nested sections for different components. Here's a comprehensive example configuration:

```yaml
# Sample Enterprise AI Configuration File

# LLM Provider Settings
llm:
  # Default provider to use when not explicitly specified
  default_provider: "anthropic"

    # Ollama configuration
    ollama:
        default_model: "ollama-model-name"
        temperature: 0.7
        max_tokens: 2048
        request_timeout: 60
    
  # OpenAI configuration
    openai:
        api_key: "your-openai-api-key"
        default_model: "gpt-4"
        temperature: 0.7
        max_tokens: 2048
        request_timeout: 60
  
    # Anthropic configuration
    anthropic:
        api_key: "your-anthropic-api-key"
        default_model: "claude-3-opus"
        temperature: 0.7
        max_tokens: 4096
        request_timeout: 90

    # Local model configuration
    local:
        model_path: "/path/to/local/model"
        device: "cuda"
        max_tokens: 2048

# Agent Configuration
agent:
  default_type: "llm"
  memory:
    type: "dict"
    max_history: 50
  
  # Default role settings
  roles:
    path: "./enterprise_ai/prompt/templates/roles"
  
  # Reasoning frameworks
  reasoning:
    default_framework: "cot"
    
  # State persistence
  state:
    save_dir: "./agent_states"
    save_on_exit: true

# Team Configuration
team:
  default_type: "hierarchical"
  
  # Tool sharing policy
  tools:
    allow_lateral_sharing: true
    restricted_tools: ["AdminTool", "SecurityAudit"]

# Flow Configuration
flow:
  max_concurrent_nodes: 10
  execution_timeout: 600
  storage_dir: "./workflow_storage"

# Tool Configuration
tool:
  registry_path: "./tools"
  
  # Tool categories
  categories:
    research: 
      enabled: true
      description: "Research and knowledge retrieval tools"
    development:
      enabled: true
      description: "Software development tools"
    execution:
      enabled: true
      description: "Code and command execution tools"
    file:
      enabled: true
      description: "File manipulation tools"
    content:
      enabled: true
      description: "Content generation and manipulation"
  
  # Browser tool configuration
  browser:
    user_agent: "Enterprise AI Browser/1.0"
    timeout: 30
    max_tabs: 5

# MCP Configuration
mcp:
  server:
    max_sessions: 100
    session_timeout: 3600
  
  client:
    reconnect_attempts: 3
    request_timeout: 30

# Sandbox Configuration
sandbox:
  image: "python:3.9-slim"
  work_dir: "/workspace"
  memory_limit: "512m"
  cpu_limit: 0.5
  timeout: 60
  network_enabled: false
  
  # Allowed packages for installation
  allowed_packages:
    - "numpy"
    - "pandas"
    - "matplotlib"
    - "scikit-learn"
    - "tensorflow"
    - "pytorch"

# Logging Configuration
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/enterprise_ai.log"
  max_size: 10485760  # 10MB
  backup_count: 5

# Security Configuration
security:
  api_key_required: true
  allowed_origins: ["localhost", "127.0.0.1"]
  token_expiry: 86400  # 24 hours in seconds
```

## Environment Variable Overrides

Any configuration setting can be overridden by an environment variable. The environment variable name is formed by:

1. Adding the prefix `ENTERPRISE_AI_`
1. Converting the dot notation to underscore
1. Making everything uppercase

For example:

| Configuration Key | Environment Variable |
|-------------------|----------------------|
| `llm.openai.api_key` | `ENTERPRISE_AI_LLM_OPENAI_API_KEY` |
| `sandbox.network_enabled` | `ENTERPRISE_AI_SANDBOX_NETWORK_ENABLED` |
| `logging.level` | `ENTERPRISE_AI_LOGGING_LEVEL` |

Environment variables take precedence over values in the configuration file.

## Sandbox Configuration

The `SandboxSettings` class provides configuration for Docker sandboxes used for secure code execution:

```python
from enterprise_ai.config.sandbox import SandboxSettings

# Create with default settings
sandbox_config = SandboxSettings()

# Create with custom settings
custom_sandbox = SandboxSettings(
    image="python:3.10-slim",
    work_dir="/app",
    memory_limit="1g",
    cpu_limit=1.0,
    timeout=120,
    network_enabled=True
)

# Access properties
print(f"Docker image: {custom_sandbox.image}")
print(f"Network enabled: {custom_sandbox.network_enabled}")
```

## Advanced Usage

### Loading Multiple Configuration Files

You can load multiple configuration files and combine them:

```python
import yaml
from enterprise_ai.config import load_config

# Load base configuration
base_config = load_config("./config/base.yml")

# Load environment-specific configuration
env_config = load_config("./config/production.yml")

# Merge configurations (simple approach)
merged_config = {**base_config, **env_config}

# Save merged configuration
with open("./config/merged.yml", "w") as f:
    yaml.dump(merged_config, f)
```

### Handling Missing Configuration

The `get_config` function handles missing configuration gracefully using default values:

```python
from enterprise_ai.config import get_config

# If the configuration key doesn't exist, return a default value
debug_mode = get_config("development.debug", False)

# Complex default values are also supported
default_options = {
    "retry_count": 3,
    "timeout": 30,
    "backoff_factor": 1.5
}
retry_options = get_config("network.retry_options", default_options)
```

## Configuration Best Practices

1. **Use a hierarchy that reflects your system architecture**

   - Group related settings under common prefixes
   - Use consistent naming patterns

1. **Don't commit sensitive information**

   - Use environment variables for API keys and secrets
   - Consider using a secrets management system for production

1. **Provide sensible defaults**

   - Always use `get_config` with default values for optional settings
   - Document the default values in comments

1. **Validate configuration at startup**

   - Check that required settings are present
   - Validate values are within expected ranges

1. **Use environment-specific configuration files**

   - Create separate files for development, testing, and production
   - Override only what's different in each environment

1. **Document your configuration**

   - Comment your YAML files
   - Create a configuration reference guide for your team

## Troubleshooting

### Common Issues

1. **Configuration not loading**

   - Check if the file path is correct
   - Verify the YAML syntax is valid
   - Ensure the file has proper read permissions

1. **Environment variables not working**

   - Verify the variable name matches the expected format
   - Check that the variable is actually set in the environment
   - Remember that environment variables are case-sensitive

1. **Configuration values being ignored**

   - Environment variables override file settings
   - More specific configuration paths override general ones
   - Check for typos in your configuration keys

### Debugging Configuration

```python
import os
from enterprise_ai.config import load_config, get_config
from enterprise_ai.constants import ENV_PREFIX

# Print all environment variables with the prefix
for key, value in os.environ.items():
    if key.startswith(ENV_PREFIX):
        print(f"{key}: {value}")

# Print the loaded configuration
config = load_config()
print(yaml.dump(config))

# Check a specific configuration value
key = "llm.openai.api_key"
value = get_config(key)
env_key = ENV_PREFIX + key.upper().replace(".", "_")
print(f"Config key: {key}")
print(f"Environment variable: {env_key}")
print(f"Value: {value}")
```
