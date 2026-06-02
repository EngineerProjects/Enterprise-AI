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

- [ ] `team/mailbox.py` — async message bus (send, receive, broadcast)
- [ ] `team/task_board.py` — shared task queue (post, claim, complete)
- [ ] `team/team.py` — Team class, persistent parallel agent sessions
- [ ] Sub-agent spawning from within an agent (one-shot delegation, `SpawnTool`)
- [ ] Shared memory: team-wide context visible to all members
- [ ] Per-member budget: max tokens + global mission timeout
- [ ] Integration tests (end-to-end missions)

**Exit criterion:** a 3-agent team can carry out a development mission end-to-end (research → code → review) without human intervention.

---

## Phase 3 — Ecosystem

**Goal:** extend the SDK to cover a broader range of real-world use cases.

### To build

- [ ] Skill system — Markdown+YAML files that inject reusable procedures into agent context (allowed-tools, model override, shell setup, fork/inline context). NOT role definitions — skills are task templates like `code-review`, `brainstorming`, `systematic-debugging`.
- [ ] Team shared memory — RAG-based searchable corpus of everything the team produces (mails, task results, agent notes):
  - `FTSMemory` — vectorless, SQLite FTS5, zero dependencies, offline-first (default)
  - `VectorMemory` — semantic search, pluggable backend (sqlite-vec / qdrant / chroma)
  - `SearchMemoryTool` + `WriteMemoryTool` — LLM-callable tools injected into agents
- [ ] Long-term memory (SQLite cross-session persistence for individual agents)
- [ ] Additional tools: BrowserTool, DocumentTool (PDF, DOCX), ImageTool
- [ ] Integrated MCP client — consume any MCP server out of the box
- [ ] Optional HTTP API (FastAPI) — for integrators who want a server surface
- [ ] More providers: Mistral, Google Gemini, AWS Bedrock

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
