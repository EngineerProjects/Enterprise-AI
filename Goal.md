# Enterprise AI — Goal

## What We're Building

Enterprise AI is a Python SDK that lets developers build **autonomous agent teams** that collaborate like real human organizations. Instead of a single agent trying to do everything, you define a team — a Manager, a Developer, a Researcher — and they coordinate, delegate, share memory, and deliver results together.

The core idea is simple: **the agent is the unit of work, the team is the unit of intelligence.**

## Why It Exists

Current options for developers who want to integrate autonomous agents into their code are either too high-level (LangChain, CrewAI — heavy abstractions, unstable APIs, framework lock-in) or too low-level (raw provider SDKs — you rebuild the execution loop, permissions, and tool orchestration yourself every time).

Enterprise AI fills the gap: a **complete agentic runtime as a Python library**, composable and dependency-minimal, that you import and build on.

## The Quality Bar

A single Enterprise AI agent must perform at the level of a complete mono-run from a production agentic runtime: multi-turn loop, parallel tool orchestration, a full 12-step per-tool pipeline (validate → permissions → safety → call → format), streaming events, sandboxed execution, and automatic context compaction.

That is the benchmark. Not "a smart chatbot that can call functions" — a **true autonomous execution unit**.

## The Differentiator

Any agent framework can run a single agent. The real value of Enterprise AI is **teams**:

```
Mission: "Implement OAuth2 authentication"

Alice (Manager)    → reads the mission → decomposes tasks → delegates
Bob   (Developer)  → claims the implementation task → writes code → uses tools
Carol (Researcher) → documents best practices → feeds context to Bob
Dave  (QA)         → reviews the output → sends feedback back to Bob
```

Each team member is a **full autonomous agent** with their own tools, sandbox, and memory. Coordination happens through shared primitives (task board, mailbox) — emergent, not top-down orchestration.

## Core Capabilities

- **Agent Hierarchy System** — Manager agents that coordinate specialized workers
- **Role-Based Specialization** — Agents with domain expertise (Developer, Researcher, Planner, QA)
- **Parallel Tool Orchestration** — Independent tool calls run concurrently; context-modifying calls run sequentially
- **Permission Pipeline** — Every tool call passes through safety checks and configurable permission rules
- **Sandboxed Execution** — Docker or local isolated environments for bash and code execution
- **Multi-Provider** — Anthropic, OpenAI, OpenRouter, Ollama via a unified interface
- **Streaming** — Full SSE-style event streaming for real-time output

## The Bigger Picture

Enterprise AI is the open-source Python expression of the agentic vision behind Nexus AI. Where Nexus is a commercial Go runtime and desktop product, Enterprise AI is the SDK that the developer community can use, extend, and contribute to.

The goal is a **living open-source project** — a place where ideas around autonomous multi-agent systems are explored publicly, and where the best ideas eventually feed back into production.
