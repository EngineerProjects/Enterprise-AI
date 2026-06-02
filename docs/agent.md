# Agent — Référence complète

`Agent` est le point d'entrée principal du SDK. Un agent = une boucle LLM autonome avec outils, mémoire, permissions et hooks.

---

## Constructeur

```python
from enterprise_ai import Agent
from enterprise_ai.providers import AnthropicProvider

agent = Agent(
    provider=AnthropicProvider(model="claude-opus-4-8"),
    # ... paramètres ci-dessous
)
```

### Paramètres

#### LLM & Provider

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `provider` | `Provider \| str` | `"anthropic"` | Instance de provider ou nom court (`"openai"`, `"ollama"`, …) |
| `fallback_provider` | `Provider \| None` | `None` | Provider secondaire tenté si le primaire échoue (erreur 4xx) |

#### Outils

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `tools` | `list[BaseTool] \| None` | `None` | Outils disponibles pour l'agent |
| `toolset` | `str \| None` | `None` | Nom d'un toolset intégré (`"development"`, `"research"`, …) |
| `deny_tools` | `set[str] \| None` | `None` | Noms d'outils à bloquer définitivement |
| `tool_search_threshold` | `int \| None` | `None` | Active le tool search bridge au-delà de N tokens de schémas |

#### Prompt & Skills

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `system_prompt` | `str` | `""` | Prompt système de base |
| `skills` | `list[str \| Skill] \| None` | `None` | Skills injectées dans le system prompt |
| `skill_vars` | `dict[str, str] \| None` | `None` | Variables `${var}` à substituer dans les skills |
| `enable_shell_in_skills` | `bool` | `False` | Exécuter les blocs ` ```bash ``` ` dans les skills |

#### Mémoire

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `max_memory` | `int` | `200` | Nombre max de messages en mémoire de session |
| `long_term_memory` | `LongTermMemory \| None` | `None` | Mémoire persistante cross-sessions (SQLite FTS5) |
| `inject_memories` | `int` | `5` | Nb de souvenirs injectés en tête de prompt |
| `compaction_config` | `CompactionConfig \| None` | `None` | Configuration de compaction LLM du contexte |
| `context_engine` | `ContextEngine \| None` | `None` | Moteur de compaction custom (prioritaire sur `compaction_config`) |

#### Permissions & Sécurité

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `permission_mode` | `PermissionMode \| str` | `"onRequest"` | `"auto"` (tout autoriser), `"onRequest"` (demander), `"bypass"` (zéro vérif) |

#### Session & Limites

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `max_turns` | `int` | `50` | Nombre max de tours LLM par session |
| `max_sub_agent_depth` | `int` | `5` | Profondeur max d'imbrication de sous-agents |
| `working_dir` | `str` | `"."` | Répertoire de travail injecté dans le contexte des outils |
| `agent_id` | `str \| None` | `None` | ID fixe pour cet agent (généré sinon) |

#### Retry & Résilience

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `retry_config` | `RetryConfig \| None` | `None` | Backoff exponentiel sur erreurs transitoires |

#### Hooks & Observabilité

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `hooks` | `list[tuple] \| HookRegistry \| None` | `None` | Handlers d'événements cycle de vie |
| `stop_hooks` | `list[StopHookEntry] \| None` | `None` | Hooks exécutés avant chaque arrêt potentiel |

#### MCP

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `mcp_servers` | `list[MCPServerConfig] \| None` | `None` | Serveurs MCP à connecter |

#### Streaming & Contexte avancé

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `stream_scrubbers` | `list[StreamScrubber] \| None` | `None` | Filtres appliqués aux text_delta du stream |
| `cache_system_prompt` | `bool` | `False` | Active le prompt caching Anthropic |
| `extended_thinking` | `bool` | `False` | Active le thinking étendu (Anthropic) |
| `thinking_budget_tokens` | `int` | `10000` | Budget de tokens pour le thinking |
| `token_budget` | `TokenBudgetConfig \| None` | `None` | Budget de tokens par session |
| `execution_mode` | `ExecutionMode` | `execute` | `execute` ou `plan` |

#### Sandbox

| Paramètre | Type | Défaut | Description |
|---|---|---|---|
| `trim_config` | `TrimConfig \| None` | `None` | Troncature des résultats trop longs |

---

## Méthodes publiques

### `await agent.run(prompt, session_id="", parent_session_id="") → SessionResult`

Lance l'agent jusqu'à complétion. Retourne un `SessionResult`.

```python
result = await agent.run("Refactorise le module auth")
print(result.output)          # réponse finale
print(result.tool_calls_count)
print(result.cache_stats.estimated_savings_pct)  # % d'économie cache
print(result.session_id)
```

