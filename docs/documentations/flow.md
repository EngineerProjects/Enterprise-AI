# Enterprise AI Documentation: Flow Module

## Module Overview

The Flow module is a powerful orchestration engine for the Enterprise AI platform that enables the creation, execution, and management of complex workflows. This module allows for the systematic coordination of agents, teams, and tasks through a flexible node-based architecture.

Key features of the Flow module include:

- **Node-Based Architecture**: Workflows are composed of modular, reusable nodes that can be combined to create complex execution paths
- **Task Orchestration**: Coordinate agents and teams to perform sequences of interdependent tasks
- **Control Flow Patterns**: Support for advanced patterns like conditionals, parallel execution, and retries
- **Execution Management**: Real-time monitoring, pausing, resuming, and cancellation of workflow execution
- **State Tracking**: Comprehensive tracking of execution status and results
- **Persistence**: Storage of workflow execution history and results
- **Fluent API**: Builder pattern for intuitive workflow construction

The Flow module serves as the "nervous system" of the Enterprise AI platform, coordinating the activities of agents and teams to accomplish complex multi-step processes. It provides a high-level abstraction for designing AI-powered business processes and automation workflows.

## Key Components

### 1. Workflow Nodes

Nodes are the fundamental building blocks of workflows, representing individual units of work or control flow.

#### `BaseNode`

The foundation class implementing the `NodeProtocol` interface:

- Unique ID and name
- Dependencies on other nodes
- Status tracking
- Execution logic

```python
from enterprise_ai.flow import BaseNode

# Create a basic node
node = BaseNode(
    name="Basic Node",
    dependencies={"node-1", "node-2"},  # Optional dependencies
    node_id="node-3"  # Optional ID (auto-generated if not provided)
)

# Check execution status
print(f"Node status: {node.status.name}")  # PENDING, RUNNING, COMPLETED, etc.

# Check dependencies
print(f"Dependencies: {node.dependencies}")
```

#### `FunctionNode`

A node that executes a Python function:

```python
from enterprise_ai.flow import FunctionNode

# Create a function node
def process_data(context):
    # Process data from context
    data = context.get("input_data", [])
    processed = [item.upper() for item in data]
    return {"processed_data": processed}

node = FunctionNode(
    name="Process Data",
    function=process_data,
    dependencies={"data-loader-node"}
)

# Node will execute the function during workflow execution
```

#### Specialized Nodes

The Flow module includes several specialized node types for common tasks:

##### `AgentTaskNode`

Assigns and monitors tasks for individual agents:

```python
from enterprise_ai.flow import AgentTaskNode
from enterprise_ai.agent import create_agent

# Create an agent
agent = create_agent(agent_type="llm", name="Research Assistant")

# Create an agent task node
node = AgentTaskNode(
    name="Research Task",
    agent=agent,
    task_description="Research the history of AI and provide a summary.",
    result_key="research_result",
    timeout=120.0  # Maximum time to wait (seconds)
)
```

##### `TeamTaskNode`

Assigns and monitors tasks for teams:

```python
from enterprise_ai.flow import TeamTaskNode
from enterprise_ai.team import create_team

# Create a team
team = create_team(team_type="collaborative", name="Research Team")

# Create a team task node
node = TeamTaskNode(
    name="Team Research",
    team=team,
    task_description="Analyze market trends for AI products.",
    target_agent_id="analyst-1",  # Optional specific agent
    result_key="market_analysis",
    timeout=300.0  # Maximum time to wait (seconds)
)
```

##### Control Flow Nodes

Nodes that manage execution flow:

```python
from enterprise_ai.flow import ConditionalNode, ParallelNode, RetryNode

# Conditional branch
condition_node = ConditionalNode(
    name="Check Data Quality",
    condition=lambda ctx: len(ctx.get("data", [])) > 10,
    then_node=process_good_data_node,
    else_node=handle_insufficient_data_node
)

# Parallel execution
parallel_node = ParallelNode(
    name="Parallel Tasks",
    nodes=[task1_node, task2_node, task3_node],
    merge_results=True  # Combine results from all branches
)

# Retry logic
retry_node = RetryNode(
    name="Retry Web Search",
    node=web_search_node,
    max_attempts=3,
    delay=2.0  # Seconds between attempts
)
```

### 2. Workflows

Workflows are collections of connected nodes with defined execution paths.

#### `BaseWorkflow`

The foundation class for workflows:

- Node management
- Status tracking
- Context maintenance
- Execution control

```python
from enterprise_ai.flow import BaseWorkflow, BaseNode

# Create a workflow
workflow = BaseWorkflow(
    name="Data Processing Workflow",
    workflow_id="workflow-123",  # Optional ID
    initial_context={"source": "customer_data.csv"}  # Initial data
)

# Add nodes
node1 = BaseNode(name="Step 1")
node2 = BaseNode(name="Step 2", dependencies={node1.id})
node3 = BaseNode(name="Step 3", dependencies={node2.id})

workflow.add_node(node1)
workflow.add_node(node2)
workflow.add_node(node3)

# Get workflow status
print(f"Workflow status: {workflow.status.name}")  # PENDING, RUNNING, COMPLETED, etc.

# Get nodes
print(f"Node count: {len(workflow.nodes)}")
```

