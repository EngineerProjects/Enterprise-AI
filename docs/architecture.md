# Enterprise AI — Architecture

## Table of Contents

1. [Overview](#1-overview)
2. [Layer Diagram](#2-layer-diagram)
3. [Schema — Core Types](#3-schema--core-types)
4. [Engine — The Agent Loop](#4-engine--the-agent-loop)
5. [Execution — Tool Orchestration](#5-execution--tool-orchestration)
6. [Permission Pipeline](#6-permission-pipeline)
7. [Providers — LLM Abstraction](#7-providers--llm-abstraction)
8. [Tools — Contract and Registry](#8-tools--contract-and-registry)
9. [Sandbox — Isolated Environments](#9-sandbox--isolated-environments)
10. [Team — Multi-Agent Coordination](#10-team--multi-agent-coordination)
11. [Memory](#11-memory)
12. [Dependency Rules](#12-dependency-rules)

---

## 1. Overview

Enterprise AI is an async-first Python SDK. An `Agent` takes a prompt, runs a multi-turn loop (LLM → tools → LLM), and delivers a result or streams events. A `Team` coordinates multiple agents with distinct roles.

The SDK is accessed through two surfaces:

```
from enterprise_ai import Agent          # direct usage
from enterprise_ai import Team           # multi-agent
enterprise-ai serve --port 8080         # optional HTTP API
```

---

## 2. Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Public API                          │
│           Agent · Team · Tool · Provider                │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                     Engine                              │
│          query_loop · state machine · session           │
└──────┬───────────────┬───────────────────────┬──────────┘
       │               │                       │
┌──────▼──────┐ ┌──────▼──────┐       ┌────────▼────────┐
│  Execution  │ │ Permissions │       │    Providers    │
│ orchestrate │ │  pipeline   │       │ Anthropic/OAI/  │
│ parallel /  │ │  deny rules │       │ OpenRouter/…    │
│ serial      │ │  safety     │       └─────────────────┘
└──────┬──────┘ └─────────────┘
       │
┌──────▼──────────────────────────────────────────────────┐
│                       Tools                             │
│    BashTool · FileEditor · WebSearch · Browser · …     │
└──────┬──────────────────────────────────────────────────┘
       │
┌──────▼──────┐   ┌──────────────┐   ┌──────────────────┐
│   Sandbox   │   │    Memory    │   │     Schema       │
│ Docker/local│   │ SQLite/…     │   │ Message/Event/…  │
└─────────────┘   └──────────────┘   └──────────────────┘
```

---

## 3. Schema — Core Types

`enterprise_ai/schema/` has no internal dependencies. It is the zero layer.

```python
# message.py
class Role(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"

class Message(BaseModel):
    role: Role
    content: str | list[ContentBlock]
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None

# tool.py
class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any]

class ToolResult(BaseModel):
    tool_call_id: str
    content: str
    is_error: bool = False

# event.py — for streaming
class EventType(str, Enum):
    text_delta = "text_delta"
    tool_start = "tool_start"
    tool_result = "tool_result"
    session_end = "session_end"

class StreamEvent(BaseModel):
    type: EventType
    data: dict[str, Any]
```

---

## 4. Engine — The Agent Loop

`enterprise_ai/engine/` orchestrates the multi-turn loop. This is the Python equivalent of `nexus-engine/internal/engine/`.

```
Session.run(prompt)
    │
    ▼
State: IDLE → RUNNING
    │
    ▼
loop:
    ├── AssemblePrompt (system + history + tool schemas)
    ├── Provider.complete() → LLMResponse
    ├── If tool_calls present:
    │       ├── State: RUNNING → TOOL_CALLING
    │       ├── Execution.orchestrate(tool_calls)
    │       ├── Append tool results to context
    │       └── State: TOOL_CALLING → RUNNING → loop
    └── Else (final text):
            └── State: RUNNING → DONE → return result
```

**State machine:**

```
IDLE ──run()──► RUNNING ──tool_calls──► TOOL_CALLING
                  ▲                          │
                  └──────────────────────────┘
                  │
                  └──text_response──► DONE
                  │
                  └──error──► ERROR
```

**Context compaction:** when the context window approaches its limit, old messages are compacted (LLM summary) to free up tokens — same logic as nexus-engine.

---

## 5. Execution — Tool Orchestration

`enterprise_ai/execution/orchestrator.py` is the core of the system. Directly inspired by `nexus-engine/internal/execution/orchestrator.go`.

```python
async def execute(self, tool_calls: list[ToolCall], ctx: ToolContext) -> ExecuteResult:
    prepared = self._prepare(tool_calls)           # resolve + validate + backfill
    batches = self._partition(prepared)            # concurrent vs sequential

    for batch in batches:
        if batch.is_concurrency_safe:
            outcomes = await self._run_concurrent(batch, ctx)   # asyncio.gather
        else:
            outcomes = await self._run_sequential(batch, ctx)   # sequential await

        for outcome in outcomes:
            ctx = self._apply_context_modifier(ctx, outcome)

    return ExecuteResult(outcomes=outcomes)
```

**Per-tool-call pipeline (12 steps):**

| # | Step | Description |
|---|---|---|
| 1 | Resolve | Find the tool in the registry, verify IsEnabled |
| 2 | ValidateInput | Validate input against the tool's Pydantic schema |
| 3 | BackfillInput | Enrich input (observable metadata for hooks) |
| 4 | PreToolHooks | Registered hooks before the call |
| 5 | SafetyCheck | Bypass-immune checks (dangerous patterns) |
| 6 | PermissionPipeline | deny rules → local → always-allow → global |
| 7 | DenialTracking | Record denials in auto mode |
| 8 | `tool.call()` | Actual execution inside the sandbox |
| 9 | PostToolHooks | Hooks after the call |
| 10 | FormatResult | Tool-controlled serialization |
| 11 | SizeLimit | Truncate if result exceeds the token budget |
| 12 | ContextModifier | Modify context (sequential only, or ordered after concurrent) |

---

## 6. Permission Pipeline

`enterprise_ai/permissions/` manages authorization for every tool call.

```
tool_call
    │
    ▼
DenyRules → deny? → DENY (immediate)
    │
    ▼
LocalCheck → agent-local config (allow list, block list)
    │
    ▼
AlwaysAllow → tools marked always-allow (Terminate, read-only tools)
    │
    ▼
GlobalCheck → global rules + mode (onRequest / auto / bypass)
    │
    ▼
ALLOW / DENY / ASK_USER
```

**Three modes:**
- `onRequest` — asks for confirmation on sensitive tool calls
- `auto` — allows everything within deny rules
- `bypass` — disables permissions (tests, internal scripts)

---

## 7. Providers — LLM Abstraction

`enterprise_ai/providers/` unifies all LLMs behind a common contract.

```python
class Provider(Protocol):
    async def complete(
        self, messages: list[Message], tools: list[ToolSchema], **kwargs
    ) -> LLMResponse: ...

    async def stream(
        self, messages: list[Message], tools: list[ToolSchema], **kwargs
    ) -> AsyncIterator[StreamEvent]: ...
```

**Implementations:**
- `AnthropicProvider` — native `anthropic` SDK
- `OpenAIProvider` — `openai` SDK (GPT-4, o3, etc.)
- `OpenRouterProvider` — `openai` SDK + OpenRouter base_url (100+ models)
- `OllamaProvider` — `openai` SDK + local base_url

All non-Anthropic providers use the `openai` SDK as a universal client — the same pattern used by hermes-agent.

---

## 8. Tools — Contract and Registry

`enterprise_ai/tools/contract.py` defines the minimal contract every tool must implement.

```python
class BaseTool(ABC):
    name: str
    description: str
    input_schema: type[BaseModel]       # Pydantic — validates input automatically

    @abstractmethod
    async def call(self, input: BaseModel, ctx: ToolContext) -> ToolResult: ...

    def is_enabled(self, ctx: ToolContext) -> bool: return True
    def is_concurrency_safe(self) -> bool: return True   # can run in parallel?
```

**Built-in tools (Phase 1):**

| Tool | Description | Sandbox |
|---|---|---|
| `BashTool` | Shell command execution | Yes (Docker or constrained local) |
| `FileEditor` | Read, write, edit files | No |
| `WebSearch` | Web search (ddgs, exa, tavily) | No |
| `CodeSearch` | Grep and find in a codebase | No |
| `Terminate` | End the session cleanly | No |

---

## 9. Sandbox — Isolated Environments

`enterprise_ai/sandbox/` isolates execution of dangerous tools (bash, code execution).

```python
class Sandbox(Protocol):
    async def exec(self, command: str, timeout: float) -> ExecResult: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

class DockerSandbox(Sandbox):
    # Creates an ephemeral Docker container
    # Mounts a working volume
    # Limits CPU / memory / network
    # PTY interface via AsyncTerminal

class LocalSandbox(Sandbox):
    # Local execution with constraints
    # Strict timeout, process group kill
    # Blocks dangerous patterns (rm -rf /, etc.)
```

**SandboxManager** handles the lifecycle of multiple sandboxes in parallel (one per agent, or shared within a team).

---

## 10. Team — Multi-Agent Coordination

`enterprise_ai/team/` is Enterprise AI's differentiator.

### The model: a real company, not a pipeline

There is **no central orchestrator** that assigns tasks and waits for results. Each agent runs as a **persistent, parallel session** — fully autonomous, deciding its own next action based on its mailbox, the shared task board, and its skills.

```
Mission dropped into the team mailbox
        │
        ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  Alice (CEO)  │   │  Bob  (CTO)   │   │  Sam  (Dev)   │
│  persistent   │   │  persistent   │   │  persistent   │
│  session      │   │  session      │   │  session      │
│               │   │               │   │               │
│  reads mail   │   │  reads mail   │   │  reads mail   │
│  posts tasks  │──►│  claims arch  │──►│  claims impl  │
│  sends mails  │   │  sends mails  │   │  spawns sub-  │
│               │   │               │   │  agents       │
└───────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                            │
                    ┌───────▼───────┐
                    │    Mailbox    │  ← shared communication bus
                    │   TaskBoard   │  ← shared task queue
                    └───────────────┘
```

### The mailbox is the primary coordination primitive

Agents communicate by **sending and receiving messages** through a shared mailbox — exactly like email in a real organization. An agent can send a message to one or multiple team members. Each agent checks its mailbox between tool calls, reacts to new messages, and decides its next action autonomously.

There is no master process telling agents when to act. They act when they have mail, when a task is available to claim, or when their current work produces output to share.

### Skills define the role

Roles are not hard-coded classes. A role is a **skill** — a set of instructions, behaviors, and constraints loaded into the agent's system prompt. The `manager` skill tells an agent to decompose missions and delegate. The `cto` skill tells an agent to think architecturally and review technical decisions.

This means roles are **composable and replaceable**: you can define a custom `security-auditor` skill and add it to any agent without touching the framework code.

### Sub-agent spawning

Any agent can spawn **one-shot sub-agents** for specific subtasks — the same model as nexus-engine's sub-agent delegation. The parent agent sends a task to a freshly created agent, waits for the result, and continues its own session. The sub-agent is ephemeral; the parent is persistent.

```python
# Inside an agent's tool call — the agent decides to delegate
result = await self.spawn_subagent(
    task="Write unit tests for the auth module",
    tools=[BashTool(), FileEditor()],
    skill="test-engineer",
)
```

### API

```python
team = Team(
    agents=[
        Agent(skills=["ceo"]),
        Agent(skills=["cto"]),
        Agent(skills=["developer", "coding-conventions"]),
    ],
    mailbox=Mailbox(),       # shared communication bus
    task_board=TaskBoard(),  # shared task queue
)
await team.run("Implement OAuth2 authentication")
```

**Budget (mandatory):** max tokens per agent session + global mission timeout. Non-optional.

---

## 11. Memory

`enterprise_ai/memory/` manages context persistence.

**Two levels:**
- **Session memory** — current conversation history (in-memory, sliding window)
- **Long-term memory** — SQLite cross-session persistence (optional)

**Team memory:**
- **Shared** — decisions, results, tasks visible to all team members
- **Private** — each agent's own session history

---

## 12. Dependency Rules

```
schema        ← no internal dependencies
providers     ← schema
sandbox       ← schema
tools         ← schema, sandbox
permissions   ← schema, tools
execution     ← schema, tools, permissions
engine        ← schema, providers, execution, memory
agent         ← engine, tools, permissions, memory
team          ← agent, memory
```

No circular dependencies. `schema` is the foundation. `team` is the top.
