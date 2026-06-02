<p align="center">
  <img src="docs/images/logo2.png" alt="Enterprise AI Logo" width="200">
</p>

<h1 align="center">Enterprise AI</h1>

<p align="center">
  <b>Python SDK for autonomous multi-agent workflows</b><br>
  <i>Build agents that work like a real team — planning, executing, collaborating</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Active%20Development-green?style=for-the-badge">
  <img src="https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python">
  <img src="https://img.shields.io/badge/AI-Multi--Agent-purple?style=for-the-badge">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge">
</p>

---

## Vision

Enterprise AI is a **Python SDK** that turns an LLM into a fully autonomous agent — capable of planning, invoking tools, and delivering results with minimal oversight.

The quality bar is explicit: **one Enterprise AI agent = one complete mono-run of a production-grade agentic runtime**. That means a proper multi-turn loop, parallel tool orchestration, a full permission pipeline, streaming events, sandboxed execution, prompt caching, extended thinking, and token budget management.

Beyond the single agent, the real differentiator is **teams**: multiple agents with defined roles that coordinate on a shared mission, delegate tasks, and share memory — like a real human team.

No LangChain. No framework lock-in. Built from scratch, minimal dependencies, exact pins.

---

## Quick Start

```python
import asyncio
from enterprise_ai import Agent
from enterprise_ai.tools import BashTool, FileEditor, WebSearch
from enterprise_ai.providers import AnthropicProvider

async def main():
    agent = Agent(
        provider=AnthropicProvider(model="claude-opus-4-8"),
        tools=[BashTool(), FileEditor(), WebSearch()],
        system_prompt="You are a senior software engineer.",
    )

    result = await agent.run("Fix the failing test in tests/auth_test.py")
    print(result.output)

    async for event in agent.stream("Refactor the auth module to use JWT"):
        print(event)

asyncio.run(main())
```

```python
# Multi-agent team — agents run in parallel via asyncio.gather
from enterprise_ai import Agent, Team

team = Team([
    Agent(role="manager"),
    Agent(role="developer"),
    Agent(role="researcher"),
])
result = await team.run("Research best practices and implement OAuth2 login")
```

---

## Core Architecture

### Agent — the execution unit

Each agent runs a complete agentic loop:

```
prompt → [AssembleContext → LLM → tool_calls → Orchestrate → results → LLM] → output
```

The orchestrator batches tool calls: independent calls run concurrently (`asyncio.gather`), context-modifying calls run sequentially. Every tool call passes through a 12-step pipeline: resolve, validate, backfill, pre-hooks, safety check, permissions, call, post-hooks, format, size limit, context modifier.

### Permission pipeline

Three modes — `onRequest` (ask for sensitive calls), `auto` (allow within deny rules), `bypass` (for scripts). Deny rules and safety checks are bypass-immune.

### Providers

Unified interface over Anthropic, OpenAI, OpenRouter, Ollama, and AWS Bedrock. Uses the `openai` SDK as a universal client for all OpenAI-compatible endpoints; native `anthropic` SDK for Anthropic models.

### Tools

Every tool implements a typed `BaseTool` contract: name, description, Pydantic input schema, `async call()`.

Built-in tools: `BashTool`, `FileEditor`, `WebSearch`, `CodeSearch`, `Terminate`, `SpawnAgent`, `Remember`/`Recall`/`Forget` (long-term memory), `TaskBoard`, `Mailbox`.

### Sandbox

Isolated execution for dangerous tools. Docker-backed (ephemeral container, volume mount, CPU/memory limits) or local (strict timeout, process group kill). A `SandboxManager` handles lifecycle across multiple agents.

### Teams

```python
team = Team([
    Agent(role="manager"),
    Agent(role="developer"),
    Agent(role="researcher"),
])
result = await team.run("Build a REST API for user management")
```

Each team member is a **full agent** with its own tools, sandbox, and memory. Coordination happens through shared tools (task board, mailbox) — emergent, not orchestrated top-down.

---

## Features

### Extended thinking (Anthropic)

```python
agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    extended_thinking=True,
    thinking_budget_tokens=10_000,
)
```

Uses `betas=["interleaved-thinking-2025-05-07"]`. Thinking blocks are preserved with their signatures across multi-turn messages, as required by the Anthropic API.

---

### Prompt caching (Anthropic)

```python
agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    system_prompt="Large static context...",
    cache_system_prompt=True,   # cache_control: ephemeral on system + last tool schema
)
```

Cache control is applied automatically to the system prompt's last block and the last tool schema on every request.

---

### Vision support

Pass images alongside text in user messages. Works on both Anthropic and OpenAI providers.

```python
from enterprise_ai.schema import ContentBlock, ImageBlock

result = await agent.run([
    ContentBlock.text("What's in this image?"),
    ImageBlock.from_url("https://example.com/chart.png"),
    # or: ImageBlock.from_base64(data, media_type="image/png")
])
```

---

### Streaming tool coordinator

