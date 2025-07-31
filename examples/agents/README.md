# Enterprise-AI Tool Testing Apps

Interactive chat applications to test your Enterprise-AI agent's tool usage capabilities.

## 🚀 Quick Start

Choose your preferred testing method:

### Option 1: Use the Launcher (Recommended)
```bash
cd /home/amiche/Projects/AI/Enterprise-AI
uv run examples/agents/launcher.py
```

### Option 2: Direct App Launch
```bash
# Streaming chat (shows real-time thinking)
uv run examples/agents/streaming_tool_chat.py

# Simple chat (traditional Q&A)
uv run examples/agents/tool_test_chat.py

# Quick automated test
uv run examples/agents/streaming_tool_chat.py quick

# Integration validation
uv run examples/agents/final_mcp_integration_test.py
```

## 📱 Available Apps

### 1. 🌊 Streaming Tool Chat (`streaming_tool_chat.py`)
- **Best for slow devices**
- Real-time response streaming
- Shows agent thinking process
- Live tool execution feedback
- 1000s timeouts optimized for slower hardware

### 2. 💬 Simple Tool Chat (`tool_test_chat.py`) 
- Traditional question/answer format
- Full responses shown at once
- Conversation history tracking
- Good for quick tool testing

### 3. ⚡ Quick Test Mode
- Automated testing of 3 tool scenarios
- Fast validation without interaction
- Run with: `streaming_tool_chat.py quick`

### 4. 🧪 Integration Test (`final_mcp_integration_test.py`)
- API-level validation only
- No LLM interaction (fastest)
- Confirms MCP-Agent integration

## 🎯 Great Questions to Test Tools

### File Operations
```
"Create a file called test.txt with today's date"
"List all files in the current directory"
"Show me the contents of the enterprise_ai folder"
"Create a Python script that prints hello world"
```

### Code Execution
```
"Calculate the factorial of 10 using Python"
"Execute Python code to check if 97 is prime"
"Run Python to generate 5 random numbers"
"Calculate 1234 * 5678 using Python"
```

### Search & Discovery
```
"Find all Python files in this project"
"Search for files containing 'agent' in their name"
"Look for .py files in the enterprise_ai directory"
```

### System Operations
```
"Show running processes"
"Check the current working directory"
"List environment variables"
```

## ⚙️ Configuration

All apps are configured for slow devices:

- **Tool execution timeout**: 1000 seconds
- **LLM timeout**: 1000 seconds  
- **Verbose logging**: Enabled to see tool usage
- **ReAct reasoning**: Includes tools in LLM prompts

## 🎛️ Chat Commands

While in any chat app:

- `quit` / `exit` - Stop the chat
- `tools` - List all available tools
- `history` - Show conversation history (simple chat)
- `clear` - Clear screen (streaming chat)

## 🔍 What Each App Tests

### Streaming Chat Tests:
- ✅ Real-time tool discovery
- ✅ Tool execution with feedback
- ✅ Agent reasoning process
- ✅ Error handling during tool use

### Simple Chat Tests:
- ✅ Tool usage in conversation
- ✅ Response completeness
- ✅ Conversation continuity

### Quick Test Tests:
- ✅ File operations
- ✅ Python execution
- ✅ Basic tool chaining

### Integration Test Tests:
- ✅ MCP creation and tool loading
- ✅ Agent-MCP API integration
- ✅ Tool filtering and selection
- ✅ Direct tool access verification

## 🐛 Troubleshooting

### Common Issues:

1. **"Agent not initialized"**
   - Check that Ollama is running
   - Verify your model (llama3.2) is available
   - Try the integration test first

2. **Tool timeouts**
   - Normal for slow devices
   - Wait for the full 1000s timeout
   - Consider using smaller test cases

3. **No tool execution**
   - Ask more specific questions
   - Try: "Create a file called test.txt"
   - Avoid vague questions like "what can you do"

4. **Browser tool hangs**
   - Apps exclude browser tool to prevent this
   - If needed, use the specific tool filtering

### Performance Tips:

- Use **Streaming Chat** for the best experience on slow devices
- Ask **specific, actionable questions** rather than general ones
- **Wait for full completion** - high timeouts are intentional
- Use **Quick Test** for fast validation

## 📁 Files Created

- `launcher.py` - Main launcher with mode selection
- `streaming_tool_chat.py` - Real-time streaming chat
- `tool_test_chat.py` - Simple interactive chat
- `final_mcp_integration_test.py` - API validation tests
- `simple_mcp_integration_test.py` - Basic MCP tests
- `fixed_agent_mcp_test.py` - Improved agent tests

## 🎉 Success Indicators

You'll know your tools are working when:

- ✅ Agent creates files when asked
- ✅ Python code executes and returns results
- ✅ File searches return actual file lists
- ✅ Tool execution shows in verbose logs
- ✅ Agent reasoning mentions specific tools

Happy testing! 🚀
