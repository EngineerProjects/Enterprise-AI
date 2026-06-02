# Enterprise AI — Vision

**Last updated: June 2026** · Canonical document. In case of conflict with any other document, **this one takes precedence**.

> **In one sentence:** Enterprise AI is an **open-source Python SDK** that turns an LLM into a fully autonomous agent — capable of planning, executing tools, and delivering results — and scales that up to **agent teams that collaborate like real humans**.

---

## 1. What Enterprise AI Is

Enterprise AI is a **Python package for developers**. You install it, import it, compose it. It is not a standalone application, not a chatbot, not a no-code workflow builder.

The quality bar is explicit: **one Enterprise AI agent must be equivalent to a complete mono-run of a production-grade agentic runtime**. That means a proper multi-turn loop, parallel tool orchestration, a full permission pipeline, streaming events, and sandboxed execution. If a single Enterprise AI agent reaches that level of robustness and autonomy, the SDK delivers on its promise.

**What Enterprise AI IS:**
- A **SDK**: `pip install enterprise-ai`, `from enterprise_ai import Agent, Team`.
- A **Python agentic runtime**: multi-turn loop, tool calling, permissions, streaming.
- A **foundation for agent teams**: the team layer is the real differentiator.
- An **open-source project**: community, contributions, public visibility.

**What Enterprise AI IS NOT:**
- ❌ An application to run (≠ hermes-agent, ≠ Nexus UI).
- ❌ A LangChain / LangGraph wrapper. Everything is built from scratch.
- ❌ A competitor to nexus-engine. Enterprise AI is the public Python corpus and open-source face of the Nexus agentic vision.
- ❌ A no-code tool. The agent reasons; it doesn't execute fixed rules.

---

## 2. The Problem

Developers who want to integrate an autonomous agent into their Python code have two options today:

- **Frameworks like LangChain / LangGraph** — heavy abstractions, unstable APIs, strong lock-in, unnecessary complexity for straightforward use cases.
- **Direct provider SDKs (Anthropic, OpenAI)** — too low-level; the execution loop, tool calling, and permission system all have to be rebuilt from scratch every time.

Enterprise AI sits between the two: **a complete agentic runtime, composable, without framework overhead**, delivered as a clean Python library.

---

## 3. Value Proposition

| Pillar | What it delivers |
|---|---|
| **Developer-first SDK** | `Agent`, `Team`, `Tool` — a clear, composable, fully typed API. No globals, no magic. |
| **Complete mono-run** | An Enterprise AI agent orchestrates its tools in parallel or serially, manages permissions, streams events — like a production runtime. |
| **Agent teams** | Multiple agents with defined roles, structured communication, task delegation — the real differentiator. |
| **From scratch, no framework** | No dependency on LangChain or equivalent. Minimal, exact-pinned deps, reduced supply-chain attack surface. |
| **Multi-provider** | Anthropic, OpenAI, OpenRouter, Ollama — via a single unified client (`openai` SDK as the universal layer). |
| **Integrated sandbox** | Docker or local isolated execution for dangerous tools (bash, code) with strict resource limits. |
| **Open source MIT** | Contributions, visibility, a community around a shared vision. |

---

## 4. The Agent as a Mono-Run

The quality bar for an Enterprise AI agent is modeled after the nexus-engine execution pipeline.

For every tool call, the pipeline is:

1. Resolve tool + IsEnabled check
2. ValidateInput
3. BackfillInput (observable enrichment for hooks/permissions)
4. Pre-tool hooks
5. Safety checks (bypass-immune)
6. Permission pipeline (deny rules → local → always-allow → global)
7. Denial tracking
8. `tool.call()`
9. Post-tool hooks
10. FormatResult
11. Content size limit
12. Context modifier

Tool calls are grouped into **batches**: independent calls run concurrently (`asyncio.gather`), context-modifying calls run sequentially. This is the same logic as the nexus-engine orchestrator, translated to Python async.

---

## 5. The Team Vision

This is Enterprise AI's long-term differentiator.

```
Mission: "Implement an authentication feature"

Alice (Manager)    → decomposes the mission → delegates
Bob   (Developer)  → receives the task → writes code → uses tools
Carol (Researcher) → documents → researches best practices
Dave  (QA)         → reviews the code → sends bugs back to Bob
```

Each team member is a **complete agent** with their own tools, sandbox, and memory. No rigid pipeline — emergent coordination through shared primitives (mailbox, task board).

---

## 6. Positioning

Enterprise AI does not replace nexus-engine. It embodies the same vision in Python, in a form accessible to the broader developer community.

- **nexus-engine** → Go runtime, commercial product, production performance, desktop-first
- **enterprise-ai** → Python SDK, open source, developer experience, community

Both share the same vision: agents that work like human teams. Enterprise AI is the public face of that vision.

---

## Related Documents

- **`architecture.md`** — technical architecture of the SDK.
- **`roadmap.md`** — Phase 1 → Phase 4 roadmap.