During streaming, tool calls are submitted to the orchestrator as soon as their full input is available — before the stream ends. Results are collected and merged at the end of the turn.

```python
async for event in agent.stream("Run the test suite and summarize failures"):
    if event.type == EventType.text_delta:
        print(event.data["delta"], end="", flush=True)
    elif event.type == EventType.thinking:
        print(f"[thinking] {event.data['delta']}")
```

---

### Token budget

Automatically nudge the agent to continue when it has consumed a configurable fraction of a turn budget.

```python
from enterprise_ai.engine.token_budget import TokenBudgetConfig

agent = Agent(
    provider=...,
    token_budget=TokenBudgetConfig(
        turn_token_budget=50_000,
        budget_completion_threshold=0.90,
        budget_diminishing_tokens=500,
        budget_continuation_limit=5,
    ),
)
```

---

### LLM-based context compaction

Automatically summarize old messages when the conversation approaches the provider's context window limit.

```python
from enterprise_ai.memory.compaction import CompactionConfig

agent = Agent(
    provider=...,
    compaction_config=CompactionConfig(
        auto_compact_threshold=0.85,   # compact at 85 % of 200k tokens
        keep_recent_messages=10,       # always preserve last N messages
        max_summary_tokens=2_000,
    ),
)
```

The `post_compact` hook fires after every compaction, so you can log or inspect the summary.

---

### Retry + circuit breaker

```python
from enterprise_ai.providers.retry import RetryConfig

agent = Agent(
    provider=...,
    retry_config=RetryConfig(
        max_attempts=3,
        backoff_base=2.0,
        circuit_breaker_threshold=5,
    ),
)
```

The circuit breaker opens after N consecutive failures and half-opens after a cool-down period to probe recovery.

---

### Hook system

```python
from enterprise_ai.hooks.events import HookEvent

agent = Agent(
    provider=...,
    hooks=[
        (HookEvent.pre_tool_call,  lambda ctx, tc: print(f"→ {tc.name}")),
        (HookEvent.post_tool_call, lambda ctx, tc, result: print(f"← {result}")),
        (HookEvent.post_compact,   lambda ctx: print("context compacted")),
    ],
)
```

Available events: `pre_tool_call`, `post_tool_call`, `pre_llm_call`, `post_llm_call`, `post_compact`, `session_start`, `session_end`.

---

### Stop hooks

Stop hooks let you inspect the final LLM response before the loop exits and decide whether to continue.

```python
from enterprise_ai.engine.stop_hooks import StopHookEntry

def require_structured_output(response, ctx) -> bool:
    return "```json" in response.content  # return True to stop, False to retry

agent = Agent(
    provider=...,
    stop_hooks=[StopHookEntry(fn=require_structured_output, max_retries=2)],
)
```

---

### Execution modes

```python
from enterprise_ai.modes.execution import ExecutionMode

agent = Agent(
    provider=...,
    execution_mode=ExecutionMode.plan,     # plan-only, no tool execution
    # execution_mode=ExecutionMode.execute # default — full execution
    # execution_mode=ExecutionMode.dry_run # tools are skipped, loop still runs
)
```

---

### Skills — reusable procedures

Skills are Markdown+YAML files that inject reusable procedures into an agent's system context.

```yaml
# skills/code-review.yaml
name: code-review
allowed_tools: [bash, file_editor, code_search]
model: claude-opus-4-8
```

```python
agent = Agent(
    provider=...,
    skills=["code-review", "systematic-debugging"],
)
```

---

### Project instructions

Place an `AGENTS.md` or `ENTERPRISE_AI.md` file in your working directory. It is automatically loaded into the agent's system context.

```markdown
<!-- AGENTS.md -->
## Rules
- Always write tests for new functions.
- Never modify the public API without updating CHANGELOG.md.
```

```python
agent = Agent(
    provider=...,
    working_dir=".",   # reads AGENTS.md from this directory
)
```

---

### Prompt builder

Fluent API for assembling system prompts with optional Anthropic caching.

```python
from enterprise_ai.prompt import PromptBuilder

system = (
    PromptBuilder()
    .add("You are a senior software engineer.")
    .add_project_instructions(".")    # reads AGENTS.md
    .mark_cached()                    # everything above is cached
    .add_skill("code-review")         # per-session skill (not cached)
    .build()
)

# Or build the Anthropic-native list[dict] format directly:
anthropic_system = (
    PromptBuilder()
    .add("Static expensive context.")
    .mark_cached()
    .build_anthropic()   # returns list[dict] with cache_control
)
```

Templates used by the engine (`COMPACTION_PROMPT`, `BUDGET_NUDGE_MESSAGE`, `SPAWN_DEFAULT_SYSTEM`) are overridable at the module level:

```python
import enterprise_ai.prompt.templates as tpl
tpl.BUDGET_NUDGE_MESSAGE = "Poursuis la tâche."
tpl.COMPACTION_PROMPT = "Résume en français:\n{messages_text}"
```

---

### Sub-agent spawning

```python
# Agent can spawn isolated one-shot sub-agents during a run
agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    tools=[BashTool(), FileEditor()],
).with_spawn()    # registers SpawnTool + injects parent registry

