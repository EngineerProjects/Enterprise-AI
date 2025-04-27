# Creating Custom Agents and Teams with Enterprise AI

This guide demonstrates how to create custom agents with specialized system prompts and organize them into effective teams using the Enterprise AI platform.

## Overview

One of the most powerful capabilities of the Enterprise AI platform is the ability to create specialized agents through custom prompts and then organize these agents into teams that can tackle complex problems collaboratively.

This guide will cover:

1. Creating custom system prompts
1. Building agents with specialized capabilities
1. Organizing agents into effective teams
1. Testing and refining your team composition

## Creating Custom System Prompts

### Basic Structure of a Custom Prompt

Custom prompts typically consist of several key components:

1. **Identity & Role Definition**: Defines who the agent is and its primary role
1. **Capabilities & Limitations**: Specifies what the agent can and cannot do
1. **Behavioral Guidelines**: Instructs the agent on how to approach tasks
1. **Specialized Knowledge**: Provides domain-specific instructions
1. **Reasoning Framework**: Defines how the agent should think through problems

### Creating a Custom Analytical Agent Prompt

Let's create a custom prompt for an analytical agent specialized in data analysis:

```python
from enterprise_ai.prompt import get_prompt_library

# Get the prompt library
library = get_prompt_library()

# Create a custom analytical agent prompt
data_analyst_prompt = """You are a specialized Data Analysis Agent with expertise in interpreting complex datasets.

Your primary responsibilities include:
- Analyzing numerical and categorical data
- Identifying patterns, trends, and anomalies
- Providing statistical insights and data-driven recommendations
- Generating clear explanations of analytical findings

When approaching data analysis tasks:
1. First understand the dataset structure and variables
2. Consider what methods would be most appropriate for the data type
3. Apply rigorous statistical thinking
4. Present findings with clarity and precision
5. Acknowledge limitations and potential biases in your analysis

$additional_guidelines

Use tools such as data visualization, statistical testing, and regression analysis when appropriate.
"""

# Register the custom prompt
library.add_prompt(
    prompt_id="custom.data_analyst",
    template=data_analyst_prompt,
    metadata={"category": "custom", "type": "role", "version": "1.0"}
)
```

### Creating a Custom Creative Agent Prompt

Now let's create a prompt for a creative agent specialized in content generation:

```python
# Create a custom creative agent prompt
content_creator_prompt = """You are a specialized Content Creation Agent with expertise in generating engaging written content.

Your primary responsibilities include:
- Creating original and creative written content
- Adapting tone and style to different audiences and purposes
- Generating compelling narratives and descriptions
- Producing clear and well-structured text

When approaching content creation tasks:
1. First understand the target audience and purpose
2. Consider the appropriate tone, style, and format
3. Generate original and engaging content
4. Review and refine your output for clarity and impact
5. Ensure content is well-organized and coherent

$additional_guidelines

You excel at creating various content types including blog posts, articles, marketing copy, and creative stories.
"""

# Register the custom prompt
library.add_prompt(
    prompt_id="custom.content_creator",
    template=content_creator_prompt,
    metadata={"category": "custom", "type": "role", "version": "1.0"}
)
```

### Combining with Reasoning Frameworks

For more sophisticated agents, we can combine our custom role prompts with existing reasoning frameworks:

```python
from enterprise_ai.prompt import combine_prompts, format_prompt

# Create an analytical agent with Chain of Thought reasoning
analytical_cot_prompt = combine_prompts(
    ["system.cot", "custom.data_analyst"],
    additional_guidelines="When analyzing data, explicitly break down your thinking step by step.",
    additional_cot_instructions="Show your statistical reasoning and calculations explicitly."
)

# Create a creative agent with ReAct reasoning for tool use
creative_react_prompt = combine_prompts(
    ["system.react", "custom.content_creator"],
    additional_guidelines="Use research tools to gather information before creating content.",
    tools_description="You have access to web search and document analysis tools."
)
```

## Building Specialized Agents

Now that we have our custom prompts, let's create specialized agents:

### Creating a Data Analyst Agent

```python
from enterprise_ai.agent import create_agent
from enterprise_ai.prompt import format_prompt

# Format our custom data analyst prompt
data_analyst_system_prompt = format_prompt(
    "custom.data_analyst",
    additional_guidelines="Focus on identifying actionable insights from business data."
)

# Create the data analyst agent
data_analyst = create_agent(
    agent_type="llm",
    name="Data Analyst",
    agent_id="analyst-1",
    llm_provider_name="anthropic",  # Using Claude for analytical capabilities
    reasoning_framework="cot",      # Chain of Thought for detailed analysis
    use_tools=True,
    tool_categories=["file", "content", "browser"],
    system_prompt=data_analyst_system_prompt
)

# Add specific analytical tools
data_analyst.add_tool(data_visualization_tool)
data_analyst.add_tool(statistical_analysis_tool)
```

