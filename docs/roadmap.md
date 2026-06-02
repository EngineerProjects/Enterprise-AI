# Enterprise AI — Roadmap

**Last updated: June 2026**

---

## Guiding Principle

> **Phase 1 first.** The single-agent runtime must be robust and proven before the team layer starts. We don't build the next floor on unfinished foundations.

---

## Phase 1 — Core Agent (IN PROGRESS)

**Goal:** a single agent that completes a full run at production-runtime quality.

### To build

- [ ] `schema/` — Message, ToolCall, ToolResult, StreamEvent, Session
- [ ] `providers/` — Provider protocol + Anthropic, OpenAI, OpenRouter, Ollama
- [ ] `tools/contract.py` — BaseTool, ToolRegistry, ToolContext
- [ ] `execution/orchestrator.py` — parallel/serial batching, 12-step pipeline
- [ ] `permissions/` — deny rules, safety checker, full pipeline, 3 modes
- [ ] `engine/` — query loop, state machine, context compaction
- [ ] `sandbox/` — DockerSandbox, LocalSandbox, SandboxManager, AsyncTerminal
- [ ] `memory/` — SessionMemory (sliding window), LongTermMemory (SQLite)
- [ ] Core tools: BashTool, FileEditor, WebSearch, CodeSearch, Terminate
- [ ] Unit tests for core: orchestrator, permissions, engine (target > 60%)
- [ ] Clean `pyproject.toml`: exact pins, optional extras, lazy-install pattern

**Exit criterion:** an agent can receive a prompt, use tools in parallel and serially, respect a permission pipeline, stream its events, and automatically compact its context.

---

## Phase 2 — Teams (the differentiator)

**Goal:** multiple agents with distinct roles collaborating on a shared mission.

### To build

- [ ] `team/` — Team class, inter-agent communication (mailbox, task board)
- [ ] Built-in roles: Manager, Developer, Researcher, Planner
- [ ] Task delegation: the manager decomposes, specialists execute
- [ ] Shared memory: team-wide memory (decisions, results)
- [ ] Per-member budget: max tokens + global mission timeout
- [ ] Integration tests (end-to-end missions)

**Exit criterion:** a 3-agent team can carry out a development mission end-to-end (research → code → review) without human intervention.

---

## Phase 3 — Ecosystem

**Goal:** extend the SDK to cover a broader range of real-world use cases.

### To build

- [ ] Skill system — portable YAML/Python skills across agents
- [ ] Additional tools: BrowserTool, DocumentTool (PDF, DOCX), ImageTool
- [ ] Integrated MCP client — consume any MCP server out of the box
- [ ] Optional HTTP API (FastAPI) — for integrators who want a server surface
- [ ] More providers: Mistral, Google Gemini, AWS Bedrock
- [ ] Basic RAG — document ingestion and retrieval inside tools

---

## Phase 4 — Open Source Ready

**Goal:** make the project public with documentation quality that attracts contributors.

### To build

- [ ] Test coverage > 70%
- [ ] Polished README with concrete examples
- [ ] Full docs: getting started, API reference, cookbook
- [ ] `CONTRIBUTING.md` — clear contribution guide
- [ ] CI/CD: GitHub Actions, linting, type checking, tests
- [ ] Versioned changelog
- [ ] First public release (v0.1.0)

---

## Non-Goals (until Phase 3)

- Standalone application with a UI (≠ hermes-agent)
- No-code / workflow builder
- Managed cloud hosting
- Model fine-tuning
- Public skill marketplace