result = await agent.run(
    "Spawn a sub-agent to run the test suite, then fix any failures yourself."
)
```

`with_spawn()` registers `SpawnTool` and injects the parent's tool registry so sub-agents can inherit tools. Sub-agents are ephemeral — they do not share session memory with the parent.

---

### MCP server integration

```python
from enterprise_ai.mcp.config import MCPServerConfig

agent = Agent(
    provider=...,
    mcp_servers=[
        MCPServerConfig(name="filesystem", command="npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]),
    ],
)
```

---

### Long-term memory

```python
from enterprise_ai.memory.long_term import LongTermMemory

memory = LongTermMemory(db_path="agent_memory.db")
agent = Agent(
    provider=...,
    long_term_memory=memory,
    inject_memories=5,   # inject N most-relevant memories into context each turn
)
# The agent automatically gets Remember / Recall / Forget / RecentMemories tools
```

---

## Package Structure

```
enterprise_ai/
├── schema/          # Message, ToolCall, ToolResult, StreamEvent — zero internal deps
├── providers/       # Anthropic, OpenAI, OpenRouter, Ollama, Bedrock + retry + circuit breaker
├── tools/           # BaseTool contract, ToolRegistry, built-in tools
├── execution/       # Orchestrator (parallel/serial batching, 12-step pipeline) + streaming coordinator
├── permissions/     # Deny rules, safety checker, permission pipeline
├── engine/          # Query loop, stop hooks, token budget, project instructions
├── memory/          # SessionMemory, LongTermMemory (SQLite), LLM-based compaction
├── prompt/          # PromptBuilder, cache helpers, overridable templates
├── hooks/           # Hook registry, executor, typed events
├── modes/           # ExecutionMode (execute / plan / dry_run)
├── skills/          # Skill loader, registry, system-prompt injection
├── mcp/             # MCP client, config, tool bridge
├── sandbox/         # DockerSandbox, LocalSandbox, SandboxManager
├── agent/           # Agent class — primary public API
└── team/            # Team class, Mailbox, TaskBoard
```

**Dependency order** (no cycles):
`schema` ← `providers`, `tools`, `sandbox` ← `permissions`, `execution`, `prompt` ← `engine`, `memory`, `hooks`, `skills`, `mcp` ← `agent` ← `team`

---

## Development Status

### Phase 1 — Core agent ✅
- [x] Schema layer (Message, ToolCall, StreamEvent, Session)
- [x] Provider abstraction + Anthropic, OpenAI, OpenRouter, Ollama, Bedrock
- [x] Tool contract + registry + built-in tools (bash, file_editor, web_search, code_search, terminate, spawn_agent, remember/recall/forget, task_board, mailbox)
- [x] Execution orchestrator (parallel/serial batching, 12-step pipeline)
- [x] Streaming tool coordinator (parallel tool execution during streaming)
- [x] Permission pipeline (3 modes, bypass-immune safety check, denial tracking)
- [x] Engine query loop + stop hooks + token budget
- [x] Sandbox — LocalSandbox + DockerSandbox + SandboxManager
- [x] Memory — SessionMemory (sliding window) + LongTermMemory (SQLite)
- [x] LLM-based context compaction (auto-compact at configurable threshold)

### Phase 2 — Provider capabilities ✅
- [x] Extended thinking — Anthropic interleaved thinking with signature preservation
- [x] Vision support — image blocks in user messages (Anthropic + OpenAI)
- [x] Prompt caching — `cache_control: ephemeral` on system prompt + tool schemas
- [x] Retry + circuit breaker — configurable backoff, half-open probing
- [x] Streaming extended thinking — `EventType.thinking` delta events

### Phase 3 — Ergonomics ✅
- [x] Skill system — Markdown+YAML procedures injected into agent context
- [x] Project instructions — auto-load `AGENTS.md` / `ENTERPRISE_AI.md`
- [x] Hook system — typed lifecycle events (pre/post tool call, LLM call, compact, session)
- [x] Stop hooks — inspect final response before loop exit, retry on failure
- [x] Execution modes — `execute` / `plan` / `dry_run`
- [x] Sub-agent spawning — `Agent.with_spawn()`, depth-limited, tool-inheriting
- [x] Prompt builder — fluent assembly with Anthropic cache markers
- [x] Overridable templates — `enterprise_ai.prompt.templates.*`
- [x] MCP client integration
- [x] Multi-agent teams — parallel execution via `asyncio.gather`

### Phase 4 — Open source ready
- [ ] Test coverage > 70%
- [ ] Full documentation + cookbook
- [ ] CONTRIBUTING.md
- [ ] v0.1.0 public release

---

## Contributing

Enterprise AI is in active development. Contributions, issues, and discussions are welcome once the v0.1.0 core is stable.

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  <i>Enterprise AI is the open-source Python expression of the Nexus agentic vision.</i>
</p>