### Creating a Content Creator Agent

```python
# Format our custom content creator prompt with tool integration
content_creator_system_prompt = format_prompt(
    "custom.content_creator",
    additional_guidelines="Research topics thoroughly before creating content."
)

# Create the content creator agent
content_creator = create_agent(
    agent_type="llm",
    name="Content Creator",
    agent_id="creator-1",
    llm_provider_name="anthropic",
    reasoning_framework="react",    # ReAct for research and action steps
    use_tools=True,
    tool_categories=["browser", "content"],
    system_prompt=content_creator_system_prompt
)

# Add specific content creation tools
content_creator.add_tool(web_search_tool)
content_creator.add_tool(content_editor_tool)
```

### Creating a Technical Lead Agent

Let's create a specialized technical lead agent with a custom prompt:

```python
# Create a custom tech lead prompt
tech_lead_prompt = """You are a Technical Lead Agent responsible for coordinating technical projects and team members.

Your primary responsibilities include:
- Providing technical direction and oversight
- Breaking down complex problems into manageable tasks
- Reviewing and integrating work from other team members
- Making architectural and technology decisions

When working with your team:
1. Understand the overall project goals and constraints
2. Delegate tasks based on team members' strengths
3. Provide clear technical guidance and feedback
4. Integrate different components into a cohesive solution
5. Ensure technical quality and consistency

$additional_guidelines

You have expertise in software development, system design, and technical project management.
"""

# Register and format the prompt
library.add_prompt(
    prompt_id="custom.tech_lead",
    template=tech_lead_prompt,
    metadata={"category": "custom", "type": "role", "version": "1.0"}
)

tech_lead_system_prompt = format_prompt(
    "custom.tech_lead",
    additional_guidelines="Focus on creating clear integration plans for team deliverables."
)

# Create the tech lead agent
tech_lead = create_agent(
    agent_type="llm",
    name="Technical Lead",
    agent_id="tech-lead-1",
    llm_provider_name="anthropic",
    reasoning_framework="mcp",      # MCP for sophisticated tool use
    use_tools=True,
    tool_categories=["development", "planning"],
    system_prompt=tech_lead_system_prompt
)
```

## Organizing Agents into Teams

Now that we have our specialized agents, let's organize them into an effective team:

### Creating a Hierarchical Project Team

```python
from enterprise_ai.team import HierarchicalTeam

# Create a hierarchical team with the tech lead as manager
project_team = HierarchicalTeam(
    team_id="project-team-1",
    name="Content Marketing Team"
)

# Set the tech lead as the team manager
project_team.manager = tech_lead

# Add specialized members
project_team.add_member(data_analyst, role="analyst")
project_team.add_member(content_creator, role="creator")

# Configure tool sharing policy
from enterprise_ai.team.tool_sharing import HierarchicalToolSharingPolicy

# Create a policy where the tech lead can access all tools
# but specialized agents retain control over their domain-specific tools
sharing_policy = HierarchicalToolSharingPolicy(
    manager_ids={tech_lead.id},
    allow_lateral_sharing=True
)

# Apply the policy to the team
project_team.set_tool_sharing_policy(sharing_policy)
```

### Creating a Collaborative Team with Tool Pools

For more flexible collaboration, we can use a collaborative team structure:

```python
from enterprise_ai.team import CollaborativeTeam

# Create a collaborative team
collab_team = CollaborativeTeam(
    team_id="collab-team-1",
    name="Content Strategy Team"
)

# Set the tech lead as the team manager
collab_team.manager = tech_lead

# Add specialized members
collab_team.add_member(data_analyst, role="analyst")
collab_team.add_member(content_creator, role="creator")

# Create specialized tool pools
collab_team.create_tool_pool("analysis_tools", ["DataVisualization", "StatisticalAnalysis"])
collab_team.create_tool_pool("content_tools", ["WebSearch", "ContentEditor"])
collab_team.create_tool_pool("common_tools", ["Browser", "FileReader"])

# Grant tool pool access
collab_team.grant_pool_access("analysis_tools", data_analyst.id)
collab_team.grant_pool_access("content_tools", content_creator.id)
collab_team.grant_pool_access("common_tools", data_analyst.id)
collab_team.grant_pool_access("common_tools", content_creator.id)

# The tech lead gets access to all pools
collab_team.grant_pool_access("analysis_tools", tech_lead.id)
collab_team.grant_pool_access("content_tools", tech_lead.id)
collab_team.grant_pool_access("common_tools", tech_lead.id)
```

