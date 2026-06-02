# Architecture

## Vue d'ensemble

enterprise-ai est un SDK Python async-first structuré en couches. L'`Agent` coordonne tout ; chaque couche a une responsabilité unique et des règles de dépendance strictes.

---

## Diagramme de couches

```
┌──────────────────────────────────────────────────────────────────┐
│                          Public API                              │
│              Agent · Team · MixtureOfAgents · Provider           │
└─────────────────────────────┬────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│                            Engine                                │
│          QueryLoop · StopHooks · TokenBudget · Instructions      │
└──────┬────────────────┬──────────────────────────┬──────────────┘
       │                │                          │
┌──────▼──────┐  ┌──────▼──────┐          ┌────────▼────────┐
│  Execution  │  │ Permissions │          │    Providers    │
│ Orchestrator│  │  Engine     │          │ Anthropic/OAI/  │
│ Streaming   │  │  SafeCheck  │          │ Ollama/Bedrock  │
└──────┬──────┘  └─────────────┘          └─────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────┐
│                           Tools                                 │
│    BashTool · FileEditor · WebSearch · MCPTool · custom         │
│    ToolRegistry · ToolSearchBridge · Toolsets                   │
└──────┬──────────────────────────────────────────────────────────┘
       │
┌──────▼──────┐   ┌──────────────────┐   ┌──────────────────────┐
│   Sandbox   │   │      Memory      │   │       Skills         │
│ Local/Docker│   │Session · LongTerm│   │Skill·Curator·Preproc │
└─────────────┘   │ContextEngine     │   └──────────────────────┘
                  │TeamMemory (FTS5) │
                  └──────────────────┘
```

---

## Flux d'une session

```
agent.run(prompt)
│
├── SessionMemory.add(user_message)
│
└── QueryLoop.run()
    │
    ├── TURN 1
    │   ├── Provider.complete(messages, tools)   <- LLM call
    │   ├── LLMResponse.tool_calls ?
    │   │   ├── YES -> Orchestrator.execute_all(tool_calls)
    │   │   │         ├── PermissionEngine.check(tool_call)
    │   │   │         ├── tool.call(input, ctx)  <- parallel
    │   │   │         └── SessionMemory.add(tool_results)
    │   │   └── NO -> StopHookRunner.run()
    │   │             ├── continue_loop=True -> TURN 2
    │   │             └── continue_loop=False -> SessionResult
    │   └── SessionMemory.add(assistant_message)
    │
    └── SessionResult(output, cache_stats, tool_calls_count, ...)
```

---

## Modules et responsabilités

| Module | Responsabilité |
|---|---|
| `enterprise_ai.agent` | Point d'entrée, coordination des composants |
| `enterprise_ai.engine` | Boucle multi-tours, budget tokens, stop hooks |
| `enterprise_ai.execution` | Orchestration parallèle des tool calls, streaming |
| `enterprise_ai.providers` | Abstraction LLM, retry, credential pool, errors |
| `enterprise_ai.tools` | Contrat BaseTool, registre, toolsets, search bridge |
| `enterprise_ai.memory` | Session, long-term (SQLite FTS5), compaction, ContextEngine |
| `enterprise_ai.skills` | Chargement, preprocessing, curator |
| `enterprise_ai.hooks` | Événements lifecycle, HookRegistry, HookExecutor |
| `enterprise_ai.permissions` | Modes auto/onRequest/bypass, safety checks |
| `enterprise_ai.sandbox` | Isolation locale et Docker |
| `enterprise_ai.mcp` | Connexion aux serveurs MCP (stdio/SSE) |
| `enterprise_ai.stream` | StreamScrubber, TagScrubber |
| `enterprise_ai.team` | Team, Mailbox, TaskBoard, TeamMemory |
| `enterprise_ai.schema` | Types partagés : Message, ToolCall, StreamEvent, SessionResult |

---

## Règles de dépendance

- `schema` n'importe rien du projet
- `providers` n'importe que `schema`
- `tools` n'importe que `schema`, `permissions`
- `memory` n'importe que `schema`, `providers`
- `engine` importe `providers`, `tools`, `memory`, `hooks`, `schema`
- `agent` importe tout (point d'entrée)

---

## Conventions de typage

- Tout le code est annoté (mypy strict sur le code source)
- Les tests sont exclus du check mypy
- Providers : `ignore_errors = true` (types externes SDK complexes)
- Python 3.11+ requis (`match`, `TypeAlias`, PEP 604 `X | Y`)

---

## Concurrence

- Toutes les opérations I/O sont `async`
- Les tool calls dans un même tour sont exécutés en **parallèle** par défaut (`asyncio.gather`)
- Les outils marqués `is_concurrency_safe() -> False` sont exécutés séquentiellement
- `Team.run()` et `MixtureOfAgents.run()` exécutent les agents en parallèle
- `LongTermMemory` protège son SQLite avec `asyncio.Lock()`
