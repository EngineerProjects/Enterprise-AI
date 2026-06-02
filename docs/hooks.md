# Hooks — Système d'événements et stop hooks

---

## Hook events — cycle de vie

Le système de hooks permet d'observer et de réagir à chaque étape de l'exécution de l'agent.

### Enregistrement des hooks

```python
from enterprise_ai import Agent
from enterprise_ai.hooks.events import HookEvent
from enterprise_ai.hooks.registry import HookRegistry

# Option 1 — liste de tuples (simple)
agent = Agent(
    provider=provider,
    hooks=[
        (HookEvent.session_start, on_session_start),
        (HookEvent.tool_uses_start, on_tool_uses_start),
        (HookEvent.post_tool_use, on_tool_done),
    ],
)

# Option 2 — HookRegistry (plus flexible)
registry = HookRegistry()
registry.on(HookEvent.session_start, on_session_start)
registry.on(HookEvent.pre_tool_use, pre_tool_handler)

agent = Agent(provider=provider, hooks=registry)
```

### Tous les événements

#### Cycle de vie de session

| Événement | Payload | Description |
|---|---|---|
| `session_start` | `session_id` | Début d'une session |
| `session_end` | `session_id`, `output`, `tool_calls_count` | Fin de session |
| `query_start` | `session_id`, `prompt` | Début d'un `agent.run()` |
| `query_complete` | `session_id`, `output` | Fin d'un `agent.run()` |

#### Tours LLM

| Événement | Payload | Description |
|---|---|---|
| `turn_start` | `session_id`, `turn_number` | Début d'un tour (appel LLM) |
| `turn_end` | `session_id`, `turn_number`, `has_tool_calls` | Fin d'un tour |
| `pre_api_call` | `session_id`, `messages` | Juste avant l'appel API LLM |
| `post_api_call` | `session_id`, `response` | Juste après la réponse LLM |

#### Outils

| Événement | Payload | Description |
|---|---|---|
| `tool_uses_start` | `session_id`, `tool_calls` | Début d'un batch de tool calls |
| `tool_uses_complete` | `session_id`, `results` | Fin du batch |
| `pre_tool_use` | `session_id`, `tool_call` | Avant chaque outil (peut bloquer) |
| `post_tool_use` | `session_id`, `tool_call`, `result` | Après chaque outil (succès) |
| `post_tool_use_fail` | `session_id`, `tool_call`, `error` | Après chaque outil (échec) |

#### Compaction et permissions

| Événement | Payload | Description |
|---|---|---|
| `pre_compact` | `session_id`, `message_count` | Avant compaction du contexte |
| `post_compact` | `session_id`, `message_count` | Après compaction |
| `permission_request` | `session_id`, `tool_call` | Demande de permission |
| `permission_denied` | `session_id`, `tool_call`, `reason` | Permission refusée |

#### Sous-agents et erreurs

| Événement | Payload | Description |
|---|---|---|
| `subagent_start` | `session_id`, `task` | Lancement d'un sous-agent |
| `subagent_stop` | `session_id`, `result` | Fin d'un sous-agent |
| `on_error` | `session_id`, `error` | Erreur non récupérée |
| `notification` | `session_id`, `message`, `level` | Notification informative |

### Exemples de handlers

```python
import asyncio

async def on_session_start(payload):
    print(f"[{payload.session_id}] Session démarrée")

async def on_tool_uses_start(payload):
    names = [t["name"] for t in payload.tool_calls]
    print(f"[{payload.session_id}] Outils : {names}")

async def on_error(payload):
    print(f"ERREUR : {payload.error}")
    await notify_slack(str(payload.error))

agent = Agent(
    provider=provider,
    hooks=[
        (HookEvent.session_start, on_session_start),
        (HookEvent.tool_uses_start, on_tool_uses_start),
        (HookEvent.on_error, on_error),
    ],
)
```

---

## Stop Hooks — contrôle de l'arrêt

Les stop hooks s'exécutent **avant chaque arrêt potentiel** de l'agent et peuvent forcer la continuation du loop.

### Cas d'usage typiques

- Quality gate : l'agent doit écrire un fichier — si absent, injecter un rappel et continuer
- Score minimum : relancer si le résultat est insuffisant
- Validation de compliance post-exécution

### Définir un stop hook

```python
from enterprise_ai.engine.stop_hooks import StopHookEntry, StopHookInput, StopHookResult
from enterprise_ai.schema import Message

async def quality_gate(input: StopHookInput) -> StopHookResult:
    """Force une itération supplémentaire si aucun fichier n'a été modifié."""
    if input.tool_calls_count == 0:
        return StopHookResult(
            continue_loop=True,
            inject_messages=[
                Message.user(
                    "Attention : tu n'as fait aucun changement. "
                    "Implémente la solution demandée."
                )
            ],
        )
    return StopHookResult()   # arrêt normal

agent = Agent(
    provider=provider,
    stop_hooks=[
        StopHookEntry(
            name="quality-gate",
            handler=quality_gate,
            priority=10,   # ordre d'exécution (plus bas = premier)
        )
    ],
)
```

### StopHookInput

```python
@dataclass
class StopHookInput:
    session_id: str
    turn_number: int
    stop_reason: str          # "no_tool_calls" | "terminate" | "max_turns"
    messages: list[Message]   # snapshot en lecture seule
    tool_calls_count: int
```

### StopHookResult

```python
@dataclass
class StopHookResult:
    continue_loop: bool = False             # force un tour supplémentaire
    inject_messages: list[Message] = []     # messages injectés avant ce tour
    error: Exception | None = None          # erreur → arrêt en état error
```

### Modes d'exécution

| Mode | Comportement |
|---|---|
| `"all"` (défaut) | Tous les hooks s'exécutent ; continue si au moins un le demande |
| `"first"` | S'arrête au premier hook qui demande `continue_loop=True` |

```python
from enterprise_ai.engine.stop_hooks import StopHookRunner

runner = StopHookRunner(hooks=[...], mode="first", timeout_s=10.0)
```

### Plusieurs hooks chaînés

```python
async def check_tests_pass(input: StopHookInput) -> StopHookResult:
    # Si les tests échouent, relancer avec les détails d'erreur
    result = subprocess.run(["pytest", "-q"], capture_output=True, text=True)
    if result.returncode != 0:
        return StopHookResult(
            continue_loop=True,
            inject_messages=[Message.user(f"Tests échoués :\n{result.stdout}")],
        )
    return StopHookResult()

async def check_no_todos(input: StopHookInput) -> StopHookResult:
    # Vérifie qu'aucun TODO n'a été laissé
    last_output = input.messages[-1].text() if input.messages else ""
    if "TODO" in last_output:
        return StopHookResult(
            continue_loop=True,
            inject_messages=[Message.user("Il reste des TODO — complète l'implémentation.")],
        )
    return StopHookResult()

agent = Agent(
    provider=provider,
    stop_hooks=[
        StopHookEntry("test-check", check_tests_pass, priority=1),
        StopHookEntry("todo-check", check_no_todos, priority=2),
    ],
)
```