## Coordinating Team Activities

Now let's coordinate tasks across our team:

### Setting up a Team Coordinator

```python
from enterprise_ai.team.coordinator import TeamCoordinator

# Create a coordinator for the team
coordinator = TeamCoordinator(collab_team)

# Create sequential task workflow
data_analysis_task = Task(
    id="task-1",
    description="Analyze website traffic data and identify content engagement patterns",
    metadata={"required_tools": ["DataVisualization", "StatisticalAnalysis"]}
)

content_creation_task = Task(
    id="task-2",
    description="Create content strategy based on traffic analysis findings",
    metadata={"required_tools": ["WebSearch", "ContentEditor"]}
)

integration_task = Task(
    id="task-3",
    description="Review and finalize the content strategy with supporting data",
    metadata={"required_capability": "technical_leadership"}
)

# Submit tasks with dependencies
coordinator.submit_task(data_analysis_task)
coordinator.submit_task(content_creation_task, dependencies=[data_analysis_task.id])
coordinator.submit_task(integration_task, dependencies=[content_creation_task.id])

# Process tasks
processed_count = coordinator.process_tasks(max_tasks=3)
print(f"Processed {processed_count} tasks")
```

### Team Communication

We can also implement direct team communication:

```python
from enterprise_ai.agent.message import create_message

# Create a query from the tech lead to the data analyst
query_message = create_message(
    "QUERY",
    sender_id=tech_lead.id,
    receiver_id=collab_team.id,  # Send to the team
    content="What are the key insights from the traffic analysis?",
    metadata={"target_agent": data_analyst.id}  # Target a specific member
)

# Process the message through the team
response = collab_team.process_message(query_message)
print(f"Response: {response.content}")

# Broadcast an update to all team members
broadcast_responses = collab_team.broadcast_message(
    "NOTIFICATION",
    "Project deadline has been extended by one week.",
    tech_lead.id
)
```

## Advanced Team Configurations

For more complex projects, you can create specialized team configurations:

### Multi-level Team Hierarchy

```python
from enterprise_ai.team import HierarchicalTeam
from enterprise_ai.team.factory import get_team_factory

# Get team factory
factory = get_team_factory()

# Create department teams
analytics_team = factory.create_analytics_team(
    name="Analytics Department",
    tool_enabled=True
)

content_team = factory.create_custom_team(
    member_roles=[
        ("Content Writer", ["content_writing", "editing"]),
        ("Content Strategist", ["content_strategy", "audience_analysis"]),
    ],
    team_type="collaborative",
    name="Content Department"
)

# Create a parent company team
company_team = HierarchicalTeam(
    team_id="company-1",
    name="Digital Agency"
)

# Create a CEO agent with a custom prompt
ceo_prompt = format_prompt(
    "roles.manager",
    additional_context="You are the CEO of a digital agency, responsible for high-level direction and oversight."
)

ceo = create_agent(
    agent_type="llm",
    name="CEO",
    system_prompt=ceo_prompt
)

company_team.manager = ceo

# Add department teams as subteams
company_team.add_subteam(analytics_team)
company_team.add_subteam(content_team)

# Task can now be assigned through the hierarchy
task = Task(
    id="company-task-1",
    description="Develop comprehensive digital marketing strategy"
)

# This will intelligently route to the appropriate subteam or agent
company_team.assign_task(task)
```

## Best Practices for Custom Agents and Teams

### Prompt Design

1. **Align prompts with specialized roles**:

   - Design prompts to reflect specific expertise and responsibilities
   - Include domain-specific instructions and terminology
   - Define clear boundaries between different specialized roles

1. **Ensure prompt compatibility**:

   - For team members that will work together, ensure their prompts are compatible
   - Avoid conflicting instructions or overlapping responsibilities
   - Create complementary capabilities between team members

1. **Balance specialization and flexibility**:

   - Make prompts specialized enough for expert-level performance
   - Keep enough flexibility for adapting to varied tasks
   - Include guidelines for collaboration and knowledge sharing

### Team Composition

1. **Design teams around workflow patterns**:

   - Analyze the typical workflow for your use case
   - Create roles that align with major workflow stages
   - Ensure smooth handoffs between specialists

