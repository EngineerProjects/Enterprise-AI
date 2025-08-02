# Enhanced Reasoning Patterns - Test Examples

This directory contains comprehensive test examples for all enhanced reasoning patterns in the Enterprise AI system.

## 📁 Test Files Overview

### Individual Pattern Tests
- **`agent_react_test.py`** - Enhanced ReAct reasoning pattern tests
- **`agent_cot_test.py`** - Enhanced Chain of Thought reasoning pattern tests  
- **`agent_swe_test.py`** - Enhanced Software Engineering reasoning pattern tests
- **`agent_metacognitive_test.py`** - Enhanced MetaCognitive reasoning pattern tests

### Comparative Analysis
- **`agent_comparative_test.py`** - Side-by-side comparison of all patterns
- **`agent_basic_test.py`** - Basic agent configuration and setup tests

## 🚀 Quick Start

### Run Individual Pattern Tests

```bash
# Test Enhanced ReAct Pattern
cd examples/agents
python agent_react_test.py

# Test Enhanced Chain of Thought Pattern  
python agent_cot_test.py

# Test Enhanced Software Engineering Pattern
python agent_swe_test.py

# Test Enhanced MetaCognitive Pattern
python agent_metacognitive_test.py
```

### Run Comparative Analysis

```bash
# Compare all patterns with identical tasks
python agent_comparative_test.py
```

## 🎯 Pattern Selection Guide

### 🔧 **Enhanced ReAct Pattern** (`reasoning_pattern="react"`)
**When to Use:**
- Research and data gathering tasks
- Tool-intensive operations
- Iterative problem solving
- Tasks requiring transparent reasoning traces

**Strengths:**
- Explicit Thought-Action-Observation format
- Excellent tool integration
- Clear reasoning transparency
- Error detection and recovery

**Example Tasks:**
- "Research renewable energy trends and create a summary"
- "Analyze this dataset and find key insights"
- "Debug this code and fix the issues"

### 🧠 **Enhanced Chain of Thought Pattern** (`reasoning_pattern="cot"`)
**When to Use:**
- Complex analytical problems
- Mathematical calculations
- Research synthesis
- Multi-criteria decision analysis

**Strengths:**
- Step-by-step analytical breakdown
- Evidence gathering and verification
- Logical reasoning progression
- Comprehensive problem decomposition

**Example Tasks:**
- "Analyze the pros and cons of different investment strategies"
- "Solve this optimization problem step-by-step"
- "Compare and contrast different marketing approaches"

### 💻 **Enhanced Software Engineering Pattern** (`reasoning_pattern="swe"`)
**When to Use:**
- Software development tasks
- Code review and refactoring
- Architecture design
- Technical optimization

**Strengths:**
- Complete development lifecycle
- Software engineering best practices
- Code quality focus
- Technical problem solving

**Example Tasks:**
- "Build a REST API for user management"
- "Review this code and suggest improvements"
- "Design a microservices architecture"

### 🧠 **Enhanced MetaCognitive Pattern** (`reasoning_pattern="metacognitive"`)
**When to Use:**
- Strategic planning
- Complex project management
- Crisis management
- Multi-phase initiatives requiring adaptation

**Strengths:**
- 6-phase reasoning flow (Planning → Execution → Monitoring → Decision → Reflection → Termination)
- Self-monitoring and adaptation
- Strategic thinking
- Natural human-like reasoning

**Example Tasks:**
- "Develop a go-to-market strategy for our new product"
- "Manage this complex software migration project"
- "Create a crisis response plan for system outages"

## 🧪 Test Scenarios Covered

### ReAct Pattern Tests
1. **Tool Usage** - Web search and data analysis
2. **Iterative Reasoning** - Multi-step calculations
3. **Error Handling** - Code debugging and fixing
4. **Planning Integration** - Project planning with tools
5. **Decision Making** - Business decision analysis

### Chain of Thought Tests
1. **Analytical Reasoning** - Business impact analysis
2. **Mathematical Reasoning** - Optimization problems
3. **Research Synthesis** - Technology comparison
4. **Logical Reasoning** - Logic puzzles and deduction
5. **Decision Analysis** - Multi-criteria evaluation

### Software Engineering Tests
1. **Full Development Cycle** - Complete API development
2. **Code Review** - Quality improvement and refactoring
3. **Architecture Design** - Microservices design
4. **Testing Strategy** - Comprehensive test development
5. **Performance Optimization** - Code and query optimization