#### `SequentialWorkflow`

A workflow that executes nodes in sequence:

```python
from enterprise_ai.flow import SequentialWorkflow, BaseNode

# Create nodes
node1 = BaseNode(name="Step 1")
node2 = BaseNode(name="Step 2")
node3 = BaseNode(name="Step 3")

# Create a sequential workflow
workflow = SequentialWorkflow(
    name="Sequential Process",
    nodes=[node1, node2, node3]  # Nodes will be connected in sequence
)

# Sequential workflow automatically adds dependencies
# node2 depends on node1, node3 depends on node2
```

### 3. Workflow Builder

The `WorkflowBuilder` provides a fluent API for constructing workflows:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create agents
research_agent = create_agent(agent_type="llm", role_type="researcher")
dev_agent = create_agent(agent_type="llm", role_type="developer")

# Build a workflow using the fluent API
workflow = (WorkflowBuilder("Research and Development")
    .add_agent_task(
        name="Market Research",
        agent=research_agent,
        task_description="Research market trends for AI products.",
        result_key="market_research"
    )
    .add_function(
        name="Process Research",
        function=lambda ctx: {"key_findings": extract_findings(ctx["market_research"])}
    )
    .add_agent_task(
        name="Product Development",
        agent=dev_agent,
        task_description="Design a product based on the following research: {market_research}",
        result_key="product_design"
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

The builder supports all node types and advanced patterns:

```python
# Building with conditional branches
workflow = (WorkflowBuilder("Conditional Workflow")
    .add_agent_task(
        name="Initial Research",
        agent=research_agent,
        task_description="Research the topic.",
        result_key="research"
    )
    .add_condition(
        name="Evaluate Research",
        condition=lambda ctx: "positive" in ctx["research"].lower(),
        then_builder=lambda b: b.add_agent_task(
            name="Positive Path",
            agent=dev_agent,
            task_description="Develop based on positive research."
        ),
        else_builder=lambda b: b.add_agent_task(
            name="Negative Path",
            agent=dev_agent,
            task_description="Address issues in the research."
        )
    )
    .build())

# Building with parallel execution
workflow = (WorkflowBuilder("Parallel Workflow")
    .add_agent_task(
        name="Initial Research",
        agent=research_agent,
        task_description="Research the topic.",
        result_key="research"
    )
    .add_parallel(
        name="Parallel Analysis",
        branch_builders=[
            lambda b: b.add_agent_task(
                name="Technical Analysis",
                agent=tech_agent,
                task_description="Analyze technical aspects."
            ),
            lambda b: b.add_agent_task(
                name="Market Analysis",
                agent=market_agent,
                task_description="Analyze market aspects."
            ),
            lambda b: b.add_agent_task(
                name="User Analysis",
                agent=ux_agent,
                task_description="Analyze user experience aspects."
            )
        ],
        merge_results=True
    )
    .build())
```

### 4. Workflow Factory

The `WorkflowFactory` provides pre-built workflow patterns for common use cases:

```python
from enterprise_ai.flow.factory import WorkflowFactory
from enterprise_ai.agent import create_agent
from enterprise_ai.team import create_team

# Create agents and teams
agent = create_agent(agent_type="llm", name="Assistant")
research_team = create_team(team_type="collaborative", name="Research")
dev_team = create_team(team_type="collaborative", name="Development")

# Create a sequential agent workflow
workflow1 = WorkflowFactory.create_sequential_agent_workflow(
    name="Agent Tasks",
    agent=agent,
    tasks=[
        "Research quantum computing applications.",
        "Summarize findings in a report.",
        "Create a presentation based on the report."
    ]
)

# Create a team collaboration workflow
workflow2 = WorkflowFactory.create_team_collaboration_workflow(
    name="Research to Development",
    research_team=research_team,
    development_team=dev_team,
    research_task="Research the latest AI technologies.",
    development_task="Develop a prototype based on: {research_result}"
)

# Create a data processing workflow
workflow3 = WorkflowFactory.create_data_processing_workflow(
    name="Data Analysis Pipeline",
    data_prep_agent=create_agent(agent_type="llm", role_type="analyst"),
    analysis_agent=create_agent(agent_type="llm", role_type="data_scientist"),
    reporting_agent=create_agent(agent_type="llm", role_type="reporting"),
    data_prep_task="Clean and prepare the dataset.",
    analysis_task="Analyze the prepared data: {prepared_data}",
    reporting_task="Create a report on the findings: {analysis_result}"
)
```

### 5. Workflow Execution

The `WorkflowExecutor` handles the execution of workflows:

```python
from enterprise_ai.flow import WorkflowExecutor

# Create an executor
executor = WorkflowExecutor(max_concurrent_nodes=5)

# Execute a workflow
import asyncio
result = asyncio.run(executor.execute_workflow(workflow))

# The executor handles:
# - Node scheduling based on dependencies
# - Concurrent execution within limits
# - Context updates
# - Error handling
```

### 6. Workflow Management

The `WorkflowManager` provides high-level management of workflows:

```python
from enterprise_ai.flow import WorkflowManager

# Create a manager with persistent storage
manager = WorkflowManager(storage_dir="/path/to/workflow/storage")

# Register a workflow
workflow_id = manager.register_workflow(workflow)

# Execute a workflow
import asyncio
status, result = asyncio.run(manager.execute_workflow(
    workflow_id,
    wait_for_completion=True,
    initial_context={"input_param": "value"}
))

# Monitor workflow status
status = manager.get_workflow_status(workflow_id)
print(f"Workflow status: {status.name}")

# Get execution history
history = manager.get_workflow_execution_history(workflow_id)
print(f"Execution count: {len(history)}")
print(f"Last execution: {history[-1]['status']}")

# Control execution
manager.pause_workflow(workflow_id)
manager.resume_workflow(workflow_id)
manager.cancel_workflow(workflow_id)
```

## Architecture Design

The Flow module follows several architectural patterns and principles:

### 1. Protocol-Based Design

The module uses protocols (interfaces) to define capabilities:

```
NodeProtocol            WorkflowProtocol
     ↑                        ↑
     |                        |
 BaseNode               BaseWorkflow
     ↑                        ↑
     |                        |
Specialized Nodes     SequentialWorkflow
```

This protocol-based design enables:

- Consistent interfaces across implementations
- Polymorphic handling of nodes and workflows
- Easy extension with new node and workflow types
- Clear separation of concerns

### 2. Builder Pattern

The `WorkflowBuilder` implements the Builder pattern:

```
WorkflowBuilder
    → add_function()
    → add_agent_task()
    → add_team_task()
    → add_condition()
    → add_parallel()
    → add_retry()
    → build()
```

This provides:

- A fluent API for workflow construction
- Encapsulation of the complex node wiring logic
- A more readable and maintainable way to define workflows
- Progressive building of complex structures

### 3. Factory Pattern

The module uses factory functions to create common workflow patterns:

```
WorkflowFactory
    → create_sequential_agent_workflow()
    → create_team_collaboration_workflow()
    → create_data_processing_workflow()
```

This provides:

- Encapsulated creation logic for complex structures
- Consistent patterns for common use cases
- Simplified creation of standard workflows

### 4. Command Pattern

Nodes implement a command-like pattern:

```
BaseNode.execute()
    → _execute_internal()
        → Custom execution logic
```

This enables:

- Encapsulation of execution logic
- Consistent execution interface
- Support for control flow patterns (retry, conditional)

### 5. Composite Pattern

Workflows are composites of nodes, and special nodes can contain sub-workflows:

```
Workflow
    ├── Node 1
    ├── Node 2
    └── ConditionalNode
            ├── Then Branch (sub-workflow)
            └── Else Branch (sub-workflow)
```

This allows for:

- Hierarchical structuring of workflows
- Nested workflows within control nodes
- Modular composition of complex workflows

### 6. Observer Pattern

The execution system observes node and workflow status:

```
WorkflowExecutor
    → Monitors node status changes
    → Updates workflow status
    → Manages execution flow
```

This provides:

- Real-time monitoring of execution
- Event-driven flow control
- Decoupled execution monitoring

## Usage Examples

### Basic Workflow Creation and Execution

#### Creating and Executing a Simple Workflow

```python
from enterprise_ai.flow import BaseWorkflow, FunctionNode, WorkflowExecutor

# Create nodes for text processing
def load_data(context):
    return {"text": "This is a sample text for processing."}

def count_words(context):
    text = context["text"]
    word_count = len(text.split())
    return {"word_count": word_count}

def analyze_sentiment(context):
    text = context["text"]
    # Simple sentiment analysis
    positive_words = ["good", "great", "excellent"]
    negative_words = ["bad", "terrible", "awful"]
    
    words = text.lower().split()
    positive_count = sum(1 for word in words if word in positive_words)
    negative_count = sum(1 for word in words if word in negative_words)
    
    sentiment = "positive" if positive_count > negative_count else "negative" if negative_count > positive_count else "neutral"
    return {"sentiment": sentiment}

# Create function nodes
load_node = FunctionNode(name="Load Data", function=load_data)
count_node = FunctionNode(name="Count Words", function=count_words, dependencies={load_node.id})
sentiment_node = FunctionNode(name="Analyze Sentiment", function=analyze_sentiment, dependencies={load_node.id})

# Create a workflow
workflow = BaseWorkflow(name="Text Analysis")
workflow.add_node(load_node)
workflow.add_node(count_node)
workflow.add_node(sentiment_node)

# Execute the workflow
import asyncio

async def run_workflow():
    executor = WorkflowExecutor()
    result = await executor.execute_workflow(workflow)
    print(f"Result: {result}")

asyncio.run(run_workflow())
```

#### Using the Builder Pattern

```python
from enterprise_ai.flow import WorkflowBuilder

# Create the same workflow using the builder
workflow = (WorkflowBuilder("Text Analysis")
    .add_function(
        name="Load Data",
        function=lambda ctx: {"text": "This is a sample text for processing."}
    )
    .add_function(
        name="Count Words",
        function=lambda ctx: {"word_count": len(ctx["text"].split())}
    )
    .add_function(
        name="Analyze Sentiment",
        function=lambda ctx: {
            "sentiment": analyze_text_sentiment(ctx["text"])
        }
    )
    .build())

# Execute the workflow
import asyncio
asyncio.run(workflow.execute())
```

### Agent-Based Workflows

#### Sequential Agent Tasks

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create an agent
agent = create_agent(
    agent_type="llm",
    name="Research Assistant",
    role_type="researcher",
    reasoning_framework="cot"
)

# Create a workflow with sequential agent tasks
workflow = (WorkflowBuilder("Research Project")
    .add_agent_task(
        name="Initial Research",
        agent=agent,
        task_description="Research the history and current state of quantum computing.",
        result_key="background_research"
    )
    .add_agent_task(
        name="Identify Applications",
        agent=agent,
        task_description="Based on this research: {background_research}\n\nIdentify 5 potential business applications of quantum computing.",
        result_key="applications"
    )
    .add_agent_task(
        name="Final Report",
        agent=agent,
        task_description="Create a comprehensive report that includes the background research: {background_research}\n\nAnd the applications: {applications}",
        result_key="final_report"
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
print(f"Final report: {result['final_report']}")
```

#### Multi-Agent Collaboration

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create specialized agents
researcher = create_agent(agent_type="llm", name="Researcher", role_type="researcher")
analyst = create_agent(agent_type="llm", name="Analyst", role_type="analyst")
writer = create_agent(agent_type="llm", name="Writer", role_type="writer")

# Create a workflow with different agents
workflow = (WorkflowBuilder("Market Analysis")
    .add_agent_task(
        name="Market Research",
        agent=researcher,
        task_description="Research the current state of the AI software market.",
        result_key="market_data"
    )
    .add_agent_task(
        name="Data Analysis",
        agent=analyst,
        task_description="Analyze this market data: {market_data}\n\nIdentify key trends and opportunities.",
        result_key="analysis"
    )
    .add_agent_task(
        name="Report Writing",
        agent=writer,
        task_description="Create a professional report based on this analysis: {analysis}",
        result_key="report"
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

### Team-Based Workflows

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.team import create_team
from enterprise_ai.agent import create_agent

# Create teams
research_team = create_team(
    team_type="collaborative",
    name="Research Team",
    manager_agent=create_agent(agent_type="llm", name="Research Lead", role_type="manager")
)
dev_team = create_team(
    team_type="collaborative",
    name="Development Team",
    manager_agent=create_agent(agent_type="llm", name="Dev Lead", role_type="manager")
)

# Add members to teams
for i in range(3):
    research_team.add_member(
        create_agent(agent_type="llm", name=f"Researcher {i+1}", role_type="researcher")
    )
    dev_team.add_member(
        create_agent(agent_type="llm", name=f"Developer {i+1}", role_type="developer")
    )

# Create a workflow with team tasks
workflow = (WorkflowBuilder("Product Development")
    .add_team_task(
        name="Market Research",
        team=research_team,
        task_description="Conduct comprehensive market research for an AI-powered code generation tool.",
        result_key="market_research"
    )
    .add_function(
        name="Extract Requirements",
        function=lambda ctx: {"requirements": extract_requirements(ctx["market_research"])}
    )
    .add_team_task(
        name="Product Development",
        team=dev_team,
        task_description="Develop a prototype based on these requirements: {requirements}",
        result_key="prototype"
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

### Advanced Control Flow

#### Conditional Execution

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create agents
researcher = create_agent(agent_type="llm", name="Researcher", role_type="researcher")
developer = create_agent(agent_type="llm", name="Developer", role_type="developer")
marketer = create_agent(agent_type="llm", name="Marketer", role_type="custom", 
                        role_kwargs={"name": "Marketing Specialist"})

# Create a workflow with conditional branching
workflow = (WorkflowBuilder("Product Evaluation")
    .add_agent_task(
        name="Market Analysis",
        agent=researcher,
        task_description="Analyze the market potential for an AI-powered code assistant.",
        result_key="market_analysis"
    )
    .add_condition(
        name="Evaluate Potential",
        condition=lambda ctx: "high potential" in ctx["market_analysis"].lower(),
        then_builder=lambda b: (
            b.add_agent_task(
                name="Develop Prototype",
                agent=developer,
                task_description="Create a prototype for this high-potential product: {market_analysis}",
                result_key="prototype"
            )
            .add_agent_task(
                name="Marketing Plan",
                agent=marketer,
                task_description="Create a marketing plan for this product: {prototype}",
                result_key="marketing_plan"
            )
        ),
        else_builder=lambda b: (
            b.add_agent_task(
                name="Alternative Research",
                agent=researcher,
                task_description="Research alternative product ideas since the original has low potential.",
                result_key="alternatives"
            )
        )
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

#### Parallel Execution

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create agents for different aspects of analysis
tech_analyst = create_agent(agent_type="llm", name="Tech Analyst", role_type="analyst")
market_analyst = create_agent(agent_type="llm", name="Market Analyst", role_type="analyst")
user_analyst = create_agent(agent_type="llm", name="User Analyst", role_type="analyst")
writer = create_agent(agent_type="llm", name="Report Writer", role_type="writer")

# Create a workflow with parallel analysis branches
workflow = (WorkflowBuilder("Comprehensive Analysis")
    .add_function(
        name="Load Product Data",
        function=lambda ctx: {"product_data": "AI-powered code assistant with real-time suggestions"}
    )
    .add_parallel(
        name="Parallel Analysis",
        branch_builders=[
            # Technical analysis branch
            lambda b: b.add_agent_task(
                name="Technical Analysis",
                agent=tech_analyst,
                task_description="Analyze the technical feasibility of: {product_data}",
                result_key="technical_analysis"
            ),
            # Market analysis branch
            lambda b: b.add_agent_task(
                name="Market Analysis",
                agent=market_analyst,
                task_description="Analyze the market potential of: {product_data}",
                result_key="market_analysis"
            ),
            # User analysis branch
            lambda b: b.add_agent_task(
                name="User Analysis",
                agent=user_analyst,
                task_description="Analyze the user experience aspects of: {product_data}",
                result_key="user_analysis"
            )
        ],
        merge_results=True
    )
    .add_agent_task(
        name="Comprehensive Report",
        agent=writer,
        task_description="Create a comprehensive report based on:\n\nTechnical: {technical_analysis}\n\nMarket: {market_analysis}\n\nUser: {user_analysis}",
        result_key="final_report"
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

#### Retry Mechanism

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create an agent
agent = create_agent(agent_type="llm", name="Research Agent", role_type="researcher")

# Create a workflow with retry logic
workflow = (WorkflowBuilder("Web Research with Retry")
    .add_function(
        name="Set Query",
        function=lambda ctx: {"query": "quantum computing applications"}
    )
    .add_retry(
        name="Web Search with Retry",
        node_builder=lambda b: b.add_agent_task(
            name="Web Search",
            agent=agent,
            task_description="Search the web for information about: {query}",
            result_key="search_results"
        ),
        max_attempts=3,
        delay=2.0
    )
    .add_agent_task(
        name="Summarize Results",
        agent=agent,
        task_description="Summarize these search results: {search_results}",
        result_key="summary"
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

### Workflow Management and Monitoring

```python
from enterprise_ai.flow import WorkflowManager, WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create a workflow
agent = create_agent(agent_type="llm", name="Assistant")
workflow = (WorkflowBuilder("Simple Process")
    .add_agent_task(
        name="Task 1",
        agent=agent,
        task_description="Perform initial analysis."
    )
    .add_agent_task(
        name="Task 2",
        agent=agent,
        task_description="Create summary report."
    )
    .build())

# Create a manager with persistent storage
manager = WorkflowManager(storage_dir="/tmp/workflow_data")

# Register the workflow
workflow_id = manager.register_workflow(workflow)

# Execute with initial context
import asyncio

async def run_workflow():
    # Execute and wait for completion
    status, result = await manager.execute_workflow(
        workflow_id,
        wait_for_completion=True,
        initial_context={"priority": "high"}
    )
    
    print(f"Execution status: {status.name}")
    print(f"Result: {result}")
    
    # Get execution history
    history = manager.get_workflow_execution_history(workflow_id)
    print(f"Execution count: {len(history)}")
    print(f"Last execution duration: {history[-1]['duration']:.2f} seconds")
    
    # Get all workflows
    all_workflows = manager.get_all_workflows()
    print(f"Total workflows: {len(all_workflows)}")

asyncio.run(run_workflow())
```

### Complex Real-World Example: Document Processing Pipeline

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent
from enterprise_ai.team import create_team

# Create specialized agents
document_processor = create_agent(agent_type="llm", name="Document Processor", role_type="analyst")
language_translator = create_agent(agent_type="llm", name="Translator", role_type="custom", 
                                  role_kwargs={"name": "Language Specialist"})
data_extractor = create_agent(agent_type="llm", name="Data Extractor", role_type="analyst")
summary_writer = create_agent(agent_type="llm", name="Summary Writer", role_type="writer")

# Create analysis team
analysis_team = create_team(team_type="collaborative", name="Analysis Team")
analysis_team.add_member(create_agent(agent_type="llm", name="Financial Analyst", role_type="analyst"))
analysis_team.add_member(create_agent(agent_type="llm", name="Business Analyst", role_type="analyst"))
analysis_team.add_member(create_agent(agent_type="llm", name="Risk Analyst", role_type="analyst"))

# Create a complex document processing workflow
workflow = (WorkflowBuilder("Document Processing Pipeline")
    # Initial document loading
    .add_function(
        name="Load Document",
        function=lambda ctx: {"document": "Sample quarterly financial report..."}
    )
    
    # Document preprocessing
    .add_agent_task(
        name="Document Cleanup",
        agent=document_processor,
        task_description="Clean and normalize this document: {document}",
        result_key="cleaned_document"
    )
    
    # Language detection and potential translation
    .add_condition(
        name="Check Language",
        condition=lambda ctx: detect_language(ctx["cleaned_document"]) != "english",
        then_builder=lambda b: b.add_agent_task(
            name="Translate Document",
            agent=language_translator,
            task_description="Translate this document to English: {cleaned_document}",
            result_key="translated_document"
        ),
        else_builder=lambda b: b.add_function(
            name="No Translation Needed",
            function=lambda ctx: {"translated_document": ctx["cleaned_document"]}
        )
    )
    
    # Extract structured data
    .add_agent_task(
        name="Extract Data",
        agent=data_extractor,
        task_description="Extract key financial metrics from this document: {translated_document}",
        result_key="extracted_data"
    )
    
    # Parallel analysis
    .add_parallel(
        name="Multi-faceted Analysis",
        branch_builders=[
            # Financial analysis
            lambda b: b.add_team_task(
                name="Financial Analysis",
                team=analysis_team,
                task_description="Perform financial analysis on this data: {extracted_data}",
                target_agent_id="Financial Analyst",
                result_key="financial_analysis"
            ),
            # Business impact analysis
            lambda b: b.add_team_task(
                name="Business Analysis",
                team=analysis_team,
                task_description="Assess business impact based on this data: {extracted_data}",
                target_agent_id="Business Analyst",
                result_key="business_analysis"
            ),
            # Risk assessment
            lambda b: b.add_team_task(
                name="Risk Assessment",
                team=analysis_team,
                task_description="Evaluate risks based on this data: {extracted_data}",
                target_agent_id="Risk Analyst",
                result_key="risk_assessment"
            )
        ],
        merge_results=True
    )
    
    # Create comprehensive report
    .add_agent_task(
        name="Generate Summary Report",
        agent=summary_writer,
        task_description="""Create a comprehensive executive summary based on the following analyses:
        
        Financial Analysis: {financial_analysis}
        
        Business Impact: {business_analysis}
        
        Risk Assessment: {risk_assessment}
        
        Include key metrics, trends, opportunities, and potential risks.
        """,
        result_key="executive_summary"
    )
    
    # Finalize and format document
    .add_function(
        name="Format Final Report",
        function=lambda ctx: {
            "final_report": {
                "title": "Quarterly Financial Analysis",
                "summary": ctx["executive_summary"],
                "data": ctx["extracted_data"],
                "analyses": {
                    "financial": ctx["financial_analysis"],
                    "business": ctx["business_analysis"],
                    "risk": ctx["risk_assessment"]
                },
                "timestamp": get_timestamp()
            }
        }
    )
    .build())

# Execute the workflow
import asyncio
result = asyncio.run(workflow.execute())
```

## Integration Points

The Flow module integrates with several other components of the Enterprise AI platform:

### 1. Agent Module

The Flow module uses agents to perform tasks within workflows:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create an agent
agent = create_agent(agent_type="llm", name="Developer", role_type="developer")

# Use the agent in a workflow
workflow = (WorkflowBuilder("Development Workflow")
    .add_agent_task(
        name="Code Generation",
        agent=agent,
        task_description="Generate Python code for a web scraper."
    )
    .build())
```

Key integration points:

- `AgentTaskNode` assigns tasks to agents
- Agents process tasks and return results
- Workflow context can be passed to agent tasks
- Agent state can be persisted between workflow steps

### 2. Team Module

The Flow module integrates with teams for collaborative tasks:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.team import create_team

# Create a team
team = create_team(team_type="collaborative", name="Research Team")

# Use the team in a workflow
workflow = (WorkflowBuilder("Research Project")
    .add_team_task(
        name="Market Research",
        team=team,
        task_description="Research market trends in AI."
    )
    .build())
```

Key integration points:

- `TeamTaskNode` assigns tasks to teams
- Teams coordinate their members to complete tasks
- Team coordinators track task progress
- Team tool sharing enables efficient collaboration

### 3. Tool System

Workflows can incorporate tool usage through agents and teams:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create an agent with tools
agent = create_agent(
    agent_type="llm",
    name="Researcher",
    role_type="researcher",
    use_tools=True,
    tool_categories=["research", "file"]
)

# Create a workflow that will use tools implicitly
workflow = (WorkflowBuilder("Research with Tools")
    .add_agent_task(
        name="Web Research",
        agent=agent,
        task_description="Research quantum computing and save the findings to a file."
    )
    .build())
```

Key integration points:

- Agents can use tools during workflow execution
- Team-based workflows can leverage shared tools
- Tool execution results become part of the workflow context
- Tool errors can trigger workflow retry mechanisms

### 4. Model Context Protocol (MCP)

Agents and teams in workflows can use MCP for dynamic tool discovery:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent

# Create an agent with MCP enabled
agent = create_agent(
    agent_type="llm",
    name="Assistant",
    role_type="researcher",
    use_tools=True,
    enable_mcp=True
)

# Create a workflow using MCP-enabled agent
workflow = (WorkflowBuilder("MCP-Enabled Workflow")
    .add_agent_task(
        name="Research Task",
        agent=agent,
        task_description="Find information about natural language processing."
    )
    .build())
```

Key integration points:

- MCP enables dynamic tool discovery during workflow execution
- Agents can leverage the full range of available tools
- Multiple agents in a workflow can share tools via MCP
- Tool execution is standardized across the workflow

### 5. Prompt Module

The Flow module indirectly integrates with the prompt system:

```python
from enterprise_ai.flow import WorkflowBuilder
from enterprise_ai.agent import create_agent
from enterprise_ai.prompt import format_prompt

# Create a custom prompt
task_prompt = format_prompt(
    "system.analytical",
    additional_instructions="Focus on quantitative analysis and data-driven insights."
)

# Create an agent with the custom prompt
agent = create_agent(
    agent_type="llm",
    name="Analyst",
    system_prompt=task_prompt
)

# Use the agent in a workflow
workflow = (WorkflowBuilder("Analysis Workflow")
    .add_agent_task(
        name="Data Analysis",
        agent=agent,
        task_description="Analyze the quarterly sales data."
    )
    .build())
```

Key integration points:

- Agents in workflows use prompts for task processing
- Custom prompts can specialize agent behavior in workflows
- Prompt templates can be used to create consistent task descriptions
- Workflow context can be integrated into prompt variables

## Best Practices

### 1. Workflow Design

Effective workflow design is critical for complex AI systems:

```python
# GOOD: Modular workflow with clear steps
workflow = (WorkflowBuilder("Well-Structured Process")
    .add_function(name="Data Loading", function=load_data)
    .add_agent_task(name="Data Preprocessing", agent=preprocessor, task_description="...")
    .add_agent_task(name="Data Analysis", agent=analyst, task_description="...")
    .add_agent_task(name="Report Generation", agent=reporter, task_description="...")
    .build())

# BAD: Monolithic workflow with unclear responsibilities
workflow = (WorkflowBuilder("Poorly-Structured Process")
    .add_agent_task(
        name="Do Everything",
        agent=generic_agent,
        task_description="Load data, preprocess it, analyze it, and create a report."
    )
    .build())
```

Guidelines:

- Break workflows into focused, single-responsibility nodes
- Use descriptive names for workflows and nodes
- Specify clear dependencies between nodes
- Design for reusability of workflow components
- Consider error handling and retry strategies
- Document expected inputs and outputs for each node

### 2. Context Management

Effective management of workflow context is essential:

```python
# GOOD: Explicit context management with clear keys
workflow = (WorkflowBuilder("Context Example")
    .add_function(
        name="Initialize Context",
        function=lambda ctx: {"input_file": "data.csv", "analysis_type": "financial"}
    )
    .add_agent_task(
        name="Process Data",
        agent=processor,
        task_description="Process {input_file} using {analysis_type} analysis.",
        result_key="processed_data"
    )
    .add_agent_task(
        name="Analyze Results",
        agent=analyst,
        task_description="Analyze this data: {processed_data}",
        result_key="analysis_results"
    )
    .build())

# BAD: Overwriting context keys and unclear references
workflow = (WorkflowBuilder("Poor Context Example")
    .add_function(
        name="Step 1",
        function=lambda ctx: {"data": "initial data"}
    )
    .add_function(
        name="Step 2",
        function=lambda ctx: {"data": process(ctx["data"])}  # Overwrites previous "data"
    )
    .add_function(
        name="Step 3",
        function=lambda ctx: {"result": analyze(ctx["data"])}  # Which "data"?
    )
    .build())
```

Guidelines:

- Use descriptive, unique keys for context values
- Use `result_key` to explicitly name outputs
- Preserve intermediate results when needed
- Be mindful of context size for complex workflows
- Use template substitution in task descriptions
- Consider namespace patterns for complex workflows

### 3. Error Handling

Implement robust error handling in workflows:

```python
# Using retry for unreliable operations
workflow = (WorkflowBuilder("Robust Workflow")
    .add_retry(
        name="Web Search With Retry",
        node_builder=lambda b: b.add_agent_task(
            name="Web Search",
            agent=researcher,
            task_description="Search for information about renewable energy."
        ),
        max_attempts=3,
        delay=2.0
    )
    .build())

# Using conditionals for error handling
workflow = (WorkflowBuilder("Error Handling")
    .add_function(
        name="Process Data",
        function=lambda ctx: {"result": process_data(), "error": None}
    )
    .add_condition(
        name="Check For Errors",
        condition=lambda ctx: ctx["error"] is None,
        then_builder=lambda b: b.add_agent_task(
            name="Continue Processing",
            agent=processor,
            task_description="Continue with the processed data: {result}"
        ),
        else_builder=lambda b: b.add_agent_task(
            name="Handle Error",
            agent=error_handler,
            task_description="Handle this error: {error}"
        )
    )
    .build())
```

Guidelines:

- Use `RetryNode` for operations that may fail transiently
- Implement appropriate timeout values for agent and team tasks
- Include error checking in workflow conditional branches
- Store error information in the workflow context
- Consider fallback strategies for critical operations
- Implement logging throughout the workflow

### 4. Performance Optimization

Optimize workflows for performance:

```python
# Using parallel execution for independent tasks
workflow = (WorkflowBuilder("Optimized Workflow")
    .add_function(
        name="Load Data",
        function=lambda ctx: {"data": load_data()}
    )
    .add_parallel(
        name="Parallel Analysis",
        branch_builders=[
            lambda b: b.add_agent_task(
                name="Technical Analysis",
                agent=tech_analyst,
                task_description="Analyze technical aspects of {data}"
            ),
            lambda b: b.add_agent_task(
                name="Financial Analysis",
                agent=financial_analyst,
                task_description="Analyze financial aspects of {data}"
            ),
            lambda b: b.add_agent_task(
                name="Market Analysis",
                agent=market_analyst,
                task_description="Analyze market aspects of {data}"
            )
        ],
        merge_results=True
    )
    .build())
```

Guidelines:

- Use `ParallelNode` for independent operations
- Set appropriate concurrency limits in the executor
- Be mindful of resource usage in parallel branches
- Consider task granularity for optimal performance
- Reuse agents and teams when appropriate
- Implement caching for expensive operations

### 5. Workflow Management

Effectively manage workflow execution:

```python
# Using the workflow manager for monitoring and persistence
from enterprise_ai.flow import WorkflowManager

# Create a manager with persistence
manager = WorkflowManager(storage_dir="/path/to/storage")

# Register workflows
workflow_id1 = manager.register_workflow(workflow1)
workflow_id2 = manager.register_workflow(workflow2)

# Execute with monitoring
import asyncio

async def run_workflows():
    # Start a workflow without waiting
    await manager.execute_workflow(
        workflow_id1,
        wait_for_completion=False,
        initial_context={"priority": "high"}
    )
    
    # Monitor status
    status = manager.get_workflow_status(workflow_id1)
    print(f"Workflow status: {status.name}")
    
    # Control execution if needed
    if some_condition:
        manager.pause_workflow(workflow_id1)
        # Later...
        manager.resume_workflow(workflow_id1)
    
    # Execute another workflow and wait for completion
    status, result = await manager.execute_workflow(workflow_id2)
    
    # Get execution history
    history = manager.get_workflow_execution_history(workflow_id1)
    print(f"Execution count: {len(history)}")

asyncio.run(run_workflows())
```

Guidelines:

- Use `WorkflowManager` for complex or long-running workflows
- Enable persistence for important workflows
- Implement appropriate monitoring and logging
- Use execution history for debugging and auditing
- Set appropriate timeouts for workflow nodes
- Implement cancellation policies for workflows

### 6. Integration Best Practices

Optimize integration with other Enterprise AI components:

```python
# Using specialized agents with appropriate reasoning frameworks
workflow = (WorkflowBuilder("Integrated Workflow")
    .add_agent_task(
        name="Research Task",
        agent=create_agent(
            agent_type="llm",
            name="Researcher",
            role_type="researcher",
            reasoning_framework="react",  # Good for research with tools
            use_tools=True,
            tool_categories=["research"]
        ),
        task_description="Research quantum computing advances."
    )
    .add_agent_task(
        name="Development Task",
        agent=create_agent(
            agent_type="llm",
            name="Developer",
            role_type="developer",
            reasoning_framework="swe",  # Good for development tasks
            use_tools=True,
            tool_categories=["development", "execution"]
        ),
        task_description="Implement a quantum algorithm simulator based on the research."
    )
    .build())
```

Guidelines:

- Match agent reasoning frameworks to task requirements
- Configure appropriate tool categories for each task
- Use teams for inherently collaborative tasks
- Enable MCP for dynamic tool discovery
- Preserve agent state between related tasks
- Consider using factory methods for standard patterns

### 7. Workflow Testing and Debugging

Develop strategies for testing and debugging workflows:

```python
# Mock function for testing
def mock_agent_task(context):
    print(f"Executing mock agent task with context: {context}")
    return {"result": "Mock result"}

# Create a test workflow
test_workflow = (WorkflowBuilder("Test Workflow")
    .add_function(
        name="Initialize",
        function=lambda ctx: {"test_data": "sample data"}
    )
    .add_function(
        name="Mock Agent Task",
        function=mock_agent_task
    )
    .build())

# Execute and check results
import asyncio

async def test_workflow_execution():
    result = await test_workflow.execute()
    assert "result" in result, "Expected 'result' key in output"
    assert result["result"] == "Mock result", "Unexpected result value"
    print("Test passed!")

asyncio.run(test_workflow_execution())
```

Guidelines:

- Use function nodes with mock implementations for testing
- Add logging at key points in the workflow
- Test workflows in isolation before integration
- Create small test workflows for specific components
- Review execution history for debugging complex workflows
- Implement proper error handling and validation
- Use conditionals to implement debugging branches