1. **Create complementary capabilities**:

   - Avoid redundant specializations unless workload requires it
   - Ensure capabilities cover all required aspects of tasks
   - Consider team balance between analytical, creative, and managerial roles

1. **Establish clear leadership**:

   - For hierarchical teams, the manager prompt should emphasize coordination
   - For collaborative teams, include collaboration instructions in all prompts
   - Ensure leadership roles have sufficient context on all specialties

### Collaboration Patterns

1. **Define communication protocols in prompts**:

   - Include guidelines on how agents should communicate with each other
   - Specify what information should be shared between agents
   - Define expectations for updates and progress reports

1. **Implement cross-agent verification**:

   - Have specialized agents review each other's outputs
   - Create feedback loops for quality improvement
   - Use the team structure to implement checks and balances

1. **Balance autonomy and coordination**:

   - Allow specialized agents to work independently in their domain
   - Implement coordination points for integration
   - Minimize unnecessary communication overhead

## Example: Complete Data-Driven Content Marketing Team

Here's a complete example of creating a specialized team for data-driven content marketing:

```python
from enterprise_ai.prompt import get_prompt_library, format_prompt
from enterprise_ai.agent import create_agent
from enterprise_ai.team import CollaborativeTeam
from enterprise_ai.team.coordinator import TeamCoordinator
from enterprise_ai.agent.types import Task

# Create custom prompts
library = get_prompt_library()

# Data Analyst prompt
data_analyst_prompt = """You are a Data Analyst specialized in content performance metrics.

Your primary responsibilities include:
- Analyzing content engagement and conversion data
- Identifying audience behavior patterns
- Generating actionable insights for content strategy
- Creating data visualizations to communicate findings

When analyzing content performance:
1. First examine overall traffic and engagement metrics
2. Segment data by audience demographics, channels, and content types
3. Identify correlations between content characteristics and performance
4. Formulate specific, actionable recommendations based on data

$additional_guidelines

You have expertise in web analytics, A/B testing, and audience segmentation.
"""

# Content Strategist prompt
content_strategist_prompt = """You are a Content Strategist specialized in data-driven content planning.

Your primary responsibilities include:
- Developing content strategies based on performance data
- Planning content calendars and themes
- Defining target audiences and content goals
- Creating content briefs and guidelines

When developing content strategies:
1. First analyze the target audience and business objectives
2. Review performance data to identify successful content patterns
3. Develop clear content themes and topics aligned with data insights
4. Create structured content plans with measurable goals

$additional_guidelines

You have expertise in content marketing, SEO, and audience engagement.
"""

# Content Creator prompt
content_creator_prompt = """You are a Content Creator specialized in engaging, high-performance content.

Your primary responsibilities include:
- Writing engaging content based on strategic briefs
- Optimizing content for specific channels and formats
- Incorporating SEO and engagement best practices
- Adapting tone and style to different audiences

When creating content:
1. First understand the strategic brief and audience needs
2. Research the topic thoroughly using available tools
3. Create compelling headlines, hooks, and structures
4. Incorporate data-driven insights into the narrative

$additional_guidelines

You have expertise in copywriting, storytelling, and audience engagement.
"""

# Marketing Manager prompt
marketing_manager_prompt = """You are a Marketing Manager responsible for overseeing content marketing initiatives.

Your primary responsibilities include:
- Coordinating content team activities and workflow
- Aligning content strategy with overall marketing goals
- Reviewing and approving content deliverables
- Making strategic decisions based on performance data

When managing content projects:
1. First ensure clear objectives and success metrics
2. Delegate specialized tasks to the appropriate team members
3. Monitor progress and provide constructive feedback
4. Integrate deliverables into cohesive marketing campaigns

$additional_guidelines

You have expertise in marketing strategy, team leadership, and project management.
"""

# Register the custom prompts
for prompt_id, prompt_template in [
    ("custom.data_analyst", data_analyst_prompt),
    ("custom.content_strategist", content_strategist_prompt),
    ("custom.content_creator", content_creator_prompt),
    ("custom.marketing_manager", marketing_manager_prompt)
]:
    library.add_prompt(
        prompt_id=prompt_id,
        template=prompt_template,
        metadata={"category": "custom", "type": "role", "version": "1.0"}
    )

# Create the specialized agents
data_analyst = create_agent(
    agent_type="llm",
    name="Data Analyst",
    agent_id="analyst-1",
    system_prompt=format_prompt("custom.data_analyst",
                               additional_guidelines="Focus on actionable content performance insights."),
    reasoning_framework="cot",
    use_tools=True,
    tool_categories=["content", "file"]
)

content_strategist = create_agent(
    agent_type="llm",
    name="Content Strategist",
    agent_id="strategist-1",
    system_prompt=format_prompt("custom.content_strategist",
                               additional_guidelines="Base all strategy recommendations on performance data."),
    reasoning_framework="cot",
    use_tools=True,
    tool_categories=["browser", "content"]
)

content_creator = create_agent(
    agent_type="llm",
    name="Content Creator",
    agent_id="creator-1",
    system_prompt=format_prompt("custom.content_creator",
                               additional_guidelines="Create content that follows the strategy and incorporates data insights."),
    reasoning_framework="react",
    use_tools=True,
    tool_categories=["browser", "content"]
)

marketing_manager = create_agent(
    agent_type="llm",
    name="Marketing Manager",
    agent_id="manager-1",
    system_prompt=format_prompt("custom.marketing_manager",
                               additional_guidelines="Ensure all content aligns with overall marketing objectives."),
    reasoning_framework="mcp",
    use_tools=True,
    tool_categories=["planning", "content"]
)

# Create a collaborative team
content_team = CollaborativeTeam(
    team_id="content-team-1",
    name="Data-Driven Content Team"
)

# Set manager and add members
content_team.manager = marketing_manager
content_team.add_member(data_analyst, role="analyst")
content_team.add_member(content_strategist, role="strategist")
content_team.add_member(content_creator, role="creator")

# Create tool pools
content_team.create_tool_pool("analysis_tools", ["WebAnalytics", "DataVisualization"])
content_team.create_tool_pool("strategy_tools", ["AudienceAnalysis", "ContentPlanner"])
content_team.create_tool_pool("creation_tools", ["ContentEditor", "SEOOptimizer"])
content_team.create_tool_pool("common_tools", ["WebSearch", "FileBrowser"])

# Grant appropriate access
content_team.grant_pool_access("analysis_tools", data_analyst.id)
content_team.grant_pool_access("strategy_tools", content_strategist.id)
content_team.grant_pool_access("creation_tools", content_creator.id)
content_team.grant_pool_access("common_tools", data_analyst.id)
content_team.grant_pool_access("common_tools", content_strategist.id)
content_team.grant_pool_access("common_tools", content_creator.id)

# Manager gets access to all pools
for pool_name in ["analysis_tools", "strategy_tools", "creation_tools", "common_tools"]:
    content_team.grant_pool_access(pool_name, marketing_manager.id)

# Create a coordinator
coordinator = TeamCoordinator(content_team)

# Define a content marketing workflow
analysis_task = Task(
    id="task-1",
    description="Analyze blog performance data from the last quarter and identify top-performing content types",
    metadata={"required_tools": ["WebAnalytics", "DataVisualization"]}
)

strategy_task = Task(
    id="task-2",
    description="Develop Q3 content strategy based on performance analysis",
    metadata={"required_tools": ["AudienceAnalysis", "ContentPlanner"]}
)

creation_task = Task(
    id="task-3",
    description="Create three blog posts following the new content strategy",
    metadata={"required_tools": ["ContentEditor", "SEOOptimizer"]}
)

review_task = Task(
    id="task-4",
    description="Review and approve the content package for publication",
    metadata={"required_capability": "marketing_management"}
)

# Submit tasks with dependencies
coordinator.submit_task(analysis_task)
coordinator.submit_task(strategy_task, dependencies=[analysis_task.id])
coordinator.submit_task(creation_task, dependencies=[strategy_task.id])
coordinator.submit_task(review_task, dependencies=[creation_task.id])

# Process tasks
coordinator.process_tasks(max_tasks=4)

# Collect results
for task_id in ["task-1", "task-2", "task-3", "task-4"]:
    result = coordinator.collect_result(task_id)
    if result:
        print(f"Task {task_id} completed by {result.agent_id}")
        print(f"Result: {result.data.get('response', 'No response')[:100]}...")
    else:
        print(f"Task {task_id} not completed yet")
```

## Conclusion

By combining custom system prompts with the team coordination capabilities of Enterprise AI, you can create powerful specialized agent teams that work together effectively. The key elements for success include:

1. **Well-designed prompts** that define specialized roles and expertise
1. **Complementary agent capabilities** that cover all required tasks
1. **Appropriate team structures** based on your workflow patterns
1. **Effective tool sharing policies** that enable collaboration
1. **Clear task coordination** to manage complex workflows

This approach allows you to build AI teams with the specific expertise required for your domain, creating a system that can tackle complex tasks through the coordinated efforts of specialized agents.
