# Memory — Session, long-terme, compaction et ContextEngine

---

## Mémoire de session (SessionMemory)

Stocke la conversation courante en RAM. Effacée à chaque nouveau `agent.run()` ou `agent.reset_memory()`.

```python
agent = Agent(
    provider=provider,
    max_memory=200,    # max de messages avant compaction automatique
)
```

La mémoire de session est cumulative : chaque `agent.run()` **continue** la conversation précédente (l'agent se souvient de ce qui a été dit avant).

---

## Mémoire long-terme (LongTermMemory)

Persistante cross-sessions, stockée dans SQLite FTS5. Privée à chaque agent.

```python
from enterprise_ai.memory.long_term import LongTermMemory

mem = LongTermMemory(
    agent_id="my-dev-agent",
    path="~/.enterprise-ai/memory/",   # None = en mémoire (tests)
    max_records=10_000,
)

agent = Agent(
    provider=provider,
    long_term_memory=mem,
    inject_memories=5,    # nb de souvenirs récents injectés en tête de prompt
)
```

Les outils `remember`, `recall`, `forget`, `recent_memories` sont automatiquement enregistrés quand `long_term_memory` est configuré.

### API directe

```python
# Écrire
record_id = await mem.remember(
    "Always use pytest for this project",
    category="preference",   # note | decision | fact | preference | context
)

# Recherche plein texte
records = await mem.recall("testing framework", limit=5)

# Récents
records = await mem.recent(limit=10)

# Supprimer
deleted = await mem.forget(record_id)

# Compter
n = await mem.count()
```

### MemoryRecord

```python
@dataclass
class MemoryRecord:
    id: str
    content: str
    category: str      # "note" | "decision" | "fact" | "preference" | "context"
    agent_id: str
    created_at: str    # ISO 8601
    metadata: dict
```

---

## Compaction LLM du contexte

Quand la mémoire de session devient trop grande, le `CompactionEngine` résume les anciens messages avec le LLM pour libérer de l'espace :

```python
from enterprise_ai.memory.compaction import CompactionConfig

agent = Agent(
    provider=provider,
    compaction_config=CompactionConfig(
        threshold=0.80,          # déclenche à 80% de max_memory
        keep_last=10,            # garde les 10 derniers messages intacts
        summary_max_tokens=500,  # taille max du résumé
    ),
)
```

---

## ContextEngine — interface plugin

Pour des stratégies de compaction custom (RAG, hiérarchique, résumé par domaine), implémente `ContextEngine` :

```python
from enterprise_ai.memory.context_engine import ContextEngine
from enterprise_ai.schema import Message

class VectorContextEngine(ContextEngine):

    def should_compact(self, messages: list[Message]) -> bool:
        return len(messages) > 30

    async def compact(
        self,
        messages: list[Message],
        system_prompt: str = "",
    ) -> list[Message]:
        # Exemples : RAG retrieval, résumé hiérarchique, élaguage par pertinence
        relevant = await self._vector_store.retrieve(messages[-5:], top_k=10)
        return relevant + messages[-5:]

    # Hooks lifecycle optionnels (no-op par défaut) :

    def on_session_start(self, session_id: str) -> None:
        self._index.create(session_id)

    def on_session_end(self, session_id: str, messages: list[Message]) -> None:
        self._index.flush(session_id)

    def on_session_reset(self) -> None:
        self._index.clear_current()

    def carry_over_new_session_context(self, old_id: str, new_id: str) -> None:
        self._index.copy(old_id, new_id)


agent = Agent(
    provider=provider,
    context_engine=VectorContextEngine(),
    # context_engine prend la priorité sur compaction_config
)
```

### Méthodes abstraites

| Méthode | Description |
|---|---|
| `should_compact(messages)` | Retourne `True` quand la compaction doit s'exécuter |
| `compact(messages, system_prompt)` | Retourne la liste compactée (peut être plus courte) |

### Hooks lifecycle (optionnels)

| Hook | Appelé quand |
|---|---|
| `on_session_start(session_id)` | Au démarrage de chaque session |
| `on_session_end(session_id, messages)` | À la fin de chaque session |
| `on_session_reset()` | Quand `agent.reset_memory()` est appelé |
| `carry_over_new_session_context(old, new)` | Quand une session forke vers une nouvelle |

Le `CompactionEngine` intégré (basé sur LLM) est une implémentation de `ContextEngine` — il peut être passé directement en `context_engine=` :

```python
from enterprise_ai.memory.compaction import CompactionEngine, CompactionConfig

engine = CompactionEngine(provider, CompactionConfig(threshold=0.75))
agent = Agent(provider=provider, context_engine=engine)
```

---

## Mémoire équipe (TeamMemory)

Partagée entre tous les agents d'une même `Team`. Indexée avec FTS5 SQLite.

Voir [Team & MoA](team.md) pour les détails.

---

## Session Branching et mémoire

`snapshot()` et `resume_from()` permettent de forker la mémoire de session :

```python
# Agent A — travail initial
await agent_a.run("Étape 1")
snapshot = agent_a.snapshot()   # copie de la conversation

# Agent B — repart du même historique
agent_b = Agent(provider=provider)
agent_b.resume_from(snapshot)
result = await agent_b.run(
    "Essaie une approche alternative",
    parent_session_id=result_a.session_id,
)
```

Voir [Agent](agent.md#session-branching) pour l'exemple complet.