### `agent.stream(prompt, session_id="", parent_session_id="") → AsyncIterator[StreamEvent]`

Stream les événements au fil de l'exécution.

```python
async for event in agent.stream("Explique ce code"):
    match event.type.value:
        case "text_delta":
            print(event.data["delta"], end="")
        case "tool_start":
            print(f"\n[outil: {event.data['name']}]")
        case "session_end":
            print(f"\n✓ {event.data['output'][:80]}")
```

### `agent.snapshot() → list[Message]`

Retourne une copie de la conversation courante pour la brancher.

### `agent.resume_from(messages: list[Message]) → None`

Charge des messages pré-existants en mémoire (efface la mémoire courante).

### `agent.add_tool(tool: BaseTool) → None`

Enregistre un outil supplémentaire après construction.

### `agent.add_skill(skill: str | Skill) → None`

Ajoute une skill et reconstruit le system prompt.

### `agent.reset_memory() → None`

Efface toute la mémoire de session.

### `await agent.connect_mcp() / disconnect_mcp()`

Gère le cycle de vie des serveurs MCP manuellement.

### `agent.mcp() → _MCPContextManager`

Context manager async pour gérer MCP automatiquement.

### `agent.with_spawn(provider_factory=None) → Agent`

Active la création de sous-agents via l'outil `spawn_agent`.

---

## SessionResult

```python
class SessionResult:
    session_id: str
    output: str                   # texte final de l'agent
    state: SessionState           # done | error
    tool_calls_count: int         # nb total de tool calls
    parent_session_id: str        # "" si session racine
    cache_stats: CacheStats       # tokens cache lus/écrits
    metadata: dict[str, Any]
```

```python
class CacheStats:
    cache_read_tokens: int
    cache_write_tokens: int
    total_cached_tokens: int          # propriété
    estimated_savings_pct: float      # propriété : économie estimée en %
```

---

## Session branching

Forker une session pour explorer une branche alternative :

```python
# Session A — travail normal
result_a = await agent_a.run("Implémente le endpoint /users", session_id="sess-a")
snapshot_a = agent_a.snapshot()

# Session B — repart du même contexte, prend un autre chemin
agent_b = Agent(provider=provider, tools=tools)
agent_b.resume_from(snapshot_a)
result_b = await agent_b.run(
    "Réimplémente en utilisant GraphQL à la place",
    session_id="sess-b",
    parent_session_id="sess-a",   # traçabilité
)
assert result_b.parent_session_id == "sess-a"
```

---

## Spawn de sous-agents

```python
agent = Agent(
    provider=AnthropicProvider(),
    tools=[BashTool(), FileEditorTool()],
).with_spawn(
    # Provider optionnel pour chaque sous-agent (haiku = moins cher)
    provider_factory=lambda: AnthropicProvider(model="claude-haiku-4-5-20251001")
)
# L'agent peut maintenant appeler spawn_agent(task="...", max_turns=20)
```

---

## Exemple complet

```python
import asyncio
from enterprise_ai import Agent
from enterprise_ai.providers import AnthropicProvider, create_provider
from enterprise_ai.providers.retry import RetryConfig
from enterprise_ai.memory.long_term import LongTermMemory
from enterprise_ai.memory.compaction import CompactionConfig
from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.tools.builtin import BashTool, FileEditorTool, CodeSearchTool

agent = Agent(
    provider=AnthropicProvider(
        model="claude-opus-4-8",
        api_keys=["sk-ant-key1", "sk-ant-key2"],   # rotation automatique sur 429
    ),
    fallback_provider=create_provider("openai", model="gpt-4o"),
    tools=[BashTool(), FileEditorTool(), CodeSearchTool()],
    system_prompt="Tu es un ingénieur backend senior.",
    skills=["code-review", "systematic-debugging"],
    skill_vars={"project": "myapp", "lang": "Python"},
    permission_mode="auto",
    max_turns=30,
    retry_config=RetryConfig(max_attempts=4, base_delay_ms=500),
    long_term_memory=LongTermMemory(
        agent_id="backend-agent",
        path="~/.enterprise-ai/memory/",
    ),
    compaction_config=CompactionConfig(threshold=0.80),
    cache_system_prompt=True,
    hooks=[
        (HookEvent.tool_uses_start, lambda p: print(f"[tools] {[t['name'] for t in p.tool_calls]}")),
    ],
)

result = asyncio.run(agent.run("Refactorise le module d'authentification"))
print(result.output)
print(f"Cache savings: {result.cache_stats.estimated_savings_pct:.1f}%")
```
