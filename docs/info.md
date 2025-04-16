```
constants.py
    ↑
exceptions.py
    ↑
types.py ← schema.py ← config/models.py
    ↑           ↑          ↑
config/loaders.py    config/__init__.py
        ↑                  ↑
    logger/          feature modules
```

______________________________________________________________________

# Prompt 1: Agent Development

```
I'm developing Enterprise AI - a multi-agent AI platform that enables users to create autonomous teams of specialized AI agents. I need help implementing the core agent framework that will serve as the foundation of the system.

## Project Vision
Enterprise AI organizes multiple AI agents into structured teams with distinct roles, responsibilities, and capabilities, functioning similar to a human organization. Agents should be able to collaborate, specialize in different domains, and execute complex tasks together.

## Current Development Stage
I'm starting with the agent/ module implementation. I want to build this incrementally, focusing first on agent fundamentals before integrating tools. The tools will be implemented separately.

## Core Agent Requirements
1. **Agent Base Class** - A foundational class for all agent types
2. **Agent State Management** - Handling memory, context, and current task state
3. **Agent Communication** - Mechanisms for agents to exchange messages
4. **Role Definition** - Ways to define agent specializations and capabilities
5. **Task Processing** - Methods for agents to process assigned tasks
6. **Agent Factory** - Patterns for creating different types of agents

## Specific Help Needed
1. Design the core agent classes and interfaces
2. Implement the basic agent functionality focusing on communication and state
3. Create patterns for role specialization without depending on tools yet
4. Support different agent personalities and instruction sets
5. Make the design extensible for later tool integration

Please help me implement this agent system to support my vision of collaborative AI teams. I'd like the code to be well-structured, modular, and ready for integration with the team system I'll build next.
```

# Prompt 2: Team Development

```
I'm developing Enterprise AI - a multi-agent platform that enables autonomous teams of specialized AI agents. Having implemented the core agent framework, I now need help building the team coordination system.

## Project Vision
Enterprise AI organizes multiple AI agents into structured teams with distinct roles, responsibilities, and capabilities, functioning similar to a human organization. I want users to be able to create custom teams, assign roles, and have agents collaborate effectively.

## Core Team Requirements
1. **Hierarchical Team Structure** - Support for manager-worker relationships
2. **Role Registry** - System for defining and assigning specialized roles
3. **Team Coordination** - Mechanisms for distributing tasks and sharing knowledge
4. **Team Templates** - Predefined team structures for common scenarios
5. **Dynamic Team Assembly** - Ability to create and modify teams at runtime
6. **Cross-Team Communication** - Support for interactions between different teams

## Specific Help Needed
1. Design the team management classes and interfaces
2. Implement hierarchical team structures with managers and specialists
3. Create flexible role assignment mechanisms
4. Build communication channels between team members
5. Design patterns for task delegation and result aggregation

Please help me implement this team system that will work with my existing agent framework. The design should allow users to create diverse team structures with specialized agents for different domains of expertise (development, research, analysis, etc.).
```

# Note on Flow and Tools Integration

Yes, ideally you would have at least the basic tool structure in place before implementing the workflow system. The flow/ module will need to coordinate task execution which typically involves tool usage.

I recommend this development sequence:

1. First, complete your agent/ module (basic agent capabilities)
1. Then, implement your team/ module (agent coordination)
1. Next, ensure your tool/core components are ready (tool interfaces)
1. Finally, develop the flow/ module (workflow orchestration)

This sequence lets you focus on one system at a time while building toward your complete platform. The flow system will tie everything together, orchestrating how teams of agents use tools to complete complex multi-step processes.

Each module builds on the previous one, so this incremental approach will make development more manageable while still progressing toward your vision of a comprehensive multi-agent collaboration platform.