### MetaCognitive Tests
1. **Strategic Planning** - Go-to-market strategy
2. **Adaptive Problem Solving** - Supply chain optimization
3. **Project Management** - Enterprise migration projects
4. **Crisis Management** - System outage response
5. **Innovation Strategy** - AI transformation planning

## ⚙️ Configuration Examples

### Basic Configuration
```python
agent = create_agent(
    name="TestBot",
    role_config={"name": "Assistant", "system_prompt": "I help with various tasks."},
    reasoning_pattern="react",  # or "cot", "swe", "metacognitive"
    mcp_config={"timeout": 1000.0, "tools": ["web_search", "python_execute"]},
    llm_config={"model_name": "llama3.2", "timeout": 800.0},
    verbose=True
)
```

### Advanced Configuration
```python
agent = create_agent(
    name="AdvancedBot",
    role_config={
        "name": "Senior Analyst", 
        "system_prompt": "Expert analyst with comprehensive capabilities."
    },
    reasoning_pattern="metacognitive",
    mcp_config={
        "timeout": 2000.0,
        "tools": ["planning", "terminate", "web_search", "python_execute", "file_system"]
    },
    llm_config={"model_name": "llama3.2", "timeout": 1500.0, "temperature": 0.7},
    verbose=True
)
```

## 📊 Expected Output Formats

### ReAct Pattern Output
```
Thought: I need to research renewable energy trends for 2024.
Action: web_search[query="renewable energy trends 2024"]
Observation: Found data showing 23% growth in solar capacity...
Thought: Now I need to analyze the specific growth drivers.
Action: web_search[query="solar energy growth drivers 2024"]
Observation: Key drivers include policy support and cost reduction...
Thought: I have sufficient data to provide a comprehensive answer.
Answer: Based on my research, renewable energy trends in 2024 show...
```

### Chain of Thought Pattern Output
```
Step 1: To analyze the investment strategies, I need to identify the key criteria for comparison...
Step 2: Let me gather data on historical performance for each strategy...
Action: web_search[query="investment strategy performance 2024"]
Evidence: Historical data shows...
Step 3: Now I'll analyze risk-return profiles for each option...
Step 4: Considering the investor's risk tolerance and timeline...
Conclusion: Based on the systematic analysis, I recommend...
```

### Software Engineering Pattern Output
```
Thought: I need to design a REST API following software engineering best practices. Let me start with requirements analysis.
Action: planning[command="create", plan_id="api_design", steps=["Requirements", "Design", "Implementation", "Testing"]]
Observation: Plan created successfully...
Thought: Now I'll implement the core API structure with proper error handling and validation.
Action: write_file[path="api.py", content="from fastapi import FastAPI..."]
Observation: File created successfully...
Answer: I've created a complete REST API with the following features...
```

### MetaCognitive Pattern Output
```
PLANNING PHASE: Breaking down the go-to-market strategy into key components...
EXECUTION PHASE: Implementing market research and competitive analysis...
MONITORING PHASE: Assessing progress on strategy development...
DECISION PHASE: Strategy is comprehensive, proceeding to finalization...
TERMINATION PHASE: Go-to-market strategy completed successfully.
```

## 🔧 Troubleshooting

### Common Issues
1. **Import Errors**: Ensure you're running from the correct directory with `sys.path` setup
2. **Model Not Found**: Verify Ollama is running and llama3.2 model is available
3. **Tool Errors**: Check that required tools are properly configured in MCP
4. **Timeout Issues**: Increase timeout values for complex tasks

### Performance Tips
- Use appropriate timeout values based on task complexity
- Start with simpler patterns (ReAct) before testing complex ones (MetaCognitive)
- Monitor tool usage and reasoning traces with `verbose=True`
- Test individual patterns before running comparative tests

## 📈 Next Steps

1. **Start with Basic Tests**: Run `agent_basic_test.py` to verify setup
2. **Test Individual Patterns**: Try each pattern with your specific use cases
3. **Compare Patterns**: Use `agent_comparative_test.py` to understand differences
4. **Production Integration**: Integrate chosen patterns into your applications

## 🎯 Production Readiness

All enhanced reasoning patterns are production-ready and provide:
- ✅ Explicit reasoning traces for debugging
- ✅ Comprehensive tool integration
- ✅ Error handling and recovery
- ✅ Scalable architecture
- ✅ Enterprise-grade reliability

Choose the pattern that best fits your use case and start building intelligent applications!