# Enhanced Enterprise-AI Sandbox System

## 🎯 **Your Requirements - FULLY IMPLEMENTED**

### ✅ **Default Behavior**: All tools run locally without Docker
```python
from enterprise_ai.mcp import create_local_mcp

# Default: Everything runs locally (no Docker required)
mcp = create_local_mcp()
tools = mcp.get_available_tools()  # All 15+ tools run on your system
```

### ✅ **Docker Sandbox Option**: Explicit configuration with Docker image
```python
from enterprise_ai.mcp import create_execution_sandbox_mcp

# Explicit sandbox for execution tools with your Docker image
mcp = create_execution_sandbox_mcp(
    docker_image="python:3.12-slim",  # YOUR Docker image
    memory_limit="512m",              # Container resources
    timeout=60                        # Execution timeout
)
```

### ✅ **Tool Groups**: Predefined groups with "execution" as default
```python
# Available tool groups:
TOOL_GROUPS = {
    "execution": {"bash", "python_execute", "process_manager"},  # Default for sandbox
    "file": {"file_editor", "file_system", "code_search"},
    "network": {"web_search", "deep_research"},
    "all": {/* all discovered tools */}
}

# Examples:
mcp = create_execution_sandbox_mcp("python:3.12")      # "execution" group (default)
mcp = create_file_sandbox_mcp("ubuntu:22.04")          # "file" group  
mcp = create_full_sandbox_mcp("ubuntu:22.04")          # "all" group
```

### ✅ **Docker Validation**: Uses existing Docker environments
```python
# Automatic validation prevents errors
mcp = create_execution_sandbox_mcp(
    docker_image="python:3.12-slim",
    validate_docker=True  # Checks Docker is running and image exists
)

# Output: ✅ Docker daemon is running
# Output: ✅ Docker image 'python:3.12-slim' found locally
```

## 🚀 **User-Friendly API**

### **1. Simple Local Execution (Default)**
```python
from enterprise_ai.mcp import create_local_mcp

# All tools run locally - no Docker needed
mcp = create_local_mcp()
mcp.print_sandbox_status()
# Output: 🏠 All tools run locally (no sandbox)
```

### **2. Execution Tools Sandbox**
```python
from enterprise_ai.mcp import create_execution_sandbox_mcp

# Sandbox dangerous execution tools
mcp = create_execution_sandbox_mcp(
    docker_image="python:3.12-slim",  # Use existing Python image
    memory_limit="512m",              # 512MB RAM limit
    timeout=60                        # 60 second timeout
)

# Output: 🐳 Sandbox: Enabled with 'python:3.12-slim'
# Output: ⚡ bash, python_execute, process_manager → Docker
# Output: 🏠 file_editor, web_search, etc. → Local
```

### **3. File Tools Sandbox**
```python
from enterprise_ai.mcp import create_file_sandbox_mcp

# Sandbox file manipulation tools
mcp = create_file_sandbox_mcp(
    docker_image="ubuntu:22.04",     # Ubuntu for file ops
    memory_limit="256m"              # Less memory needed
)

# Output: 📁 file_editor, file_system, code_search → Docker
# Output: ⚡ bash, python_execute → Local
```

### **4. Full Sandbox (All Tools)**
```python
from enterprise_ai.mcp import create_full_sandbox_mcp

# Maximum security - all tools in Docker
mcp = create_full_sandbox_mcp(
    docker_image="ubuntu:22.04",
    memory_limit="1g",
    network_enabled=False  # No network access
)

# Output: 🔐 All tools → Docker (maximum security)
```

### **5. Custom Sandbox**
```python
from enterprise_ai.mcp import create_custom_sandbox, create_simple_mcp

# Precise control over which tools are sandboxed
config = create_custom_sandbox(
    docker_image="python:3.11-alpine",           # Your choice of image
    specific_tools=["python_execute", "bash"],   # Only these tools
    exclude_tools=["process_manager"],           # Never this tool
    memory_limit="128m"                          # Minimal resources
)

mcp = create_simple_mcp(sandbox_config=config)
```

## 📊 **Sandbox Status & Information**

### **Get Detailed Information**
```python
# Get comprehensive sandbox info
info = mcp.get_sandbox_info()

print(f"Sandbox enabled: {info['sandbox_enabled']}")
print(f"Docker image: {info['docker_image']}")  
print(f"Sandboxed tools: {info['sandboxed_tools']}")
print(f"Local tools: {info['local_tools']}")
```

### **Print User-Friendly Status**
```python
# Print detailed status report
mcp.print_sandbox_status()

# Example output:
# 🔧 Enterprise-AI MCP Sandbox Status
# ==================================================
# 🐳 Sandbox: Enabled with 'python:3.12-slim' | 📦 Groups: execution
# 🛠️  Total Tools: 12
# 🐳 Sandboxed Tools (3):
#    • bash
#    • python_execute  
#    • process_manager
# 🏠 Local Tools (9):
#    • file_editor
#    • web_search
#    • ...
```

## 🛡️ **Safety & Validation**

### **Docker Validation**
```python
# Automatic validation (default)
try:
    mcp = create_execution_sandbox_mcp("python:3.12-slim")
    # ✅ Validates Docker is running and image exists
except ValueError as e:
    print(f"Docker issue: {e}")
    # Provides helpful error message
```

### **Skip Validation** (when you're sure Docker is available)
```python
mcp = create_execution_sandbox_mcp(
    docker_image="python:3.12-slim",
    validate_docker=False  # Skip validation for speed
)
```

## 🎯 **Real-World Usage Examples**

### **Development Environment**
```python
# Development: execution tools sandboxed, others local for speed
mcp = create_execution_sandbox_mcp("python:3.12-slim")
```

### **Production Environment** 
```python
# Production: maximum security with all tools sandboxed
mcp = create_full_sandbox_mcp(
    docker_image="ubuntu:22.04",
    memory_limit="1g",
    network_enabled=False  # No external network access
)
```

### **CI/CD Pipeline**
```python
# CI/CD: specific tools sandboxed with validation disabled
mcp = create_execution_sandbox_mcp(
    docker_image="python:3.12-slim",
    validate_docker=False,  # Docker guaranteed in CI
    timeout=120             # Longer timeout for CI
)
```

## 🔍 **Tool Group Reference**

| Group | Tools | Use Case |
|-------|-------|----------|
| `execution` | bash, python_execute, process_manager | **Default** - Most dangerous tools |
| `file` | file_editor, file_system, code_search | File manipulation |
| `network` | web_search, deep_research | Network operations |
| `research` | web_search, deep_research, browser | Research tools |
| `browser` | browser | Browser automation |
| `all` | *all discovered tools* | Maximum security |

## 💡 **Key Benefits**

### ✅ **Matches Your Requirements Exactly**
- **Default**: All tools run locally without Docker ✅
- **Optional Sandbox**: Explicit Docker image specification ✅  
- **Tool Groups**: Predefined groups with "execution" default ✅
- **Docker Validation**: Uses existing Docker environments ✅
- **User-Friendly**: Clear APIs and error messages ✅

### 🚀 **Additional Benefits**
- **Performance**: Only dangerous tools use Docker by default
- **Flexibility**: Mix local and sandboxed execution
- **Safety**: Automatic Docker/image validation
- **Debugging**: Comprehensive status reporting
- **Backward Compatible**: Works with existing configurations

## 🧪 **Testing the System**

Run the comprehensive examples:
```bash
# Test the enhanced sandbox system
python examples/enhanced_sandbox_examples.py
```

This will show you all configurations in action and validate your Docker setup!
